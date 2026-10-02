"""分析入口：汇总可达性与终止性诊断。"""

from __future__ import annotations

from dataclasses import dataclass

from .model import Flow
from .reachability import ReachabilityResult, analyze_reachability
from .termination import NonTerminationWitness, find_non_termination


@dataclass
class AnalysisReport:
    """一次流程分析的完整诊断结果。"""

    flow_name: str
    reachability: ReachabilityResult
    non_termination: NonTerminationWitness | None

    def node_reachable(self, node_id: str) -> bool:
        return self.reachability.node_reachable(node_id)

    def branch_reachable(self, node_id: str, index: int | None) -> bool:
        return self.reachability.branch_reachable(node_id, index)

    @property
    def terminates(self) -> bool:
        return self.non_termination is None


def analyze_flow(flow: Flow) -> AnalysisReport:
    """对流程做完整分析，结果在内存中返回。"""
    return AnalysisReport(
        flow_name=flow.name,
        reachability=analyze_reachability(flow),
        non_termination=find_non_termination(flow),
    )
