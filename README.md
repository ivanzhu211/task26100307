# task26100307

## flowroute：对话路由流程分析库

纯 Python 库，无接口层。流程定义存放在本地 JSON 文件，分析结果在内存中返回。

### 流程 JSON 格式

```json
{
  "name": "demo",
  "keywords": ["refund", "invoice"],
  "intents": ["complaint", "query"],
  "entry": "start",
  "nodes": [
    {
      "id": "start",
      "type": "router",
      "branches": [
        {"condition": {"keyword": "refund"}, "target": "dept_refund"},
        {"condition": {"intent": "complaint"}, "target": "dept_complaint"}
      ],
      "default": "dept_general"
    },
    {"id": "dept_refund", "type": "terminal", "department": "退款部"}
  ]
}
```

- 路由节点按配置顺序评估条件分支，全部不成立时走 `default`；即使多条
  条件同时成立也只走第一条。
- 条件二选一：`{"keyword": "..."}`（关键词存在）或 `{"intent": "..."}`
  （意图等于指定值）。
- 终点节点 `"type": "terminal"`，无出边，携带 `department`。
- 允许合流、回边与未被入口引用的节点。

### 使用

```python
from flowroute import analyze, load_flow, simulate

flow = load_flow("flow.json")
result = analyze(flow)

result.nodes                     # {节点 id: ItemReport}
result.condition_branches        # {(节点 id, 分支序号): ItemReport}
result.default_branches          # {节点 id: ItemReport}
result.non_termination           # NonTerminationWitness 或 None
```

- 每个 `ItemReport` 标明可达性；可达时附带见证（一份合法输入 + 从入口
  出发的路径）。不可达表示确实不存在这样的输入。
- `non_termination` 非空时，包含可复现的来电输入、进入循环前的路径
  （`prefix`）与一圈闭合循环（`cycle`）；用 `simulate(flow, witness.
  caller_input)` 可复现该诊断。
- 分析基于符号路径约束的完备搜索：输入固定时走路是确定性的，能到达
  某处的输入必然经由不重复节点的简单路径到达，因此沿简单路径搜索
  即可覆盖全部合法输入。

### 测试

```bash
python3 -m pytest tests/ -q
```
