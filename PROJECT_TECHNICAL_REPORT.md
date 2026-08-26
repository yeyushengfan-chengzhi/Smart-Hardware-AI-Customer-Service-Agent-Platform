# DIY PC Hardware Agentic Customer Service Platform

## 项目技术报告 / 开发归档 / AI 上下文交接文档

> 原项目名：Smart Hardware AI Customer Service Agent Platform\
> 当前定位：面向 DIY 电脑硬件售前 / 售后的 Agentic Customer Service
> Platform 原型\
> 项目阶段：截至 Phase 7.4\
> 用途：GitHub 项目归档、换机后 ChatGPT/Codex
> 上下文恢复、实习成果展示、简历与面试项目讲解

------------------------------------------------------------------------

# 1. 项目概述

本项目面向 DIY 电脑硬件售前、售后和装机咨询场景，构建融合
**LLM、RAG、Multi-Agent、Tool Calling、规则引擎、Agent Trace、Evaluation
Harness、Knowledge Center 与 Human Handoff** 的智能客服平台原型。

项目并非简单聊天机器人，而是从基础知识库问答逐步演进为具备任务路由、故障诊断、确定性硬件兼容判断、知识资产管理、运行链路追踪、自动化评测和人工客服兜底能力的垂直领域
Agent 应用。

核心演进路线：

``` text
FastAPI + MySQL
→ PDF Knowledge Pipeline
→ RAG + LLM
→ SupervisorAgent
→ KnowledgeAgent / DiagnosisAgent
→ ToolAgent + Tool Calling
→ DIY PC Compatibility Rule Engine
→ Agent Trace + Evaluation Harness
→ Knowledge Center + Agent Management
→ Human Handoff + Ticket Workspace
→ Official Manual Knowledge Expansion
→ RAG Index Consistency Fix
→ Community Experience Layer
```

一句话定位：

> 一个以官方硬件说明书 RAG 为知识依据、以 ToolAgent
> 规则引擎完成确定性兼容判断，并具备 Agent Runtime
> Trace、自动评测、知识管理与人工客服兜底能力的 DIY PC 垂直领域 AI Agent
> 客服平台。

------------------------------------------------------------------------

# 2. 技术栈

## Backend

-   Python / FastAPI
-   SQLAlchemy / PyMySQL / MySQL
-   JWT / bcrypt

## AI & RAG

-   DeepSeek LLM
-   SentenceTransformer
-   BAAI/bge-small-zh-v1.5
-   512 维 Embedding
-   Chroma Vector Database
-   pypdf
-   Query Rewrite
-   Hybrid Retrieval

## Agent

-   SupervisorAgent
-   KnowledgeAgent
-   DiagnosisAgent
-   ToolAgent
-   GeneralAgent
-   Hardware Tools
-   PC Build Compatibility Rule Engine

## Frontend

-   Vue
-   AI Chat
-   Admin Console
-   Knowledge Center
-   Agent Management
-   Agent Trace
-   Evaluation Dashboard
-   Customer Service Workspace

------------------------------------------------------------------------

# 3. 系统架构

``` text
                         User
                           │
                           ▼
                     AI Chat / API
                           │
                           ▼
                    SupervisorAgent
                           │
       ┌───────────────────┼───────────────────┐
       ▼                   ▼                   ▼
DiagnosisAgent       KnowledgeAgent         ToolAgent
       │                   │                   │
故障诊断流程          Query Rewrite        Tool Calling
       │                   ▼                   ▼
       │              RAG Retrieval    Compatibility Engine
       └──────────────┬────┴───────────────────┘
                      ▼
                  Final Answer
                      │
              ┌───────┴────────┐
              ▼                ▼
          Agent Trace      Handoff Decision
                               │
                               ▼
                             Ticket
                               │
                               ▼
                    Customer Service Workspace
```

管理端：

``` text
Admin Console
├── Dashboard
├── Knowledge Center
├── Agent Management
├── Agent Trace
├── Evaluation
└── Customer Service
```

------------------------------------------------------------------------

# 4. 项目核心设计思想

系统没有把所有问题都交给 LLM。

