# 使用 GitHub Desktop 发布

仓库已经按公开展示的标准排除了密钥、依赖、构建产物、上传文件、PDF 说明书和向量数据库。

## 发布步骤

1. 打开 GitHub Desktop，选择 **File → Add local repository**。
2. 选择本项目根目录：`Smart Hardware AI Customer Service Agent Platform`。
3. 确认当前分支是 `main`，并能看到本地初始提交。
4. 点击 **Publish repository**。
5. 推荐仓库名：`smart-hardware-ai-agent-platform`。
6. 用于面试展示时，取消勾选 **Keep this code private**；如果暂不想公开则保留勾选，检查完远程页面后再改为 Public。
7. 发布后打开 GitHub 仓库页面，确认 README、`backend`、`frontend`、`docs` 和 `data_sources` 均可见，而 `backend/.env`、`node_modules`、`uploads`、`vector_store`、`manuals` 和 `tmp` 不可见。

## 建议填写的仓库信息

- Description：`A local-first AI customer service agent platform for PC hardware support, featuring RAG, diagnosis, compatibility tools, human handoff, traces, and evaluation.`
- Topics：`ai-agent`、`rag`、`fastapi`、`vue3`、`chromadb`、`customer-service`、`hardware`

发布后不要在网页端上传 `backend/.env` 或本地数据备份。完整的新电脑迁移步骤见 [NEW_COMPUTER_SETUP.md](NEW_COMPUTER_SETUP.md)。
