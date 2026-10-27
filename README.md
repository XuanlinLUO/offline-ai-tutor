# 离线 AI 教学助手（offline-ai-tutor）

面向香橙派等本地教学终端的离线问答项目。系统支持拍照或上传题目图片，经 OCR 识别、人工核对后，调用本机 llama.cpp 的 `llama-server` 加载 GGUF 模型，以流式方式生成中文解答。

解答采用四步结构：**问题分析、解题步骤、最终答案、知识点讲解**。用户也可以直接输入文字题目，并继续追问。

## 代码目录

| 目录或文件 | 内容与用途 |
| --- | --- |
| `backend/` | 应用后端：HTTP 接口、配置读取、提示词与请求处理 |
| `backend/services/` | 模型调用、OCR 识别与摄像头采集服务 |
| `frontend/` | 交互页面：拍照、图片上传、题目编辑、流式解答、复制和追问 |
| `scripts/` | 数据处理、模型服务启动与性能采集脚本 |
| `training/` | LoRA 数据检查、训练、适配器合并、GGUF 转换与量化脚本，以及配置示例 |
| `deploy/` | llama.cpp 与应用服务配置、启动脚本、桌面及全屏浏览器自启模板 |
| `benchmarks/` | 自编测试题与性能评测说明 |
| `tests/` | 后端、模型接口、数据处理、训练入口和前端的自动检查 |
| `docs/` | 部署、接口、训练、第三方资源和验证范围等详细文档 |
| `models/` | 模型使用说明与模型清单模板，不附带权重 |
| `data/` | 数据目录使用说明；真实数据与运行记录按配置存放，默认不提交 |
| `.github/workflows/` | GitHub Actions 自动检查配置 |
| `.env.example` | 本地配置模板，包括模型路径、服务地址及摄像头参数 |
| `.gitignore` | 排除本地凭据、模型、数据和运行产物等文件 |
| `requirements.txt` | 基础 Python 依赖说明 |
| `requirements-vision.txt` | OCR 与摄像头相关依赖 |
| `start.sh` | 应用启动脚本 |
| `LICENSE` | 本仓库新编写代码的 MIT 许可证 |
| `ROADMAP.md` | 后续开发与验证计划 |

## 主要代码文件

| 文件 | 负责的功能 |
| --- | --- |
| `backend/app.py` | 提供页面与问答接口，处理拍照、识别、提问和流式响应 |
| `backend/config.py` | 读取模型、应用和摄像头配置 |
| `backend/prompts.py` | 定义四步讲解的提示词与回答要求 |
| `backend/services/llm_service.py` | 对接 llama.cpp 的聊天接口，处理流式输出、状态及计时信息 |
| `backend/services/ocr_service.py` | 封装摄像头采集、图像处理和 PaddleOCR 文字识别 |
| `frontend/index.html` | 页面结构 |
| `frontend/static/app.js` | 页面交互、接口请求及流式解答显示 |
| `frontend/static/style.css` | 页面样式 |
| `scripts/serve_model.py` | 根据本地配置启动 `llama-server`，加载实际 GGUF 文件 |
| `scripts/prepare_dataset.py` | 调用配置的 API，将英文样本翻译并改写为中文四步讲解候选数据 |
| `scripts/export_reviewed.py` | 导出人工确认的数据，去重并划分训练集与验证集 |
| `scripts/benchmark.py` | 采集实际模型回答、耗时和模型文件标识等评测记录 |
| `training/check_dataset.py` | 检查训练数据格式与训练集、验证集的重复情况 |
| `training/train_lora.py` | 校验配置并调用 LLaMA-Factory 执行 LoRA 训练，保存运行记录 |
| `training/merge_lora.py` | 调用 LLaMA-Factory 将 LoRA 适配器与对应基础模型合并导出 |
| `training/quantize_gguf.py` | 调用 llama.cpp 工具完成 GGUF 转换与量化 |

## 模块如何配合

1. **题目输入**：前端接收摄像头照片、上传图片或直接输入的文字题目。
2. **识别与核对**：后端执行 OCR，用户在页面中核对、修改识别结果。
3. **本地推理**：后端结合四步提示词与对话历史，向本机 `llama-server` 发送请求。
4. **解答展示**：前端逐步显示模型输出，支持复制和继续追问。

数据准备与训练属于独立流程：英文数据经 API 翻译、改写后，先人工复核，再导出训练数据；LoRA 训练产出的适配器与基础模型合并，随后转换、量化为 GGUF，供 llama.cpp 加载。数据准备脚本需要联网，不参与终端日常问答流程。

## 相关文档

- [部署与运行说明](docs/deployment.md)
- [后端接口说明](docs/api.md)
- [数据处理与模型训练](docs/training.md)
- [LoRA 训练模块说明](training/README.md)
- [模型清单说明](models/README.md)
- [测试与性能评测](benchmarks/README.md)
- [故障排查](docs/troubleshooting.md)
- [第三方资源与开源说明](docs/resources.md)
- [当前验证范围](docs/verification.md)
- [后续计划](ROADMAP.md)

## 开源范围与验证说明

本仓库代码依据项目需求和既有技术说明，在 AI 辅助下重新实现，包含应用源码、数据处理工具、训练与部署脚本、配置示例及文档；不包含原同学的源码、历史训练权重、外部完整数据集、访问凭据或原始测试日志。

自动检查使用本地模拟服务。实际模型效果、LoRA 训练结果、香橙派硬件与摄像头兼容性需要在对应环境中验证，详见验证范围文档。

新编写的应用代码采用 [MIT 许可证](LICENSE)。第三方软件、基础模型和外部数据集分别遵守各自条款，具体来源与使用方式见第三方资源文档。
