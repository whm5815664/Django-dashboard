# AIoT农业智能问答系统

## 系统概述

AIoT农业智能问答系统是一个基于Django框架开发的综合性农业知识服务平台，集成了先进的问答系统、知识库增强技术、图像识别和知识图谱抽取等核心功能。系统致力于为农业从业者提供精准、智能的农业知识问答服务，推动农业信息化和智能化发展。


## 技术架构

- **后端框架**：Django + Python
- **AI模型**：DeepSeek-R1, Spark API, TC-MRSN
- **数据处理**：FAISS, SentenceTransformers, LTP
- **前端技术**：HTML5, CSS3, JavaScript, ECharts
- **数据存储**：JSON, 关系型数据库
- **部署方式**：支持本地和云端部署

## 开发团队

**华中农业大学AIoT实验室**

本系统由华中农业大学AIoT实验室开发。


## 系统功能结构
### A. 数据汇聚模块
- **冷库退绿储存数据接口**
  - 对接现有冷库系统 API
  - 采集并存储温湿度、气体浓度（CO₂、O₂、C₂H₄ 等）及图像路径
  - 支持时间序列数据管理

---

### B. 大数据管理模块
- **多源文件管理**
  - 实验室 JPG、文本报告、ZIP 数据集在线预览与下载
- **多数据库集成**
  - MySQL / MongoDB 等数据库切换
  - 统一数据模型（Django Model）与管理界面

---

### C. 智能分析模块
- **柑橘深度学习模型**
  - 集成现有柑橘相关模型
- **贮藏调控分析模型**
  - 面向褪绿与贮藏环境调控分析
- **柑橘 LLM 问答系统**
  - 基于 RAG + Ollama
  - 支持文本与语音问答
  - 支持知识库动态维护

---

### D. 数据可视化模块
- **全国柑橘分布地图**
  - ECharts 中国地图
  - 高德地图卫星视图
- **冷库环境数据图表**
  - 折线图、仪表盘、实时与历史数据
- **知识图谱展示**
  - 实体关系抽取
  - ECharts 关系图
- **语音问答**
  - 语音识别 → LLM → 语音合成

---

### F. 页面与业务模块

#### 主页
- 全国柑橘分布地图
- 冷库入口导航

#### 冷库展示页面
- 冷库列表与详情页
- 环境监测图表
- 卫星地图定位

#### 模型管理页面
- 深度学习模型上传与调用
- 褪绿模型分析页面
- LLM 问答页面（含语音功能）

#### 数据管理页面
- 冷库数据后台管理（统计 + 表格）
- 实验室数据集管理
- 知识图谱管理与展示

---

## 页面逻辑结构

```text
主页（全国柑橘地图）
   ↓ 点击省份
冷库展示页面（冷库列表）
   ├─ 冷库详情页（监测数据 + 图表）
   └─ 工具箱
       ├─ 数据分析模块
       │   ├─ 深度学习模型
       │   ├─ 褪绿模型分析
       │   └─ LLM 问答
       └─ 数据管理模块
           ├─ 冷库数据管理
           ├─ 实验室文件管理
           └─ 知识图谱
```

## 更新日志（2026-02-01 ～ 至今）

### 智能体系统（Agent）与对话体验

- **新增：智能体助手弹窗页**
  - 新增 `aiModels/templates/qaModel/agent.html`，提供客服风格小窗 UI（欢迎语、输入框、发送、加载态）。
  - 支持回车发送、点击遮罩关闭；关闭时通过 `postMessage` 通知父页面隐藏 iframe。
  - 每次打开自动清空界面与上下文：调用 `/aiModels/clear_chat_history` 静默清理历史并重置欢迎信息。

- **新增：大脑智能体（BrainAgent）统一入口 + 流式状态回传**
  - 新增/完善 `aiModels/agent/brain_agent.py`，作为路由中枢，支持在「数据库智能体 / 网页爬虫智能体」之间决策调用。
  - `POST /aiModels/brain` 使用 `StreamingHttpResponse` 以 SSE 形式推送：
    - `type=status`：推送“正在调用：数据库/网页爬虫智能体”
    - `type=result` / `type=error`：推送最终结果/错误信息
  - 前端使用 `fetch + ReadableStream` 解析 `data: {...}` 行，实时更新“思考中”提示并渲染最终答案。

### 数据库智能体（SearchDBAgent）能力增强

- **自然语言自动选表/模型**
  - `aiModels/agent/searchDB_agent.py` 增加意图规则（如：基地/设备/告警/产量/品种/传感器等关键词）自动路由到合适的 Django Model 或原生表。
  - 新增 `auto_query`：输入自然语言问题即可返回匹配意图、命中关键词及查询结果。

- **原生表查询与字段安全**
  - 支持原生表白名单（示例：`sensor_readings1`）查询，且可通过 `SHOW COLUMNS` 获取真实字段并缓存，自动过滤不存在字段。
  - 原生 SQL 执行限制为只读 `SELECT`，并对表名/字段名做基础安全校验。

### 前端集成：主页工具箱接入可拖拽小窗

- **改造：工具箱“智能体助手”入口**
  - `screen/templates/screen/base_map.html` 将原先跳转链接改为按钮，点击后打开 `iframe` 小窗（`/aiModels/agent`）。
  - 支持靠近按钮的自动定位与窗口拖拽（父页面实现拖拽手柄，避免 iframe 吞鼠标事件）。
  - 监听子页面 `agent-close` 消息，统一隐藏小窗与拖拽手柄。

### 后端路由与依赖更新

- **新增路由**
  - `aiModels/views.py` 新增 `agent_view`，用于渲染 `qaModel/agent.html`。
  - `aiModels/urls.py` 新增：
    - `/aiModels/agent`：智能体弹窗页
    - `/aiModels/brain`：智能体统一问答入口（SSE 流式）

- **新增依赖**
  - `requirements.txt` 增加 `beautifulsoup4==4.12.3`（网页爬虫智能体解析 HTML 用）。
  - 新增 `aiModels/agent/spider_agent.py`：支持百度 / DuckDuckGo 搜索、网页抓取与内容提取。

### 数据模型与细节修正

- **修正：设备表名映射**
  - `storageSystem/models.py` 将 `Device.Meta.db_table` 修正为 `devices`（避免与真实表名不一致）。

- **其他**
  - `screen/models.py` 清理少量多余空行（不影响功能）。