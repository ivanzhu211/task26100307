"""从本地 JSON 文件加载流程定义。"""
from __future__ import annotations

import json

from .model import (
    Branch,
    Flow,
    IntentCondition,
    KeywordCondition,
    RouterNode,
    TerminalNode,
)


def load_flow(path: str) -> Flow:
    """读取 JSON 文件并解析为 Flow。"""
    with open(path, "r", encoding="utf-8") as fh:
        return parse_flow(json.load(fh))


def parse_flow(data: dict) -> Flow:
    """把已解析的 JSON 字典转换为 Flow。"""
    nodes = {}
    for raw in data["nodes"]:
        if raw["type"] == "router":
            branches = [
                Branch(condition=_parse_condition(b["condition"]), target=b["target"])
                for b in raw.get("branches", [])
            ]
            nodes[raw["id"]] = RouterNode(
                id=raw["id"], branches=branches, default=raw["default"]
            )
        else:
            nodes[raw["id"]] = TerminalNode(
                id=raw["id"], department=raw.get("department", "")
            )
    return Flow(
        name=data.get("name", ""),
        keywords=list(data.get("keywords", [])),
        intents=list(data.get("intents", [])),
        entry=data["entry"],
        nodes=nodes,
    )


def _parse_condition(raw: dict):
    if "keyword" in raw:
        return KeywordCondition(keyword=raw["keyword"])
    return IntentCondition(intent=raw["intent"])
