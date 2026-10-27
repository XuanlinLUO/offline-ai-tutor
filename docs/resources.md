# 开源及第三方资源使用清单

这里列出本次实现涉及的组件与用途。未安装、未导入的组件不填写虚构的实际版本。
参赛提交前将实际部署版本、来源、许可义务落实情况补齐，报告与仓库保持一致。

| 资源 | 使用方式 | 当前版本记录 | 许可核对入口 |
|---|---|---|---|
| Python | 标准库 HTTP 服务、JSON、脚本和自动检查 | 检查环境实际版本见验证记录 | https://docs.python.org/3/license.html |
| llama.cpp | 本机 GGUF 推理服务、模型转换和量化 | 实际 commit、启动命令及构建方式待填写 | https://github.com/ggml-org/llama.cpp/blob/master/LICENSE |
| Qwen3 或实际基础模型 | 本地教学问答、LoRA 实验基础 | 实际标签、revision 和摘要待填写 | 以实际模型仓库 LICENSE 为准 |
| PaddleOCR | 文本检测与识别 | 目标设备待填写 | https://github.com/PaddlePaddle/PaddleOCR/blob/main/LICENSE |
| PaddlePaddle | OCR 推理框架 | ARM 包版本待填写 | https://github.com/PaddlePaddle/Paddle/blob/develop/LICENSE |
| OpenCV | 摄像头和图像解码 | 目标设备待填写 | https://github.com/opencv/opencv/blob/4.x/LICENSE |
| NumPy | 图像数组 | 目标设备待填写 | https://github.com/numpy/numpy/blob/main/LICENSE.txt |
| LLaMA-Factory | 可选 LoRA 训练和合并工具 | 实际镜像标签/摘要待填写 | https://github.com/hiyouga/LlamaFactory/blob/main/LICENSE |
| 魔搭社区英文数据集 | 训练准备阶段的上游数据 | 精确数据集、revision、规模待填写 | 实际数据集页面及许可 |
| DS API | 联网翻译和教学表达改写 | 实际 API 模型及处理批次待填写 | 实际使用服务的适用条款 |

自研范围为本仓库的接口组织、模型服务封装、离线页面、四步提示词、数据处理工具和部署文档。
本仓库使用 AI 辅助编写代码和文档，审核与测试情况见验证记录；没有直接打包第三方源代码和权重。
配置示例参考了官方参数文档，参数应按实际环境调整。

各资源的署名、许可证/NOTICE 保留、修改说明、分发限制等按实际版本逐项核对。
API 生成的中文样本仍需检查源数据授权、处理方式和再分发条件。当前完整训练数据默认不公开。
