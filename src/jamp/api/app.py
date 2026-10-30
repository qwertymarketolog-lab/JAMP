from __future__ import annotations

import hmac
import json
import os
import re
import time
from collections.abc import Callable
from contextlib import suppress
from pathlib import Path
from typing import Any
from urllib.request import Request as UrlRequest
from urllib.request import urlopen

from jamp.api.auth import require_api_key, verify_auth_config
from jamp.provider.anymodel import AnyModelChatExecutor, AnyModelError
from jamp.provider.coingecko_verify import verify_claim_with_coingecko
from jamp.provider.e2_verify import verify_generation
from jamp.provider.fallback import FallbackChainExecutor
from jamp.provider.groq import GroqChatExecutor, GroqError
from jamp.provider.moex_verify import (
    E4_CONTRADICTED,
    E4_INCONCLUSIVE,
    E4_OUT_OF_SCOPE,
    E4_VERIFIED,
    verify_claim_with_moex,
)
from jamp.provider.openrouter import OpenRouterChatExecutor, OpenRouterError
from jamp.runtime import (
    AuditPersistence,
    CapabilityResolver,
    ModelSelector,
    ProvenanceTracker,
    TaskClassifier,
)
from jamp.runtime.qualification import evaluate_model_qualification
from jamp.runtime.universal_verdict import (
    CriteriaRef,
    EvidenceRef,
    ExecutionRef,
    SpecRef,
    UniversalClassification,
    UniversalVerdict,
    VerdictResult,
    VerifierInfo,
    compute_jamp_verdict_hash,
)
from jamp.runtime.verdict import (
    JampVerdict,
    aggregate_verdict,
    critical_unverified_claims,
)
from jamp.transport.telegram_updates import TelegramUpdateStore, TelegramUpdateStoreError


