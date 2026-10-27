"""Convert merged HF weights to GGUF and actually run llama.cpp quantization."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import sys
from training.common import check_base_model, check_new_output, sha256


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--model-dir", type=Path, required=True, help="Actual merged Hugging Face model")
    p.add_argument("--llama-cpp", type=Path, required=True, help="Built llama.cpp checkout")
    p.add_argument("--output-dir", type=Path, default=Path("outputs/qwen3-teaching-gguf"))
    p.add_argument("--quantization", choices=["Q4_K_M", "Q4_0", "Q5_K_M", "Q8_0"], default="Q4_K_M")
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()
    try:
        model = check_base_model(args.model_dir, require_weights=not args.dry_run)
        output = check_new_output(args.output_dir)
        if output == model or model in output.parents:
            raise ValueError("量化输出不能写入输入模型目录")
        tools = args.llama_cpp.expanduser().resolve()
        converter = tools / "convert_hf_to_gguf.py"
        quantizer = tools / "build/bin/llama-quantize"
        if not converter.is_file() or not quantizer.is_file():
            raise ValueError("缺少 convert_hf_to_gguf.py 或 build/bin/llama-quantize，请先准备并构建 llama.cpp")
        output.mkdir(parents=True, exist_ok=True)
        f16 = output / "model-f16.gguf"
        quantized = output / f"model-{args.quantization.lower()}.gguf"
        commands = [[sys.executable, str(converter), str(model), "--outfile", str(f16), "--outtype", "f16"],
                    [str(quantizer), str(f16), str(quantized), args.quantization]]
        manifest_path = output / "quantization_manifest.json"
        manifest = {"status": "planned" if args.dry_run else "running",
                    "created_at": datetime.now(timezone.utc).isoformat(),
                    "source_config_sha256": sha256(model / "config.json"),
                    "format": args.quantization, "commands": commands,
                    "converter_sha256": sha256(converter), "quantizer_sha256": sha256(quantizer),
                    "artifacts": []}

        def save():
            temp = manifest_path.with_suffix(".tmp")
            temp.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            temp.replace(manifest_path)

        save()
        if args.dry_run:
            print("量化计划已保存，未转换模型或执行量化：", manifest_path)
            return
        try:
            with (output / "process.log").open("w", encoding="utf-8") as log:
                for index, command in enumerate(commands, 1):
                    print(f"正在执行第 {index}/2 步，输出日志：{output / 'process.log'}", flush=True)
                    log.write(json.dumps(command, ensure_ascii=False) + "\n"); log.flush()
                    subprocess.run(command, stdout=log, stderr=subprocess.STDOUT, check=True)
                    expected = f16 if index == 1 else quantized
                    if not expected.is_file() or expected.stat().st_size == 0:
                        raise RuntimeError("进程返回成功但没有生成非空 GGUF 文件")
            manifest["artifacts"] = [{"path":str(file), "bytes":file.stat().st_size, "sha256":sha256(file)}
                                     for file in [f16, quantized]]
            manifest["status"] = "completed"
        except BaseException as exc:
            manifest["status"] = "interrupted" if isinstance(exc, KeyboardInterrupt) else "failed"
            manifest["error"] = str(exc)
            raise
        finally:
            manifest["finished_at"] = datetime.now(timezone.utc).isoformat(); save()
        print("量化完成：", quantized)
    except (OSError, ValueError, RuntimeError, subprocess.CalledProcessError) as exc:
        p.exit(2, f"量化未完成：{exc}\n")


if __name__ == "__main__": main()
