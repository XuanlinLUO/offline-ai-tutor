"""Merge an actual LoRA adapter through LLaMA-Factory's export engine."""
import argparse
from pathlib import Path
from training.common import (check_adapter, check_base_model, check_new_output,
                             execute_factory, sha256)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--base-model", type=Path, required=True)
    p.add_argument("--adapter", type=Path, required=True)
    p.add_argument("--output-dir", type=Path, default=Path("outputs/qwen3-teaching-merged"))
    p.add_argument("--template", default="qwen3_nothink")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--run-dir", type=Path)
    args = p.parse_args()
    try:
        base = check_base_model(args.base_model, require_weights=not args.dry_run)
        adapter, adapter_config, weights = check_adapter(args.adapter)
        output = check_new_output(args.output_dir)
        if output in {base, adapter} or base in output.parents or adapter in output.parents:
            raise ValueError("合并输出不能写入基础模型或适配器目录")
        config = {"model_name_or_path": str(base), "adapter_name_or_path": str(adapter),
                  "template": args.template, "finetuning_type": "lora",
                  "export_dir": str(output), "export_size": 2,
                  "export_device": "cpu", "export_legacy_format": False,
                  "trust_remote_code": False}
        metadata = {"base_config_sha256": sha256(base / "config.json"),
                    "adapter_config_sha256": sha256(adapter / "adapter_config.json"),
                    "adapter_weights": [{"path":str(w),"sha256":sha256(w)} for w in weights],
                    "adapter_declared_base": adapter_config.get("base_model_name_or_path"),
                    "note": "请按真实训练记录确认基础模型相同；本工具不通过目录名证明版本一致。"}
        execute_factory("export", config, output, "merged", metadata,
                        dry_run=args.dry_run, run_dir=args.run_dir)
    except (OSError, ValueError, RuntimeError) as exc:
        p.exit(2, f"LoRA 合并未完成：{exc}\n")


if __name__ == "__main__": main()