``` text
LLM             → 自然语言理解与回答组织
RAG             → 官方说明书知识依据
SupervisorAgent → 意图识别和任务路由
KnowledgeAgent  → 产品知识问答
DiagnosisAgent  → 故障诊断流程
ToolAgent       → 确定性规格与兼容判断
Trace           → 运行链路追踪
Evaluation      → 自动化回归验证
Ticket          → AI 无法可靠处理时人工兜底
```

核心原则：

> RAG 提供 Evidence，Tool 提供 Decision，LLM 提供 Explanation。

------------------------------------------------------------------------

# 5. Phase 1～3：基础后端与 RAG

完成 FastAPI、MySQL、用户认证、PDF/Markdown 上传、PDF
解析、Chunk、Embedding、Chroma 和 LLM + RAG。

用户表包括 id、username、password_hash、role、created_time，并实现
bcrypt 与 JWT。

RAG
初期真实问题是：用户问"我的主板开机没有显示怎么办"，纯向量检索可能召回主板存放温度、机箱螺柱、BIOS
更新等弱相关内容。

针对该问题逐步完成：

-   PDF 文本清洗；
-   去除页码、URL、无意义数字和特殊符号；
-   按章节进行 Chunk；
-   增加 filename、page_number、section_title、chunk_id metadata；
-   semantic_score + keyword_score 混合检索；
-   Query Rewrite。

最终能够召回"简易侦错 LED"及 CPU、DRAM、GPU、启动设备等相关内容。

Embedding 模型为 BAAI/bge-small-zh-v1.5，维度 512。

------------------------------------------------------------------------

# 6. Phase 3.6：Knowledge Pipeline 工程化

新增 `backend/scripts/process_knowledge.py`，形成：

``` text
扫描文件
→ SHA256
→ 增量判断
→ PDF Parse
→ Chunk
→ Embedding
→ Chroma
→ 更新状态
```

处理过的真实工程问题：

### 6.1 Python 入口错误

直接运行 FastAPI router 导致
`ModuleNotFoundError: No module named 'app'`，最终统一从 backend
根目录执行脚本。

### 6.2 AES PDF

部分 PDF 需要 cryptography 才能由 pypdf 解析，补齐依赖后解决。

### 6.3 HuggingFace 模型加载

使用本地缓存、离线环境变量，后续 Embedding 服务设置
`local_files_only=True`，减少环境不确定性。

### 6.4 MySQL 长 Session 超时

大型 PDF 处理期间一个 DB Session 长时间无操作，出现
`Lost connection to MySQL server during query`。

优化为：

``` text
读取 Document
→ 释放 Session
→ Parse / Embedding / Chroma
→ 新建 Session
→ 更新状态
```

并增加 rollback / retry。

### 6.5 SHA256 增量处理

Hash 相同且状态 completed
的文档直接跳过；只有新文件、文件变化或上次失败才重新处理，避免重复 Chunk
和向量污染。

------------------------------------------------------------------------

# 7. Phase 4：Multi-Agent

## 7.1 SupervisorAgent

负责统一意图路由，支持
hardware_fault、product_info、after_sales、unknown，并识别主板、显卡、内存、电源、机箱等设备。

`POST /api/agent/route`

模糊输入不会强行归类，进入 GeneralAgent。

## 7.2 DiagnosisAgent

负责设备识别、故障类型判断、诊断步骤生成，并结合 RAG 获取说明书依据。

支持
no_display、boot_failure、hardware_error、overheating、installation_error
等故障类型。

一次重要修复是：`/api/agent/route`
已正确识别"我的显卡无法检测怎么办"，但 `/api/agent/diagnosis`
因内部旧关键词规则返回 422。最终取消 Diagnosis API 的重复判断，让
Supervisor 成为唯一 Route Decision Source，DiagnosisAgent
只负责诊断执行。

## 7.3 KnowledgeAgent

负责产品知识问答，并复用已有 RAG。

针对"B850 主板支持 DDR5 吗"这类用户语言与说明书术语不一致的问题，引入
Query Rewrite，将 DDR5、Memory、DIMM、内存规格等领域词扩展后再检索。

## 7.4 ToolAgent

新增 `hardware_spec_tool` 和 `compatibility_check_tool`。

