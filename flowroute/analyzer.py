"""流程诊断：可达性分析与终止性分析。"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from .model import (
    AnalysisResult,
    CallerInput,
    EdgeRef,
    Flow,
    IntentCondition,
    ItemReport,
    KeywordCondition,
    NonTerminationWitness,
    PathStep,
    RouterNode,
    Witness,
)


@dataclass
class _Constraints:
    """一条路径对输入的约束：只有满足约束的输入才会走出这条路径。"""

    must_have: frozenset[str] = frozenset()  # 必须存在的关键词
    must_not_have: frozenset[str] = frozenset()  # 必须不存在的关键词
    intent_eq: Optional[str] = None  # 意图必须等于该值
    intent_ne: frozenset[str] = frozenset()  # 意图不能等于这些值

    def consistent(self, flow: Flow) -> bool:
        if self.must_have & self.must_not_have:
            return False
        if self.intent_eq is not None:
            return self.intent_eq not in self.intent_ne
        return any(i not in self.intent_ne for i in flow.intents)

    def witness_input(self, flow: Flow) -> CallerInput:
        intent = self.intent_eq
        if intent is None:
            intent = next(i for i in flow.intents if i not in self.intent_ne)
        return CallerInput(keywords=frozenset(self.must_have), intent=intent)

    def _with_keyword(self, keyword: str, positive: bool) -> "_Constraints":
        if positive:
            return _Constraints(
                self.must_have | {keyword},
                self.must_not_have,
                self.intent_eq,
                self.intent_ne,
            )
        return _Constraints(
            self.must_have,
            self.must_not_have | {keyword},
            self.intent_eq,
            self.intent_ne,
        )

    def _with_intent(self, intent: str, positive: bool) -> "_Constraints":
        if positive:
            return _Constraints(
                self.must_have, self.must_not_have, intent, self.intent_ne
            )
        return _Constraints(
            self.must_have,
            self.must_not_have,
            self.intent_eq,
            self.intent_ne | {intent},
        )

    def require(self, condition, positive: bool) -> "_Constraints":
        if isinstance(condition, KeywordCondition):
            return self._with_keyword(condition.keyword, positive)
        return self._with_intent(condition.intent, positive)


def analyze(flow: Flow) -> AnalysisResult:
    """对流程做完整诊断，返回每个节点/分支的可达性与不终止见证。"""
    result = AnalysisResult()
    for node_id, node in flow.nodes.items():
        result.nodes[node_id] = ItemReport(reachable=False)
        if isinstance(node, RouterNode):
            for index in range(len(node.branches)):
                result.condition_branches[(node_id, index)] = ItemReport(False)
            result.default_branches[node_id] = ItemReport(False)

    # 从入口出发做符号 DFS。输入固定时每次走路是确定性的，
    # 因此能到达某处的输入必然经由一条不重复节点的简单路径到达，
    # 沿简单路径搜索即可保证完备（不可达 = 确实不存在这样的输入）。
    entry_input = CallerInput(keywords=frozenset(), intent=flow.intents[0])
    result.nodes[flow.entry] = ItemReport(True, Witness(entry_input, []))
    _dfs(flow, flow.entry, _Constraints(), [], {flow.entry}, result)
    return result


def _dfs(flow, node_id, constraints, path, on_path, result) -> None:
    node = flow.nodes[node_id]
    if not isinstance(node, RouterNode):
        return
    negated = constraints
    for index, branch in enumerate(node.branches):
        taken = negated.require(branch.condition, positive=True)
        if taken.consistent(flow):
            edge = EdgeRef(node_id, "condition", index)
            _step(flow, taken, path, on_path, result, edge, branch.target)
        negated = negated.require(branch.condition, positive=False)
    if negated.consistent(flow):
        edge = EdgeRef(node_id, "default")
        _step(flow, negated, path, on_path, result, edge, node.default)


def _step(flow, constraints, path, on_path, result, edge, target) -> None:
    step = PathStep(via=edge, arrive=target)
    new_path = path + [step]
    witness = Witness(constraints.witness_input(flow), new_path)
    if edge.kind == "condition":
        _mark(result.condition_branches[(edge.node_id, edge.index)], witness)
    else:
        _mark(result.default_branches[edge.node_id], witness)
    _mark(result.nodes[target], witness)
    if target in on_path:
        # 发现套索：当前路径上首次出现 target 之前是进入循环的前缀，
        # 之后连同这条闭合边构成一圈可被同一输入持续绕行的循环。
        if result.non_termination is None:
            if target == flow.entry:
                cut = 0
            else:
                cut = next(i for i, s in enumerate(path) if s.arrive == target) + 1
            result.non_termination = NonTerminationWitness(
                caller_input=witness.caller_input,
                prefix=new_path[:cut],
                cycle=new_path[cut:],
            )
        return
    _dfs(flow, target, constraints, new_path, on_path | {target}, result)


def _mark(report: ItemReport, witness: Witness) -> None:
    if not report.reachable:
        report.reachable = True
        report.witness = witness


def simulate(flow: Flow, caller_input: CallerInput, max_steps: int = 10000):
    """模拟一次来电的走路过程，返回 (路径, 终点节点 id 或 None)。

    终点为 None 表示在 max_steps 步内未到达终点（进入了循环）。
    """
    path: list[PathStep] = []
    current = flow.entry
    for _ in range(max_steps):
        node = flow.nodes[current]
        if not isinstance(node, RouterNode):
            return path, current
        target, edge = _select(node, caller_input)
        step = PathStep(via=edge, arrive=target)
        path.append(step)
        current = target
    return path, None


def _select(node: RouterNode, caller_input: CallerInput):
    for index, branch in enumerate(node.branches):
        if _holds(branch.condition, caller_input):
            return branch.target, EdgeRef(node.id, "condition", index)
    return node.default, EdgeRef(node.id, "default")


def _holds(condition, caller_input: CallerInput) -> bool:
    if isinstance(condition, KeywordCondition):
        return condition.keyword in caller_input.keywords
    return caller_input.intent == condition.intent
