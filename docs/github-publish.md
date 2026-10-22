# GitHub 发布说明

这份说明用于把本地工程推到你自己的 GitHub 仓库。

## 方式一：命令行已有 Git 登录态

在仓库根目录执行：

```bash
git status
git add .
git commit -m "feat: bootstrap autovision demo workflow"
git remote add origin <你的仓库地址>
git push -u origin main
```

如果你的默认分支不是 `main`，把最后一行中的分支名改掉。

## 方式二：使用 GitHub CLI

先确认登录状态：

```bash
gh auth status
```

如果还没登录：

```bash
gh auth login
```

然后在仓库根目录执行：

```bash
git add .
git commit -m "feat: bootstrap autovision demo workflow"
gh repo create <仓库名> --private --source . --remote origin --push
```

如果你想公开仓库，把 `--private` 改成 `--public`。

## 推送前建议确认

- `backend/.env` 是否包含不该上传的本机私密配置
- `backend/storage/` 是否包含不该上传的大文件或测试垃圾
- `frontend/node_modules/` 不要提交
- `backend/.venv/` 不要提交

## 推荐提交内容

- 源代码
- `README.md`
- `docs/demo-quickstart.md`
- `docs/troubleshooting.md`
- `docs/integration-checklist.md`

## 不建议提交的内容

- 本机数据库
- 导出的成片
- 临时调试日志
- 大模型权重
- ComfyUI 本地模型目录
