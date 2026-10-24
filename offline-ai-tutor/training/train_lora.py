"""Start real LoRA SFT inside an installed LLaMA-Factory environment.

Example: python -m training.train_lora --base-model /models/Qwen3-4B-Instruct-2507
"""
import argparse
from pathlib import Path
from training.check_dataset import validate_dataset
from training.common import check_base_model, check_new_output, execute_factory, read_object, sha256


def build_config(args):
    base = check_base_model(args.base_model, require_weights=not args.dry_run)
    dataset_dir = args.dataset_dir.expanduser().resolve()
    summary = validate_dataset(dataset_dir)
    output = check_new_output(args.output_dir)
    if output == base or base in output.parents or output == dataset_dir or dataset_dir in output.parents:
        raise ValueError("训练输出不能写入基础模型或数据目录")
    if args.rank <= 0 or args.alpha <= 0 or args.epochs <= 0 or args.learning_rate <= 0:
        raise ValueError("rank、alpha、epochs、learning-rate 必须为正数")
    if args.batch_size <= 0 or args.accumulation <= 0 or args.cutoff_len < 32:
        raise ValueError("batch-size、accumulation 必须为正数；cutoff-len 至少为 32")
    config = {"model_name_or_path": str(base), "trust_remote_code": False,
              "stage": "sft", "do_train": True, "do_eval": True,
              "finetuning_type": "lora", "lora_target": args.targets,
              "lora_rank": args.rank, "lora_alpha": args.alpha, "lora_dropout": 0.05,
              "dataset_dir": str(dataset_dir), "dataset": "teaching_zh_train",
              "eval_dataset": "teaching_zh_validation", "template": args.template,
              "cutoff_len": args.cutoff_len, "preprocessing_num_workers": 2,
              "dataloader_num_workers": 0, "output_dir": str(output),
              "overwrite_output_dir": False, "logging_steps": 10,
              "save_strategy": "epoch", "eval_strategy": "epoch", "save_total_limit": 2,
              "load_best_model_at_end": True, "metric_for_best_model": "eval_loss",
              "greater_is_better": False, "plot_loss": True,
              "per_device_train_batch_size": args.batch_size, "per_device_eval_batch_size": 1,
              "gradient_accumulation_steps": args.accumulation,
              "learning_rate": args.learning_rate, "num_train_epochs": args.epochs,
              "lr_scheduler_type": "cosine", "warmup_ratio": 0.1,
              "bf16": args.precision == "bf16", "fp16": args.precision == "fp16",
              "report_to": "none", "seed": args.seed}
    metadata = {"base_config_sha256": sha256(base / "config.json"),
                "dataset": summary, "environment_reference": args.environment_reference,
                "training_method": "LoRA SFT; training engine is LLaMA-Factory"}
    return config, metadata


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--base-model", type=Path, required=True)
    p.add_argument("--dataset-dir", type=Path, default=Path("data/reviewed"))
    p.add_argument("--output-dir", type=Path, default=Path("outputs/qwen3-teaching-lora"))
    p.add_argument("--template", default="qwen3_nothink")
    p.add_argument("--rank", type=int, default=8)
    p.add_argument("--alpha", type=int, default=16)
    p.add_argument("--targets", default="all")
    p.add_argument("--epochs", type=float, default=3.0)
    p.add_argument("--learning-rate", type=float, default=1e-4)
    p.add_argument("--batch-size", type=int, default=1)
    p.add_argument("--accumulation", type=int, default=8)
    p.add_argument("--cutoff-len", type=int, default=2048)
    p.add_argument("--precision", choices=["bf16", "fp16", "fp32"], default="bf16")
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--environment-reference", default="not_recorded", help="Actual container image tag/digest or environment version")
    p.add_argument("--dry-run", action="store_true", help="Check input and write plan; do not train")
    p.add_argument("--run-dir", type=Path)
    args = p.parse_args()
    try:
        config, metadata = build_config(args)
        # Validate the registry; never replace an existing source-data registry.
        registry = args.dataset_dir.expanduser().resolve() / "dataset_info.json"
        info = read_object(registry)
        for name, filename in [("teaching_zh_train", "train.json"), ("teaching_zh_validation", "validation.json")]:
            entry = info.get(name, {})
            if (not isinstance(entry, dict) or entry.get("file_name") != filename
                    or entry.get("formatting", "alpaca") != "alpaca"
                    or entry.get("columns") != {"prompt":"instruction", "query":"input", "response":"output"}):
                raise ValueError("dataset_info.json 与本项目字段不符；请参考 training/dataset_info.example.json")
        execute_factory("train", config, config["output_dir"], "lora", metadata,
                        dry_run=args.dry_run, run_dir=args.run_dir)
    except (OSError, ValueError, RuntimeError) as exc:
        p.exit(2, f"LoRA 训练未完成：{exc}\n")


if __name__ == "__main__": main()
