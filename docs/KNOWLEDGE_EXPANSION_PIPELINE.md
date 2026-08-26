# Knowledge Expansion Pipeline

## 目标与边界

Phase 7.3 把公开官方说明书从“已下载文件”稳定地接入现有 Knowledge Center。该流程不是全站爬虫，而是由 Hermes 以低频、人工约束的方式收集厂商公开资料，再由本项目做本地增量导入和知识处理。

流程不会重新下载 PDF，不会修改 `data_sources/manuals` 中的原始文件，也不会写入或覆盖 `data_sources/download_manifest.json`。

## 数据流

1. Hermes 半自动下载公开的官方 PDF 到 `data_sources/manuals`。
2. `data_sources/download_manifest.json` 记录厂商、产品、分类、来源 URL、本地路径、校验状态和下载状态，用于来源追踪。
3. `backend/scripts/import_manual_seed_dataset.py` 读取 manifest，只复制校验有效且 `status=downloaded` 的新增 PDF 到 `backend/uploads/knowledge`，并写入 `knowledge_documents`。
4. `backend/scripts/process_knowledge.py` 对待处理文档执行 parse、chunk、embedding 和 vectorize。
5. Knowledge Center 的 “Manual Seed Dataset” 卡片通过 `GET /api/knowledge/manual-seed-status` 展示 manifest、导入文档、Embedding 和 Chunk 状态。

## 增量与幂等策略

导入器可以重复运行。每条已下载记录按以下信息查重：

- `file_hash`
- `file_url`
- `support_url`
- `original_filename`

命中任意一项的文档会跳过，不会重复复制 PDF 或创建数据库记录。新文件只有在本地路径存在、文件不少于 1024 字节、扩展名为 `.pdf` 且文件头为 `%PDF-` 时才会被复制。

`needs_review`、`failed` 和 `partial` 状态只计入统计，不会被强制导入。纯图片 PDF 需要 OCR；当前解析流程不处理 OCR。

## 并发读取 manifest

Hermes 可能正在写入 manifest。导入器和状态接口只读取文件快照；如果读取期间 JSON 不完整或暂时不可读，会返回：

```text
download_manifest.json may be updating, please retry later
```

调用方应稍后重试。系统不会尝试修复、截断或覆盖 manifest。

## 使用方式

增量导入：

```powershell
cd backend
python scripts/import_manual_seed_dataset.py
```

处理新导入文档：

```powershell
python scripts/process_knowledge.py
```

管理员接口：

```text
GET  /api/knowledge/manual-seed-status
POST /api/knowledge/import-manual-seeds
```

导入接口只登记文档并复制有效 PDF；解析、切片和向量化仍由知识处理脚本负责，保持现有 RAG 流程向后兼容。
