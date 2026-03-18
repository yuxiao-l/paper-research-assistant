# Paper Research Assistant

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue)](https://www.python.org/)
[![Streamlit](https://img.shields.io/badge/UI-Streamlit-red)](https://streamlit.io/)
[![License](https://img.shields.io/badge/License-MIT-green)](LICENSE)

一个面向论文调研场景的单 Agent 助手。输入研究任务后，系统会自动生成检索关键词，检索论文标题与摘要，筛选候选论文，抽取标准信息卡，并生成简要综述与对比表；对于可获取 PDF 的论文，还会进一步解析全文摘录，提升信息提取质量。

## Features

- 自动生成研究任务对应的检索关键词
- 基于 OpenAlex 与 arXiv 检索论文标题、摘要和元信息
- 对候选论文进行启发式排序与 LLM 重排
- 自动抽取标准信息卡
- 自动生成综述与对比表
- 支持解析 PDF 全文摘录，并纳入信息卡与综述生成
- 提供命令行与 Streamlit Web 界面
- 支持 DeepSeek 等 OpenAI 兼容接口

## Tech Stack

- Python
- Streamlit
- OpenAlex API
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
OPENAI_API_KEY=your_api_key
OPENAI_BASE_URL=https://api.deepseek.com/v1
OPENAI_MODEL=deepseek-chat
OPENALEX_EMAIL=your_email@example.com
```

说明：

- `OPENAI_API_KEY` / `OPENAI_BASE_URL` / `OPENAI_MODEL` 支持 OpenAI 兼容接口
- 使用 DeepSeek 时，上面的默认示例可以直接套用
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
- `--no-pdf-full-text`：跳过 PDF 全文解析
- `--no-save`：不保存输出文件

### 4. Run in Web

```bash
streamlit run streamlit_app.py
```

Web 界面支持：

- 配置调研参数
- 查看折叠式调研过程
- 查看综述与对比表
- 查看每篇入选论文的摘要、PDF 全文摘录和标准信息卡

## Output

默认会在 `outputs/<timestamp>/` 下生成：

- `result.json`
- `report.md`

其中 `result.json` 会保留检索结果、入选论文、信息卡、综述，以及 `pdf_url`、`full_text_excerpt` 等字段。

## PDF Full-Text Parsing

当论文提供可访问的 PDF 链接时，系统会：

1. 下载 PDF
2. 解析前若干页文本
3. 提取全文摘录
4. 将摘录纳入信息卡和综述生成

如果某篇论文没有可用 PDF，或 PDF 无法解析，系统不会中断整次调研，而是退回为基于标题和摘要生成对应结果。

## Tests

```bash
python -m unittest discover -s tests
```

`tests/` 目录建议保留。即使测试数量不多，它仍然能帮助他人快速验证项目是否可运行，也更符合 GitHub 上开源项目的基本工程化习惯。

## Notes

- 请不要提交 `.env`
- `outputs/` 为运行产物，建议不要提交到 GitHub
- 如果你使用的是国内可访问的 OpenAI 兼容服务，优先在 `.env` 中配置 `OPENAI_BASE_URL`

## Roadmap

- 支持更多论文检索源
- 支持更稳健的 PDF 结构化解析
- 支持导出 BibTeX / CSV
- 支持更丰富的综述模板

## License

MIT License. See [LICENSE](LICENSE).
