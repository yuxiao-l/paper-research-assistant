from __future__ import annotations

import json
from typing import Any

from paper_research_assistant.errors import AgentLoopError, LLMResponseError
from paper_research_assistant.models import AgentTraceStep, Paper, ResearchProgress, ResearchState
from paper_research_assistant.tools import ToolContext, ToolDefinition, build_tool_registry


def _report(progress_callback, message: str, current: int | None = None, total: int | None = None) -> None:
    if progress_callback is None:
        return
    progress_callback(ResearchProgress(step="react", message=message, current=current, total=total))


class ReActResearchAgent:
    def __init__(
        self,
        ctx: ToolContext,
        max_iterations: int = 10,
        tools: dict[str, ToolDefinition] | None = None,
    ) -> None:
        self.ctx = ctx
        self.max_iterations = max_iterations
        self.tools = tools or build_tool_registry()

    def run(self, state: ResearchState) -> ResearchState:
        for iteration in range(1, self.max_iterations + 1):
            if state.done:
                break
            action_payload = self._decide_next_action(state, iteration)
            thought = self._stringify(action_payload.get("thought"), fallback="Continue with the most useful next step.")
            action = self._stringify(action_payload.get("action"))
            action_input = action_payload.get("action_input") or {}
            if not isinstance(action_input, dict):
                raise AgentLoopError("ReAct agent returned a non-object action_input.")
            if action not in self.tools:
                raise AgentLoopError(f"ReAct agent selected unknown tool: {action}")

            _report(self.ctx.progress_callback, f"第 {iteration} 轮思考：{thought}", current=iteration, total=self.max_iterations)
            tool = self.tools[action]
            observation = tool.handler(state, action_input, self.ctx)
            state.reasoning_trace.append(
                AgentTraceStep(
                    iteration=iteration,
                    thought=thought,
                    action=action,
                    action_input=action_input,
                    observation=observation,
                )
            )
            _report(self.ctx.progress_callback, f"第 {iteration} 轮执行 `{action}`：{observation}", current=iteration, total=self.max_iterations)

        if not state.done:
            if state.selected or state.candidates:
                observation = self.tools["finish"].handler(state, {}, self.ctx)
                state.reasoning_trace.append(
                    AgentTraceStep(
                        iteration=len(state.reasoning_trace) + 1,
                        thought="Iteration limit reached; finalize with the accumulated evidence.",
                        action="finish",
                        action_input={},
                        observation=observation,
                    )
                )
                _report(self.ctx.progress_callback, "达到最大轮次，已自动收尾。")
            else:
                raise AgentLoopError("ReAct agent reached the maximum iterations without finding usable papers.")
        return state

    def _decide_next_action(self, state: ResearchState, iteration: int) -> dict[str, Any]:
        prompt = self._build_prompt(state, iteration)
        result = self.ctx.llm.json_response(prompt)
        if not isinstance(result, dict):
            raise LLMResponseError("ReAct agent decision must be a JSON object.")
        return result

    def _build_prompt(self, state: ResearchState, iteration: int) -> str:
        tool_specs = [
            {
                "name": tool.name,
                "description": tool.description,
                "input_schema": tool.input_schema,
            }
            for tool in self.tools.values()
        ]
        scratchpad = [step.to_dict() for step in state.reasoning_trace[-4:]]
        prompt = f"""
You are a ReAct-style paper research agent.
At each step, decide the single best next tool to call.
You must reason over the current state and return JSON only.

Output format:
{{
  "thought": "short explanation of the next best step",
  "action": "one tool name from the tool list",
  "action_input": {{}}
}}

Rules:
- Prefer broad search before narrow search.
- Avoid repeating the same query unless you intentionally refine it.
- Use `rank_candidates` before `select_papers` when many papers are available.
- Use `read_papers` after selecting promising papers, especially before writing cards or the final overview.
- Use `build_cards` before `generate_report`.
- Use `finish` only when the evidence is sufficient for a useful answer.
- Never invent paper ids. Use only ids shown in the state summary.
- Stay within {self.max_iterations} total iterations. Current iteration: {iteration}.

Research task:
{state.task}

Tool list:
{json.dumps(tool_specs, ensure_ascii=False)}

Current state summary:
{json.dumps(self._summarize_state(state), ensure_ascii=False)}

Recent scratchpad:
{json.dumps(scratchpad, ensure_ascii=False)}
""".strip()
        return prompt

    def _summarize_state(self, state: ResearchState) -> dict[str, Any]:
        return {
            "keywords": state.keywords,
            "search_history": state.search_history[-8:],
            "candidate_count": len(state.candidates),
            "selected_count": len(state.selected),
            "card_count": len(state.cards),
            "overview_ready": bool(state.overview),
            "comparison_table_ready": bool(state.comparison_table),
            "candidate_preview": [self._paper_snapshot(paper) for paper in state.candidates[:8]],
            "selected_preview": [self._paper_snapshot(paper) for paper in state.selected[:8]],
        }

    @staticmethod
    def _paper_snapshot(paper: Paper) -> dict[str, Any]:
        return {
            "paper_id": paper.paper_id,
            "title": paper.title,
            "year": paper.year,
            "source": paper.source,
            "score": round(paper.score, 4),
            "has_pdf_text": bool(paper.full_text_excerpt),
            "venue": paper.venue,
        }

    @staticmethod
    def _stringify(value: Any, fallback: str = "") -> str:
        if isinstance(value, str) and value.strip():
            return value.strip()
        return fallback