def _send_telegram_message(bot_token: str, chat_id: int, text: str) -> None:
    """Send one Telegram reply without logging the token or message contents."""
    body = json.dumps(
        {"chat_id": chat_id, "text": text},
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")
    request = UrlRequest(
        f"https://api.telegram.org/bot{bot_token}/sendMessage",
        data=body,
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=10) as response:
            result = json.loads(response.read().decode("utf-8"))
    except Exception:
        raise RuntimeError("Telegram delivery failed") from None
    if not isinstance(result, dict) or result.get("ok") is not True:
        raise RuntimeError("Telegram delivery failed")


def _verdict_signing_key() -> str | None:
    """Use a configured key; dev-secret is only a non-production fallback."""
    key = os.environ.get("JAMP_SIGNING_KEY")
    if key:
        return key
    if os.environ.get("JAMP_ENV", "development").lower() in {"production", "prod"}:
        return None
    return "dev-secret"


_REF_HASH_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
_EVIDENCE_TYPES = frozenset(
    {
        "raw_document",
        "ocr_block",
        "api_response",
        "db_row",
        "cve_record",
        "vendor_advisory",
        "deployment_log",
        "scan_report",
        "version_check",
        "patch_receipt",
    }
)


def _universal_verdict_from_dict(payload: dict[str, Any]) -> UniversalVerdict:
    """Reconstruct UniversalVerdict from canonical_payload() dict.

    Inverse of canonical_payload(). Lives here (not in universal_verdict.py)
    to honor the constraint: universal_verdict.py is not modified in this PR.
    """
    return UniversalVerdict(
        spec_ref=SpecRef(**payload["spec_ref"]),
        criteria_ref=CriteriaRef(**payload["criteria_ref"]),
        execution_ref=ExecutionRef(**payload["execution_ref"]),
        evidence_refs=tuple(EvidenceRef(**r) for r in payload["evidence_refs"]),
        classification=UniversalClassification(**payload["classification"]),
        verdict=VerdictResult(**payload["verdict"]),
        verifier=VerifierInfo(**payload["verifier"]),
        timestamp=payload["timestamp"],
    )


DEFAULT_EVIDENCE = Path(__file__).parents[3] / "tests/fixtures/runtime_evidence_projection.json"

COINGECKO_TICKER_MAP = {
    "BTC": "bitcoin",
    "ETH": "ethereum",
    "SOL": "solana",
    "USDT": "tether",
    "USDC": "usd-coin",
    "BNB": "binancecoin",
    "XRP": "ripple",
    "ADA": "cardano",
    "DOGE": "dogecoin",
    "DOT": "polkadot",
    "AVAX": "avalanche-2",
    "MATIC": "matic-network",
}


def create_app(
    evidence_path: str | Path = DEFAULT_EVIDENCE,
    executor: Callable[[str, dict[str, Any]], Any] | None = None,
    audit_storage_path: str | Path | None = None,
    telegram_update_db_path: str | Path | None = None,
):
    try:
        from fastapi import Depends, FastAPI
        from fastapi import Request as FastAPIRequest
        from fastapi.responses import JSONResponse
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("FastAPI is required for the API serving layer") from exc

    classifier = TaskClassifier()
    resolver = CapabilityResolver()
    try:
        resolver.validate_projection(evidence_path)
    except (OSError, TypeError, ValueError):
        # Invalid, stale, or inconsistent evidence must prevent the API from serving.
        raise RuntimeError("Canonical capability evidence failed integrity validation") from None
    selector = ModelSelector()
    provenance = ProvenanceTracker()
    persistence = AuditPersistence(audit_storage_path)
    configured_update_db_path = telegram_update_db_path
    if configured_update_db_path is None:
        configured_update_db_path = os.environ.get("JAMP_TELEGRAM_UPDATE_DB")
    telegram_update_store = TelegramUpdateStore(configured_update_db_path)
    if executor is not None:
        configured_executor = executor
    else:
        available_executors = [
            provider
            for provider in (
                OpenRouterChatExecutor.from_env(),
                GroqChatExecutor.from_env(),
                AnyModelChatExecutor.from_env(),
            )
            if provider is not None
        ]
        configured_executor = (
            FallbackChainExecutor(available_executors, max_attempts=5)
            if available_executors
            else None
        )

    app = FastAPI(title="JAMP API", version="v1")
    app.openapi_version = "3.0.3"

    @app.on_event("startup")
    def _startup_auth_check() -> None:
        verify_auth_config()

    @app.post("/v1/classify", dependencies=[Depends(require_api_key)])
    def classify(payload: dict[str, Any]):
        task_profile = classifier.classify(payload)
        required = resolver.get_required_capabilities(task_profile)
        return {"task_profile": task_profile, "required_capabilities": list(required)}

    @app.post("/v1/execute", dependencies=[Depends(require_api_key)])
    def execute(payload: dict[str, Any]):
        request_id = payload.get("request_id")
        try:
            task_profile = classifier.classify(payload)
            required = resolver.get_required_capabilities(task_profile)
        except ValueError as exc:
            trace = provenance.create_trace(
                "unknown",
                (),
                "REFUSE",
                str(exc),
                0,
                request_id=request_id,
                refusal_reason="UNKNOWN_OR_UNSUPPORTED_TASK",
            )
            persistence.write_trace(trace)
            return JSONResponse(
                status_code=422,
                content={
                    "status": "REFUSE",
                    "reason": "UNKNOWN_OR_UNSUPPORTED_TASK",
                    "trace_id": trace["trace_id"],
                },
            )

        try:
            eligible = resolver.get_eligible_models(task_profile)
            action, selected = selector.select_model(eligible, task_profile)
        except (OSError, TypeError, ValueError):
            reason = "EVIDENCE_INTEGRITY_FAILED"
            trace = provenance.create_trace(
                task_profile,
                required,
                "REFUSE",
                reason,
                0,
                request_id=request_id,
                refusal_reason=reason,
            )
            persistence.write_trace(trace)
            return JSONResponse(
                status_code=503,
                content={"status": "REFUSE", "reason": reason, "trace_id": trace["trace_id"]},
            )

        if action == "REFUSE":
            trace = provenance.create_trace(
                task_profile,
                required,
                action,
                selected,
                len(eligible),
                request_id=request_id,
                refusal_reason=selected,
            )
            persistence.write_trace(trace)
            return {
                "status": "REFUSE",
                "reason": selected,
                "trace_id": trace["trace_id"],
            }

        if configured_executor is None:
            reason = "PROVIDER_NOT_CONFIGURED"
            trace = provenance.create_trace(
                task_profile,
                required,
                "REFUSE",
                reason,
                len(eligible),
                request_id=request_id,
                refusal_reason=reason,
            )
            persistence.write_trace(trace)
            return JSONResponse(
                status_code=503,
                content={"status": "REFUSE", "reason": reason, "trace_id": trace["trace_id"]},
            )

        try:
            output = configured_executor(selected, payload)
        except Exception as exc:
            if (
                isinstance(exc, (AnyModelError, OpenRouterError, GroqError))
                or str(exc) == "All fallback providers failed."
            ):
                reason = "PROVIDER_EXECUTION_FAILED"
            else:
                reason = "EXECUTOR_ERROR"
            failure_diagnostics = None
            fallback_history = getattr(exc, "fallback_history", None)
            if isinstance(exc, (OpenRouterError, GroqError)) and (exc.diagnostics or exc.code):
                failure_diagnostics = {
                    **exc.diagnostics,
                    "selected_model": selected,
                }
                if exc.code:
                    failure_diagnostics["code"] = exc.code
            trace = provenance.create_trace(
                task_profile,
                required,
                "REFUSE",
                reason,
                len(eligible),
                request_id=request_id,
                refusal_reason=reason,
                failure_diagnostics={
                    **(failure_diagnostics or {}),
                    **(
                        {"fallback_history": fallback_history}
                        if isinstance(fallback_history, list)
                        else {}
                    ),
                }
                or None,
            )
            persistence.write_trace(trace)
            empty_content_exhausted = getattr(exc, "code", None) == "OPENROUTER_EMPTY_CONTENT" or (
                isinstance(fallback_history, list)
                and any(
                    isinstance(item, dict)
                    and "no text content after one retry" in str(item.get("error", "")).lower()
                    for item in fallback_history
                )
            )
            if empty_content_exhausted:
                return JSONResponse(
                    status_code=200,
                    content={
                        "status": "INCONCLUSIVE",
                        "execution_status": "INCONCLUSIVE",
                        "reason": "OPENROUTER_EMPTY_CONTENT_RETRY_EXHAUSTED",
                        "trace_id": trace["trace_id"],
                        "evidence_status": "INCONCLUSIVE",
                        "model_verification": "INCONCLUSIVE",
                        "aggregate_status": "PARTIAL",
                        "claims": [],
                        "critical_unverified": [],
                    },
                )
            return JSONResponse(
                status_code=502,
                content={"status": "REFUSE", "reason": reason, "trace_id": trace["trace_id"]},
            )

        evidence_status = "NOT_APPLICABLE"
        evidence_details = None

        # Providers with no supported E2 Generation API are explicitly exempt.
        non_e2_providers = ("groq", "anymodel")
        output_provider = output.get("provider") if isinstance(output, dict) else None

        # Fail closed for OpenRouter and unknown/missing provider metadata.
        if output_provider not in non_e2_providers:
            evidence_status, evidence_details = verify_generation(
                output if isinstance(output, dict) else {}
            )

            if evidence_status != "VERIFIED":
                reason = evidence_details.get("reason", f"E2_{evidence_status}")
                if evidence_status == "CONTRADICTED":
                    reason = "EVIDENCE_CONTRADICTED"
                elif evidence_status == "INCONCLUSIVE":
                    reason = "E2_VERIFICATION_INCONCLUSIVE"

                trace = provenance.create_trace(
                    task_profile,
                    required,
                    "REFUSE",
                    reason,
                    len(eligible),
                    request_id=request_id,
                    refusal_reason=reason,
                    failure_diagnostics={
                        **(evidence_details if isinstance(evidence_details, dict) else {}),
                        "evidence_status": evidence_status,
                        "output_provider": (
                            output.get("provider") if isinstance(output, dict) else None
                        ),
                        "output_response_id": (
                            output.get("provider_response_id") if isinstance(output, dict) else None
                        ),
                        "output_model_id": (
                            output.get("provider_model_id") if isinstance(output, dict) else None
                        ),
                        "fallback_history": (
                            output.get("fallback_history", []) if isinstance(output, dict) else []
                        ),
                    },
                )
                persistence.write_trace(trace)
                return JSONResponse(
                    status_code=502,
                    content={
                        "status": "REFUSE",
                        "reason": reason,
                        "trace_id": trace["trace_id"],
                    },
                )

        # E2 verifies model provenance; E4 verifies only bounded MOEX claims.
        claims = []
        if task_profile == "search_and_extraction" and evidence_status == "VERIFIED":
            prompt_text = payload.get("prompt", "")
            output_text = output.get("content", "") if isinstance(output, dict) else ""
            searchable_text = " ".join(
                text for text in (prompt_text, output_text) if isinstance(text, str)
            )

            structured_claim = payload.get("e4_claim")
            if not isinstance(structured_claim, dict) and isinstance(output, dict):
                structured_claim = output.get("e4_claim")
            if isinstance(structured_claim, dict):
                ticker = structured_claim.get("ticker")
                claim_type = structured_claim.get("claim_type")
                claimed_value = structured_claim.get("claimed_value")
                if isinstance(ticker, str) and isinstance(claim_type, str):
                    normalized_ticker = ticker.upper().lstrip("$")
                    explicit_coin_id = structured_claim.get("coin_id")
                    mapped_coin_id = COINGECKO_TICKER_MAP.get(normalized_ticker)
                    is_crypto_claim = (
                        structured_claim.get("asset_class") == "crypto"
                        or isinstance(explicit_coin_id, str)
                        or mapped_coin_id is not None
                    )
                    if is_crypto_claim:
                        coin_id = (
                            explicit_coin_id
                            if isinstance(explicit_coin_id, str)
                            else mapped_coin_id
                        )
                        crypto_claim_type = (
                            "existence" if claim_type in {"exists", "existence"} else claim_type
                        )
                        if not coin_id:
                            raw_status, details = (
                                E4_INCONCLUSIVE,
                                {
                                    "reason": "CRYPTO_TICKER_NOT_MAPPED",
                                    "ticker": ticker,
                                    "checked_source": "coingecko",
                                },
                            )
                        else:
                            raw_status, details = verify_claim_with_coingecko(
                                coin_id, crypto_claim_type, claimed_value
                            )
                        if (
                            structured_claim.get("comparison") == "greater_than"
                            and claim_type == "market_cap"
                            and isinstance(details, dict)
                            and isinstance(details.get("observed_value"), (int, float))
                            and not isinstance(details.get("observed_value"), bool)
                            and isinstance(claimed_value, (int, float))
                            and not isinstance(claimed_value, bool)
                        ):
                            predicate_satisfied = details["observed_value"] > claimed_value
                            raw_status = E4_VERIFIED if predicate_satisfied else E4_CONTRADICTED
                            details = {
                                **details,
                                "comparison": "greater_than",
                                "threshold_usd": claimed_value,
                                "predicate_satisfied": predicate_satisfied,
                            }
                        source = "E4_COINGECKO"
                    else:
                        raw_status, details = verify_claim_with_moex(
                            ticker, claim_type, claimed_value
                        )
                        source = "E4_MOEX"
                    normalized = {
                        E4_VERIFIED: "VERIFIED",
                        E4_CONTRADICTED: "CONTRADICTED",
                        E4_OUT_OF_SCOPE: "OUT_OF_SCOPE",
                        E4_INCONCLUSIVE: "INCONCLUSIVE",
                    }.get(raw_status, "INCONCLUSIVE")
                    claims.append(
                        {
                            "text": str(structured_claim.get("text") or f"{ticker} {claim_type}"),
                            "type": claim_type,
                            "source": source,
                            "status": normalized,
                            "evidence": details,
                            "reason": details.get("reason") if isinstance(details, dict) else None,
                            "critical": bool(structured_claim.get("critical", False)),
                        }
                    )
                else:
                    claims.append(
                        {
                            "text": "Malformed structured E4 claim",
                            "type": "unknown",
                            "source": "E4_MOEX",
                            "status": "INCONCLUSIVE",
                            "reason": "STRUCTURED_E4_CLAIM_INVALID",
                            "critical": False,
                        }
                    )
            else:
                # This bounded extractor records explicit input assumptions and known
                # claim shapes; it is not a general-purpose claim extraction model.
                ticker_values = list(
                    dict.fromkeys(
                        match.group(1).upper()
                        for match in re.finditer(
                            r"\(([A-Za-z][A-Za-z0-9.-]{1,9})\)", searchable_text
                        )
                    )
                )
                for ticker in ticker_values:
                    raw_status, details = verify_claim_with_moex(ticker, "exists", None)
                    normalized = {
                        E4_VERIFIED: "VERIFIED",
                        E4_CONTRADICTED: "CONTRADICTED",
                        E4_OUT_OF_SCOPE: "OUT_OF_SCOPE",
                        E4_INCONCLUSIVE: "INCONCLUSIVE",
                    }.get(raw_status, "INCONCLUSIVE")
                    claims.append(
                        {
                            "text": f"{ticker} is listed on MOEX",
                            "type": "existence",
                            "source": "E4_MOEX",
                            "status": normalized,
                            "evidence": details,
                            "reason": details.get("reason") if isinstance(details, dict) else None,
                            "critical": False,
                        }
                    )

                movement_pattern = (
                    r"(?:упал\w*|подешевел\w*|снизил\w*|fell|dropped|down)"
                    r".{0,45}?\b(\d{1,3}(?:[.,]\d+)?)\s*%"
                )
                movement = re.search(movement_pattern, searchable_text, re.IGNORECASE)
                if movement:
                    claims.append(
                        {
                            "text": movement.group(0).strip(),
                            "type": "price_movement",
                            "source": None,
                            "status": "INCONCLUSIVE",
                            "reason": (
                                "MOEX verifier does not establish historical percentage movement"
                            ),
                            "critical": False,
                        }
                    )

                ipo_match = re.search(
                    (
                        r"\bIPO\b|initial public offering|"
                        r"первичн\w+ публичн\w+ размещен|выходит на IPO|готовится к IPO"
                    ),
                    searchable_text,
                    re.IGNORECASE,
                )
                if ipo_match:
                    fake_tech = bool(re.search(r"\bFakeTech\b", searchable_text, re.IGNORECASE))
                    claims.append(
                        {
                            "text": ipo_match.group(0),
                            "type": "ipo_event",
                            "source": "E4_MOEX",
                            "status": "OUT_OF_SCOPE",
                            "reason": (
                                "MOEX ISS does not verify IPO events; E5 general search is required"
                            ),
                            "critical": fake_tech,
                        }
                    )

                if re.search(r"крупнейш\w+|largest|number one", searchable_text, re.IGNORECASE):
                    claims.append(
                        {
                            "text": "market leadership / largest-company claim",
                            "type": "superlative",
                            "source": None,
                            "status": "INCONCLUSIVE",
                            "reason": "No independent market-share source checked",
                            "critical": False,
                        }
                    )
                if re.search(r"банкротств\w*|bankruptcy", searchable_text, re.IGNORECASE):
                    claims.append(
                        {
                            "text": "bankruptcy-risk assessment",
                            "type": "prediction",
                            "source": None,
                            "status": "INCONCLUSIVE",
                            "reason": (
                                "Requires financial/news evidence; "
                                "prediction is not a verified fact"
                            ),
                            "critical": False,
                        }
                    )

        aggregate_status = aggregate_verdict(claims)
        critical_unverified = critical_unverified_claims(claims)
        crypto_critical_unverified = any(
            isinstance(claim, dict)
            and claim.get("source") == "E4_COINGECKO"
            and bool(claim.get("critical"))
            and claim.get("status") != "VERIFIED"
            for claim in claims
        )
        if aggregate_status == "CONTRADICTED" or critical_unverified:
            reason = (
                "E4_CANNOT_VERIFY_EXISTENCE"
                if crypto_critical_unverified
                else (
                    "CLAIM_LEVEL_CONTRADICTION"
                    if aggregate_status == "CONTRADICTED"
                    else "E4_CANNOT_VERIFY_EXISTENCE"
                )
            )
            trace = provenance.create_trace(
                task_profile,
                required,
                "REFUSE",
                reason,
                len(eligible),
                request_id=request_id,
                evidence_status=evidence_status,
                evidence_details={
                    "aggregate_status": aggregate_status,
                    "claims": claims,
                    "critical_unverified": critical_unverified,
                },
                refusal_reason=reason,
                failure_diagnostics={
                    "aggregate_status": aggregate_status,
                    "claims": claims,
                    "critical_unverified": critical_unverified,
                    "model_verification": evidence_status,
                },
            )
            persistence.write_trace(trace)
            refusal_content = {
                "status": "REFUSE",
                "execution_status": "REFUSE",
                "reason": reason,
                "trace_id": trace["trace_id"],
                "evidence_status": evidence_status,
                "model_verification": evidence_status,
                "aggregate_status": aggregate_status,
                "claims": claims,
                "critical_unverified": critical_unverified,
            }
            if crypto_critical_unverified and isinstance(output, dict):
                refusal_content["output"] = output
            return JSONResponse(status_code=200, content=refusal_content)

        signing_key = _verdict_signing_key() if evidence_status == "VERIFIED" else None
        if evidence_status == "VERIFIED" and signing_key is None:
            reason = "SIGNING_KEY_NOT_CONFIGURED"
            trace = provenance.create_trace(
                task_profile,
                required,
                "REFUSE",
                reason,
                len(eligible),
                request_id=request_id,
                refusal_reason=reason,
                failure_diagnostics={"evidence_status": evidence_status},
            )
            persistence.write_trace(trace)
            return JSONResponse(
                status_code=503,
                content={"status": "REFUSE", "reason": reason, "trace_id": trace["trace_id"]},
            )

        successful_model = (
            (
                output.get("provider_model_id")
                or output.get("provider_requested_model_id")
                or output.get("model")
                or selected
            )
            if isinstance(output, dict)
            else selected
        )
        qualification = evaluate_model_qualification(successful_model, task_profile)
        trace = provenance.create_trace(
            task_profile,
            required,
            action,
            selected,
            len(eligible),
            output=output,
            request_id=request_id,
            evidence_status=evidence_status,
            evidence_details={
                **(evidence_details if isinstance(evidence_details, dict) else {}),
                "model_verification": evidence_status,
                "aggregate_status": aggregate_status,
                "claims": claims,
                "critical_unverified": critical_unverified,
            },
            fallback_history=output.get("fallback_history", []) if isinstance(output, dict) else [],
        )
        if isinstance(trace.get("execution_details"), dict):
            trace["execution_details"]["qualification"] = qualification
        persistence.write_trace(trace)
        response = {
            "status": "EXECUTE",
            "execution_status": "EXECUTE",
            "selected_model": successful_model,
            "trace_id": trace["trace_id"],
            "evidence_status": evidence_status,
            "model_verification": evidence_status,
            "aggregate_status": aggregate_status,
            "claims": claims,
            "critical_unverified": critical_unverified,
            "qualification": qualification,
        }
        if output is not None:
            response["output"] = output
        if evidence_status == "VERIFIED":
            assert signing_key is not None
            output_digest = trace.get("execution_details", {}).get("output_digest")
            if not isinstance(output_digest, str) or not output_digest:
                reason = "VERDICT_EVIDENCE_HASH_MISSING"
                return JSONResponse(
                    status_code=503,
                    content={"status": "REFUSE", "reason": reason, "trace_id": trace["trace_id"]},
                )
            verdict = JampVerdict(
                trace_id=trace["trace_id"],
                status=evidence_status,
                provider_model_id=(
                    output.get("provider_model_id") if isinstance(output, dict) else None
                ),
                evidence_hash=output_digest,
                timestamp=time.time(),
                execution_status="EXECUTE",
                model_verification=evidence_status,
                claims=claims,
                aggregate_status=aggregate_status,
                critical_unverified=critical_unverified,
            ).sign(signing_key)
            verdict_dict = verdict.to_dict()
            persistence.write_verdict(trace["trace_id"], verdict_dict)
            response["verdict"] = verdict_dict
        return response

    def telegram_webhook(payload: dict[str, Any], request: FastAPIRequest):
        """Authenticated Telegram webhook; allowlisted chat only, no secret logging."""
        webhook_secret = os.environ.get("TELEGRAM_WEBHOOK_SECRET", "")
        bot_token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
        allowed_chat = os.environ.get("TELEGRAM_CHAT_ID", "")
        supplied_secret = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
        if not webhook_secret or not bot_token or not allowed_chat:
            return JSONResponse(
                status_code=503,
                content={"status": "REFUSE", "reason": "TELEGRAM_NOT_CONFIGURED"},
            )
        if not hmac.compare_digest(supplied_secret, webhook_secret):
            return JSONResponse(
                status_code=401,
                content={"status": "REFUSE", "reason": "TELEGRAM_WEBHOOK_UNAUTHORIZED"},
            )
        message = payload.get("message")
        if not isinstance(message, dict):
            return {"status": "IGNORED"}
        chat = message.get("chat")
        text_value = message.get("text")
        if not isinstance(chat, dict) or not isinstance(chat.get("id"), int):
            return {"status": "IGNORED"}
        chat_id = chat["id"]
        if str(chat_id) != allowed_chat:
            return JSONResponse(
                status_code=403,
                content={"status": "REFUSE", "reason": "TELEGRAM_CHAT_NOT_ALLOWED"},
            )
        # Reserve the authenticated, allowlisted update before parsing its text.
        # This makes even malformed commands idempotent across Telegram retries.
        request_id = payload.get("update_id")
        if isinstance(request_id, bool) or not isinstance(request_id, int):
            return JSONResponse(
                status_code=422,
                content={
                    "status": "REFUSE",
                    "reason": "TELEGRAM_UPDATE_ID_REQUIRED",
                },
            )
        try:
            claimed = telegram_update_store.claim(request_id)
        except TelegramUpdateStoreError:
            return JSONResponse(
                status_code=503,
                content={
                    "status": "REFUSE",
                    "reason": "TELEGRAM_IDEMPOTENCY_UNAVAILABLE",
                },
            )
        if not claimed:
            return JSONResponse(
                status_code=200,
                content={
                    "status": "DUPLICATE",
                    "reason": "TELEGRAM_UPDATE_ALREADY_CLAIMED",
                },
            )

        if not isinstance(text_value, str) or not text_value.strip():
            return {"status": "IGNORED"}

        # Telegram messages must declare a supported task profile explicitly.
        command, _, prompt = text_value.strip().partition(" ")
        task_profiles = {
            "/search": {"intent": "search_and_extraction"},
            "/tools": {"intent": "tool_execution_agent"},
        }
        profile = task_profiles.get(command)
        if profile is None:
            return {"status": "IGNORED", "reason": "UNKNOWN_COMMAND"}
        if not prompt.strip():
            hint = (
                "Формат: /search <вопрос>\n"
                "Например: /search какие модели топ сегодня\n"
                "Или: /tools <задача>"
            )
            with suppress(Exception):
                # A hint is best-effort; acknowledge the update to stop retry loops.
                _send_telegram_message(bot_token, chat_id, hint)
            return {"status": "HINT_SENT"}

        result = execute(
            {
                **profile,
                "prompt": prompt.strip(),
                "request_id": f"telegram:{request_id}",
            }
        )
        if isinstance(result, JSONResponse):
            try:
                result_body = json.loads(result.body.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                result_body = {"status": "REFUSE", "reason": "RUNTIME_RESPONSE_INVALID"}
        else:
            result_body = result
        status = result_body.get("status", "REFUSE")
        trace_id = result_body.get("trace_id", "unknown")
        if status == "EXECUTE":
            output = result_body.get("output")
            if isinstance(output, dict):
                reply_text = output.get("content")
                if not isinstance(reply_text, str):
                    reply_text = json.dumps(output, ensure_ascii=False)
            else:
                reply_text = str(output or "")
        else:
            reply_text = f"REFUSE: {result_body.get('reason', 'EXECUTION_BLOCKED')}"
        reply_text = f"{reply_text[:3500]}\n\ntrace_id: {trace_id}"
        try:
            _send_telegram_message(bot_token, chat_id, reply_text)
        except Exception:
            return JSONResponse(
                status_code=502,
                content={
                    "status": "REFUSE",
                    "reason": "TELEGRAM_DELIVERY_FAILED",
                    "trace_id": trace_id,
                },
            )
        return {"status": status, "trace_id": trace_id}

    # FastAPI is imported lazily inside create_app; with postponed annotations,
    # resolve the locally imported Request class before route registration.
    telegram_webhook.__annotations__["request"] = FastAPIRequest
    app.post("/v1/telegram/webhook")(telegram_webhook)

    @app.post("/v1/verify-verdict", dependencies=[Depends(require_api_key)])
    def verify_verdict(payload: dict[str, Any]):
        """Verify a verdict signature; malformed or unverifiable payloads fail closed."""
        signing_key = _verdict_signing_key()
        if signing_key is None:
            return {"valid": False}
        try:
            verdict = JampVerdict.from_dict(payload)
            valid = verdict.verify(signing_key)
        except (TypeError, ValueError, OverflowError):
            valid = False
        return {"valid": valid}

    @app.post("/v1/universal-verdict", dependencies=[Depends(require_api_key)])
    def universal_verdict(payload: dict[str, Any]):
        """Wrap a signed JampVerdict in a UniversalVerdict v0 envelope.

        spec_hash/criteria_hash are SHA-256 of identifier strings, not of
        document content (v0 semantics). evidence_refs are committed in the
        canonical payload; reproducible remains False until independent
        full-chain reproduction is implemented.
        """
        import hashlib
        from datetime import UTC, datetime

        jv_payload = payload.get("jamp_verdict")
        spec_id = (payload.get("spec_id") or "").strip()
        criteria_id = (payload.get("criteria_id") or "").strip()
        if not spec_id or not criteria_id:
            return JSONResponse(
                status_code=400,
                content={"detail": "spec_id and criteria_id required"},
            )

        raw_refs = payload.get("evidence_refs", [])
        if not isinstance(raw_refs, list):
            return JSONResponse(
                status_code=400,
                content={"detail": "evidence_refs must be a list"},
            )
        validated = []
        for i, ref in enumerate(raw_refs):
            if not isinstance(ref, dict):
                return JSONResponse(
                    status_code=400,
                    content={"detail": f"evidence_refs[{i}] must be an object"},
                )
            evidence_type = ref.get("type")
            ref_hash = ref.get("ref_hash")
            source_sha256 = ref.get("source_sha256")
            if not isinstance(evidence_type, str) or evidence_type not in _EVIDENCE_TYPES:
                return JSONResponse(
                    status_code=400,
                    content={"detail": f"evidence_refs[{i}].type not allowed"},
                )
            if not isinstance(ref_hash, str) or _REF_HASH_RE.fullmatch(ref_hash) is None:
                return JSONResponse(
                    status_code=400,
                    content={"detail": (f"evidence_refs[{i}].ref_hash invalid (sha256:<64hex>)")},
                )
            if not isinstance(source_sha256, str) or _REF_HASH_RE.fullmatch(source_sha256) is None:
                return JSONResponse(
                    status_code=400,
                    content={"detail": f"evidence_refs[{i}].source_sha256 invalid"},
                )
            validated.append(
                EvidenceRef(
                    type=evidence_type,
                    ref_hash=ref_hash,
                    source_sha256=source_sha256,
                )
            )

        if not isinstance(jv_payload, dict):
            return JSONResponse(
                status_code=400,
                content={"detail": "jamp_verdict must be an object"},
            )

        signing_key = _verdict_signing_key()
        if signing_key is None:
            return JSONResponse(
                status_code=503,
                content={"detail": "signing key not configured"},
            )

        try:
            jv = JampVerdict.from_dict(jv_payload)
        except (TypeError, ValueError, KeyError):
            return JSONResponse(
                status_code=400,
                content={"detail": "invalid jamp_verdict"},
            )
        if not jv.verify(signing_key):
            return JSONResponse(
                status_code=400,
                content={"detail": "jamp_verdict signature invalid"},
            )

        result_str = str(jv.aggregate_status)
        ts = datetime.now(UTC).isoformat().replace("+00:00", "Z")

        uv = UniversalVerdict(
            spec_ref=SpecRef(
                spec_id=spec_id,
                spec_hash=hashlib.sha256(spec_id.encode("utf-8")).hexdigest(),
            ),
            criteria_ref=CriteriaRef(
                criteria_id=criteria_id,
                criteria_hash=hashlib.sha256(criteria_id.encode("utf-8")).hexdigest(),
            ),
            execution_ref=ExecutionRef(
                jamp_verdict_hash=compute_jamp_verdict_hash(jv),
                execution_status=str(jv.execution_status),
            ),
            evidence_refs=tuple(validated),
            classification=UniversalClassification(label=result_str),
            verdict=VerdictResult(result=result_str),
            verifier=VerifierInfo(
                version="uv0.2.0",
                reproducible=False,  # v0: evidence committed, not reproduced
                aggregation_rule_hash=hashlib.sha256(
                    b"uv0-preserve-jamp-aggregate-status"
                ).hexdigest(),
            ),
            timestamp=ts,
        )

        response_body = {
            "universal_verdict": uv.canonical_payload(),
            "verdict_hash": uv.compute_verdict_hash(),
            "signature": uv.sign(signing_key.encode("utf-8")),
            "semantics": (
                "spec_hash/criteria_hash are SHA-256 of identifiers, not of document content (v0)"
            ),
        }
        persistence.write_universal_verdict(jv.trace_id, response_body)
        return response_body

    @app.get(
        "/v1/universal-verdict/{trace_id}",
        dependencies=[Depends(require_api_key)],
    )
    def get_universal_verdict(trace_id: str):
        """Return the last persisted UniversalVerdict envelope for trace_id.

        Re-POST with the same trace_id creates a new record; this endpoint
        returns the most recent one. Absence of an envelope → 404 (the
        underlying JampVerdict may still exist and be retrievable via
        GET /v1/jamp-verdict/{trace_id}).
        """
        stored = persistence.read_universal_verdict_by_id(trace_id)
        if stored is None:
            return JSONResponse(
                status_code=404,
                content={"detail": "Universal verdict not found for trace_id"},
            )

        signing_key = _verdict_signing_key()
        if signing_key is None:
            return JSONResponse(
                status_code=503,
                content={"detail": "signing key not configured"},
            )

        try:
            envelope = stored["universal_verdict"]
            stored_outer_hash = stored["verdict_hash"]
            stored_signature = stored["signature"]
            stored_classification_hash = envelope["classification"].get("classification_hash", "")
        except (KeyError, TypeError):
            return JSONResponse(
                status_code=500,
                content={"detail": "stored universal verdict missing fields"},
            )

        try:
            uv = _universal_verdict_from_dict(envelope)
        except (TypeError, ValueError, KeyError):
            return JSONResponse(
                status_code=500,
                content={"detail": "stored universal verdict failed to parse"},
            )

        if uv.compute_verdict_hash() != stored_outer_hash:
            return JSONResponse(
                status_code=500,
                content={"detail": "stored universal verdict hash mismatch"},
            )

        if uv.classification.classification_hash != stored_classification_hash:
            return JSONResponse(
                status_code=500,
                content={"detail": "stored classification hash mismatch"},
            )

        if not uv.verify(signing_key.encode("utf-8"), stored_signature):
            return JSONResponse(
                status_code=500,
                content={"detail": "stored universal verdict signature invalid"},
            )

        return stored

    @app.get("/v1/jamp-verdict/{trace_id}", dependencies=[Depends(require_api_key)])
    def get_jamp_verdict(trace_id: str):
        """Return the persisted signed JampVerdict for a trace_id.

        This is the raw execution verdict. UniversalVerdict envelope is not
        reconstructed here — spec_ref and criteria_ref are client-supplied at
        POST /v1/universal-verdict and are not persisted. Use that endpoint
        to wrap a verdict; use this one to retrieve the persisted original.
        """
        stored = persistence.read_verdict_by_id(trace_id)
        if stored is None:
            return JSONResponse(
                status_code=404,
                content={"detail": "Verdict not found for trace_id"},
            )

        signing_key = _verdict_signing_key()
        if signing_key is None:
            return JSONResponse(
                status_code=503,
                content={"detail": "signing key not configured"},
            )

        try:
            jv = JampVerdict.from_dict(stored)
        except (TypeError, ValueError, KeyError):
            return JSONResponse(
                status_code=500,
                content={"detail": "stored verdict failed to parse"},
            )

        if not jv.verify(signing_key):
            return JSONResponse(
                status_code=500,
                content={"detail": "stored verdict failed integrity check"},
            )

        return stored

    @app.get("/v1/provenance/{trace_id}", dependencies=[Depends(require_api_key)])
    def get_provenance(trace_id: str):
        trace = persistence.read_trace_by_id(trace_id)
        if trace is None:
            return JSONResponse(status_code=404, content={"detail": "Trace not found"})
        return trace

    return app
