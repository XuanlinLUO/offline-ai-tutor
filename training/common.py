"""Shared validation and actual process recording; no training dependencies imported."""
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import uuid


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_object(path):
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected a JSON object: {path}")
    return value


def check_base_model(directory, require_weights=True):
    directory = Path(directory).expanduser().resolve()
    config = directory / "config.json"
    if not config.is_file():
        raise ValueError("基础模型目录缺少 config.json，请提供完整本地 Hugging Face 模型目录")
    read_object(config)
    weights = sorted(directory.glob("*.safetensors")) + sorted(directory.glob("pytorch_model*.bin"))
    if require_weights and not weights:
        raise ValueError("基础模型目录没有找到权重；请先准备完整模型")
    return directory


def check_new_output(directory):
    directory = Path(directory).expanduser().resolve()
    if directory.exists() and (not directory.is_dir() or any(directory.iterdir())):
        raise ValueError(f"输出路径已有内容，请使用新的目录，避免覆盖实验：{directory}")
    return directory


def check_adapter(directory):
    directory = Path(directory).expanduser().resolve()
    config = read_object(directory / "adapter_config.json")
    if str(config.get("peft_type", "")).upper() != "LORA":
        raise ValueError("适配器配置的 peft_type 不是 LORA")
    weights = [p for p in [directory / "adapter_model.safetensors", directory / "adapter_model.bin"]
               if p.is_file() and p.stat().st_size > 0]
    if not weights:
        raise ValueError("适配器目录缺少 adapter_model.safetensors 或 adapter_model.bin")
    return directory, config, weights


def new_run_dir(operation):
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return Path("outputs/runs") / f"{operation}-{stamp}-{uuid.uuid4().hex[:8]}"


def execute_factory(operation, config, expected_output, kind, metadata, dry_run=False, run_dir=None):
    """Run real LLaMA-Factory; preserve plan/log/status even on failure.

    JSON is a YAML subset: effective_config.yaml can be read by OmegaConf without
    adding PyYAML to this project's standard-library tooling.
    """
    executable = shutil.which("llamafactory-cli")
    if not dry_run and executable is None:
        raise ValueError("未找到 llamafactory-cli，请在已经安装 LLaMA-Factory 的镜像或环境内运行")
    run_dir = Path(run_dir or new_run_dir(operation)).expanduser().resolve()
    run_dir.mkdir(parents=True, exist_ok=False)
    config_path = run_dir / "effective_config.yaml"
    config_path.write_text(json.dumps(config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    command = [executable or "llamafactory-cli", operation, str(config_path)]
    manifest_path = run_dir / "run_manifest.json"
    manifest = {"operation": operation, "kind": kind, "status": "planned" if dry_run else "running",
                "created_at": datetime.now(timezone.utc).isoformat(), "command": command,
                "python": sys.version, "metadata": metadata, "artifacts": []}

    def save():
        temporary = manifest_path.with_suffix(".tmp")
        temporary.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        temporary.replace(manifest_path)

    save()
    print("配置：", config_path)
    print("运行记录：", manifest_path)
    if dry_run:
        print("仅完成计划与数据检查；未启动训练或导出。")
        return manifest_path
    process = None
    try:
        with (run_dir / "process.log").open("w", encoding="utf-8") as log:
            process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                       text=True, encoding="utf-8", errors="replace", bufsize=1,
                                       start_new_session=os.name == "posix")
            try:
                for line in process.stdout:
                    sys.stdout.write(line); log.write(line); log.flush()
                return_code = process.wait()
            finally:
                process.stdout.close()
        manifest["return_code"] = return_code
        if return_code:
            raise RuntimeError(f"LLaMA-Factory 退出码为 {return_code}，请查看 process.log")
        expected_output = Path(expected_output)
        if kind == "lora":
            _, adapter, weights = check_adapter(expected_output)
            if int(adapter.get("r", 0)) != config["lora_rank"]:
                raise RuntimeError("输出适配器 rank 与本次配置不符")
            artifacts = [expected_output / "adapter_config.json", *weights]
        else:
            if not (expected_output / "config.json").is_file():
                raise RuntimeError("导出进程结束，但没有发现 config.json")
            weights = sorted(expected_output.glob("*.safetensors")) + sorted(expected_output.glob("pytorch_model*.bin"))
            if not weights:
                raise RuntimeError("导出进程结束，但没有发现合并模型权重")
            artifacts = [expected_output / "config.json", *weights]
        manifest["artifacts"] = [{"path": str(p), "sha256": sha256(p), "bytes": p.stat().st_size} for p in artifacts]
        manifest["status"] = "completed"
        manifest["note"] = "进程和产物检查完成；模型质量仍需独立评测。"
    except BaseException as exc:
        if process is not None and process.poll() is None:
            if os.name == "posix": os.killpg(process.pid, signal.SIGTERM)
            else: process.terminate()
            try: process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                if os.name == "posix": os.killpg(process.pid, signal.SIGKILL)
                else: process.kill()
                process.wait()
        manifest["status"] = "interrupted" if isinstance(exc, KeyboardInterrupt) else "failed"
        manifest["error"] = str(exc)
        raise
    finally:
        manifest["finished_at"] = datetime.now(timezone.utc).isoformat()
        save()
    return manifest_path
