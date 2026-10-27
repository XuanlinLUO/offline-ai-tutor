# 模型文件

本目录不包含模型权重。将真实 GGUF 文件路径填入 `.env` 的 `LLAMA_MODEL_PATH`，
`LLAMA_MODEL` 设置为服务别名，`LLAMA_SERVER_BIN` 设置为实际 llama-server 可执行文件。

基础模型、LoRA 适配器、合并模型和量化模型分别记录来源及哈希。参考
`manifest.example.json` 建立本地 `manifest.json`；该文件默认被 Git 忽略。
如需公开核验信息，可另建不含本机私有路径的清单提交。

模型别名是接口标识，不是文件校验值。请保存 GGUF 的 SHA-256 与 llama.cpp commit，
并将其对应到实际基础模型和 LoRA 产物。
实际接入步骤见 [模型训练和部署](../docs/training.md)。
