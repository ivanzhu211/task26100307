"""flowroute 分析库的自动化测试。"""
import json

from flowroute import CallerInput, analyze, load_flow, parse_flow, simulate
from flowroute.model import RouterNode


def make_flow(data):
    return parse_flow(data)


def router(node_id, branches, default):
    return {
        "id": node_id,
        "type": "router",
        "branches": [
            {"condition": cond, "target": target} for cond, target in branches
        ],
        "default": default,
    }


def terminal(node_id, department):
    return {"id": node_id, "type": "terminal", "department": department}


def check_witness(flow, witness, expect_arrive=None):
    """见证必须可复现：用见证输入模拟，路径与分析给出的完全一致。"""
    path, _end = simulate(flow, witness.caller_input)
    assert path[: len(witness.path)] == witness.path
    if expect_arrive is not None:
        assert witness.path[-1].arrive == expect_arrive


def check_all_witnesses(flow, result):
    reports = list(result.nodes.values())
    reports += list(result.condition_branches.values())
    reports += list(result.default_branches.values())
    for report in reports:
        if report.reachable:
            check_witness(flow, report.witness)


class TestStructuralCycleButTerminating:
    """结构上有环 A->B->A，但进入 B 要求关键词 k 存在，
    而 B 回到 A 要求 k 不存在，同一份输入不可能绕行，必须判定为终止。"""

    def build(self):
        return make_flow(
            {
                "name": "structural-cycle",
                "keywords": ["k"],
                "intents": ["query"],
                "entry": "A",
                "nodes": [
                    router("A", [({"keyword": "k"}, "B")], "T"),
                    router("B", [({"keyword": "k"}, "T")], "A"),
                    terminal("T", "general"),
                ],
            }
        )

    def test_terminates(self):
        result = analyze(self.build())
        assert result.non_termination is None

    def test_cycle_edge_unreachable(self):
        """B->A 的默认分支不可达，且这是独立于不终止的诊断。"""
        result = analyze(self.build())
        assert not result.default_branches["B"].reachable
        assert result.default_branches["B"].witness is None

    def test_reachable_items(self):
        flow = self.build()
        result = analyze(flow)
        assert result.nodes["A"].reachable
        assert result.nodes["B"].reachable
        assert result.nodes["T"].reachable
        assert result.condition_branches[("A", 0)].reachable
        assert result.default_branches["A"].reachable
        assert result.condition_branches[("B", 0)].reachable
        check_all_witnesses(flow, result)


class TestKeywordCombinationLoop:
    """只有同时携带 k1 和 k2 的输入才会陷入 A->B->A 循环。"""

    def build(self):
        return make_flow(
            {
                "name": "combo-loop",
                "keywords": ["k1", "k2"],
                "intents": ["query"],
                "entry": "A",
                "nodes": [
                    router("A", [({"keyword": "k1"}, "B")], "T"),
                    router("B", [({"keyword": "k2"}, "A")], "T"),
                    terminal("T", "general"),
                ],
            }
        )

    def test_non_termination_witness(self):
        flow = self.build()
        result = analyze(flow)
        nt = result.non_termination
        assert nt is not None
        # 见证输入必须同时包含 k1 与 k2
        assert nt.caller_input.keywords == frozenset({"k1", "k2"})
        # 前缀从入口出发，循环闭合（回到循环起点）
        assert nt.prefix == []
        assert nt.cycle[0].via.node_id == "A"
        assert nt.cycle[-1].arrive == "A"
        # 用见证输入模拟：先走前缀，随后反复绕行同一圈循环
        path, end = simulate(flow, nt.caller_input, max_steps=20)
        assert end is None
        cycle_len = len(nt.cycle)
        assert path[: len(nt.prefix)] == nt.prefix
        body = path[len(nt.prefix):]
        for lap in range(0, len(body) - cycle_len + 1, cycle_len):
            assert body[lap:lap + cycle_len] == nt.cycle

    def test_other_inputs_terminate(self):
        flow = self.build()
        for keywords in (frozenset(), frozenset({"k1"}), frozenset({"k2"})):
            _path, end = simulate(flow, CallerInput(keywords, "query"))
            assert end == "T"


