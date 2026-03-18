# Quick Start

## 1. 安装依赖

```bash
cd agent
pip install -r requirements.txt
```

## 2. 配置 `.env`

```env
OPENAI_API_KEY=your_api_key
OPENAI_BASE_URL=https://api.deepseek.com/v1
OPENAI_MODEL=deepseek-chat
OPENALEX_EMAIL=your_email@example.com
```

## 3. 命令行运行

```bash
python main.py --task "面向代码生成的多 Agent 协作方法综述"
```

如果你想跳过 PDF 全文解析：

```bash
python main.py --task "面向代码生成的多 Agent 协作方法综述" --no-pdf-full-text
```

## 4. 启动 Web

```bash
streamlit run streamlit_app.py
```

## 5. 结果说明

- Web 页面会展示调研过程、综述、对比表和入选论文详情
- 如果 PDF 可用，会额外展示“PDF 全文摘录”
- 保存结果后，会生成 `outputs/<timestamp>/result.json` 和 `outputs/<timestamp>/report.md`
