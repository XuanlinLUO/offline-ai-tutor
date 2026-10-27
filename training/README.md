# LoRA 微调模块

这里的 Python 脚本是在实际 LLaMA-Factory 环境中运行的训练入口。
数据加载、模型 LoRA 注入、反向传播和优化由 LLaMA-Factory 执行；
本项目负责四步教学数据检查、参数组织、调用、日志保存和产物核对。

| 文件 | 作用 |
|---|---|
| `check_dataset.py` | 检查 Alpaca JSON、四步标题、重复题及训练验证集交叉 |
| `train_lora.py` | 配置并启动实际 LoRA SFT，保存运行记录和适配器哈希 |
| `merge_lora.py` | 调用框架将真实适配器合并到对应基础模型 |
| `quantize_gguf.py` | 调用 llama.cpp 转换 GGUF，并实际执行 Q4_K_M 等量化 |
| `common.py` | 模型/输出检查、文件哈希、框架进程调用与状态记录 |
| `lora_sft.example.yaml` | 可直接手动修改的训练配置示例 |
| `export_lora.example.yaml` | 手动导出配置示例 |
| `dataset_info.example.json` | LLaMA-Factory 数据注册格式 |
| `../scripts/serve_model.py` | 将实际 GGUF 文件交给 llama-server 加载 |
| `sample_candidates.example.jsonl` | 自编的四步回答格式示例，默认未通过人工复核 |

## 运行位置

在你的 LLaMA-Factory 镜像中挂载本仓库、本地基础模型和处理后的数据。
脚本应从仓库根目录运行。先在镜像中确认 `llamafactory-cli` 可用，
GPU、PyTorch、Transformers 和实际模型版本兼容。
不要在香橙派上启动这些训练任务。当前模板面向 Qwen3 Instruct，
实际训练其他模型时需要相应改变模板和参数。

## 数据目录

先使用 `scripts/prepare_dataset.py` 产生中文四步候选数据，人工复核后导出：

```bash
python -m scripts.export_reviewed data/processed/candidates.jsonl data/reviewed
cp training/dataset_info.example.json data/reviewed/dataset_info.json
python -m training.check_dataset --dataset-dir data/reviewed
```

`data/reviewed` 应包含 `train.json`、`validation.json`、`dataset_info.json`。
训练脚本将检查这三个文件，并拒绝训练集/验证集中的完全重复题。
格式检查不代表数学答案正确；人工评阅和题目族去重仍需要独立进行。

## 启动训练

```bash
python -m training.train_lora \
  --base-model /models/Qwen3-4B-Instruct-2507 \
  --dataset-dir data/reviewed \
  --output-dir outputs/qwen3-teaching-lora \
  --rank 8 --alpha 16 --epochs 3 --precision bf16 \
  --environment-reference '实际镜像标签或摘要'
```

可选 `--targets`、`--learning-rate`、`--batch-size`、`--accumulation`、
`--cutoff-len`、`--template` 和 `--seed`。训练显存不够时应调整参数；
bf16 需要 GPU 支持，可按实际环境改为 fp16 或 fp32。
这条训练路径为 LoRA SFT，部署用的 4 位量化在后续独立进行，未默认启用 QLoRA。

加 `--dry-run` 只检查数据、配置和本地基础模型的 config.json，并保存计划，
不会训练、不会写入适配器或生成损失曲线。正式运行需要完整基础模型权重。
已存在内容的输出目录会被拒绝，以免覆盖以前实验。

训练实际执行时，`outputs/runs/` 下会保存：

- `effective_config.yaml`：实际提交给 LLaMA-Factory 的配置。
- `process.log`：框架真实输出，不人工生成训练日志。
- `run_manifest.json`：开始结束时间、数据哈希、状态及输出适配器哈希。

框架训练成功后，适配器目录应有 `adapter_config.json` 和 `adapter_model.safetensors`
或 `adapter_model.bin`。脚本只有在退出码与这些产物检查均通过后才记录 completed；
completed 表示进程及文件检查完成，不代表教学效果已经合格。

## 合并与量化

先按真实训练记录确认基础模型与适配器匹配：

```bash
python -m training.merge_lora \
  --base-model /models/Qwen3-4B-Instruct-2507 \
  --adapter outputs/qwen3-teaching-lora \
  --output-dir outputs/qwen3-teaching-merged

python -m training.quantize_gguf \
  --model-dir outputs/qwen3-teaching-merged \
  --llama-cpp /tools/llama.cpp \
  --output-dir outputs/qwen3-teaching-gguf \
  --quantization Q4_K_M
```

llama.cpp 目录需要已安装转换依赖，并已构建 `build/bin/llama-quantize`。
量化阶段同时保留 f16 和量化文件，请预留足够磁盘与内存。
Q4_K_M 是具体的混合量化格式，不等于所有权重都是相同的 INT4 精度。

最后在应用 `.env` 中填写真实生成的 GGUF 文件和 llama-server 路径：

```dotenv
LLAMA_MODEL_PATH=/absolute/path/to/model-q4_k_m.gguf
LLAMA_SERVER_BIN=/absolute/path/to/llama.cpp/build/bin/llama-server
LLAMA_MODEL=offline-tutor
```

执行 `python -m scripts.serve_model`，由 llama.cpp 直接加载文件，
再执行 `python -m backend.app` 启动应用。部署说明见 `docs/deployment.md`。
本次补齐的是可执行训练流程，没有在当前开发环境执行 GPU 训练、合并或量化。

框架参数会随版本变化。示例参考 [LLaMA-Factory 官方 Qwen3 配置](https://github.com/hiyouga/LlamaFactory/blob/main/examples/train_lora/qwen3_lora_sft.yaml)，
请在实际镜像版本中核对可用参数。
