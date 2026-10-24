"""Record actual local generation timings, not previous report estimates."""
import argparse
from dataclasses import replace
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import statistics
from backend.config import Settings
from backend.services.llm_service import OllamaClient


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--questions", type=Path, default=Path("benchmarks/questions.jsonl"))
    p.add_argument("--output", type=Path, default=Path("data/reports/benchmark.jsonl"))
    p.add_argument("--condition", required=True, help="Record UI state, CPU configuration, cold/warm, device")
    p.add_argument("--repeat", type=int, default=1)
    args = p.parse_args()
    if not 1 <= args.repeat <= 30: p.error("repeat must be between 1 and 30")
    s = Settings.from_env()
    if s.demo: p.error("Benchmarks never use demonstration mode")
    client = OllamaClient(s); status = client.status()
    if not status.get("ready"): p.error(status["message"])
    rows = [json.loads(line) for line in args.questions.read_text(encoding="utf-8").splitlines() if line.strip()]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    speeds = []
    with args.output.open("x", encoding="utf-8") as out:
        for repeat in range(args.repeat):
            for row in rows:
                result = {"question_id": row["id"], "repeat": repeat + 1,
                          "condition": args.condition, "recorded_at": datetime.now(timezone.utc).isoformat(),
                          "model": s.model, "model_digest": status.get("digest"),
                          "max_tokens": s.max_tokens, "temperature": s.temperature, "think": s.think,
                          "question_sha256": hashlib.sha256(row["question"].encode()).hexdigest()}
                answer = ""
                try:
                    for event in client.stream(row["question"], []):
                        if event["type"] == "token": answer += event["content"]
                        if event["type"] == "done": result.update(event["metrics"])
                    result["answer"] = answer
                    if result.get("tokens_per_second"): speeds.append(result["tokens_per_second"])
                except Exception as exc:
                    result.update({"error": str(exc), "answer": answer})
                out.write(json.dumps(result, ensure_ascii=False) + "\n"); out.flush()
                print(row["id"], "ERROR" if "error" in result else "saved")
    if speeds: print("Median generation tok/s:", statistics.median(speeds))


if __name__ == "__main__": main()
