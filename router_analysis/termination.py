"""终止性分析：是否存在永远到不了终点的合法输入。"""

from __future__ import annotations

from dataclasses import dataclass

from .conditions import (
    Conjunction,
    condition_literal,
    conjunction_satisfiable,
    witness_input,
)
from .model import CallerInput, Flow, next_node


@dataclass(frozen=True)
class NonTerminationWitness:
    """不终止见证：输入、进入循环前的路径、一圈闭合循环。"""

    caller_input: CallerInput
    prefix_path: tuple[str, ...]
    cycle: tuple[str, ...]


def _divergence_conditions(flow: Flow) -> dict[str, list[Conjunction]]:
    """用最大不动点计算每个节点上会导致永不终止的输入条件（DNF）。"""
    top: list[Conjunction] = [Conjunction()]
    current: dict[str, list[Conjunction]] = {
        nid: [] if node.kind == "end" else list(top)
        for nid, node in flow.nodes.items()
    }
    while True:
        updated: dict[str, list[Conjunction]] = {}
        for nid, node in flow.nodes.items():
            if node.kind == "end":
                updated[nid] = []
                continue
            literals = [condition_literal(b.condition) for b in node.branches]
            edges: list[tuple[str, list]] = []
            for idx, branch in enumerate(node.branches):
                guard = [lit.negate() for lit in literals[:idx]] + [literals[idx]]
                edges.append((branch.target, guard))
            edges.append((node.default_target, [lit.negate() for lit in literals]))
            dnf: list[Conjunction] = []
            for target, guard in edges:
                for conj in current[target]:
                    merged = conj
                    for lit in guard:
                        merged = merged.with_literal(lit)
                    if merged not in dnf:
                        dnf.append(merged)
            updated[nid] = dnf
        if all(set(updated[nid]) == set(current[nid]) for nid in flow.nodes):
            return updated
        current = updated


def find_non_termination(flow: Flow) -> NonTerminationWitness | None:
    """若存在永不终止的合法输入，返回可复现见证，否则返回 None。"""
    divergence = _divergence_conditions(flow)
    entry_conj = next(
        (
            conj
            for conj in divergence[flow.entry]
            if conjunction_satisfiable(conj, flow.intents)
        ),
        None,
    )
    if entry_conj is None:
        return None
    caller_input = witness_input(entry_conj, flow.intents)

    path: list[str] = [flow.entry]
    index_by_node = {flow.entry: 0}
    current = flow.entry
    while True:
        nxt = next_node(flow, current, caller_input)
        if nxt in index_by_node:
            start = index_by_node[nxt]
            return NonTerminationWitness(
                caller_input=caller_input,
                prefix_path=tuple(path[:start]),
                cycle=tuple(path[start:]),
            )
        index_by_node[nxt] = len(path)
        path.append(nxt)
        current = nxt
