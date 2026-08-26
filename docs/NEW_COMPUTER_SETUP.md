# 新电脑迁移与恢复

这份清单把可公开的源码和必须私下迁移的运行数据分开，避免 API Key、数据库和本地文档被上传到 GitHub。

## 卖电脑前

### 1. 发布源码

按照 [GITHUB_DESKTOP_PUBLISH.md](GITHUB_DESKTOP_PUBLISH.md) 将本仓库发布到 GitHub。

### 2. 导出私有本地资产

在 PowerShell 中执行，目标目录必须位于项目外部，例如移动硬盘或私人云盘：

```powershell
.\scripts\export_local_assets.ps1 -Destination "F:\smart-hardware-ai-private-backup"
```

该脚本会复制：

- `backend/.env`：MySQL 密码、JWT Secret、LLM API Key
- `data_sources/manuals`：本地官方 PDF
- `backend/uploads`：已导入文件
- `backend/vector_store`：本地 ChromaDB 数据

这些内容均不应进入公开 GitHub 仓库。

### 3. 导出 MySQL

确保 MySQL 的 `bin` 目录已加入 PATH，然后执行：

```powershell
mysqldump -u root -p --single-transaction --routines --triggers smart_agent > "F:\smart-hardware-ai-private-backup\smart_agent.sql"
```

输入密码时终端不会显示字符，这是正常行为。完成后确认备份目录已同步或已安全拔出移动硬盘，再处理旧电脑。

## 新电脑安装

推荐环境：

- GitHub Desktop
- Python 3.12（安装时勾选 Add Python to PATH）
- Node.js 20 LTS
- MySQL 8.0

在 GitHub Desktop 中 Clone 仓库后，打开项目目录并运行：

```powershell
.\setup_windows.bat
```

脚本会创建 `backend/.venv`、安装 Python 与 Node.js 依赖，并在缺失时生成 `backend/.env`。

## 恢复数据库和私有资产

先创建数据库：

```sql
CREATE DATABASE smart_agent CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

再恢复 SQL：

```powershell
mysql -u root -p smart_agent < "F:\smart-hardware-ai-private-backup\smart_agent.sql"
```

把私有备份中的 `backend/.env`、`data_sources/manuals`、`backend/uploads` 和 `backend/vector_store` 复制回仓库中的相同相对路径。若不恢复旧数据库和向量库，应用仍可启动，但 Knowledge Center、历史会话、工单和既有 RAG 索引不会自动出现。

## 启动与验证

```powershell
.\start_dev.bat
```

然后检查：

- 前端：`http://localhost:5173`
- 后端健康检查：`http://127.0.0.1:8000/health`
- Swagger：`http://127.0.0.1:8000/docs`

最后执行一次构建与测试：

```powershell
cd frontend
npm run build

cd ..\backend
.\.venv\Scripts\python.exe -m pytest -q
```

如果不想继续使用旧的 LLM Key，应在服务商后台撤销旧 Key，并在新电脑的 `backend/.env` 中创建和填写新 Key。
