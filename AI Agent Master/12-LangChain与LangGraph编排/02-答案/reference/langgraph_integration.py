"""同一邮件流程的真实 LangGraph 写法；安装 frameworks extra 后运行。"""

from __future__ import annotations

from typing import Literal, TypedDict

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt


class State(TypedDict, total=False):
    email: str
    intent: Literal["refund", "question"]
    evidence: list[str]
    draft: str
    approved: bool
    sent: bool


def classify(state: State) -> State:
    return {"intent": "refund" if "退款" in state["email"] else "question"}


def retrieve(state: State) -> State:
    return {"evidence": ["policy:refund-v1" if state["intent"] == "refund" else "faq:general"]}


def draft(state: State) -> State:
    return {"draft": f"根据 {state['evidence'][0]} 回复"}


def review(state: State) -> State:
    if state["intent"] != "refund":
        return {"approved": True}
    decision = interrupt({"action": "refund_review", "draft": state["draft"]})
    return {"approved": bool(decision.get("approved"))}


def send(state: State) -> State:
    # 真实发送必须委托带 operation id 的幂等 ToolExecutor；node 内只表达更新。
    return {"sent": bool(state.get("approved"))}


def route_after_review(state: State) -> str:
    return "send" if state.get("approved") else "end"


def build_graph():
    graph = StateGraph(State)
    graph.add_node("classify", classify)
    graph.add_node("retrieve", retrieve)
    graph.add_node("draft", draft)
    graph.add_node("review", review)
    graph.add_node("send", send)
    graph.add_edge(START, "classify")
    graph.add_edge("classify", "retrieve")
    graph.add_edge("retrieve", "draft")
    graph.add_edge("draft", "review")
    graph.add_conditional_edges("review", route_after_review, {"send": "send", "end": END})
    graph.add_edge("send", END)
    return graph.compile(checkpointer=InMemorySaver())


if __name__ == "__main__":
    app = build_graph()
    print(app.invoke({"email": "普通问题"}, {"configurable": {"thread_id": "demo"}}))

