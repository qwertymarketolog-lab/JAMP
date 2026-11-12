"""Sequential AnyModel v0.1a Stage A runner."""
import hashlib, json, os, sys, time, urllib.error, urllib.request
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import HTTPRedirectHandler, build_opener

MODEL = "am/nemotron-3-ultra-550b-a55b"
COMMIT = "9d41f43af9af2292fe5b47e179bdbcf8c6789a70"
INPUT = Path("stage-a-inputs")
OUT = Path("stage-a-evidence")
RAW, META = OUT / "raw", OUT / "metadata"
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
def now():
    return datetime.now(timezone.utc).isoformat()
def save(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
def blob_sha(data):
    return hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()
def task2_prompt():
    parts = {}
    for name in EXPECTED:
        data = (INPUT / name).read_bytes()
        actual = blob_sha(data)
        if actual != EXPECTED[name]:
            raise RuntimeError(f"pinned_blob_mismatch:{name}:{actual}")
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
def main():
    key = os.environ.get("ANYMODEL_API_KEY", "")
    if not key: raise RuntimeError("ANYMODEL_API_KEY_missing")
    RAW.mkdir(parents=True, exist_ok=True); META.mkdir(parents=True, exist_ok=True)
    tasks = [("task1", TASK1), ("task2", task2_prompt()), ("task5", TASK5)]
    opener = build_opener(NoRedirect)
    results = []
    for i, (tid, prompt) in enumerate(tasks):
        (OUT / f"prompt_{tid}.txt").write_text(prompt, encoding="utf-8")
        payload = {"model": MODEL, "messages": [{"role":"user","content":prompt}], "max_tokens":2048}
        req = urllib.request.Request(
            "https://anymodel.org/v1/chat/completions",
            data=json.dumps(payload, ensure_ascii=False).encode(),
            headers={"Authorization":f"Bearer {key}","Content-Type":"application/json",
                     "User-Agent":"JAMP-Evidence-Client/0.1","Accept":"application/json"},
            method="POST")
        start = time.monotonic(); status = None; headers = {}; body = b""; error = None
        try:
            with opener.open(req, timeout=180) as response:
                status=response.status; headers=dict(response.headers.items()); body=response.read()
        except urllib.error.HTTPError as exc:
            status=exc.code; headers=dict(exc.headers.items()) if exc.headers else {}; body=exc.read()
        except Exception as exc:
            error=f"{type(exc).__name__}: {exc}"
        latency=round((time.monotonic()-start)*1000)
        parsed=None; content=None; parse_error=None
        if body:
            try:
                parsed=json.loads(body)
                choices=parsed.get("choices") if isinstance(parsed,dict) else None
                if isinstance(choices,list) and choices and isinstance(choices[0],dict):
                    msg=choices[0].get("message",{})
                    if isinstance(msg,dict): content=msg.get("content")
                if content is None:
                    parse_error="response_choices_or_message_content_missing"
            except Exception as exc:
                parse_error=f"{type(exc).__name__}: {exc}"
        raw=RAW/f"{tid}.json"
        if body: raw.write_bytes(body)
        else: save(raw, {"transport_error":error or "empty_response","http_status":status})
        ok=status==200 and error is None and parse_error is None and content is not None
        meta={"task_id":tid,"model":MODEL,"http_status":status,"max_tokens":2048,
              "request_sent":True,"response_received":status is not None,"retry_count":0,
              "redirects_followed":0,"latency_ms":latency,"response_headers":headers,
              "transport_error":error,"parse_error":parse_error,"model_content":content,
              "result":"SUCCESS" if ok else "FAILED"}
        save(META/f"{tid}.json",meta)
        results.append({"task_id":tid,"result":meta["result"],"http_status":status,
                        "latency_ms":latency,"raw_response":str(raw)})
        print(f"{tid}: {meta['result']} HTTP={status} latency_ms={latency}",flush=True)
        if i < 2:
            print(f"COOLDOWN_START after={tid} seconds=60",flush=True)
            time.sleep(60)
            print(f"COOLDOWN_END after={tid}",flush=True)
    summary={"state":"COMPLETED" if all(x["result"]=="SUCCESS" for x in results) else "FAILED",
             "model":MODEL,"source_commit":COMMIT,"source_git_blob_sha1":EXPECTED,
             "tasks":results,"requests_sent":len(results),"retry_count":0,
             "cooldowns_seconds":[60,60],"completed_at":now()}
    save(OUT/"summary.json",summary)
    print(json.dumps(summary,ensure_ascii=False,indent=2))
    return 0 if summary["state"]=="COMPLETED" else 1
if __name__=="__main__":
    try: raise SystemExit(main())
    except Exception as exc:
        OUT.mkdir(parents=True,exist_ok=True)
        save(OUT/"fatal-error.json",{"state":"FAILED_BEFORE_OR_DURING_SETUP",
             "error":f"{type(exc).__name__}: {exc}","completed_at":now()})
        print(f"STAGE_A_FATAL: {type(exc).__name__}: {exc}",file=sys.stderr)
        raise SystemExit(1) from exc
