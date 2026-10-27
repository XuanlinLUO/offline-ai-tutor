import json
import math
import time
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
from backend.prompts import build_messages


class ModelError(RuntimeError):
    pass


def sse_payloads(response):
    """Read complete UTF-8 SSE events, including multi-line data and final EOF."""
    parts = []
    for raw in response:
        line = raw.decode("utf-8").rstrip("\r\n")
        if not line:
            if parts:
                yield "\n".join(parts)
                parts = []
        elif line.startswith("data:"):
            value = line[5:]
            parts.append(value[1:] if value.startswith(" ") else value)
    if parts:
        yield "\n".join(parts)


class LlamaCppClient:
    def __init__(self, settings):
        self.settings = settings

    def status(self):
        if not self.settings.model:
            return {"ready": False, "message": "请先在 .env 中设置 LLAMA_MODEL，与服务模型别名一致"}
        try:
            with urlopen(self.settings.llama_host + "/health", timeout=2) as res:
                health = json.load(res)
            if health.get("status") != "ok":
                return {"ready": False, "message": "llama.cpp 模型尚未就绪"}
            with urlopen(self.settings.llama_host + "/v1/models", timeout=2) as res:
                body = json.load(res)
            models = body.get("data", [])
            alias = self.settings.model
            match = next((m for m in models if m.get("id") == alias), None)
            return {"ready": match is not None,
                    "message": "llama.cpp 本地模型可用" if match else "模型别名不匹配，请核对 LLAMA_MODEL 和服务 --alias",
                    "model": alias, "engine": "llama.cpp"}
        except HTTPError as exc:
            return {"ready": False, "message": "llama.cpp 正在加载模型，请稍候" if exc.code == 503
                    else f"llama.cpp 状态接口失败（HTTP {exc.code}）"}
        except (OSError, ValueError, URLError, AttributeError, TypeError):
            return {"ready": False, "message": "无法连接 llama.cpp，请先启动本地 llama-server"}

    def stream(self, text, history):
        s = self.settings
        if not s.model:
            raise ModelError("尚未配置 LLAMA_MODEL")
        payload = {"model": s.model, "messages": build_messages(text, history),
                   "stream": True, "temperature": s.temperature, "max_tokens": s.max_tokens,
                   "stream_options": {"include_usage": True}}
        if s.think != "auto":
            payload["chat_template_kwargs"] = {"enable_thinking": s.think == "true"}
        req = Request(s.llama_host + "/v1/chat/completions",
                      data=json.dumps(payload, ensure_ascii=False).encode(),
                      headers={"Content-Type": "application/json", "Accept": "text/event-stream"})
        started = time.monotonic()
        first = None
        visible = False
        finish_reason = "unknown"
        usage = {}
        timings = {}
        fingerprint = None
        try:
            with urlopen(req, timeout=s.timeout) as res:
                for raw in sse_payloads(res):
                    if time.monotonic() - started > s.timeout:
                        raise ModelError("模型生成超时，请缩短题目或回答长度")
                    if raw.strip() == "[DONE]":
                        if not visible:
                            raise ModelError("模型没有返回可见解答，请检查思考模式或提高生成上限")
                        count = usage.get("completion_tokens", timings.get("predicted_n"))
                        speed = timings.get("predicted_per_second")
                        if not isinstance(speed, (int, float)) or not math.isfinite(speed) or speed < 0:
                            duration = timings.get("predicted_ms")
                            n = timings.get("predicted_n")
                            speed = n * 1000 / duration if isinstance(n, (int, float)) and isinstance(duration, (int, float)) and duration > 0 else None
                        yield {"type": "done", "metrics": {
                            "model": s.model, "engine": "llama.cpp", "first_output_seconds": first,
                            "generation_seconds": round(time.monotonic() - started, 3),
                            "output_tokens": count,
                            "tokens_per_second": round(speed, 3) if speed is not None else None,
                            "speed_source": "llama.cpp timings" if speed is not None else "not_reported",
                            "system_fingerprint": fingerprint,
                            "finish_reason": finish_reason}}
                        return
                    data = json.loads(raw)
                    if data.get("error"):
                        raise ModelError("本地模型返回错误，请查看 llama-server 日志")
                    if isinstance(data.get("usage"), dict): usage.update(data["usage"])
                    if isinstance(data.get("timings"), dict): timings.update(data["timings"])
                    fingerprint = data.get("system_fingerprint") or fingerprint
                    for choice in data.get("choices", []):
                        if choice.get("index", 0) != 0: continue
                        if choice.get("finish_reason"): finish_reason = choice["finish_reason"]
                        content = choice.get("delta", {}).get("content")
                        if content:
                            if not isinstance(content, str): raise ModelError("模型可见输出格式异常")
                            visible = True
                            if first is None: first = round(time.monotonic() - started, 3)
                            yield {"type": "token", "content": content}
                raise ModelError("模型连接提前结束，未收到 [DONE] 完成标志")
        except HTTPError as exc:
            raise ModelError(f"llama.cpp 请求失败（HTTP {exc.code}），请核对模型和参数") from exc
        except (OSError, URLError) as exc:
            raise ModelError("本地模型连接失败或读取超时") from exc
        except (ValueError, TypeError, AttributeError) as exc:
            raise ModelError("模型响应格式异常") from exc


class DemoClient:
    """Fixed example; deliberately marked as a simulation in every UI state."""
    def status(self):
        return {"ready": True, "message": "界面演示：固定示例，不调用模型", "model": "DEMO"}

    def stream(self, text, history):
        answer = ("【固定示例，未调用 AI 模型】\n\n一、问题分析\n"
                  "示例题：解方程 2x + 6 = 14。目标是求出 x。\n\n二、解题步骤\n"
                  "1. 两边同时减去 6：2x = 8。\n2. 两边同时除以 2：x = 4。\n"
                  "3. 代回检验：2 × 4 + 6 = 14，成立。\n\n三、最终答案\nx = 4。\n\n"
                  "四、知识点讲解\n等式两边同时加减同一个数，或乘除同一个非零数，等式仍成立。"
                  "\n\n这是交互测试示例，不是对输入题目的真实推理。")
        for i in range(0, len(answer), 9):
            time.sleep(0.01)
            yield {"type": "token", "content": answer[i:i + 9]}
        yield {"type": "done", "metrics": {"model": "DEMO", "simulation": True}}
