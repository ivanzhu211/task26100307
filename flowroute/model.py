"""数据模型：流程定义与分析结果。"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, Union


@dataclass(frozen=True)
class KeywordCondition:
    """检查某个关键词是否存在。"""

    keyword: str


@dataclass(frozen=True)
class IntentCondition:
    """检查意图是否等于指定值。"""

    intent: str


Condition = Union[KeywordCondition, IntentCondition]


@dataclass(frozen=True)
class Branch:
    """一条条件分支：条件成立时转向 target。"""

    condition: Condition
    target: str


@dataclass
class RouterNode:
    """路由节点：按顺序评估条件分支，全部不成立时走默认分支。"""

    id: str
    branches: list[Branch] = field(default_factory=list)
    default: str = ""


@dataclass
class TerminalNode:
    """终点节点：无出边，指定目标部门。"""

    id: str
    department: str = ""


Node = Union[RouterNode, TerminalNode]


@dataclass
class Flow:
    """一个完整的路由流程。"""

    name: str
    keywords: list[str]
    intents: list[str]
    entry: str
    nodes: dict[str, Node]


@dataclass(frozen=True)
class CallerInput:
    """一轮来电的输入：已提取的关键词集合 + 一个意图。"""

    keywords: frozenset[str]
    intent: str


@dataclass(frozen=True)
class EdgeRef:
    """对一条出边的引用：条件分支（带序号）或默认分支。"""

    node_id: str
    kind: str  # "condition" 或 "default"
    index: Optional[int] = None  # kind 为 "condition" 时的分支序号


@dataclass(frozen=True)
class PathStep:
    """路径上的一步：经过某条边到达某个节点。"""

    via: EdgeRef
    arrive: str


@dataclass
class Witness:
    """可达性见证：一份合法输入 + 从入口出发的路径。"""

    caller_input: CallerInput
    path: list[PathStep]


@dataclass
class ItemReport:
    """单个分析对象（节点 / 条件分支 / 默认分支）的诊断。"""

    reachable: bool
    witness: Optional[Witness] = None


@dataclass
class NonTerminationWitness:
    """不终止见证：输入、进入循环前的路径、一圈闭合循环。"""

    caller_input: CallerInput
    prefix: list[PathStep]
    cycle: list[PathStep]


@dataclass
class AnalysisResult:
    """完整分析结果。"""

    nodes: dict[str, ItemReport] = field(default_factory=dict)
    condition_branches: dict[tuple[str, int], ItemReport] = field(default_factory=dict)
    default_branches: dict[str, ItemReport] = field(default_factory=dict)
    non_termination: Optional[NonTerminationWitness] = None
