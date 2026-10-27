"""Loopback-only HTTP service. Run: python -m backend.app [--demo]."""
import argparse
import base64
import binascii
from dataclasses import replace
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import logging
import threading
from urllib.parse import urlsplit
from backend.config import ROOT, Settings
from backend.services.llm_service import DemoClient, ModelError, LlamaCppClient
from backend.services.ocr_service import VisionError, VisionService

LOG = logging.getLogger("ai-tutor")
MAX_BODY = 8 * 1024 * 1024
STATIC = {"/": ("index.html", "text/html; charset=utf-8"),
          "/static/app.js": ("static/app.js", "text/javascript; charset=utf-8"),
          "/static/style.css": ("static/style.css", "text/css; charset=utf-8")}


def validate_question(body):
    text = body.get("text")
    history = body.get("history", [])
    if not isinstance(text, str) or not text.strip() or len(text) > 12000:
        raise ValueError("请输入题目，最多 12000 个字符")
    if not isinstance(history, list) or len(history) > 12:
        raise ValueError("对话历史过长，请开始新题目")
    clean = []
    for index, item in enumerate(history):
        if (not isinstance(item, dict) or item.get("role") != ("user" if index % 2 == 0 else "assistant")
                or not isinstance(item.get("content"), str) or len(item["content"]) > 12000):
            raise ValueError("对话历史格式错误")
        clean.append({"role": item["role"], "content": item["content"]})
    if len(clean) % 2 or sum(len(m["content"]) for m in clean) + len(text) > 32000:
        raise ValueError("对话历史不完整或过长，请开始新题目")
    return text.strip(), clean


class TutorServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, settings, model=None, vision=None):
        self.settings = settings
        self.model = model or (DemoClient() if settings.demo else LlamaCppClient(settings))
        self.vision = vision or VisionService(settings)
        self.generation_lock = threading.Lock()
        super().__init__((settings.host, settings.port), Handler)


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, format, *args):
        # Do not log question text, uploaded image data, or upstream credentials.
        LOG.info("%s %s", self.command, urlsplit(self.path).path)

    def _headers(self, code, content_type, length=None):
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Content-Security-Policy", "default-src 'self'; img-src 'self' data:; "
                         "style-src 'self'; script-src 'self'; connect-src 'self'; "
                         "frame-ancestors 'none'; base-uri 'none'; form-action 'self'")
        self.send_header("Cache-Control", "no-store")
        if length is not None:
            self.send_header("Content-Length", str(length))
        else:
            self.send_header("Connection", "close")
            self.close_connection = True
        self.end_headers()

    def _json(self, code, value):
        raw = json.dumps(value, ensure_ascii=False).encode()
        self._headers(code, "application/json; charset=utf-8", len(raw))
        self.wfile.write(raw)

    def _local_request(self):
        port = self.server.server_address[1]
        allowed = {f"localhost:{port}", f"127.0.0.1:{port}"}
        if port == 80:
            allowed |= {"localhost", "127.0.0.1"}
        host = self.headers.get("Host", "").lower()
        if host not in allowed:
            self.close_connection = True
            self._json(403, {"error": "Only local requests are accepted"})
            return False
        origin = self.headers.get("Origin")
        if origin and origin not in {"http://" + item for item in allowed}:
            self.close_connection = True
            self._json(403, {"error": "Cross-origin requests are not accepted"})
            return False
        return True

    def _body(self):
        if self.headers.get("Transfer-Encoding"):
            raise ValueError("不支持分块请求体")
        if self.headers.get_content_type() != "application/json":
            raise ValueError("请求需要 application/json")
        size = int(self.headers.get("Content-Length", "0"))
        if not 0 < size <= MAX_BODY:
            raise ValueError("请求体为空或超过 8 MiB")
        self.connection.settimeout(20)
        raw = self.rfile.read(size)
        if len(raw) != size:
            raise ValueError("请求体不完整")
        body = json.loads(raw)
        if not isinstance(body, dict):
            raise ValueError("请求体需要 JSON 对象")
        return body

    def do_GET(self):
        if not self._local_request():
            return
        path = urlsplit(self.path).path
        if path in STATIC:
            relative, mime = STATIC[path]
            raw = (ROOT / "frontend" / relative).read_bytes()
            self._headers(200, mime, len(raw))
            self.wfile.write(raw)
        elif path == "/api/health":
            self._json(200, {"service": "ok", "demo": self.server.settings.demo,
                             "model": self.server.model.status(),
                             "vision": self.server.vision.status(),
                             "busy": self.server.generation_lock.locked()})
        else:
            self._json(404, {"error": "接口不存在"})

    def do_POST(self):
        if not self._local_request():
            return
        try:
            body = self._body()
            path = urlsplit(self.path).path
            if path == "/api/ask":
                text, history = validate_question(body)
                if not self.server.model.status().get("ready"):
                    self._json(503, {"error": "本地模型尚未就绪，请查看顶部连接状态"})
                    return
                if not self.server.generation_lock.acquire(blocking=False):
                    self._json(409, {"error": "模型正在解答另一条请求，请稍后重试"})
                    return
                try:
                    self._stream(text, history)
                finally:
                    self.server.generation_lock.release()
            elif path in {"/api/capture", "/api/ocr"}:
                if self.server.settings.demo:
                    raise VisionError("界面演示不执行真实拍照或 OCR；请关闭演示模式并安装依赖")
                image = None
                if path == "/api/ocr":
                    value = body.get("image", "")
                    if not isinstance(value, str):
                        raise ValueError("图片格式错误")
                    if value.startswith("data:"):
                        prefix, sep, value = value.partition(",")
                        if prefix not in {"data:image/png;base64", "data:image/jpeg;base64"} or not sep:
                            raise ValueError("仅支持 PNG / JPEG 图片")
                    try:
                        image = base64.b64decode(value, validate=True)
                    except (binascii.Error, ValueError) as exc:
                        raise ValueError("图片编码错误") from exc
                    if not image or len(image) > 5 * 1024 * 1024:
                        raise ValueError("图片需要小于 5 MiB")
                self._json(200, self.server.vision.process(image))
            else:
                self._json(404, {"error": "接口不存在"})
        except (ValueError, UnicodeError) as exc:
            self.close_connection = True
            self._json(400, {"error": str(exc)})
        except VisionError as exc:
            self._json(503, {"error": str(exc)})
        except (BrokenPipeError, ConnectionResetError):
            self.close_connection = True
        except Exception:
            LOG.exception("Request failed")
            self.close_connection = True
            self._json(500, {"error": "请求处理失败，请查看本地服务日志"})

    def _event(self, event):
        self.wfile.write(("data: " + json.dumps(event, ensure_ascii=False) + "\n\n").encode())
        self.wfile.flush()

    def _stream(self, text, history):
        self._headers(200, "text/event-stream; charset=utf-8")
        events = None
        try:
            self._event({"type": "start", "demo": self.server.settings.demo})
            events = self.server.model.stream(text, history)
            for event in events:
                self._event(event)
        except (BrokenPipeError, ConnectionResetError):
            pass
        except ModelError as exc:
            self._event({"type": "error", "message": str(exc)})
        except Exception:
            LOG.exception("Generation failed")
            self._event({"type": "error", "message": "生成失败，请查看本地日志"})
        finally:
            if events is not None and hasattr(events, "close"):
                events.close()


def main():
    parser = argparse.ArgumentParser(description="Offline AI tutor")
    parser.add_argument("--demo", action="store_true", help="Run a clearly labelled fixed UI example")
    parser.add_argument("--port", type=int)
    args = parser.parse_args()
    settings = Settings.from_env()
    if args.demo:
        settings = replace(settings, demo=True)
    if args.port is not None:
        if not 1 <= args.port <= 65535:
            parser.error("port must be between 1 and 65535")
        settings = replace(settings, port=args.port)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    server = TutorServer(settings)
    LOG.info("Open http://%s:%s — %s", settings.host, server.server_port,
             "DEMO / fixed example" if settings.demo else "local model mode")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
