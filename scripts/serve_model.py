"""Load a local GGUF file with llama.cpp's llama-server; never downloads models."""
import argparse
import os
from pathlib import Path
import shlex
import shutil
from urllib.parse import urlsplit
from backend.config import Settings


def build_command(settings, executable):
    if not settings.model:
        raise ValueError("请在 .env 中配置 LLAMA_MODEL（服务别名）")
    if not settings.model_path:
        raise ValueError("请在 .env 中配置 LLAMA_MODEL_PATH（真实 GGUF 路径）")
    path = Path(settings.model_path).expanduser().resolve()
    if not path.is_file():
        raise ValueError(f"GGUF 模型文件不存在：{path}")
    with path.open("rb") as model:
        if model.read(4) != b"GGUF":
            raise ValueError("模型不是 GGUF 文件，请先完成转换和量化")
    origin = urlsplit(settings.llama_host)
    if (origin.scheme != "http" or origin.hostname not in {"127.0.0.1", "localhost"}
            or origin.path or origin.query or origin.fragment or origin.username or origin.password):
        raise ValueError("LLAMA_HOST 必须是本机 HTTP 地址，不含 /v1 路径")
    return [str(executable), "--model", str(path), "--alias", settings.model,
            "--host", origin.hostname, "--port", str(origin.port or 80),
            "--threads", str(settings.model_threads), "--ctx-size", str(settings.context_size),
            "--parallel", str(settings.parallel), "--n-gpu-layers", "0", "--jinja"]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--print-command", action="store_true", help="Validate configuration and print argv without starting inference")
    args = parser.parse_args()
    try:
        settings = Settings.from_env()
        executable = shutil.which(settings.server_bin)
        if executable is None:
            raise ValueError("找不到 llama-server，请构建后设置 LLAMA_SERVER_BIN 为实际可执行文件路径")
        command = build_command(settings, executable)
        print(shlex.join(command), flush=True)
        if not args.print_command:
            os.execv(executable, command)
    except (OSError, ValueError) as exc:
        parser.exit(2, f"模型服务未启动：{exc}\n")


if __name__ == "__main__": main()