高准确性结构化问题不完全交给 LLM，例如 CPU 与主板兼容判断。

未知型号返回 `unknown`，而不是武断返回 false。

硬件规格从 Python 写死数据逐步抽离为 JSON
数据驱动，实现数据与工具逻辑解耦。

------------------------------------------------------------------------

# 8. Phase 5～6：产品化与 Agent Harness

用户端完成 AI Chat、Loading、错误处理、处理状态和 Human Handoff。

Agent Trace 记录：

-   trace_id
-   query
-   route
-   agent_name
-   tool_name
-   tool_input
-   tool_result
-   latency
-   status
-   handoff

形成：

``` text
User Query
→ Supervisor Route
→ Agent
→ Tool / RAG
→ Final Answer
→ Handoff
```

Evaluation Harness 建立 Evaluation Case / Run / Result，支持 Expected
Route、Actual Route、Agent、Keyword、Pass Rate 和失败结果跳转 Trace。

第一版真实 Evaluation 基线为：

``` text
Total Cases: 55
Passed: 33
Failed: 22
Pass Rate: 60%
```

该数据是早期真实基线，不应包装成最终模型准确率；其价值是证明 Evaluation
能真实暴露 Agent 路由和回答问题。

Knowledge Center 支持文档、Chunk、Embedding 状态、版本、TopK
检索验证和来源元数据。

Agent Management 支持
SupervisorAgent、KnowledgeAgent、DiagnosisAgent、ToolAgent
的状态、Prompt、版本历史、Tool Binding 和 Knowledge Binding 展示。

------------------------------------------------------------------------

# 9. Auth、Handoff 与 Customer Service Workspace

Phase 6.7.1 补齐：

``` text
Register / Login
→ JWT
→ Backend Chat Session
→ AI Chat
→ Handoff
→ Ticket
```

新增 AuthGate、authStore、apiClient、Chat Session 自动创建/恢复，Ticket
自动绑定 user_id、session_id、trace_id。

Phase 6.7.2 / 6.8 增加 user / agent / admin 三类演示角色：

``` text
user  → AI Chat
agent → Customer Service
admin → Admin Console
```

客服可以查看客户问题、AI 回答、Handoff
原因、Session、消息流并发送人工回复。

最终业务闭环：

``` text
User
→ AI Chat
→ Handoff
→ Ticket
→ Human Agent Reply
→ User Re-login
→ Restore Session
→ View Human Reply
```

------------------------------------------------------------------------

# 10. Phase 7.0：DIY PC Compatibility Rule Engine

项目定位从普通硬件售后进一步扩展到 DIY PC 售前装机咨询。

覆盖：

-   CPU ↔ Motherboard Socket
-   Motherboard ↔ Case Form Factor
-   GPU Length ↔ Case Clearance
-   GPU Thickness ↔ Bottom Fan
-   CPU Cooler Height ↔ Case
-   Dual Tower Cooler ↔ RAM
-   PSU Wattage ↔ GPU
-   ATX Case + M-ATX Board 视觉留空提醒

结果：

``` text
yes
warning
no
unknown
```

Warning 类型：

``` text
aesthetic
clearance
power
specification
data_missing
```

重要原则：

> unknown 不等于 no。缺少真实参数时返回 missing_info，不允许 LLM
> 虚构规格。

------------------------------------------------------------------------

# 11. Phase 7.1：Official Manual Seed Dataset

通过 Hermes 半自动整理公开官方硬件说明书，建立：

``` text
data_sources/download_manifest.json
data_sources/manuals/
```

Manifest 保存
vendor、product_name、product_category、document_type、local_file_path、support_url、file_url、original_filename、status、verified、needs_review、notes。

第一阶段：

``` text
Manifest: 31
Downloaded: 19
Needs Review / Skip: 12
```

新增：

-   `backend/scripts/import_manual_seed_dataset.py`
-   `backend/app/services/manual_seed_import_service.py`
-   `POST /api/knowledge/import-manual-seeds`

首次导入：

``` text
19 imported / 12 skipped / 0 failed
```

再次执行：

``` text
0 imported / 31 skipped / 0 failed
```

证明幂等。