class TestReachability:
    def test_unreferenced_node_unreachable(self):
        flow = make_flow(
            {
                "name": "orphan",
                "keywords": [],
                "intents": ["query"],
                "entry": "A",
                "nodes": [
                    router("A", [], "T"),
                    terminal("T", "general"),
                    terminal("orphan", "sales"),
                ],
            }
        )
        result = analyze(flow)
        assert not result.nodes["orphan"].reachable
        assert result.nodes["T"].reachable
        assert result.non_termination is None

    def test_first_match_wins(self):
        """多条条件同时成立时只走第一条，后续分支的见证必须排除前者。"""
        flow = make_flow(
            {
                "name": "order",
                "keywords": ["k"],
                "intents": ["complaint", "query"],
                "entry": "A",
                "nodes": [
                    router(
                        "A",
                        [({"keyword": "k"}, "X"), ({"intent": "complaint"}, "Y")],
                        "Z",
                    ),
                    terminal("X", "dept_x"),
                    terminal("Y", "dept_y"),
                    terminal("Z", "dept_z"),
                ],
            }
        )
        result = analyze(flow)
        w1 = result.condition_branches[("A", 0)].witness
        assert "k" in w1.caller_input.keywords
        w2 = result.condition_branches[("A", 1)].witness
        assert w2.caller_input.intent == "complaint"
        assert "k" not in w2.caller_input.keywords
        w3 = result.default_branches["A"].witness
        assert w3.caller_input.keywords == frozenset()
        assert w3.caller_input.intent == "query"
        check_all_witnesses(flow, result)

    def test_intent_exhaustion_makes_branch_unreachable(self):
        """唯一意图被前置条件独占时，后续默认分支不可达。"""
        flow = make_flow(
            {
                "name": "intent-cover",
                "keywords": [],
                "intents": ["complaint"],
                "entry": "A",
                "nodes": [
                    router("A", [({"intent": "complaint"}, "X")], "Y"),
                    terminal("X", "dept_x"),
                    terminal("Y", "dept_y"),
                ],
            }
        )
        result = analyze(flow)
        assert result.condition_branches[("A", 0)].reachable
        assert not result.default_branches["A"].reachable
        assert not result.nodes["Y"].reachable

    def test_merge_and_back_edge(self):
        """合流与回边同时存在时，各环节仍应正确判定。"""
        flow = make_flow(
            {
                "name": "merge",
                "keywords": ["retry"],
                "intents": ["query"],
                "entry": "A",
                "nodes": [
                    router("A", [({"keyword": "retry"}, "B")], "C"),
                    router("B", [], "C"),
                    router("C", [({"keyword": "retry"}, "A")], "T"),
                    terminal("T", "general"),
                ],
            }
        )
        result = analyze(flow)
        assert all(r.reachable for r in result.nodes.values())
        # 输入含 retry 时 A->B->C->A 构成可行循环
        nt = result.non_termination
        assert nt is not None
        assert nt.caller_input.keywords == frozenset({"retry"})
        check_all_witnesses(flow, result)


class TestLoader:
    def test_load_from_json_file(self, tmp_path):
        data = {
            "name": "file-flow",
            "keywords": ["invoice"],
            "intents": ["query"],
            "entry": "start",
            "nodes": [
                router("start", [({"keyword": "invoice"}, "billing")], "general"),
                terminal("billing", "billing_dept"),
                terminal("general", "general_dept"),
            ],
        }
        path = tmp_path / "flow.json"
        path.write_text(json.dumps(data), encoding="utf-8")
        flow = load_flow(str(path))
        assert flow.entry == "start"
        assert isinstance(flow.nodes["start"], RouterNode)
        result = analyze(flow)
        assert result.non_termination is None
        assert all(r.reachable for r in result.nodes.values())
        check_all_witnesses(flow, result)
