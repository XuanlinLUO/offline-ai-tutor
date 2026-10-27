import json
import http.client
import threading
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from dataclasses import replace
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from backend.config import Settings
from backend.app import TutorServer
from backend.services.llm_service import LlamaCppClient, ModelError, sse_payloads


class StubLlama(BaseHTTPRequestHandler):
    last_payload = None
    last_path = None

    def log_message(self, *args): pass

    def do_GET(self):
        if self.path == "/health":
            value = {"status": "ok"}
        elif self.path == "/v1/models":
            value = {"data": [{"id": "test", "object": "model"}]}
        else:
            self.send_error(404); return
        raw = json.dumps(value).encode()
        self.send_response(200); self.send_header("Content-Length", str(len(raw))); self.end_headers(); self.wfile.write(raw)

    def do_POST(self):
        StubLlama.last_path = self.path
        payload = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        StubLlama.last_payload = payload
        if self.path != "/v1/chat/completions": self.send_error(404); return
        self.send_response(200); self.send_header("Content-Type", "text/event-stream"); self.end_headers()
        prompt = payload["messages"][-1]["content"]
        events = [{"choices": [{"index":0,"delta":{"reasoning_content":"not visible reasoning"}}]},
                  {"choices": [{"index":0,"delta":{"content":"中文回答"}}]}]
        if prompt == "reasoning-only": events = events[:1]
        events.append({"choices":[{"index":0,"delta":{},"finish_reason":"stop"}]})
        if prompt != "no-metrics":
            events.append({"choices":[], "usage":{"completion_tokens":4}, "system_fingerprint":"test-build",
                           "timings":{"predicted_n":4,"predicted_ms":2000,"predicted_per_second":2.0}})
        for event in events:
            # This HTTP stream may split a multi-byte Chinese character across writes.
            data = ("data: " + json.dumps(event,ensure_ascii=False) + "\r\n\r\n").encode()
            for i in range(0,len(data),5): self.wfile.write(data[i:i+5]); self.wfile.flush()
        if prompt != "truncated": self.wfile.write(b"data: [DONE]\n\n"); self.wfile.flush()


class LlamaCppTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(("127.0.0.1",0),StubLlama)
        cls.thread = threading.Thread(target=cls.server.serve_forever,daemon=True); cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown(); cls.server.server_close(); cls.thread.join()

    def client(self,**kwargs):
        return LlamaCppClient(replace(Settings(),llama_host=f"http://127.0.0.1:{self.server.server_port}",model="test",**kwargs))

    def test_actual_http_sse_usage_and_timings(self):
        client = self.client(think="false")
        self.assertTrue(client.status()["ready"])
        events = list(client.stream("测试题",[]))
        self.assertEqual(events[0],{"type":"token","content":"中文回答"})
        self.assertEqual(events[-1]["metrics"]["tokens_per_second"],2)
        self.assertEqual(events[-1]["metrics"]["output_tokens"],4)
        self.assertEqual(events[-1]["metrics"]["system_fingerprint"],"test-build")
        self.assertEqual(StubLlama.last_path,"/v1/chat/completions")
        self.assertEqual(StubLlama.last_payload["chat_template_kwargs"],{"enable_thinking":False})
        self.assertEqual(StubLlama.last_payload["max_tokens"],1024)

    def test_missing_metrics_not_fabricated(self):
        metrics = list(self.client().stream("no-metrics",[]))[-1]["metrics"]
        self.assertIsNone(metrics["tokens_per_second"])
        self.assertIsNone(metrics["output_tokens"])
        self.assertEqual(metrics["speed_source"],"not_reported")

    def test_premature_eof_is_error(self):
        with self.assertRaisesRegex(ModelError,"DONE"): list(self.client().stream("truncated",[]))

    def test_reasoning_only_is_not_visible_answer(self):
        with self.assertRaisesRegex(ModelError,"可见解答"): list(self.client().stream("reasoning-only",[]))

    def test_unknown_alias_status(self):
        client = LlamaCppClient(replace(self.client().settings,model="missing"))
        self.assertFalse(client.status()["ready"])

    def test_unconfigured_model(self):
        client = LlamaCppClient(Settings())
        self.assertFalse(client.status()["ready"])
        with self.assertRaises(ModelError): list(client.stream("题目",[]))

    def test_multiline_sse_and_comments(self):
        self.assertEqual(list(sse_payloads([b": keep alive\n",b"event: message\n",b"data: one\n",b"data: two\n",b"\n"])),["one\ntwo"])

    def test_loading_503_is_not_reported_ready(self):
        with patch("backend.services.llm_service.urlopen",side_effect=HTTPError("http://localhost/health",503,"Loading",{},None)):
            value=self.client().status()
        self.assertFalse(value["ready"])
        self.assertIn("加载",value["message"])

    def test_application_uses_llama_cpp_by_default(self):
        app=TutorServer(replace(self.client().settings,port=0))
        thread=threading.Thread(target=app.serve_forever,daemon=True); thread.start()
        try:
            conn=http.client.HTTPConnection("127.0.0.1",app.server_port,timeout=5)
            conn.request("POST","/api/ask",body=json.dumps({"text":"测试题"}).encode(),headers={"Content-Type":"application/json"})
            response=conn.getresponse()
            self.assertEqual(response.status,200)
            events=[json.loads(part[6:]) for part in response.read().decode().strip().split("\n\n")]
            self.assertEqual(events[-1]["metrics"]["engine"],"llama.cpp")
            self.assertEqual("".join(e.get("content","") for e in events),"中文回答")
            conn.close()
        finally:
            app.shutdown(); app.server_close(); thread.join()


if __name__ == "__main__": unittest.main()
