# 上传到 GitHub

仓库建议名称为 `offline-ai-tutor`。当前代码包没有自动上传到 GitHub。

## 网页上传

1. 登录 GitHub，打开 https://github.com/new 。
2. 填入仓库名称。整理阶段可先选 Private；准备公开时再检查模型、数据和第三方许可范围。
3. 创建仓库，在空仓库中点击 uploading an existing file。
4. 解压代码包，进入 `offline-ai-tutor` 文件夹，上传里面的代码文件和目录。
5. 填写真实提交说明，例如“添加离线教学助手初版代码和部署文档”，完成提交。

不要把整个项目只作为一个 ZIP 文件放到仓库里；让 README、源码和文档可以直接浏览。
网页上传会从此次操作建立提交记录，不会恢复以前不存在的开发记录。

## Git 推送

如果要保留代码包中附带的本地开发提交，可从根目录的 `development-history.bundle`
恢复工作目录；该文件包含本次实际创建的提交，不包含此前同学的历史记录。

```bash
git clone development-history.bundle offline-ai-tutor-git
cd offline-ai-tutor-git
git remote remove origin
git remote add origin https://github.com/你的用户名/offline-ai-tutor.git
git push -u origin main
```

远程仓库应为空，且需要你在自己的电脑上完成 GitHub 身份验证。
推送前确认仓库地址和可见范围。不要把密码、短信验证码、验证器密钥或访问令牌发给协作者。

## 本次提交包含什么

应用代码、四步提示词、可选 OCR/摄像头封装、训练和量化模板、评测工具与部署说明。
它不包含真实微调权重、此前实验日志或目标香橙派的实测结果。
比赛报告中的实际部署模型与测试结果，应在接入真实设备后补齐。
