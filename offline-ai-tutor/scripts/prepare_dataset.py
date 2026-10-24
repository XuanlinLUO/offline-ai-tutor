"""Translate/rewrite local JSONL through an explicitly configured remote API.

Writes review candidates only. It never treats generated answers as verified data.
Run from repository root: python -m scripts.prepare_dataset --help
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

FIELDS = ("问题分析", "解题步骤", "最终答案", "知识点讲解")
REWRITE_PROMPT = """将用户给出的英文教学问答翻译并改写为中文。
保留题目的数字、单位、条件和数学含义，参考答案是待核对材料，不能把明显错误照抄成事实。
语气温和、耐心、具体，不空泛夸奖。不得新增未经说明的题目条件。
只输出 JSON 对象，字段：question（中文题目）、问题分析、解题步骤、最终答案、知识点讲解、review_notes。
每个字段都是字符串。解题步骤应充分解释操作依据。识别出原题/答案错误或信息不足时，在 review_notes 中说明。
所有样本将由人工复核，你的输出不代表答案已被验证。"""


def rewrite(question, answer, base, key, model):
    url = urlsplit(base)
    if url.scheme != "https" or not url.hostname or url.username or url.password or url.query or url.fragment:
        raise ValueError("REWRITE_API_BASE must be an HTTPS base URL")
    payload = {"model": model, "stream": False, "temperature": 0.2,
               "response_format": {"type": "json_object"},
               "messages": [{"role": "system", "content": REWRITE_PROMPT},
                            {"role": "user", "content": json.dumps({"question": question, "answer": answer}, ensure_ascii=False)}]}
    req = Request(base.rstrip("/") + "/chat/completions",
                  data=json.dumps(payload, ensure_ascii=False).encode(),
                  headers={"Content-Type": "application/json", "Authorization": "Bearer " + key})
    with urlopen(req, timeout=120) as res:
        content = json.load(res)["choices"][0]["message"]["content"]
    value = json.loads(content)
    if not isinstance(value, dict) or any(not isinstance(value.get(k), str) or not value[k].strip()
                                          for k in ("question", *FIELDS)):
        raise ValueError("API 返回数据缺少四步式字段")
    return value


def main():
    parser = argparse.ArgumentParser(description="Generate Chinese four-step review candidates; sends source QA to configured API")
    parser.add_argument("input", type=Path, help="Local JSONL dataset")
    parser.add_argument("output", type=Path, help="New candidates JSONL (will not overwrite)")
    parser.add_argument("--question-key", default="question")
    parser.add_argument("--answer-key", default="answer")
    parser.add_argument("--source", required=True, help="Exact dataset URL and version")
    parser.add_argument("--limit", type=int, default=10)
    args = parser.parse_args()
    if args.limit < 1:
        parser.error("limit must be positive")
    key = os.getenv("REWRITE_API_KEY", "")
    base = os.getenv("REWRITE_API_BASE", "https://api.deepseek.com")
    model = os.getenv("REWRITE_API_MODEL", "")
    if not key or not model:
        parser.error("Set REWRITE_API_KEY and REWRITE_API_MODEL in the process environment")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    # Exclusive create preserves partial work if any API call fails.
    with args.output.open("x", encoding="utf-8") as out, args.input.open(encoding="utf-8") as src:
        for lineno, line in enumerate(src, 1):
            if not line.strip(): continue
            row = json.loads(line)
            q, a = row[args.question_key], row[args.answer_key]
            if not isinstance(q, str) or not isinstance(a, str):
                raise ValueError(f"Line {lineno}: expected string question and answer")
            item = rewrite(q, a, base, key, model)
            record = {"instruction": item["question"], "input": "",
                      "output": "\n\n".join(f"{i + 1}. {k}\n{item[k]}" for i, k in enumerate(FIELDS)),
                      "review_notes": item.get("review_notes", ""), "accepted": False,
                      "provenance": {"source": args.source, "source_line": lineno,
                         "source_qa_sha256": hashlib.sha256(json.dumps([q, a], ensure_ascii=False).encode()).hexdigest(),
                         "rewrite_model": model, "created_at": datetime.now(timezone.utc).isoformat()}}
            out.write(json.dumps(record, ensure_ascii=False) + "\n"); out.flush()
            count += 1
            print(f"Saved review candidate {count}")
            if count >= args.limit: break
    if not count: raise ValueError("No source records were found")


if __name__ == "__main__": main()
