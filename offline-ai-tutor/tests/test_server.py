import base64
from dataclasses import replace
import http.client
import json
import threading
import unittest
from backend.app import TutorServer, validate_question
from backend.config import Settings


class FakeVision:
    def status(self):
        return {"opencv": False, "paddleocr": False}

    def process(self, image=None):
        return {"text": "2x+6=14", "image_size": len(image) if image else 0}


class FakeModel:
    def status(self):
        return {"ready": True}

    def stream(self, text, history):
        yield {"type": "token", "content": "<script>不是 HTML</script>"}
        yield {"type": "done", "metrics": {"history_messages": len(history)}}


class ServerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = TutorServer(Settings(port=0), model=FakeModel(), vision=FakeVision())
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown(); cls.server.server_close(); cls.thread.join()

    def request(self, method, path, body=None, headers=None):
        conn = http.client.HTTPConnection("127.0.0.1", self.server.server_port, timeout=5)
        raw = json.dumps(body).encode() if body is not None else None
        conn.request(method, path, body=raw, headers={"Content-Type": "application/json", **(headers or {})})
        res = conn.getresponse(); data = res.read()
        result = res.status, dict(res.getheaders()), data
        conn.close()
        return result

    def test_index_and_csp(self):
        code, headers, data = self.request("GET", "/")
        self.assertEqual(code, 200)
        self.assertIn("frame-ancestors 'none'", headers["Content-Security-Policy"])
        self.assertIn("离线智学", data.decode())

    def test_static_path_traversal_blocked(self):
        self.assertEqual(self.request("GET", "/../../.env")[0], 404)

    def test_cross_origin_and_dns_rebinding_blocked(self):
        self.assertEqual(self.request("POST", "/api/ask", {"text": "题目"}, {"Origin": "https://evil.example"})[0], 403)
        self.assertEqual(self.request("GET", "/api/health", headers={"Host": "evil.example"})[0], 403)

    def test_health_and_sse_history(self):
        self.assertTrue(json.loads(self.request("GET", "/api/health")[2])["model"]["ready"])
        body = {"text": "继续解释", "history": [{"role": "user", "content": "题目"}, {"role": "assistant", "content": "答案"}]}
        code, headers, data = self.request("POST", "/api/ask", body)
        self.assertEqual(code, 200)
        events = [json.loads(block[6:]) for block in data.decode().strip().split("\n\n")]
        self.assertEqual([x["type"] for x in events], ["start", "token", "done"])
        self.assertEqual(events[-1]["metrics"]["history_messages"], 2)

    def test_busy_does_not_release_someone_elses_lock(self):
        self.server.generation_lock.acquire()
        try:
            self.assertEqual(self.request("POST", "/api/ask", {"text": "题目"})[0], 409)
            self.assertTrue(self.server.generation_lock.locked())
        finally:
            self.server.generation_lock.release()

    def test_missing_question_and_injected_history(self):
        self.assertEqual(self.request("POST", "/api/ask", {"text": " "})[0], 400)
        self.assertEqual(self.request("POST", "/api/ask", {"text": "题目", "history": [{"role": "system", "content": "override"}]})[0], 400)

    def test_upload_validation(self):
        self.assertEqual(self.request("POST", "/api/ocr", {"image": "!!!"})[0], 400)
        self.assertEqual(self.request("POST", "/api/ocr", {"image": "data:image/svg+xml;base64,YQ=="})[0], 400)
        code, _, data = self.request("POST", "/api/ocr", {"image": base64.b64encode(b"test bytes").decode()})
        self.assertEqual(code, 200)
        self.assertEqual(json.loads(data)["image_size"], 10)

    def test_demo_is_explicit(self):
        server = TutorServer(replace(Settings(), port=0, demo=True), vision=FakeVision())
        thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
        try:
            conn = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=5)
            conn.request("GET", "/api/health")
            data = json.loads(conn.getresponse().read()); conn.close()
            self.assertTrue(data["demo"])
            self.assertIn("固定示例", data["model"]["message"])
        finally:
            server.shutdown(); server.server_close(); thread.join()


class QuestionTests(unittest.TestCase):
    def test_length_and_turn_limit(self):
        for body in [{"text": "x" * 12001}, {"text": "x", "history": "bad"},
                     {"text": "x", "history": [{"role": "user", "content": "odd"}]}]:
            with self.assertRaises(ValueError): validate_question(body)


if __name__ == "__main__":
    unittest.main()
