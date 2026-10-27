# 更新为 llama.cpp 部署

此版本按实际部署要求统一采用 llama.cpp 的 `llama-server` 直接加载 GGUF。
LoRA 训练仍使用 LLaMA-Factory，合并、GGUF 转换和量化工具继续保留。

## 本机更新

1. 保存旧 `.env` 作为私有备份，按新版 `.env.example` 重新填写配置。
2. 设置 `LLAMA_SERVER_BIN`、`LLAMA_MODEL_PATH`、`LLAMA_MODEL` 和 `LLAMA_HOST`。
3. 启动 `python -m scripts.serve_model`，检查 `/health` 与 `/v1/models`。
4. 启动 `python -m backend.app`，完成真实题目测试。
5. 如曾安装自启服务，按部署文档替换用户服务文件并重新加载 systemd。

## GitHub 网页更新

在实际放置项目文件的目录中上传新版文件与子目录，保持层级一致。
如果原仓库根目录里还有一层 `offline-ai-tutor`，这次更新应进入那一层再上传内容，
或另行完整整理根目录；避免重复增加一层同名文件夹。

网页上传只会添加或覆盖文件，不会自动同步本次删除。请删除旧版两个文件：

- `tests/test_ollama.py`：旧接口测试已经由 `tests/test_llama_cpp.py` 替换。
- `training/Modelfile.example`：现改为 GGUF 文件路径和 llama-server 启动配置。

如通过 Git 更新，使用实际差异提交并推送即可。保存真实修改记录。

## 技术材料同步

报告、视频字幕、架构图和资源清单中，部署链路应统一为：
GGUF 模型由 llama.cpp 加载，应用通过本机 HTTP 流式接口调用。
数据准备阶段的远程改写 API 与设备上的离线推理分别说明。
旧版实测数据只有在确认对应引擎、模型文件和配置后才能沿用。

本次代码未执行真实 GGUF 推理、GPU 微调或香橙派硬件测量。
