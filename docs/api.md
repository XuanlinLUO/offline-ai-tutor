# 接口说明

服务地址默认 `http://127.0.0.1:5000`。POST 使用 `Content-Type: application/json`，
请求体最大 8 MiB。不提供跨域访问。错误响应格式为 `{"error":"说明"}`。

| 方法 | 路径 | 用途 |
|---|---|---|
| GET | `/` | 加载本地页面 |
| GET | `/api/health` | 后端、模型标签/摘要、图像依赖及忙闲状态 |
| POST | `/api/capture` | 拍照并识别；请求体 `{}` |
| POST | `/api/ocr` | 识别 PNG/JPEG；请求体 `{"image":"data:image/png;base64,..."}` |
| POST | `/api/ask` | 题目问答；以 SSE 返回生成过程 |

## 问答请求

```json
{
  "text": "解方程：2x+6=14。",
  "history": []
}
```

题目最多 12000 字符。历史仅接受成对的 `user`、`assistant` 消息，最多 6 轮，
与当前题目合计最多 32000 字符。客户端不能传入历史 system 消息。
历史只在页面内存中保存，刷新或“新题目”会清空，不写入数据库。

```bash
curl -N http://127.0.0.1:5000/api/ask \
  -H 'Content-Type: application/json' \
  -d '{"text":"解方程：2x+6=14。","history":[]}'
```

流中每个 JSON 事件前有 `data: `，事件以空行分隔：

```text
data: {"type":"start","demo":false}

data: {"type":"token","content":"一、问题分析"}

data: {"type":"done","metrics":{"model":"actual-local-tag"}}

```

发生模型错误时返回 `type=error`，附带 `message`。客户端不能把连接关闭等同于成功，
必须收到 `done`。同一时间只允许一个生成请求，忙时返回 409。

`first_output_seconds` 从后端发起模型请求计时到首段可见输出，包含连接和可能的加载/预填充等待，
不包含拍照和 OCR。`generation_seconds` 也从模型请求阶段开始；
`tokens_per_second` 使用 llama.cpp 返回的 `timings.predicted_per_second`，
或由 `predicted_n / (predicted_ms / 1000)` 计算，不等于端到端吞吐。
若所用服务版本没有返回 timings，则该字段为 null，不从字符数推算 token 速度。
`output_tokens` 来自服务的 usage/timings，可能包含模型内部生成的思考 token；没有返回时为 null。
`system_fingerprint` 按服务返回值记录，不作为 GGUF 文件哈希。

停止接收会关闭浏览器读取；后端在检测到断连后关闭模型响应流。
模型处于长时间预填充、尚未写出内容时，释放可能延迟，不保证即时中止计算。

## 图像返回

返回文字、逐行文本及置信度、JPEG 预览，以及采集/OCR/总耗时。
OCR 计时可能包含首次加载；评测时应明确区分冷启动与热运行。
上传图像不写入持久目录，当前服务不保存题目或解答历史。
