import json
import time
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
from backend.prompts import build_messages


class ModelError(RuntimeError):
    pass


class OllamaClient:
    def __init__(self, settings):
        self.settings = settings

    def status(self):
        if not self.settings.model:
            return {"ready": False, "message": "请先在 .env 中设置 OLLAMA_MODEL"}
        try:
            with urlopen(self.settings.ollama_host + "/api/tags", timeout=2) as res:
                body = json.load(res)
            models = body.get("models", [])
            tag = self.settings.model
            match = next((m for m in models if m.get("name") in {tag, tag + ":latest"}
                          or m.get("model") in {tag, tag + ":latest"}), None)
            return {"ready": match is not None,
                    "message": "本地模型可用" if match else "模型未安装，请先用 ollama list 核对标签",
                    "model": tag, "digest": match.get("digest") if match else None}
        except (OSError, ValueError, URLError):
            return {"ready": False, "message": "无法连接本地 Ollama，请确认服务已启动"}

    def stream(self, text, history):
        s = self.settings
        if not s.model:
            raise ModelError("尚未配置 OLLAMA_MODEL")
        payload = {"model": s.model, "messages": build_messages(text, history),
                   "stream": True, "keep_alive": "5m",
                   "options": {"temperature": s.temperature, "num_predict": s.max_tokens}}
        if s.think != "auto":
            payload["think"] = s.think == "true"
        req = Request(s.ollama_host + "/api/chat",
                      data=json.dumps(payload, ensure_ascii=False).encode(),
                      headers={"Content-Type": "application/json"})
        started = time.monotonic()
        first = None
        visible = False
        try:
            with urlopen(req, timeout=s.timeout) as res:
                for line in res:
                    if time.monotonic() - started > s.timeout:
                        raise ModelError("模型生成超时，请缩短题目或回答长度")
                    if not line.strip():
                        continue
                    data = json.loads(line)
                    if data.get("error"):
                        raise ModelError("本地模型返回错误，请查看 Ollama 日志")
                    content = data.get("message", {}).get("content", "")
                    if content:
                        visible = True
                        if first is None:
                            first = round(time.monotonic() - started, 3)
                        yield {"type": "token", "content": content}
                    if data.get("done"):
                        if not visible:
                            raise ModelError("模型没有返回可见解答，请检查思考模式或提高生成上限")
                        count = data.get("eval_count", 0)
                        duration = data.get("eval_duration", 0)
                        yield {"type": "done", "metrics": {
                            "model": s.model, "first_output_seconds": first,
                            "generation_seconds": round(time.monotonic() - started, 3),
                            "output_tokens": count,
                            "tokens_per_second": round(count * 1e9 / duration, 3) if duration else None,
                            "finish_reason": data.get("done_reason", "unknown")}}
                        return
                raise ModelError("模型连接提前结束，未收到完成标志")
        except HTTPError as exc:
            raise ModelError(f"Ollama 请求失败（HTTP {exc.code}），请核对模型和参数") from exc
        except (OSError, URLError) as exc:
            raise ModelError("本地模型连接失败或读取超时") from exc
        except (ValueError, TypeError) as exc:
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
