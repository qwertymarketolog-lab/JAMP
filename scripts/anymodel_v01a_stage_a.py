"""Sequential AnyModel v0.1a Stage A runner."""

import hashlib
import json
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from urllib.request import HTTPRedirectHandler, build_opener

MODEL = "am/nemotron-3-ultra-550b-a55b"
COMMIT = "9d41f43af9af2292fe5b47e179bdbcf8c6789a70"
INPUT = Path("stage-a-inputs")
OUT = Path("stage-a-evidence")
RAW = OUT / "raw"
META = OUT / "metadata"
EXPECTED = {
    "g1_verify.py": "2229ade069087c4beb1289b65f0f1e811d55fa97",
    "test_g1_verify.py": "547755a7348e205f1e112b3299dab61a98582ae8",
}

TASK1 = """Дана последовательность a(n) = n² для n = 1, 2, 3, ...
Задача: докажи формально, что для всех целых n ≥ 1 верно a(n+1) - a(n) = 2n + 1.
Требуется:
1. Формальное доказательство (алгебраическое преобразование или индукция). Эмпирическая проверка нескольких значений доказательством не считается.
2. Указание, какой метод использован.
3. Если доказательство требует дополнительных аксиом — укажи это.
Ответ должен быть самодостаточным: без ссылок на внешние источники, которые читатель должен открыть."""

TASK5 = """Предложи один механизм, снижающий вероятность галлюцинаций LLM при генерации кода, без увеличения числа запросов к API.
Требуется:
1. Название механизма.
2. Как работает — 3-5 предложений, без псевдокода.
3. Чем отличается от существующих подходов (self-consistency, retrieval-augmented, chain-of-verification, tool-use). Будь конкретен: если отличие незначительно, скажи это прямо.
4. Как проверить, что механизм работает — конкретный эксперимент с измеримым результатом.
5. Ограничения: в каких случаях механизм не работает.
Не заявляй, что механизм "новый" — просто опиши. Оценка новизны будет выполнена отдельно и независимо."""


def now() -> str:
    return datetime.now(UTC).isoformat()


def save(path: Path, obj: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    content = json.dumps(obj, ensure_ascii=False, indent=2) + "\n"
    path.write_text(content, encoding="utf-8")


def git_blob_sha(data: bytes) -> str:
    header = f"blob {len(data)}\0".encode()
    return hashlib.sha1(header + data).hexdigest()


def task2_prompt() -> str:
    parts = {}
    for name, expected_sha in EXPECTED.items():
        data = (INPUT / name).read_bytes()
        actual_sha = git_blob_sha(data)
        if actual_sha != expected_sha:
            raise RuntimeError(f"pinned_blob_mismatch:{name}:{actual_sha}")
        parts[name] = data.decode("utf-8")

    return f"""Ниже — два реальных файла из коммита {COMMIT}.

=== scripts/g1_verify.py ===
{parts["g1_verify.py"]}

=== tests/test_g1_verify.py ===
{parts["test_g1_verify.py"]}

Задача: найди конкретный сценарий, в котором fail-closed логика g1_verify.py может быть нарушена — то есть скрипт вернёт PASS там, где по смыслу проверки должен вернуть FAIL.

Требуется:
1. Минимальный воспроизводимый сценарий: какие входные данные, какие действия, какой результат.
2. Конкретная строка или блок кода, который позволяет обойти проверку (с номером строки).
3. Что должно быть изменено, чтобы закрыть этот сценарий.
4. Если дыр нет — обоснование, почему каждый путь проверки в коде заканчивается fail-closed.

Не предлагай гипотетических уязвимостей, которые не следуют из предоставленного кода."""


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, new_url):
        return None


