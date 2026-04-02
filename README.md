# Paper Research Assistant

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue)](https://www.python.org/)
[![Streamlit](https://img.shields.io/badge/UI-Streamlit-red)](https://streamlit.io/)
[![License](https://img.shields.io/badge/License-MIT-green)](LICENSE)

一个面向论文调研场景的 ReAct Agent。用户输入研究任务后，系统不会再按固定顺序执行一条写死的流水线，而是由 LLM 在每一轮根据当前状态自主决定下一步该调用哪个工具，例如生成关键词、搜索 arXiv / OpenAlex、排序候选论文、下载 PDF、抽取信息卡，最后生成综述与对比表。

## What It Is

这个项目的核心目标是把“论文调研”拆成一组可调用工具，再由 ReAct 控制器把这些工具串成动态决策过程。

它适合做的事：

- 根据一个研究问题自动构造检索词
- 在多个学术搜索源中抓取论文元数据
- 对候选论文进行启发式排序和 LLM 重排
- 下载并解析 PDF 作为更强证据
- 为每篇论文生成结构化信息卡
- 基于多篇论文生成中文综述和对比表
- 输出完整的 ReAct 决策轨迹，便于调试和复盘

## Tech Stack

项目的技术栈分成 5 层。

### 1. Runtime / App Layer

- Python 3.10+
- `argparse`：CLI 参数入口
- Streamlit：Web 界面和运行过程展示

### 2. LLM Layer

- `openai>=1.40.0`
- OpenAI-compatible API
- 支持通过 `OPENAI_BASE_URL` 接入兼容服务，例如 OpenAI、DeepSeek 等

LLM 在项目中的职责不是直接“一次性写完整答案”，而是承担两类任务：

- 控制层：在 ReAct 循环中决定下一步调用哪个工具
- 认知层：生成关键词、重排论文、抽取信息卡、撰写综述

### 3. Retrieval Layer

- arXiv API
- OpenAlex API
- `requests`
- `urllib`
- `xml.etree.ElementTree`

其中：

- arXiv 负责补充较新的预印本和 PDF 链接
- OpenAlex 负责更通用的学术检索和引用等元数据

### 4. Document Processing Layer

- `pypdf`

PDF 下载后会抽取全文文本，并截取一段 `full_text_excerpt` 作为后续信息卡和综述生成的证据输入。

### 5. Agent / Orchestration Layer

- 自定义 `ReActResearchAgent`
- 自定义工具注册表 `ToolDefinition`
- 自定义运行时状态 `ResearchState`
- 自定义推理轨迹 `AgentTraceStep`

这层是本项目和普通 RAG 脚本最不一样的部分。它不是固定流程编排，而是“状态驱动 + 工具选择 + 多轮观察”的 Agent 结构。

## ReAct Workflow

项目的核心控制器在 [react_agent.py](/d:/practice/agent/paper_research_assistant/react_agent.py)。

Agent 每一轮都会做三件事：

1. `Thought`
   基于当前任务、已搜索历史、候选论文、已选论文、是否已有 PDF 证据、是否已生成卡片和综述，思考当前最有价值的下一步。

2. `Action`
   从工具列表中选择一个工具，并给出结构化参数。

3. `Observation`
   工具执行后，把结果回写到状态里，并把摘要写入推理轨迹，供下一轮继续决策。

LLM 看到的是一个受约束的状态摘要，而不是整个程序上下文。它返回 JSON，而不是自由文本：

```json
{
  "thought": "Current results are too sparse. I should search arXiv first.",
  "action": "search_arxiv",
  "action_input": {
    "query": "multi-agent code generation planning",
    "limit": 8
  }
}
```

这让 ReAct 循环更稳定，也更容易测试。

### Agent State

运行中的状态保存在 [models.py](/d:/practice/agent/paper_research_assistant/models.py) 的 `ResearchState` 里，主要包括：

- `task`
- `keywords`
- `search_history`
- `candidates`
- `selected`
- `cards`
- `overview`
- `comparison_table`
- `reasoning_trace`
- `done`

### Tool Set

工具定义在 [tools.py](/d:/practice/agent/paper_research_assistant/tools.py)，当前包含：

- `generate_keywords`
- `search_arxiv`
- `search_openalex`
- `rank_candidates`
- `select_papers`
- `read_papers`
- `build_cards`
- `generate_report`
- `finish`

这些工具各自负责具体执行，而不是自己决定何时执行。何时调用它们，由 ReAct 控制器决定。

### Typical Execution Path

一次运行的大致过程：

1. Agent 先生成检索词
2. 根据任务决定先搜 arXiv 或 OpenAlex
3. 如果候选论文较多，先做启发式排序
4. 再让 LLM 对候选论文做精排，选出重点论文
5. 对重点论文下载 PDF 并抽取全文片段
6. 基于标题、摘要和 PDF 证据生成信息卡
7. 生成综述和对比表
8. 触发 `finish`，结束本次研究

和传统固定流程相比，ReAct 版本有几个明显区别：

- 可以根据中间结果自主决定下一步动作
- 可以在多个检索源之间切换
- 可以在“先筛选”还是“先读 PDF”之间做策略判断
- 会保留完整的 thought / action / observation 轨迹

## Project Structure

```text
agent/
├─ paper_research_assistant/
│  ├─ agent.py
│  ├─ cards.py
│  ├─ cli.py
│  ├─ config.py
│  ├─ errors.py
│  ├─ keywords.py
│  ├─ llm.py
│  ├─ models.py
│  ├─ pdf_utils.py
│  ├─ ranking.py
│  ├─ react_agent.py
│  ├─ report.py
│  ├─ search.py
│  └─ tools.py
├─ tests/
├─ main.py
├─ streamlit_app.py
├─ requirements.txt
├─ .env.example
└─ README.md
```

### Core Modules

- [agent.py](/d:/practice/agent/paper_research_assistant/agent.py)
  外部统一入口，负责加载配置、创建 LLM 客户端、启动 ReAct Agent、保存结果。

- [react_agent.py](/d:/practice/agent/paper_research_assistant/react_agent.py)
  ReAct 主循环，负责构造 prompt、解析 action、执行工具、维护推理轨迹。

- [tools.py](/d:/practice/agent/paper_research_assistant/tools.py)
  工具层。把搜索、排序、读 PDF、抽卡、生成综述这些能力封装成可调用工具。

- [search.py](/d:/practice/agent/paper_research_assistant/search.py)
  学术检索层。负责对接 arXiv 和 OpenAlex，并做基础去重。

- [ranking.py](/d:/practice/agent/paper_research_assistant/ranking.py)
  两阶段排序：
  先启发式排序，再让 LLM 做高质量重排。

- [pdf_utils.py](/d:/practice/agent/paper_research_assistant/pdf_utils.py)
  下载并解析 PDF，抽取全文文本片段作为更强证据。

- [cards.py](/d:/practice/agent/paper_research_assistant/cards.py)
  为单篇论文生成结构化信息卡。

- [report.py](/d:/practice/agent/paper_research_assistant/report.py)
  负责生成综述、对比表，并把最终结果落盘为 JSON / Markdown。

## Quick Start

### 1. Install

```bash
pip install -r requirements.txt
```

### 2. Configure `.env`

复制 `.env.example` 为 `.env`，并填写配置：

```env
OPENAI_API_KEY=
OPENAI_BASE_URL=
OPENAI_MODEL=
OPENALEX_EMAIL=
```

说明：

- `OPENAI_API_KEY`：必填，LLM 访问凭证
- `OPENAI_BASE_URL`：可选，接入 OpenAI-compatible 服务时使用
- `OPENAI_MODEL`：可选，默认是 `gpt-4o-mini`
- `OPENALEX_EMAIL`：可选，但建议填写，便于规范访问 OpenAlex

### 3. Run in CLI

```bash
python main.py --task "面向代码生成的多 Agent 协作方法综述"
```

常用参数：

- `--top-n`：最终保留的论文数
- `--per-keyword`：每个检索请求的论文数
- `--max-keywords`：最大关键词数
- `--overview-words`：综述目标长度
- `--no-pdf-full-text`：跳过 PDF 解析
- `--no-save`：不保存输出文件

CLI 会输出：

- 研究任务
- 关键词
- 入选论文
- 对比表
- ReAct 轨迹

### 4. Run in Web

```bash
streamlit run streamlit_app.py
```

Web 界面支持：

- 配置研究任务和调研参数
- 查看运行中的进度消息
- 查看最终综述和对比表
- 查看每篇入选论文的信息卡
- 查看 ReAct 决策轨迹

## Output

默认会在 `outputs/<timestamp>/` 下生成：

- `result.json`
- `report.md`

其中：

- `result.json` 保存结构化结果，便于后续程序处理
- `report.md` 保存适合阅读的研究报告

结果中包含这些核心字段：

- `keywords`
- `candidates`
- `selected`
- `cards`
- `overview`
- `comparison_table`
- `reasoning_trace`

`reasoning_trace` 是这次改造成 ReAct Agent 后新增的重要输出，可用于分析 Agent 每一轮为什么做出某个动作。

## Testing

运行测试：

```bash
python -m unittest discover -s tests -v
```

当前测试覆盖：

- 排序逻辑
- PDF 解析逻辑
- LLM 客户端的基本行为
- 检索错误处理
- ReAct 主循环的基本路径
