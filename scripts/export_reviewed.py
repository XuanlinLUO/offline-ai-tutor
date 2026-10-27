"""Export manually accepted records to LLaMA-Factory's Alpaca JSON format."""
import argparse
import hashlib
import json
from pathlib import Path
import random
from scripts.prepare_dataset import FIELDS


def export(rows, seed=42):
    kept, seen = [], set()
    for row in rows:
        if row.get("accepted") is not True:
            continue
        if any(not isinstance(row.get(k), str) or not row[k].strip() for k in ("instruction", "output")):
            raise ValueError("Accepted record has empty instruction/output")
        if any(field not in row["output"] for field in FIELDS):
            raise ValueError("Accepted record is missing a four-step heading")
        item = {"instruction": row["instruction"], "input": row.get("input", ""), "output": row["output"]}
        digest = hashlib.sha256(item["instruction"].strip().encode()).hexdigest()
        if digest not in seen:
            seen.add(digest); kept.append(item)
    if len(kept) < 2:
        raise ValueError("Need at least two unique, manually accepted records; this is only a structural minimum")
    random.Random(seed).shuffle(kept)
    n = max(1, int(len(kept) * 0.1))
    return kept[n:], kept[:n]


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("input", type=Path); p.add_argument("output_dir", type=Path)
    p.add_argument("--seed", type=int, default=42)
    args = p.parse_args()
    rows = [json.loads(line) for line in args.input.read_text(encoding="utf-8").splitlines() if line.strip()]
    train, val = export(rows, args.seed)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    for name, values in [("train.json", train), ("validation.json", val)]:
        with (args.output_dir / name).open("x", encoding="utf-8") as f:
            json.dump(values, f, ensure_ascii=False, indent=2)
    print(f"Exported train={len(train)}, validation={len(val)}; seed={args.seed}")


if __name__ == "__main__": main()
