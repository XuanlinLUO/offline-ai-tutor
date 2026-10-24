# 离线智学

面向本地教学终端的拍照问答原型。用户拍照或上传图片，核对 OCR 文字，再由本机
Ollama 模型流式生成中文讲解。回答采用“问题分析、解题步骤、最终答案、知识点讲解”四步结构。

本仓库是根据项目需求和既有说明重新实现的代码，开发使用了 AI 辅助。它不包含原同学的源码、
历史训练权重或原始测试日志。当前检查范围见 [验证记录](docs/verification.md)。


## 连接实际模型

1. 安装并启动 Ollama，准备实际使用的模型；运行 `ollama list` 核对标签。
2. 复制 `.env.example` 为 `.env`，将 `OLLAMA_MODEL` 填成实际标签。
3. 执行 `python3 -m backend.app`，不加 `--demo`。
4. 打开本地页面，先用文字题目测试。确认模型可用后，再安装 OCR/摄像头依赖。

```bash
cp .env.example .env
# 编辑 .env：例如填入你实际安装的基础模型或已导入的微调模型标签
python3 -m backend.app
```

模型标签不会证明模型经历了微调。LoRA 适配器需与对应基础模型合并、量化并实际导入，
或采用经核验兼容的其他加载方式。详见 [训练与模型接入](docs/training.md)。

## 功能

- 摄像头拍照与 PNG/JPEG 图片上传；识别文字可人工修改。
- 本地模型流式输出、四步讲解、复制解答及多轮追问。
- 明确区分模型未就绪、识别失败、生成中、完成和连接中断。
- 实测模型首个可见输出时间、生成用时及生成速度。
- 本地回环监听；不加载 CDN、在线字体或云端问答资源。
- 提供数据改写脚本、LoRA 训练入口、适配器合并、GGUF 量化及部署模板。

训练数据改写脚本是独立的联网准备工具；它不在终端运行流程中，也不会被后端自动调用。
首次安装依赖和准备模型可能需要联网，断网运行前应先完整缓存 OCR 与语言模型。

## 目录安排

| 目录 | 用途 |
|---|---|
| `backend/` | HTTP 接口、四步提示词和服务模块 |
| `backend/services/` | Ollama 调用、OCR 和摄像头封装 |
| `frontend/` | 离线可加载的 HTML、CSS、JavaScript |
| `scripts/` | 数据改写、人工复核后导出、真实性能采集 |
| `training/` | 数据检查、LoRA 训练、合并、量化 Python 入口及配置 |
| `deploy/` | 用户服务、桌面自启和全屏浏览器脚本 |
| `benchmarks/` | 自编测试题及测量说明，不包含伪造结果 |
| `docs/` | 部署、接口、数据来源、故障排查和验证记录 |
| `tests/` | 使用本地模拟服务的自动检查 |
| `models/` | 模型清单模板；权重默认不提交 |
| `data/` | 本地原始、候选、复核数据和评测记录，默认不提交 |

## 文档

- [部署到本机或香橙派](docs/deployment.md)
- [接口说明](docs/api.md)
- [数据处理与模型训练](docs/training.md)
- [LoRA 训练模块与直接运行命令](training/README.md)
- [测试和性能评测](benchmarks/README.md)
- [故障排查](docs/troubleshooting.md)
- [开源及第三方资源清单](docs/resources.md)
- [当前验证范围](docs/verification.md)
- [上传到 GitHub](docs/github-upload.md)
- [后续计划](ROADMAP.md)

## 检查代码

```bash
python3 -m unittest discover -s tests -v
python3 -m compileall -q backend scripts training
node --test tests/frontend.test.cjs
```

这些检查使用本地模拟模型及模拟图像服务，不代表教学准确率或香橙派硬件性能。
实际模型质量、摄像头节点、ARM 依赖和开机自启应在目标设备上验证。

## 开源范围

本仓库新编写的应用代码采用 [MIT 许可证](LICENSE)。第三方软件、基础模型、
外部数据集和 API 服务分别遵守各自条款；其来源与使用方式见资源清单。
本仓库不附带模型权重、外部完整数据集或任何访问凭据。