def send_task(opener, task_id: str, prompt: str) -> dict[str, object]:
    prompt_path = OUT / f"prompt_{task_id}.txt"
    prompt_path.write_text(prompt, encoding="utf-8")

    payload = {
        "model": MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 2048,
    }
    request = urllib.request.Request(
        "https://anymodel.org/v1/chat/completions",
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {os.environ['ANYMODEL_API_KEY']}",
            "Content-Type": "application/json",
            "User-Agent": "JAMP-Evidence-Client/0.1",
            "Accept": "application/json",
        },
        method="POST",
    )

    started = time.monotonic()
    status = None
    headers = {}
    body = b""
    transport_error = None

    try:
        with opener.open(request, timeout=180) as response:
            status = response.status
            headers = dict(response.headers.items())
            body = response.read()
    except urllib.error.HTTPError as error:
        status = error.code
        headers = dict(error.headers.items()) if error.headers else {}
        body = error.read()
    except Exception as error:  # Continue to the next task after transport failures.
        transport_error = f"{type(error).__name__}: {error}"

    latency_ms = round((time.monotonic() - started) * 1000)
    content = None
    parse_error = None
    if body:
        try:
            parsed = json.loads(body)
            choices = parsed.get("choices") if isinstance(parsed, dict) else None
            if choices and isinstance(choices, list) and isinstance(choices[0], dict):
                message = choices[0].get("message", {})
                if isinstance(message, dict):
                    content = message.get("content")
            if content is None:
                parse_error = "response_choices_or_message_content_missing"
        except Exception as error:
            parse_error = f"{type(error).__name__}: {error}"

    raw_path = RAW / f"{task_id}.json"
    if body:
        raw_path.write_bytes(body)
    else:
        save(
            raw_path,
            {
                "transport_error": transport_error or "empty_response",
                "http_status": status,
            },
        )

    success = (
        status == 200
        and transport_error is None
        and parse_error is None
        and content is not None
    )
    metadata = {
        "task_id": task_id,
        "model": MODEL,
        "http_status": status,
        "max_tokens": 2048,
        "request_attempted": True,
        "request_sent": status is not None,
        "response_received": status is not None,
        "retry_count": 0,
        "redirects_followed": 0,
        "latency_ms": latency_ms,
        "response_headers": headers,
        "transport_error": transport_error,
        "parse_error": parse_error,
        "model_content": content,
        "result": "SUCCESS" if success else "FAILED",
    }
    save(META / f"{task_id}.json", metadata)

    result = {
        "task_id": task_id,
        "result": metadata["result"],
        "http_status": status,
        "latency_ms": latency_ms,
        "raw_response": str(raw_path),
        "metadata": str(META / f"{task_id}.json"),
    }
    print(
        f"{task_id}: {metadata['result']} HTTP={status} "
        f"latency_ms={latency_ms}",
        flush=True,
    )
    return result


def main() -> int:
    api_key = os.environ.get("ANYMODEL_API_KEY", "")
    if not api_key:
        raise RuntimeError("ANYMODEL_API_KEY_missing")

    RAW.mkdir(parents=True, exist_ok=True)
    META.mkdir(parents=True, exist_ok=True)

    tasks = [
        ("task1", TASK1),
        ("task2", task2_prompt()),
        ("task5", TASK5),
    ]
    opener = build_opener(NoRedirect)
    results = []

    for index, (task_id, prompt) in enumerate(tasks):
        results.append(send_task(opener, task_id, prompt))
        if index < len(tasks) - 1:
            print(
                f"COOLDOWN_START after={task_id} seconds=60",
                flush=True,
            )
            time.sleep(60)
            print(f"COOLDOWN_END after={task_id}", flush=True)

    all_succeeded = all(item["result"] == "SUCCESS" for item in results)
    summary = {
        "state": "COMPLETED" if all_succeeded else "FAILED",
        "model": MODEL,
        "source_commit": COMMIT,
        "source_git_blob_sha1": EXPECTED,
        "tasks": results,
        "requests_sent": len(results),
        "retry_count": 0,
        "cooldowns_seconds": [60, 60],
        "completed_at": now(),
    }
    save(OUT / "summary.json", summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if all_succeeded else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        OUT.mkdir(parents=True, exist_ok=True)
        save(
            OUT / "fatal-error.json",
            {
                "state": "FAILED_BEFORE_OR_DURING_SETUP",
                "error": f"{type(error).__name__}: {error}",
                "completed_at": now(),
            },
        )
        print(
            f"STAGE_A_FATAL: {type(error).__name__}: {error}",
            file=sys.stderr,
        )
        raise SystemExit(1) from error