官方说明书处理曾达到 18/19 成功，共 3141 chunks；1 份纯图片 PDF
无文本层，保留元数据并标记失败。

同时将部分 MySQL 文本字段升级为 utf8mb4，解决多语言说明书四字节 Unicode
写入失败。

阶段记录：

``` text
Backend: 140 passed, 1 warning
Frontend: 1610 modules transformed
```

------------------------------------------------------------------------

# 12. Phase 7.2：Agent Runtime Harness & Productization Polish

项目表达从"RAG 智能客服"升级为"Agentic Customer Service Platform"。

模块重新明确：

``` text
RAG              = Knowledge Access Layer
ToolAgent        = Deterministic Decision Layer
SupervisorAgent  = Routing Layer
DiagnosisAgent   = Diagnostic Workflow Layer
Agent Trace      = Runtime Observability
Evaluation       = Evaluation Harness
Knowledge Center = Knowledge Asset Management
Ticket           = Human Fallback
Admin Console    = Operations / Management
```

用户端优化发送后清空、失败保留、loading/disabled、防重复提交、Enter
发送、Shift+Enter 换行和示例问题。

项目补充 README、Agent Runtime Harness、Evaluation Harness、Demo
Script、`.env.example`、`.gitignore` 和快速启动脚本。

------------------------------------------------------------------------

# 13. Phase 7.3：Knowledge Expansion Pipeline & Cooling Compatibility Polish

本阶段强化官方知识增量扩展和散热兼容规则。

Manual Seed 去重支持：

-   file_hash
-   file_url
-   support_url
-   original_filename

当 manifest 正在写入造成临时 JSON
解析失败时，返回明确重试提示，不破坏文件。

新增：

`GET /api/knowledge/manual-seed-status`

Knowledge Center 增加 Manual Seed Dataset 统计卡片和导入按钮。

Cooling Compatibility 新增：

-   机箱冷排尺寸支持
-   360 水冷
-   前置冷排影响显卡长度
-   顶部冷排空间风险
-   厚冷排 + 风扇
-   风冷限高
-   双塔风冷与高马甲内存
-   missing_info

相关问题能够进入 ToolAgent，Trace 保存
`pc_build_compatibility_tool`、`tool_input`、`tool_result`。

新增 10 条散热兼容 Evaluation Case。

阶段验收：

``` text
Manifest: 47
Downloaded: 35
Needs Review: 12
Official Docs: 19 → 31
Second Import: 31
Backend: 157 passed, 1 warning
Frontend: 1610 modules
```

后续 Manifest 继续扩充到 62 条，覆盖
DDR4、B760/B660/H610、机箱、水冷、风冷等资料。

最新知识处理记录：

``` text
processed = 54
failed = 5
```

成功示例：

``` text
MSI MAG B760M MORTAR WIFI DDR4  616 chunks
MSI PRO B760M-A WIFI DDR4       569 chunks
MSI PRO H610M-G DDR4            395 chunks
MSI MAG B550M MORTAR WIFI       612 chunks
MSI MAG B650M MORTAR WIFI       603 chunks
JONSBO Z20                       26 chunks
LIAN LI LANCOOL 216              25 chunks
LIAN LI LANCOOL 205M              9 chunks
```

5 个失败文档主要为纯图片或无文本层 PDF。

------------------------------------------------------------------------

# 14. Phase 7.3.1：RAG Index Consistency & Retrieval Fix

这是项目中最值得面试讲解的真实 RAG 工程排障之一。

问题：

``` text
LIAN LI LANCOOL 216 支持多大水冷？
```

Trace：

``` text
route = knowledge
intent = product_info
sources = []
```

但数据实际存在：

``` text
document_id = 35
DB chunks = 25
Chroma vectors = 25
```

最终定位不是"没有向量"，而是 Retrieval Pipeline 一致性问题：

1.  旧混合评分把约 0.61 的相关结果降到约 0.49；
2.  低于 0.60 全局阈值后被过滤；
3.  success / completed 状态兼容不完整；
4.  Chroma metadata 不完整；
5.  产品名匹配不足；
6.  Knowledge Center TopK 与 AI Chat 未完全复用统一 RAG 链路。

修复：

