"""可达性分析：每个节点、每条条件分支与默认分支是否存在合法输入经过。"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field

from .conditions import (
    Conjunction,
    condition_literal,
    conjunction_satisfiable,
    witness_input,
)
from .model import CallerInput, Flow, next_node


@dataclass(frozen=True)
class Witness:
    """可达见证：一份合法输入与入口到目标的路径。"""

    caller_input: CallerInput
    path: tuple[str, ...]


@dataclass
class ReachabilityResult:
    """各节点与各分支的可达性及见证。

    branch_witnesses 的键为 (节点 id, 分支序号)，默认分支序号为 None。
    不在字典中的节点或分支即不可达。
    """

    node_conditions: dict[str, list[Conjunction]]
    node_witnesses: dict[str, Witness]
    branch_witnesses: dict[tuple[str, int | None], Witness]

    def node_reachable(self, node_id: str) -> bool:
        return node_id in self.node_witnesses

    def branch_reachable(self, node_id: str, index: int | None) -> bool:
        return (node_id, index) in self.branch_witnesses


def _simulate(flow: Flow, caller_input: CallerInput) -> list[str]:
    """从入口按确定性规则模拟，返回经过的节点序列（遇终点或环即停）。"""
    path = [flow.entry]
    seen = {flow.entry}
    current = flow.entry
    while flow.nodes[current].kind == "router":
        nxt = next_node(flow, current, caller_input)
        path.append(nxt)
        if nxt in seen or flow.nodes[nxt].kind != "router":
            break
        seen.add(nxt)
        current = nxt
    return path


def analyze_reachability(flow: Flow) -> ReachabilityResult:
    """计算流程中所有节点与分支的可达性，并为可达项给出见证。"""
    node_dnf: dict[str, list[Conjunction]] = {nid: [] for nid in flow.nodes}
    branch_conj: dict[tuple[str, int | None], Conjunction] = {}
    node_dnf[flow.entry] = [Conjunction()]
    queue: deque[str] = deque([flow.entry])
    in_queue = {flow.entry}
    while queue:
        nid = queue.popleft()
        in_queue.discard(nid)
        node = flow.nodes[nid]
        if node.kind != "router":
            continue
        dnf = node_dnf[nid]
        literals = [condition_literal(b.condition) for b in node.branches]
        edges: list[tuple[int | None, str, list]] = []
        for idx, branch in enumerate(node.branches):
            guard = [lit.negate() for lit in literals[:idx]] + [literals[idx]]
            edges.append((idx, branch.target, guard))
        edges.append((None, node.default_target, [lit.negate() for lit in literals]))
        for idx, target, guard in edges:
            for conj in dnf:
                merged = conj
                for lit in guard:
                    merged = merged.with_literal(lit)
                if not conjunction_satisfiable(merged, flow.intents):
                    continue
                branch_conj.setdefault((nid, idx), merged)
                if merged not in node_dnf[target]:
                    node_dnf[target].append(merged)
                    if target not in in_queue:
                        queue.append(target)
                        in_queue.add(target)

    node_witnesses: dict[str, Witness] = {}
    for nid, dnf in node_dnf.items():
        if not dnf:
            continue
        caller_input = witness_input(dnf[0], flow.intents)
        path = _simulate(flow, caller_input)
        path = path[: path.index(nid) + 1]
        node_witnesses[nid] = Witness(caller_input=caller_input, path=tuple(path))

    branch_witnesses: dict[tuple[str, int | None], Witness] = {}
    for (nid, idx), conj in branch_conj.items():
        node = flow.nodes[nid]
        target = node.default_target if idx is None else node.branches[idx].target
        caller_input = witness_input(conj, flow.intents)
        path = _simulate(flow, caller_input)
        cut = path.index(nid)
        branch_witnesses[(nid, idx)] = Witness(
            caller_input=caller_input, path=tuple(path[: cut + 1] + [target])
        )

    return ReachabilityResult(
        node_conditions=node_dnf,
        node_witnesses=node_witnesses,
        branch_witnesses=branch_witnesses,
    )
