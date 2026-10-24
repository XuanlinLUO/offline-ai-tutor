"""Check reviewed Alpaca JSON and train/validation overlap before training."""
import argparse
import json
from pathlib import Path
import unicodedata
from training.common import sha256

HEADINGS = ("问题分析", "解题步骤", "最终答案", "知识点讲解")


def question_key(text):
    return "".join(unicodedata.normalize("NFKC", text).split())


def inspect_split(path):
    path = Path(path)
    rows = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(rows, list) or not rows:
        raise ValueError(f"{path.name} 必须为非空 JSON 数组")
    seen = set()
    for index, row in enumerate(rows, 1):
        if not isinstance(row, dict):
            raise ValueError(f"{path.name} 第 {index} 条不是对象")
        if any(not isinstance(row.get(k), str) or not row[k].strip() for k in ("instruction", "output")):
            raise ValueError(f"{path.name} 第 {index} 条缺少题目或答案")
        if not isinstance(row.get("input", ""), str):
            raise ValueError(f"{path.name} 第 {index} 条 input 应为字符串")
        if row.get("accepted") is False:
            raise ValueError("发现未通过复核的候选样本，请先通过 export_reviewed 导出")
        positions = [row["output"].find(h) for h in HEADINGS]
        if min(positions) < 0 or positions != sorted(positions):
            raise ValueError(f"{path.name} 第 {index} 条缺少四步标题，或顺序不一致")
        key = question_key(row["instruction"] + "\n" + row.get("input", ""))
        if key in seen:
            raise ValueError(f"{path.name} 中存在重复题目")
        seen.add(key)
    return {"file": str(path.resolve()), "count": len(rows), "sha256": sha256(path)}, seen


def validate_dataset(directory):
    directory = Path(directory).expanduser().resolve()
    train, train_keys = inspect_split(directory / "train.json")
    validation, val_keys = inspect_split(directory / "validation.json")
    if train_keys & val_keys:
        raise ValueError("训练集与验证集存在相同题目，请重新按原题分组划分")
    return {"train": train, "validation": validation,
            "note": "仅检查格式与规范化后的完全重复；不验证教学正确性和语义近重复。"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset-dir", type=Path, default=Path("data/reviewed"))
    args = parser.parse_args()
    try:
        print(json.dumps(validate_dataset(args.dataset_dir), ensure_ascii=False, indent=2))
    except (OSError, ValueError) as exc:
        parser.exit(2, f"数据检查失败：{exc}\n")


if __name__ == "__main__": main()
