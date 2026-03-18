from __future__ import annotations

import streamlit as st

from paper_research_assistant.agent import run_research
from paper_research_assistant.errors import ResearchAssistantError
from paper_research_assistant.models import ResearchProgress


st.set_page_config(page_title="Paper Research Assistant", page_icon="⭐", layout="wide")


def _init_state() -> None:
    st.session_state.setdefault("is_running", False)
    st.session_state.setdefault("run_requested", False)
    st.session_state.setdefault("progress_messages", [])
    st.session_state.setdefault("last_result", None)
    st.session_state.setdefault("last_paths", None)
    st.session_state.setdefault("last_error", None)


def _request_run() -> None:
    st.session_state.is_running = True
    st.session_state.run_requested = True
    st.session_state.progress_messages = []
    st.session_state.last_error = None


def render_overview(overview: str) -> None:
    st.subheader("调研综述")
    st.info(overview)


def render_selected_papers(result) -> None:
    st.subheader("入选论文")
    if not result.selected:
        st.info("暂无入选论文。")
        return

    cards_by_title = {card.title: card for card in result.cards}

    for index, paper in enumerate(result.selected, start=1):
        card = cards_by_title.get(paper.title)
        with st.expander(f"{index}. {paper.title}", expanded=index == 1):
            st.write(f"**年份**: {paper.year or 'N/A'}")
            st.write(f"**来源**: {paper.source}")
            st.write(f"**Venue**: {paper.venue or 'N/A'}")
            st.write(f"**得分**: {paper.score:.3f}")
            st.write(f"**入选理由**: {paper.reason}")
            if paper.url:
                st.write(f"**论文链接**: {paper.url}")
            if paper.pdf_url:
                st.write(f"**PDF 链接**: {paper.pdf_url}")
            st.write("**摘要**")
            st.write(paper.abstract)

            if card is not None:
                st.divider()
                st.write(f"**证据范围**: {card.evidence_scope}")
                st.write(f"**相关性**: {card.relevance}")
                st.write(f"**研究问题**: {card.problem}")
                st.write(f"**方法**: {card.method}")
                st.write(f"**数据/场景**: {card.data_or_setting}")
                st.write(f"**主要发现**: {card.findings}")
                st.write(f"**局限性**: {card.limitations}")
                st.write(f"**标签**: {', '.join(card.tags)}")


def render_progress(progress_messages: list[str]) -> None:
    with st.expander("调研过程", expanded=False):
        if not progress_messages:
            st.write("点击“开始调研”后会在这里显示过程。")
        for message in progress_messages:
            st.write(f"- {message}")


_init_state()

st.title("论文调研助手")
st.caption("输入研究任务后，自动生成关键词、检索论文、解析 PDF 全文、抽取信息卡并生成综述。")

controls_disabled = st.session_state.is_running

with st.sidebar:
    st.header("调研参数")
    task = st.text_area(
        "研究任务",
        value="面向代码生成的多 Agent 协作方法综述",
        height=140,
        key="task",
        disabled=controls_disabled,
    )
    top_n = st.slider("入选论文数 N", min_value=1, max_value=10, value=5, key="top_n", disabled=controls_disabled)
    max_keywords = st.slider(
        "最多生成关键词数",
        min_value=1,
        max_value=12,
        value=8,
        key="max_keywords",
        disabled=controls_disabled,
    )
    per_keyword = st.slider(
        "每个检索源检索论文数",
        min_value=3,
        max_value=15,
        value=8,
        key="per_keyword",
        disabled=controls_disabled,
    )
    overview_words = st.slider(
        "综述字数",
        min_value=100,
        max_value=10000,
        value=300,
        step=50,
        key="overview_words",
        disabled=controls_disabled,
    )
    parse_pdf_full_text = st.checkbox(
        "解析 PDF 全文",
        value=True,
        key="parse_pdf_full_text",
        disabled=controls_disabled,
    )
    save_output = st.checkbox(
        "保存 JSON / Markdown 结果",
        value=True,
        key="save_output",
        disabled=controls_disabled,
    )
    st.button(
        "开始调研",
        type="primary",
        disabled=controls_disabled,
        on_click=_request_run,
    )

progress_panel = st.empty()
if st.session_state.is_running or st.session_state.progress_messages:
    with progress_panel.container():
        render_progress(st.session_state.progress_messages)


if st.session_state.run_requested:
    task_value = st.session_state.task.strip()
    if not task_value:
        st.session_state.last_result = None
        st.session_state.last_paths = None
        st.session_state.last_error = "请先输入研究任务。"
        st.session_state.is_running = False
        st.session_state.run_requested = False
        st.rerun()

    def on_progress(progress: ResearchProgress) -> None:
        st.session_state.progress_messages.append(progress.message)
        progress_panel.empty()
        with progress_panel.container():
            render_progress(st.session_state.progress_messages)

    try:
        result, paths = run_research(
            task=task_value,
            top_n=st.session_state.top_n,
            per_keyword=st.session_state.per_keyword,
            max_keywords=st.session_state.max_keywords,
            overview_words=st.session_state.overview_words,
            parse_pdf_full_text=st.session_state.parse_pdf_full_text,
            save_output=st.session_state.save_output,
            progress_callback=on_progress,
        )
    except ResearchAssistantError as exc:
        st.session_state.last_result = None
        st.session_state.last_paths = None
        st.session_state.last_error = str(exc)
    else:
        st.session_state.last_result = result
        st.session_state.last_paths = paths
        st.session_state.last_error = None
    finally:
        st.session_state.is_running = False
        st.session_state.run_requested = False
        st.rerun()


if st.session_state.last_error:
    st.toast(st.session_state.last_error, icon="❌")
    st.error(st.session_state.last_error)


if st.session_state.last_result is not None:
    result = st.session_state.last_result
    paths = st.session_state.last_paths

    st.success("调研完成。")
    st.subheader("检索关键词")
    st.write(result.keywords)
    render_overview(result.overview)

    st.subheader("对比表")
    st.markdown(result.comparison_table)

    render_selected_papers(result)

    if paths:
        st.subheader("结果文件")
        st.write(f"JSON: {paths[0]}")
        st.write(f"Markdown: {paths[1]}")