-   success / completed 均可检索；
-   新成功文档统一 completed；
-   vendor / product_name / filename / original_filename 优先匹配；
-   明确产品命中后避免被全局高阈值误杀；
-   增加水冷、冷排、机箱尺寸检索扩展；
-   Knowledge Center TopK 复用统一 RAG 链路；
-   非破坏性补齐 48 个文档、9351 条现有向量 metadata；
-   新增 vector-status 诊断接口；
-   新增 `debug_knowledge_retrieval.py`。

验收：

``` text
LANCOOL 216 Top5 → 全部目标说明书
AI Chat → 正确回答 360 / 280 / 240 mm
Sources → 3 条 LANCOOL 216 来源
Backend → 167 passed
```

没有删除或重建 Chroma，没有清空知识库，也没有重新下载 PDF。

------------------------------------------------------------------------

# 15. Phase 7.4：Community Experience Seed Dataset Integration

在官方说明书之外增加社区经验提示层，但不让社区经验参与官方规格覆盖。

Hermes 整理：

``` text
entries = 26
topics = 10
source_url = 26
needs_review = 4
confidence medium = 24
confidence low = 2
```

文件：

``` text
data_sources/community_experience/community_experience_seed.md
data_sources/community_experience/community_experience_manifest.json
```

每条数据包含
topic、scenario、experience_summary、risk_type、applicable_conditions、confidence、source_url、source_title、source_type、verified、usage_policy。

策略：

``` text
source_type = community_experience
verified = false
usage_policy = 仅作为社区经验提示，不作为官方规格依据
```

Hermes 校验：

``` text
Verification: PASS
OK | entries=26 topics=10 urls=26 review=4 low=2 medium=24
```

新增：

-   `backend/scripts/import_community_experience_seed.py`
-   `backend/app/services/community_experience_import_service.py`
-   `backend/app/services/source_policy.py`

第一次导入：

``` text
total=1 imported=1 skipped=0 failed=0
```

第二次：

``` text
total=1 imported=0 skipped=1 failed=0
```

实际：

``` text
document_id = 55
embedding_status = completed
chunks / vectors = 14 / 14
```

来源优先级：

``` text
ToolAgent Deterministic Result
        ↓
Official Manual Evidence
        ↓
Community Experience Hint
```

社区内容命中时强制提示：

> 社区经验仅作为装机风险提示，不代表官方规格结论。

离线验证：

``` text
7 / 7 社区问法召回 community_experience
```

同时 LANCOOL 216、JONSBO Z20、MSI B760M DDR4 仍准确召回
official_manual_seed。

新增 5 条社区经验 Evaluation Case。

最终阶段记录：

``` text
Backend: 179 passed, 1 warning
Frontend: 1610 modules transformed
```

------------------------------------------------------------------------

# 16. 当前 Layered Knowledge Architecture

``` text
┌───────────────────────────────────┐
│ Deterministic Tool / Rule Engine │
│ Socket / Length / Height / Power │
└─────────────────┬─────────────────┘
                  │ Highest Priority
                  ▼
┌───────────────────────────────────┐
│ Official Manual Knowledge        │
│ Official Manual Seed + RAG       │
└─────────────────┬─────────────────┘
                  │ Supplemental
                  ▼
┌───────────────────────────────────┐
│ Community Experience Layer       │
│ Risk Hint / Practical Experience │
└───────────────────────────────────┘
```

原则：

> Tool 确定性结果不被 RAG
> 覆盖；官方资料不被社区经验覆盖；社区经验只作为风险与体验提示。

------------------------------------------------------------------------

# 17. 关键工程问题总结

面试时比"我用了 RAG/Agent"更值得讲：

1.  PDF Noise 导致 Retrieval Failure → Cleaning + Section Chunk +
    Metadata + Hybrid Retrieval。
2.  用户语言与说明书术语不一致 → Query Rewrite + Domain Expansion。
3.  Supervisor 与 Diagnosis 重复判断 → Supervisor 成为 Single Route
    Decision Source。
4.  大 PDF 处理导致 MySQL Session 超时 → DB Session 与耗时 Pipeline
    解耦。
