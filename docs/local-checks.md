# 本地检查记录

检查日期：2026-10-27。

环境：Python 3.12.14，Node.js v24.22.1，Linux 容器。

| 检查 | 结果 | 范围 |
|---|---|---|
| `python -m unittest discover -s tests -v` | 30 项通过 | 后端 HTTP、模拟 llama-server、SSE、模型启动、数据与 LoRA 工具 |
| `node --test tests/frontend.test.cjs` | 3 项通过 | 中文流式分块、异常提示、完成状态和历史记录 |
| `python -m compileall -q backend scripts training` | 通过 | Python 语法 |
| `node --check frontend/static/app.js` | 通过 | JavaScript 语法 |
| `bash -n start.sh deploy/start-model.sh deploy/ai-tutor-kiosk.sh` | 通过 | Shell 语法 |
| CLI 演示服务启动及真实 HTTP 请求 | 通过 | 健康检查、SSE、固定示例标记、正常结束 |
| LoRA CLI dry-run | 通过 | 数据注册、配置生成、planned 状态、无训练产物 |

前端流程检查使用轻量 DOM 适配器和真实 Web Streams API，不等于真实浏览器视觉检查。
当前环境没有可启动的浏览器引擎，页面排版仍需在目标浏览器打开后确认。
当前也没有实际 llama-server 二进制、GGUF 权重、摄像头和 PaddleOCR 运行环境，
因此没有报告硬件性能或模型准确率。模型 HTTP 协议、加载中状态、SSE 与应用对接使用本地模拟服务检查。
新增训练脚本的子进程日志和失败识别通过模拟框架检查，尚未在 GPU 镜像中实际训练。

CI 工作流已提供，上传 GitHub 后方可实际运行；目前没有声称 GitHub Actions 已执行。
