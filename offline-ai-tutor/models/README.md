# 模型文件

本目录不包含模型权重。请将 Ollama 实际安装的标签填入 `.env` 的 `OLLAMA_MODEL`。

基础模型、LoRA 适配器、合并模型和量化模型分别记录来源及哈希。参考
`manifest.example.json` 建立本地 `manifest.json`；该文件默认被 Git 忽略。
如需公开核验信息，可另建不含本机私有路径的清单提交。

把模型改名为 `teaching-lora` 不会改变其权重，也不能证明已经加载 LoRA。
实际接入步骤见 [模型训练和部署](../docs/training.md)。
