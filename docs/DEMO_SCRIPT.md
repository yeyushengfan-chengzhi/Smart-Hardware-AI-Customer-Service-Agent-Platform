# Phase 7.2 Demo Script

建议演示时长：8–10 分钟。

## 演示前检查

1. 确认 MySQL 已启动，`backend/.env` 的连接参数正确。
2. 确认 `LLM_API_KEY` 已配置；否则知识问答会明确提示 API Key 未配置。
3. 分别运行 `start_backend.bat` 和 `start_frontend.bat`。
4. 打开 `http://127.0.0.1:8000/health`，确认返回 `{"status":"ok"}`。
5. 打开 `http://localhost:5173`，确认登录页可见。

## 1. 用户端 AI Chat（3 分钟）

1. 点击“普通用户登录”，进入 AI Chat。
2. 介绍首页项目名称与副标题，以及故障诊断、产品知识、兼容性三种能力。
3. 点击示例问题“B850 主板支持 DDR5 吗？”，确认问题自动填入输入框。
4. 点击“发送问题”，指出按钮进入禁用和 loading 状态，避免重复请求。
5. 回答出现后，确认输入框自动清空。
6. 展示回答正文、Agent 类型、来源文档、是否建议转人工；有 `trace_id` 时展示“查看 Trace”。
7. 再点击“TUF GAMING B850M-PLUS WIFI 的 Debug LED 是什么意思？”并发送，确认第二次发送后输入框仍自动清空。

## 2. 错误与空状态（1 分钟）

1. 新建空会话，确认出现 5 个示例问题。
2. 对没有引用来源的回答，确认显示“暂无可展示来源”。
3. 说明系统会分别提示：后端未启动、登录失效、API Key 未配置、请求超时。
4. 不输入内容时，发送按钮应保持禁用。

## 3. Knowledge Center 与 Trace（2 分钟）

1. 退出普通用户，点击“管理员登录”。
2. 进入 Knowledge Center，展示官方说明书列表、产品信息、Chunk 数量和 Embedding 状态。
3. 打开一份说明书，展示文档详情与 Chunk。
4. 使用 Knowledge Center 的检索验证输入一个 B850 问题，查看 Top 5 结果。
5. 进入 Agent Trace，打开刚才的请求，展示 Supervisor 路由、Agent、来源、耗时和状态。

## 4. Ticket 人工接管（2 分钟）

1. 切回普通用户，发送“转人工”，系统创建人工工单。
2. 退出后点击“客服账号登录”，进入 Customer Service。
3. 若列表为空，应显示“暂无工单”；有工单时打开刚创建的工单。
4. 展示完整聊天上下文、转人工原因和关联 Trace。
5. 输入客服回复，并将工单更新为“处理中”或“已解决”。
6. 切回普通用户，在原会话中刷新工单状态并查看客服回复。

## 5. Evaluation 与收尾（1 分钟）

1. 使用管理员账号进入 Evaluation。
2. 展示路由准确率、RAG 命中、工具准确率和失败用例。
3. 回到 Dashboard，总结系统已形成“用户提问 → Agent 路由 → RAG / Tool → Trace → Evaluation → Ticket”的闭环。

## 验收清单

- [ ] 前端 `npm run build` 成功
- [ ] 后端 `python -m pytest -q` 通过
- [ ] 连续发送两条问题，两次成功后输入框均清空
- [ ] 5 个示例问题均可填入输入框
- [ ] Knowledge Center 可加载和检索
- [ ] Ticket 可创建、查看、回复和更新状态
- [ ] Trace 列表与详情可打开
