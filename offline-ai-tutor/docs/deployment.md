# 部署说明

## 运行环境

基础服务使用 Python 3.10+ 标准库，没有 Flask 依赖。这是本次重新实现版本的技术选择，
参赛报告应与实际提交的版本保持一致。电脑可以先测试文字输入和本地模型接口，
摄像头与 OCR 则需在目标设备上核验。

服务只监听 `127.0.0.1` 或 `localhost`，当前版本不提供跨设备访问或公网托管。
Ollama 也必须位于本机 HTTP 地址。

## 文字问答

1. 安装 Python 和 Ollama。
2. 下载实际模型，执行 `ollama list` 确认标签。
3. 复制 `.env.example` 为 `.env`，设置 `OLLAMA_MODEL`。
4. 运行 `python3 -m backend.app`，访问 `http://127.0.0.1:5000`。
5. 测试固定文字题，再断开公网重试，确认不依赖云端资源。

`OLLAMA_THINK=auto` 保持模型默认；如果实际模型支持关闭思考输出，可设置为 `false`。
不支持该选项时按实际模型文档调整。过长思考可能消耗生成上限，导致没有可见回答。

## 图像依赖

建议使用隔离环境安装依赖：

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-vision.txt
```

PaddlePaddle 需要另行安装与操作系统、Python 版本和 ARM 架构兼容的发行包。
不要将 x86 wheel 当作 ARM wheel。先确认包能导入，再测试 PaddleOCR。
依赖范围文件不是目标硬件的已验证锁定文件；硬件通过测试后保存实际版本清单。

OCR 模型首次使用可能自动下载。请提前完成首次识别，并在断网后再次识别同一张图片，
确认缓存可用。运行时禁用了文档方向校正和展平子模型，减少额外模型依赖；
倾斜图片应由用户先拍正。

输入图片最多 5 MiB，限制 PNG/JPEG，长边超过 2000 像素时缩小后识别。
记录分辨率，评测时不要混用不同缩放配置。当前未提供专门数学公式 OCR。

## 摄像头

`.env` 的 `CAMERA_DEVICE=11` 是来自需求说明的初始值，不保证在所有板卡上成立。
先用 `v4l2-ctl --list-devices` 和系统工具确认实际采集节点、输出格式与设备权限。
`CAMERA_WARMUP=20` 控制丢弃的预热帧数；实际效果与曝光收敛需现场比较。

OCR 的线程数默认 4，可设置为 1～4。这是保守的初始部署限制，
并不是对所有版本均存在“超过 4 线程必然崩溃”的结论。

## 开机启动

以下示例假设项目放在 `~/offline-ai-tutor`，且桌面为 X11/XFCE。不同桌面需调整。

```bash
mkdir -p ~/.config/systemd/user ~/.config/autostart ~/.local/bin
cp deploy/ai-tutor.service ~/.config/systemd/user/
cp deploy/ai-tutor-browser.desktop ~/.config/autostart/
cp deploy/ai-tutor-kiosk.sh ~/.local/bin/
chmod +x start.sh ~/.local/bin/ai-tutor-kiosk.sh
systemctl --user daemon-reload
systemctl --user enable --now ai-tutor.service
systemctl --user status ai-tutor.service
```

如需用户未登录时启动后端，可按机器管理策略配置 `loginctl enable-linger 用户名`。
这只解决用户服务启动，不会自动创建图形桌面会话。全屏浏览器仍依赖桌面登录；
无人值守终端应另行配置合适的自动登录策略并测试。Ollama 服务也应单独配置启动。

脚本默认打开 5000 端口；修改后端端口时，同时修改浏览器脚本的默认地址或设置 `TUTOR_URL`。
脚本保留正常退出方式，不关闭浏览器沙箱。

## 模型与版本快照

```bash
python3 --version
python3 -m pip freeze
ollama --version
ollama list
ollama show 实际模型标签
```

记录板卡准确型号、SoC、内存、系统镜像、内核、模型摘要及配置。以实机输出为准，
不要直接复制说明文档中的硬件规格和性能结果。
