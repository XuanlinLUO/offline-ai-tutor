# 故障排查

| 现象 | 检查与处理 |
|---|---|
| 模型未配置 | 在 `.env` 设置 `LLAMA_MODEL`、`LLAMA_MODEL_PATH`、`LLAMA_SERVER_BIN` |
| 找不到 llama-server | 核对构建输出和可执行权限，先运行其 `--help` |
| 找不到 GGUF | 使用真实文件的绝对路径，模型不会由启动脚本自动下载 |
| 模型服务连接失败 | 先启动 `python -m scripts.serve_model`，核对 `LLAMA_HOST` 与端口 |
| 模型加载中 | `/health` 可返回 503，等待加载并检查内存与服务日志 |
| 模型别名不匹配 | `LLAMA_MODEL` 与 `--alias` 及 `/v1/models` 的 id 保持一致 |
| 有思考但无可见解答 | 核对模型、Jinja 模板、思考模式与输出上限 |
| SSE 提前断开 | 检查模型进程、内存及超时；没有 `[DONE]` 时不会记录为成功 |
| 没有显示 tok/s | 当前服务没有提供 timings，客户端不会从字数推算 token 速度 |
| 摄像头无法打开 | 核对 OV13855 的 MIPI CSI/V4L2 节点、格式和用户权限 |
| 前几帧曝光异常 | 比较预热帧设置与实际图像，调整光照并记录效果 |
| OCR 缺依赖 | 准备与目标 ARM 系统兼容的 PaddlePaddle、PaddleOCR、OpenCV |
| OCR 第一次很慢 | 提前准备缓存，区分冷启动与热运行 |
| OCR 进程崩溃 | 保留系统日志和版本，尝试降低线程数，继续定位原因 |
| 屏幕空闲后无信号 | 区分服务故障与 DPMS/屏保，X11 下检查显示休眠配置 |
| 后端正常但无全屏页面 | 检查图形会话登录和桌面 autostart |

查看实际服务状态与日志：

```bash
systemctl --user status llama-server.service ai-tutor.service
journalctl --user -u llama-server.service -f
journalctl --user -u ai-tutor.service -f
```

日志可能包含本机模型路径，公开前检查内容。
