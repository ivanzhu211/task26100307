"""对话路由流程分析的自动化测试。"""

import json

import pytest

from router_analysis import analyze_flow, load_flow, parse_flow
from router_analysis.model import next_node


def make_flow(data: dict):
    return parse_flow(data)


def simulate(flow, caller_input, max_steps=100):
    """按确定性规则模拟，返回节点序列；检测到环时停止。"""
    path = [flow.entry]
    current = flow.entry
    for _ in range(max_steps):
        if flow.nodes[current].kind == "end":
            return path
        nxt = next_node(flow, current, caller_input)
        path.append(nxt)
        if nxt in path[:-1]:
            return path
        current = nxt
    raise AssertionError("模拟超过步数上限")


def assert_witness_valid(flow, witness, expected_last):
    """见证必须可复现：用见证输入模拟，路径与见证一致且到达目标。"""
    path = simulate(flow, witness.caller_input)
    assert tuple(path[: len(witness.path)]) == witness.path
    assert witness.path[-1] == expected_last


@pytest.fixture
def infeasible_cycle_flow():
    """结构上有环，但回边条件与进入条件互斥，不存在可行循环。"""
    return make_flow(
        {
            "name": "infeasible-cycle",
            "keywords": [],
            "intents": ["vip", "normal"],
            "entry": "start",
            "nodes": [
                {
                    "id": "start",
                    "type": "router",
                    "branches": [
                        {"condition": {"intent": "vip"}, "target": "loop"}
                    ],
                    "default": "end_general",
                },
                {
                    "id": "loop",
                    "type": "router",
                    "branches": [
                        {"condition": {"intent": "normal"}, "target": "loop"}
                    ],
                    "default": "end_vip",
                },
                {"id": "end_general", "type": "end", "department": "general"},
                {"id": "end_vip", "type": "end", "department": "vip"},
            ],
        }
    )


@pytest.fixture
def keyword_combo_loop_flow():
    """仅当关键词 x 与 y 同时出现时会陷入循环。"""
    return make_flow(
        {
            "name": "keyword-combo-loop",
            "keywords": ["x", "y"],
            "intents": ["query"],
            "entry": "start",
            "nodes": [
                {
                    "id": "start",
                    "type": "router",
                    "branches": [
                        {"condition": {"keyword": "x"}, "target": "gate"}
                    ],
                    "default": "end_general",
                },
                {
                    "id": "gate",
                    "type": "router",
                    "branches": [
                        {"condition": {"keyword": "y"}, "target": "spin"}
                    ],
                    "default": "end_x_only",
                },
                {
                    "id": "spin",
                    "type": "router",
                    "branches": [
                        {"condition": {"keyword": "x"}, "target": "spin"}
                    ],
                    "default": "end_escape",
                },
                {"id": "end_general", "type": "end", "department": "general"},
                {"id": "end_x_only", "type": "end", "department": "x_only"},
                {"id": "end_escape", "type": "end", "department": "escape"},
            ],
        }
    )


class TestInfeasibleCycle:
    def test_terminates_despite_structural_cycle(self, infeasible_cycle_flow):
        report = analyze_flow(infeasible_cycle_flow)
        assert report.terminates
        assert report.non_termination is None

    def test_all_reachable_items_have_witnesses(self, infeasible_cycle_flow):
        report = analyze_flow(infeasible_cycle_flow)
        flow = infeasible_cycle_flow
        for node_id in ("start", "loop", "end_general", "end_vip"):
            assert report.node_reachable(node_id)
            witness = report.reachability.node_witnesses[node_id]
            assert_witness_valid(flow, witness, node_id)
        assert report.branch_reachable("start", 0)
        assert report.branch_reachable("start", None)
        assert report.branch_reachable("loop", None)
        for key, witness in report.reachability.branch_witnesses.items():
            assert_witness_valid(flow, witness, witness.path[-1])

    def test_infeasible_back_edge_is_unreachable(self, infeasible_cycle_flow):
        report = analyze_flow(infeasible_cycle_flow)
        assert not report.branch_reachable("loop", 0)


