"""流程定义的数据模型。"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Condition:
    """单条分支条件：检查一个关键词是否存在，或意图是否等于指定值。"""

    keyword: str | None = None
    intent: str | None = None


@dataclass(frozen=True)
class Branch:
    """一条条件分支。"""

    condition: Condition
    target: str


@dataclass(frozen=True)
class Node:
    """路由节点或终点节点。"""

    id: str
    kind: str  # "router" 或 "end"
    branches: tuple[Branch, ...] = ()
    default_target: str | None = None
    department: str | None = None


@dataclass(frozen=True)
class Flow:
    """完整流程定义。"""

    name: str
    keywords: tuple[str, ...]
    intents: tuple[str, ...]
    entry: str
    nodes: dict[str, Node] = field(default_factory=dict)


@dataclass(frozen=True)
class CallerInput:
    """一轮来电输入：关键词集合 + 一个意图。"""

    keywords: frozenset[str]
    intent: str


def condition_holds(cond: Condition, caller_input: CallerInput) -> bool:
    """判断单条分支条件在给定输入下是否成立。"""
    if cond.keyword is not None:
        return cond.keyword in caller_input.keywords
    return caller_input.intent == cond.intent


def next_node(flow: Flow, node_id: str, caller_input: CallerInput) -> str | None:
    """按配置顺序选择第一个成立的分支，全部不成立时走默认分支。"""
    node = flow.nodes[node_id]
    if node.kind != "router":
        return None
    for branch in node.branches:
        if condition_holds(branch.condition, caller_input):
            return branch.target
    return node.default_target