5.  重复处理污染知识库 → SHA256 Incremental Pipeline。
6.  未知硬件被误判 → unknown + missing_info。
7.  已有 DB Chunk/Vector 却检索不到 → Status + Metadata + Threshold +
    Product Matching + Unified Retriever。
8.  社区经验可靠性 → source_type + confidence + verified +
    usage_policy + source_policy + disclaimer。

------------------------------------------------------------------------

# 18. 测试演进

``` text
Phase 6 初期 Evaluation：55 cases
Backend：106 passed
Phase 6.8：112 passed
Phase 7.1：140 passed
Phase 7.3：157 passed
Phase 7.3.1：167 passed
Phase 7.4：179 passed
```

这些数字表示不同阶段自动化测试通过情况，不是模型准确率。

前端多阶段生产构建均成功，近期记录为：

``` text
1610 modules transformed
```

------------------------------------------------------------------------

# 19. 面试 30 秒介绍

> 我做的是一个面向 DIY 电脑硬件售前售后的 AI Agent
> 客服平台。项目最开始是基于官方说明书的 RAG 问答，后来加入
> SupervisorAgent 做任务路由，并拆分 KnowledgeAgent、DiagnosisAgent 和
> ToolAgent。对于
> CPU、主板、机箱、显卡、散热器这类兼容性问题，我没有完全交给大模型，而是做了结构化规格数据和兼容性规则引擎。工程上还实现了
> Agent Trace、自动 Evaluation、Knowledge Center
> 和人工客服工单闭环。后期我重点处理过新增说明书已经有 DB Chunk 和
> Chroma Vector、但 AI Chat 仍查不到的真实 RAG 一致性问题，对 48
> 个文档、9351 条向量做了非破坏性 metadata
> 修复，并进一步把官方说明书和社区经验设计成分层知识体系。

------------------------------------------------------------------------

# 20. 面试 2 分钟介绍

> 这个项目是我实习期间做的 DIY 电脑硬件智能客服 Agent
> 平台，目标是解决电脑小白在装机兼容、产品参数和售后故障排查中的问题。
>
> 最开始我搭建 FastAPI、MySQL 和用户系统，然后实现 PDF
> 说明书上传、解析、Chunk、Embedding 和 Chroma 检索，形成基础
> RAG。实际测试发现纯向量检索会受到 PDF
> 噪声和用户口语表达影响，所以后来做了文本清洗、章节切片、混合检索和
> Query Rewrite。
>
> 在 RAG 基础上，我用 SupervisorAgent 做统一路由，KnowledgeAgent
> 处理产品知识，DiagnosisAgent 处理故障排查，ToolAgent
> 处理确定性硬件判断。比如 CPU 和主板
> Socket、显卡长度和机箱限长、水冷和显卡空间、电源功率等问题会优先进入规则引擎，而不是让
> LLM 自由生成。
>
> 工程化方面，我做了 Agent Trace 和 Evaluation Harness。Trace 会保存
> Route、Agent、Tool Input/Result、RAG Source、Latency 和
> Handoff；Evaluation 用测试集做回归验证。后台还实现了 Knowledge
> Center、Agent Management 和人工客服 Ticket。
>
> 后期比较有代表性的一个问题是，新导入的 LANCOOL 216 说明书已经有 DB
> Chunk 和 Chroma Vector，但 AI Chat
> 查不到。我最后定位到状态字段、metadata、混合评分阈值和不同检索入口不一致，最终非破坏性修复了
> 48 个文档、9351 条向量 metadata，并统一 Knowledge Center 和 AI Chat
> 检索链路。
>
> 最后又加入社区装机经验层，但没有让社区内容覆盖官方结论，而是设计
> ToolAgent \> Official Manual \> Community Experience
> 的优先级和来源策略。整个项目最后从 RAG Demo
> 演进成一个比较完整的垂直领域 Agentic Customer Service Platform 原型。

------------------------------------------------------------------------

# 21. 常见面试追问

## 为什么 Multi-Agent？

不是为了堆 Agent，而是职责隔离：Supervisor 负责路由，Knowledge
负责知识，Diagnosis 负责诊断，Tool
负责确定性判断，更容易测试、追踪和扩展。

## 为什么兼容性不用纯 RAG？

