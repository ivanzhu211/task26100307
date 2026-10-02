"""从本地 JSON 文件加载流程定义。"""

from __future__ import annotations

import json

from .model import Branch, Condition, Flow, Node


def load_flow(path: str) -> Flow:
    """读取 JSON 文件并解析为 Flow。"""
    with open(path, "r", encoding="utf-8") as fh:
        data = json.load(fh)
    return parse_flow(data)


def parse_flow(data: dict) -> Flow:
    """把已解析的 JSON 字典转换为 Flow。"""
    nodes: dict[str, Node] = {}
    for raw in data["nodes"]:
        kind = raw["type"]
        if kind == "router":
            branches = tuple(
                Branch(
                    condition=Condition(
                        keyword=branch["condition"].get("keyword"),
                        intent=branch["condition"].get("intent"),
                    ),
                    target=branch["target"],
                )
                for branch in raw.get("branches", [])
            )
            nodes[raw["id"]] = Node(
                id=raw["id"],
                kind="router",
                branches=branches,
                default_target=raw["default"],
            )
        else:
            nodes[raw["id"]] = Node(
                id=raw["id"],
                kind="end",
                department=raw["department"],
            )
    return Flow(
        name=data.get("name", ""),
        keywords=tuple(data.get("keywords", [])),
        intents=tuple(data["intents"]),
        entry=data["entry"],
        nodes=nodes,
    )
