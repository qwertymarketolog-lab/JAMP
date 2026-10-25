from __future__ import annotations

import hmac
import json
import os
from collections.abc import Callable
from contextlib import suppress
from pathlib import Path
from typing import Any
from urllib.request import Request as UrlRequest
from urllib.request import urlopen

from jamp.provider.anymodel import AnyModelChatExecutor, AnyModelError
from jamp.provider.e2_verify import verify_generation
from jamp.provider.groq import GroqChatExecutor, GroqError
from jamp.provider.openrouter import OpenRouterChatExecutor, OpenRouterError
from jamp.runtime import (
    AuditPersistence,
    CapabilityResolver,
    ModelSelector,
    ProvenanceTracker,
    TaskClassifier,
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


DEFAULT_EVIDENCE = Path(__file__).parents[3] / "tests/fixtures/runtime_evidence_projection.json"


def create_app(
    evidence_path: str | Path = DEFAULT_EVIDENCE,
    executor: Callable[[str, dict[str, Any]], Any] | None = None,
    audit_storage_path: str | Path | None = None,
    telegram_update_db_path: str | Path | None = None,
):
    try:
        from fastapi import FastAPI
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
    configured_executor = (
        executor
        if executor is not None
        else (
            OpenRouterChatExecutor.from_env()
            or GroqChatExecutor.from_env()
            or AnyModelChatExecutor.from_env()
        )
    )

    app = FastAPI(title="JAMP API", version="v1")
    app.openapi_version = "3.0.3"

    @app.post("/v1/classify")
    def classify(payload: dict[str, Any]):
        task_profile = classifier.classify(payload)
        required = resolver.get_required_capabilities(task_profile)
        return {"task_profile": task_profile, "required_capabilities": list(required)}

    @app.post("/v1/execute")
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
            if isinstance(exc, (AnyModelError, OpenRouterError, GroqError)):
                reason = "PROVIDER_EXECUTION_FAILED"
            else:
                reason = "EXECUTOR_ERROR"
            failure_diagnostics = None
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
                failure_diagnostics=failure_diagnostics,
            )
            persistence.write_trace(trace)
            return JSONResponse(
                status_code=502,
                content={"status": "REFUSE", "reason": reason, "trace_id": trace["trace_id"]},
            )

        evidence_status = "NOT_APPLICABLE"
        evidence_details = None

        if isinstance(configured_executor, OpenRouterChatExecutor) or (
            isinstance(output, dict) and output.get("provider") == "openrouter"
        ):
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
                        "evidence_status": evidence_status,
                        **evidence_details,
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

        trace = provenance.create_trace(
            task_profile,
            required,
            action,
            selected,
            len(eligible),
            output=output,
            request_id=request_id,
            evidence_status=evidence_status,
            evidence_details=evidence_details,
        )
        persistence.write_trace(trace)
        response = {
            "status": "EXECUTE",
            "selected_model": selected,
            "trace_id": trace["trace_id"],
            "evidence_status": evidence_status,
        }
        if output is not None:
            response["output"] = output
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

    @app.get("/v1/provenance/{trace_id}")
    def get_provenance(trace_id: str):
        trace = persistence.read_trace_by_id(trace_id)
        if trace is None:
            return JSONResponse(status_code=404, content={"detail": "Trace not found"})
        return trace

    return app
