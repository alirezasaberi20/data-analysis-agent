"""LangGraph orchestrator that wires the multi-agent analysis workflow."""

from __future__ import annotations

import operator
from typing import Annotated, TypedDict

from langchain_core.messages import BaseMessage
from langgraph.graph import StateGraph, END

from backend.agents.nodes import (
    planner_node,
    sql_agent_node,
    python_agent_node,
    chart_agent_node,
    insight_agent_node,
)


class AnalysisState(TypedDict):
    messages: Annotated[list[BaseMessage], operator.add]
    plan: str
    schema: str
    context: str
    target_tables: list[str]
    sql_results: list[str]
    analysis_results: str
    python_chart_paths: list[str]
    chart_paths: list[str]
    final_report: str


def _wrap_node(node_fn, name: str):
    """Wrap a node function to handle state merging properly."""
    def wrapper(state: AnalysisState) -> dict:
        result = node_fn(state)
        # Only return the keys that this node produces
        # Messages are handled via the Annotated[..., operator.add] reducer
        output = {}
        for key, value in result.items():
            if key == "messages":
                # For messages, only return the NEW messages (not the full list)
                existing = state.get("messages", [])
                new_msgs = value[len(existing):]
                output["messages"] = new_msgs
            else:
                output[key] = value
        return output
    wrapper.__name__ = name
    return wrapper


def create_analysis_graph() -> StateGraph:
    """Build and compile the multi-agent analysis graph."""

    graph = StateGraph(AnalysisState)

    graph.add_node("planner", _wrap_node(planner_node, "planner"))
    graph.add_node("sql_agent", _wrap_node(sql_agent_node, "sql_agent"))
    graph.add_node("python_agent", _wrap_node(python_agent_node, "python_agent"))
    graph.add_node("chart_agent", _wrap_node(chart_agent_node, "chart_agent"))
    graph.add_node("insight_agent", _wrap_node(insight_agent_node, "insight_agent"))

    graph.set_entry_point("planner")
    graph.add_edge("planner", "sql_agent")
    graph.add_edge("sql_agent", "python_agent")
    graph.add_edge("python_agent", "chart_agent")
    graph.add_edge("chart_agent", "insight_agent")
    graph.add_edge("insight_agent", END)

    return graph.compile()
