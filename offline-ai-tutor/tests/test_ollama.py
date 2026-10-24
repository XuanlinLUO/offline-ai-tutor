import io
import json
import threading
import unittest
from dataclasses import replace
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from backend.config import Settings
from backend.services.llm_service import OllamaClient, ModelError


class StubOllama(BaseHTTPRequestHandler):
    last_payload = None

    def log_message(self, *args): pass

    def do_GET(self):
        raw = json.dumps({"models": [{"name": "test:latest", "digest": "local-test-digest"}]}).encode()
        self.send_response(200); self.send_header("Content-Length", str(len(raw))); self.end_headers(); self.wfile.write(raw)

    def do_POST(self):
        StubOllama.last_payload = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        self.send_response(200); self.end_headers()
        for event in [{"message": {"thinking": "hidden internal text"}},
                      {"message": {"content": "中文回答"}},
                      {"done": True, "eval_count": 4, "eval_duration": 2_000_000_000, "done_reason": "stop"}]:
            self.wfile.write((json.dumps(event, ensure_ascii=False) + "\n").encode()); self.wfile.flush()


class OllamaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), StubOllama)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True); cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown(); cls.server.server_close(); cls.thread.join()

    def client(self, **kwargs):
        return OllamaClient(replace(Settings(), ollama_host=f"http://127.0.0.1:{self.server.server_port}", model="test", **kwargs))

    def test_real_http_ndjson_and_metrics(self):
        client = self.client(think="false")
        self.assertEqual(client.status()["digest"], "local-test-digest")
        events = list(client.stream("测试题", []))
        self.assertEqual(events[0], {"type": "token", "content": "中文回答"})
        self.assertEqual(events[-1]["metrics"]["tokens_per_second"], 2)
        self.assertFalse(StubOllama.last_payload["think"])
        self.assertEqual(StubOllama.last_payload["messages"][0]["role"], "system")

    def test_unknown_model_status(self):
        client = OllamaClient(replace(self.client().settings, model="missing"))
        self.assertFalse(client.status()["ready"])

    def test_unconfigured_model(self):
        client = OllamaClient(Settings())
        self.assertFalse(client.status()["ready"])
        with self.assertRaises(ModelError): list(client.stream("题目", []))


if __name__ == "__main__": unittest.main()
