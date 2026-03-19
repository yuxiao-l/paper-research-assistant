# Paper Research Assistant

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue)](https://www.python.org/)
[![Streamlit](https://img.shields.io/badge/UI-Streamlit-red)](https://streamlit.io/)
[![License](https://img.shields.io/badge/License-MIT-green)](LICENSE)

一个用于论文调研的 Agent 助手。输入研究任务后，系统会自动生成检索关键词，检索论文标题与摘要，筛选候选论文，抽取标准信息卡，并生成简要综述与对比表；对于可获取 PDF 的论文，还会进一步解析PDF，提升信息提取质量。

<img width="1920" height="979" alt="app-preview" src="https://github.com/user-attachments/assets/068335a0-5d11-4734-a591-8b3f84363923" />

## Features

- 自动生成研究任务对应的检索关键词
- 基于 arXiv 检索论文标题、摘要和元信息
- 对候选论文进行启发式排序与 LLM 重排
- 自动抽取标准信息卡
- 自动生成综述与对比表
- 支持下载并解析 PDF
- 提供命令行与 Streamlit Web 界面
- 支持 DeepSeek 等 OpenAI 兼容接口

## Tech Stack

- Python
- Streamlit
- arXiv API
- OpenAI-compatible LLM API
- `pypdf` for PDF text extraction

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
│  ├─ report.py
│  └─ search.py
├─ tests/
├─ main.py
├─ streamlit_app.py
├─ requirements.txt
├─ .env.example
└─ README.md
```

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

- `OPENAI_API_KEY` / `OPENAI_BASE_URL` / `OPENAI_MODEL` 支持 OpenAI 兼容接口
- `OPENALEX_EMAIL` 不是必填，但建议填写

### 3. Run in CLI

```bash
python main.py --task "面向代码生成的多 Agent 协作方法综述"
```

常用参数：

- `--top-n`：最终保留的论文数
- `--per-keyword`：每个关键词检索的论文数
- `--max-keywords`：最多生成的关键词数
- `--overview-words`：综述目标字数
- `--no-pdf-full-text`：跳过 PDF 解析
- `--no-save`：不保存输出文件

### 4. Run in Web

```bash
streamlit run streamlit_app.py
```

Web 界面支持：

- 配置调研参数
- 查看调研过程
- 查看综述与对比表
- 查看每篇入选论文的摘要和信息卡

## Output

默认会在 `outputs/<timestamp>/` 下生成：

- `result.json`
- `report.md`

其中 `result.json` 会保留检索结果、入选论文、信息卡和综述等结果字段。
