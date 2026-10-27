from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit
import os

ROOT = Path(__file__).resolve().parents[1]


def load_env(path=ROOT / ".env"):
    """Simple non-executable dotenv: existing process settings take precedence."""
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            key, sep, value = line.partition("=")
            if not sep or not key.strip().replace("_", "").isalnum():
                raise ValueError("Invalid .env assignment")
            os.environ.setdefault(key.strip(), value.strip().strip("\"'"))


def integer(name, default, low, high):
    value = int(os.getenv(name, str(default)))
    if not low <= value <= high:
        raise ValueError(f"{name} must be between {low} and {high}")
    return value


@dataclass(frozen=True)
class Settings:
    host: str = "127.0.0.1"
    port: int = 5000
    llama_host: str = "http://127.0.0.1:8080"
    model: str = ""
    think: str = "auto"
    model_path: str = ""
    server_bin: str = "llama-server"
    model_threads: int = 4
    context_size: int = 2048
    parallel: int = 1
    temperature: float = 0.3
    max_tokens: int = 1024
    timeout: int = 600
    camera_device: int = 11
    camera_warmup: int = 20
    ocr_threads: int = 4
    ocr_det: str = "PP-OCRv6_medium_det"
    ocr_rec: str = "PP-OCRv6_medium_rec"
    demo: bool = False

    @classmethod
    def from_env(cls):
        load_env()
        host = os.getenv("TUTOR_HOST", "127.0.0.1")
        if host not in {"127.0.0.1", "localhost"}:
            raise ValueError("This local prototype only binds to 127.0.0.1 / localhost")
        upstream = os.getenv("LLAMA_HOST", "http://127.0.0.1:8080").rstrip("/")
        url = urlsplit(upstream)
        if (url.scheme != "http" or url.hostname not in {"localhost", "127.0.0.1"}
                or url.username or url.password or url.query or url.fragment or url.path):
            raise ValueError("LLAMA_HOST must be a loopback HTTP origin")
        try:
            if url.port is not None and not 1 <= url.port <= 65535:
                raise ValueError("Invalid port")
        except ValueError as exc:
            raise ValueError("LLAMA_HOST has an invalid port") from exc
        think = os.getenv("LLAMA_THINK", "auto").lower()
        if think not in {"auto", "true", "false"}:
            raise ValueError("LLAMA_THINK must be auto / true / false")
        temp = float(os.getenv("LLM_TEMPERATURE", "0.3"))
        if not 0 <= temp <= 2:
            raise ValueError("LLM_TEMPERATURE must be between 0 and 2")
        return cls(host=host, port=integer("TUTOR_PORT", 5000, 1, 65535),
                   llama_host=upstream, model=os.getenv("LLAMA_MODEL", "").strip(),
                   think=think, temperature=temp,
                   model_path=os.getenv("LLAMA_MODEL_PATH", "").strip(),
                   server_bin=os.getenv("LLAMA_SERVER_BIN", "llama-server").strip(),
                   model_threads=integer("LLAMA_THREADS", 4, 1, 64),
                   context_size=integer("LLAMA_CTX_SIZE", 2048, 256, 131072),
                   parallel=integer("LLAMA_PARALLEL", 1, 1, 8),
                   max_tokens=integer("LLM_MAX_TOKENS", 1024, 32, 8192),
                   timeout=integer("LLM_TIMEOUT", 600, 10, 3600),
                   camera_device=integer("CAMERA_DEVICE", 11, 0, 128),
                   camera_warmup=integer("CAMERA_WARMUP", 20, 0, 120),
                   ocr_threads=integer("OCR_CPU_THREADS", 4, 1, 4),
                   ocr_det=os.getenv("OCR_DET_MODEL", "PP-OCRv6_medium_det"),
                   ocr_rec=os.getenv("OCR_REC_MODEL", "PP-OCRv6_medium_rec"),
                   demo=os.getenv("TUTOR_DEMO", "0") == "1")