RAG 能找到资料，但 Socket、长度、功率等本质是结构化条件判断，因此采用
`RAG = Evidence / Tool = Decision / LLM = Explanation`。

## RAG 最难的问题？

Phase 7.3.1。真正的问题涉及 DB、Vector Store、Metadata、Document
Status、Scoring、Threshold、Product Matching
和业务入口的一致性，而不是简单调 TopK。

## 如何降低幻觉？

ToolAgent 确定性判断、unknown +
missing_info、官方说明书优先、Sources、Community
Disclaimer、无法可靠判断时 Human Handoff。

## Evaluation 怎么做？

Evaluation Case 定义 Question、Expected Route、Expected Agent、Expected
Keyword/Result；运行后保存实际结果，失败可以跳 Trace 定位。

------------------------------------------------------------------------

# 22. 简历项目描述

**DIY 电脑硬件智能客服 Agent 平台**

基于 FastAPI、MySQL、Vue、LLM、RAG、Chroma 和 Multi-Agent 架构开发面向
DIY 电脑硬件售前售后的 AI 客服平台。设计
SupervisorAgent、KnowledgeAgent、DiagnosisAgent、ToolAgent，实现知识问答、故障诊断和任务路由；基于结构化硬件数据开发
PC 装机兼容性规则引擎，覆盖
CPU/主板、显卡/机箱、散热器/内存、电源功率等典型场景。构建官方说明书
Knowledge Expansion Pipeline、Agent Trace、Evaluation Harness、Knowledge
Center 与 Human Handoff 工单闭环。针对新增知识无法召回问题，定位并修复
DB 状态、Chroma metadata、检索阈值及业务检索链路一致性问题，非破坏性补齐
48 个文档、9351 条向量 metadata。项目后端自动化测试最终达到 179 passed。

------------------------------------------------------------------------

# 23. GitHub 展示建议

建议将本文件放到：

``` text
docs/PROJECT_TECHNICAL_REPORT.md
```

README 第一屏重点展示：

1.  项目一句话定位；
2.  Architecture Diagram；
3.  Demo Screenshots；
4.  Key Features；
5.  Engineering Highlights；
6.  Quick Start；
7.  Evaluation；
8.  Documentation。

建议文档目录：

``` text
docs/
├── PROJECT_TECHNICAL_REPORT.md
├── AGENT_RUNTIME_HARNESS.md
├── EVALUATION_HARNESS.md
├── KNOWLEDGE_EXPANSION_PIPELINE.md
├── COMMUNITY_EXPERIENCE_DATASET.md
└── DEMO_SCRIPT.md
```

大量官方 PDF 不建议直接提交 GitHub，优先提交 manifest、来源
URL、数据结构说明和导入脚本，并确认授权与仓库体积。

------------------------------------------------------------------------

# 24. 换电脑后的 AI / Codex 上下文恢复

本文件同时承担"项目记忆快照"。

新电脑上可以直接告诉 ChatGPT / Codex：

> 请先阅读 `docs/PROJECT_TECHNICAL_REPORT.md`、README
> 和仓库实际代码。该文档记录了项目截至 Phase 7.4
> 的架构、历史问题、技术决策、测试数据和当前状态。后续开发以仓库实际实现为准，不要重新设计已经完成的模块。

推荐给 Codex 的规则：

``` text
1. 修改前先检查已有实现，不重复创建模块。
2. 保持 Supervisor / Knowledge / Diagnosis / ToolAgent 职责边界。
3. ToolAgent 确定性结果优先于 RAG。
4. official_manual_seed 优先于 community_experience。
5. community_experience 只能作为经验提示。
6. unknown 不得自动解释为 incompatible。
7. 修改 Retrieval 时同时检查 Knowledge Center、AI Chat、Trace。
8. 新功能补充 Evaluation Case 和自动化测试。
9. 不破坏现有 Chroma / MySQL 数据。
10. 完成后同步更新项目文档。
```

------------------------------------------------------------------------

# 25. 卖旧电脑前必须额外备份

GitHub 不能替代完整迁移。尤其注意 `.gitignore` 中的本地数据。

建议额外保存：

