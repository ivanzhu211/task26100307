# task26100307

对话路由流程分析库（纯 Python，无接口层）。流程定义存放在本地 JSON 文件中，
分析结果在内存中返回，供上层调用。

## 流程定义格式（JSON）

```json
{
  "name": "示例流程",
  "keywords": ["refund", "invoice"],
  "intents": ["complaint", "query"],
  "entry": "start",
  "nodes": [
    {
      "id": "start",
      "type": "router",
      "branches": [
        {"condition": {"keyword": "refund"}, "target": "end_refund"},
        {"condition": {"intent": "complaint"}, "target": "end_complaint"}
      ],
      "default": "end_general"
    },
    {"id": "end_refund", "type": "end", "department": "refunds"},
    {"id": "end_complaint", "type": "end", "department": "complaints"},
    {"id": "end_general", "type": "end", "department": "general"}
  ]
}
```

- `keywords` / `intents`：流程声明的关键词词表与意图集合。来电输入 = 词表任意子集 + 一个已声明意图。
- `router` 节点：`branches` 按配置顺序匹配，每条条件只检查一个关键词是否存在或意图是否等于指定值；
  全部不成立时走 `default`。
- `end` 节点：没有出边，`department` 指定目标部门。
- 允许合流、回边及未被入口引用的节点。

## 用法

```python
from router_analysis import load_flow, analyze_flow

flow = load_flow("flow.json")
report = analyze_flow(flow)

report.node_reachable("end_refund")            # 节点是否可达
report.branch_reachable("start", 0)            # 条件分支是否可经过（默认分支索引用 None）
report.reachability.node_witnesses["start"]    # 可达见证：合法输入 + 入口到该处的路径
report.terminates                              # 是否所有合法输入都能到达终点
report.non_termination                         # 不终止见证：输入、进入循环前的路径、一圈闭合循环
```

不可达表示确实不存在能经过该项的合法输入（基于符号条件的完备分析，而非搜索未果）。

## 测试

```bash
python3 -m pytest tests/ -q
```