class TestKeywordComboLoop:
    def test_non_termination_witness_reproducible(self, keyword_combo_loop_flow):
        report = analyze_flow(keyword_combo_loop_flow)
        assert not report.terminates
        witness = report.non_termination
        assert witness.caller_input.keywords == frozenset({"x", "y"})
        assert witness.caller_input.intent == "query"
        assert witness.prefix_path == ("start", "gate")
        assert witness.cycle == ("spin",)
        path = simulate(keyword_combo_loop_flow, witness.caller_input)
        assert path[: len(witness.prefix_path)] == list(witness.prefix_path)
        cycle_start = path.index(witness.cycle[0])
        assert path[cycle_start:-1] == list(witness.cycle)
        assert path[-1] == witness.cycle[0]

    def test_other_inputs_terminate(self, keyword_combo_loop_flow):
        flow = keyword_combo_loop_flow
        from router_analysis import CallerInput

        for keywords in (frozenset(), frozenset({"x"}), frozenset({"y"})):
            path = simulate(flow, CallerInput(keywords, "query"))
            assert flow.nodes[path[-1]].kind == "end"


class TestUnreachableNodes:
    def test_unreferenced_node_and_dead_branch(self):
        flow = make_flow(
            {
                "name": "unreachable",
                "keywords": ["k"],
                "intents": ["a", "b"],
                "entry": "start",
                "nodes": [
                    {
                        "id": "start",
                        "type": "router",
                        "branches": [
                            {"condition": {"intent": "a"}, "target": "mid"}
                        ],
                        "default": "end_a",
                    },
                    {
                        "id": "mid",
                        "type": "router",
                        "branches": [
                            {"condition": {"intent": "a"}, "target": "end_b"}
                        ],
                        "default": "end_c",
                    },
                    {"id": "end_a", "type": "end", "department": "a"},
                    {"id": "end_b", "type": "end", "department": "b"},
                    {"id": "end_c", "type": "end", "department": "c"},
                    {"id": "orphan", "type": "end", "department": "orphan"},
                ],
            }
        )
        report = analyze_flow(flow)
        assert not report.node_reachable("orphan")
        assert report.branch_reachable("start", None)
        assert not report.branch_reachable("mid", None)
        assert not report.node_reachable("end_c")
        assert report.node_reachable("end_a")
        assert report.node_reachable("end_b")
        assert report.terminates


class TestBranchOrder:
    def test_first_matching_branch_wins(self):
        flow = make_flow(
            {
                "name": "order",
                "keywords": [],
                "intents": ["a"],
                "entry": "start",
                "nodes": [
                    {
                        "id": "start",
                        "type": "router",
                        "branches": [
                            {"condition": {"intent": "a"}, "target": "end_first"},
                            {"condition": {"intent": "a"}, "target": "end_second"},
                        ],
                        "default": "end_first",
                    },
                    {"id": "end_first", "type": "end", "department": "first"},
                    {"id": "end_second", "type": "end", "department": "second"},
                ],
            }
        )
        report = analyze_flow(flow)
        assert report.branch_reachable("start", 0)
        assert not report.branch_reachable("start", 1)
        assert not report.node_reachable("end_second")


class TestLoader:
    def test_load_flow_from_json_file(self, tmp_path, keyword_combo_loop_flow):
        path = tmp_path / "flow.json"
        data = {
            "name": "keyword-combo-loop",
            "keywords": ["x", "y"],
            "intents": ["query"],
            "entry": "start",
            "nodes": [
                {
                    "id": "start",
                    "type": "router",
                    "branches": [{"condition": {"keyword": "x"}, "target": "gate"}],
                    "default": "end_general",
                },
                {
                    "id": "gate",
                    "type": "router",
                    "branches": [{"condition": {"keyword": "y"}, "target": "spin"}],
                    "default": "end_x_only",
                },
                {
                    "id": "spin",
                    "type": "router",
                    "branches": [{"condition": {"keyword": "x"}, "target": "spin"}],
                    "default": "end_escape",
                },
                {"id": "end_general", "type": "end", "department": "general"},
                {"id": "end_x_only", "type": "end", "department": "x_only"},
                {"id": "end_escape", "type": "end", "department": "escape"},
            ],
        }
        path.write_text(json.dumps(data), encoding="utf-8")
        flow = load_flow(str(path))
        assert flow == keyword_combo_loop_flow
        report = analyze_flow(flow)
        assert not report.terminates