-   `.env`（私人离线备份，绝对不要公开上传 GitHub）
-   MySQL 数据库 dump
-   Chroma / vector_store
-   `uploads/knowledge`
-   未提交的官方 PDF / manifest
-   Conda 环境信息
-   Python requirements
-   frontend `package-lock.json`
-   必要时保存本地 Embedding 模型缓存

建议导出：

``` text
conda env export > environment.yml
pip freeze > requirements-lock.txt
```

MySQL 也应在卖电脑前完成 dump。

如果 `.env` 中包含 DeepSeek/API Key、数据库密码或 JWT Secret，必须确认
Git 历史中没有提交这些秘密。

------------------------------------------------------------------------

# 26. 当前状态快照

截至 Phase 7.4：

``` text
SupervisorAgent              完成
KnowledgeAgent               完成
DiagnosisAgent               完成
ToolAgent                    完成
PDF / Chunk / Embedding      完成
Chroma RAG                   完成
Query Rewrite                完成
Hybrid Retrieval             完成
PC Compatibility Engine      完成
Cooling Compatibility        完成
Official Manual Seed         完成
Incremental Import           完成
Knowledge Center             完成
Community Experience Layer   完成
Source Policy                完成
Agent Trace                  完成
Evaluation Harness           完成
Agent Management             完成
Human Handoff                完成
Customer Service Workspace   完成
```

最新重要记录：

``` text
Backend Tests: 179 passed, 1 warning
Frontend Build: success / 1610 modules transformed
Community Dataset: 26 entries / 10 topics
Community Vector: 14 / 14
RAG Metadata Repair: 48 documents / 9351 vectors
```

------------------------------------------------------------------------

# 27. 当前限制

1.  纯图片 PDF 尚未接 OCR Pipeline；
2.  部分硬件规格仍需人工结构化；
3.  兼容规则无法覆盖所有机箱内部结构；
4.  Community Experience 数据量仍较小；
5.  没有实时电商价格 / 库存；
6.  没有 WebSocket 实时客服推送；
7.  暂未实现完整多租户；
8.  RBAC 可继续加强；
9.  Evaluation 仍需持续扩展真实用户问题；
10. 前端主 Chunk 存在 \>500kB 构建提示；
11. Agent 配置尚未实现完整运行时热更新。

------------------------------------------------------------------------

# 28. 后续最值得继续做的方向

求职展示优先级建议：

### P0：GitHub 展示

README 重构、架构图、关键页面截图、Demo GIF/Video、Quick
Start、敏感信息清理。

### P1：Evaluation 报告

基于现有 Evaluation Case 真正计算 Route Accuracy、Tool Selection
Accuracy、Retrieval Hit Rate 和 Failure
Categories。只有真实跑出数据后再写百分比。

### P2：OCR

为纯图片 PDF 增加 OCR fallback。

### P3：Structured Spec Extraction

从官方规格页/PDF 半自动抽取 Socket、Form Factor、GPU Clearance、Cooler
Height、Radiator Support、PSU Recommendation，经审核后进入 Tool 数据。

### P4：Source-aware Retrieval

让 Retriever 显式支持
official_only、official_plus_community、tool_first。

------------------------------------------------------------------------

# 29. 最终总结

> 本项目从一个基础硬件说明书 RAG 问答系统，逐步演进为融合
> Multi-Agent、Tool Calling、DIY PC 兼容性规则引擎、分层知识体系、Agent
> Runtime Trace、Evaluation Harness 与 Human Handoff 的垂直领域 AI
> 客服平台原型。

项目最重要的工程边界：

``` text
Supervisor 负责路由
Knowledge 负责知识
Diagnosis 负责诊断
Tool 负责确定性判断
RAG 提供依据
Official Manual 是主要事实来源
Community Experience 只是经验提示
Trace 负责解释运行过程
Evaluation 负责验证行为
Ticket 负责人工兜底
```

后续不应为了"更 Agent"而把所有逻辑重新交给 LLM，也不应为了"更
RAG"而把确定性硬件规则改成纯文本检索。

项目当前最有价值的特点是：

> **让 LLM、RAG、Tool、Rule Engine、Trace、Evaluation 和 Human Agent
> 各自承担适合自己的职责，并通过统一工程链路形成可解释、可测试、可维护的
> Agentic Application。**
