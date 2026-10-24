# 数据处理与微调模型接入

这里提供可执行脚本和配置示例，不包含已经训练完成的模型或历史训练证明。
用户曾完成过的实验应另行加入真实配置、训练日志和模型哈希，再关联具体版本。

## 数据准备

从魔搭社区获取数据后，记录精确数据集名称、链接、版本、许可和原始字段。
本仓库不知道此前使用的是哪一个英文数据集，不预填来源和规模。
外部数据放在 `data/raw/`，默认不提交。

`scripts/prepare_dataset.py` 读取英文 JSONL，经用户配置的 DS/OpenAI 兼容 API 生成中文候选问答。
它使用四个讲解字段，输出的每条记录均标记 `accepted: false`，并记录源样本哈希和实际处理时间。
执行这个工具会向配置的服务发送所选题目及参考答案；它不会被终端后端自动执行。

```bash
# 在进程环境设置 REWRITE_API_KEY、REWRITE_API_MODEL；不要把密钥写入代码。
# REWRITE_API_BASE 默认 https://api.deepseek.com，可按实际使用服务设置。
python3 -m scripts.prepare_dataset data/raw/source.jsonl data/processed/candidates.jsonl \
  --source '实际数据集链接和版本' --question-key question --answer-key answer --limit 10
```

请先用少量样本验证服务返回格式。脚本不会覆盖已有输出；失败前保存的记录仍保留。
执行完毕后检查数字、单位、条件、推导和答案，再把真正复核通过的记录设为 `accepted: true`。
保留复核备注及来源记录。

```bash
python3 -m scripts.export_reviewed data/processed/candidates.jsonl data/reviewed
cp training/dataset_info.example.json data/reviewed/dataset_info.json
```

导出脚本按中文题目去重并划分训练/验证集。相似改写、同题翻译和共享题干仍可能泄漏，
应另按原始题目或题目族分组检查；这不是完整的数据去重或教学正确性验证。
`benchmarks/questions.jsonl` 是另行编写的功能测试题，不应加入训练集。

## LoRA 训练

在具备合适 GPU 的 LLaMA-Factory 环境或镜像中运行，不在香橙派上直接执行训练。
保留镜像完整标签/摘要、LLaMA-Factory 版本、GPU、数据版本、随机种子和命令。

本项目现在提供 `training/train_lora.py` 独立启动入口，数据检查、实际训练、
日志与适配器产物记录一起执行。完整说明见 [LoRA 模块](../training/README.md)。

```bash
python -m training.check_dataset --dataset-dir data/reviewed
python -m training.train_lora \
  --base-model /models/Qwen3-4B-Instruct-2507 \
  --dataset-dir data/reviewed \
  --output-dir outputs/qwen3-teaching-lora \
  --rank 8 --alpha 16 --epochs 3 --precision bf16
```

如果希望手动维护配置，也可以修改 `training/lora_sft.example.yaml` 后使用
`llamafactory-cli train training/lora_sft.example.yaml`。底层 LoRA 训练均由框架实现。

配置依据官方 Qwen3 示例整理。示例中的基础模型和 `qwen3_nothink` 模板必须与实际模型匹配，
bf16 也需要硬件支持。不能把该模板参数当作之前实验实际使用的参数。
训练结束后保留 `adapter_config.json`、适配器权重、训练日志、损失曲线和验证结果。

## 合并、量化与导入

使用真实适配器，且基础模型与训练时严格匹配。修改 `training/export_lora.example.yaml` 后运行：

```bash
llamafactory-cli export training/export_lora.example.yaml
```

也可使用封装入口 `python -m training.merge_lora --base-model 实际基础模型目录 --adapter 实际适配器目录`，
自动保存本次配置、实际进程日志和导出产物哈希。
`training/quantize_gguf.py` 则提供转换与量化的 Python 调用入口，具体参数见 LoRA 模块说明。

随后在已安装相应依赖的 llama.cpp 目录中执行实际转换与量化。路径仅为示例：

```bash
python3 convert_hf_to_gguf.py /path/to/merged-model --outfile /path/to/model-f16.gguf --outtype f16
./build/bin/llama-quantize /path/to/model-f16.gguf /path/to/model-q4_k_m.gguf Q4_K_M
```

这些步骤需要足够内存和磁盘，并依赖所用工具版本对实际模型架构的支持。
Q4_K_M 是具体的混合量化格式，不能用它推断所有权重均为相同 INT4 精度。

修改 Modelfile 的 FROM 为真实量化文件路径，导入 Ollama：

```bash
ollama create offline-tutor-lora -f training/Modelfile.example
ollama show offline-tutor-lora
ollama run offline-tutor-lora
```

确认模型对话模板与停止标记正确，能生成正常输出。再把 `.env` 的 `OLLAMA_MODEL` 设为该真实标签，
启动本项目，并通过健康接口核对标签与摘要。保存从适配器、合并文件到 GGUF 的哈希对应关系。

## 效果比较

同一题集、提示词、输出长度上限、采样设置和设备条件下比较基础模型与微调模型。
分别评价答案正确性、步骤正确性、四步结构遵循率、讲解表达及耗时。
若效果下降，也保留真实结果，不填造训练曲线和准确率。

## 官方参考

- [LLaMA-Factory Qwen3 LoRA 示例](https://github.com/hiyouga/LlamaFactory/blob/main/examples/train_lora/qwen3_lora_sft.yaml)
- [LLaMA-Factory](https://github.com/hiyouga/LlamaFactory)
- [llama.cpp 量化工具](https://github.com/ggml-org/llama.cpp/tree/master/tools/quantize)
- [Ollama 模型导入](https://docs.ollama.com/import)
- [DeepSeek Chat Completions](https://api-docs.deepseek.com/api/create-chat-completion/)
