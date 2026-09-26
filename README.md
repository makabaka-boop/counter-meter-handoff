# 冷库机械累计表 · 绝对计数轨迹恢复

冷库货位的机械累计表只保留固定模数 `modulus` 内的读数。跨零回绕（甚至连续
多圈）或漏抄后，直接把两次读数相减会把**正常耗用**误记成**倒退**。本服务
根据相邻抄表位置的步长约束，恢复唯一可复算的绝对计数序列。

## 数学模型

设第 `i` 个位置的绝对计数为 `A[i]`（非负、单调不减），抄表读数为
`r[i] = A[i] mod m`，每步增量 `d[i] = A[i+1] - A[i]`。

- 已知读数：`A[i] ≡ readings[i] (mod m)`，首项 `A[0] = readings[0]`（空仓库
  起步，首项回绕次数为 0）；
- 未知读数（`null`）：余数与回绕次数都自由；
- 步长约束：`minStep[i] <= d[i] <= maxStep[i]`。

相邻已知点 a→b（读数 r_a、r_b）之间的总增量必为

```
S = m·q + (r_b - r_a),  q 为非负整数（本段累计回绕数）
```

故每个已知段对 `q` 给出一个整数区间
`[ceil((smin-(r_b-r_a))/m), floor((smax-(r_b-r_a))/m)]`。

求解两级目标：

1. **先最小化最终绝对计数** `A[-1]`（等价于最小化终点回绕次数）：对各已知点
   的回绕次数做一次 O(n) 的前向区间传播；
2. **再取完整序列字典序最小者**：后向传播得到每个已知点允许的回绕区间后，
   从左到右贪心——每一步在“仍能延伸出可行后缀”的前提下取最小增量。剩余边
   的可行总增量是连续整数区间，因此每次选择只需常数次大整数取整运算。

**实现从不枚举绝对计数值或其上界**：`modulus` 可取任意大整数，复杂度只与
读数项数 `n` 有关（O(n) 次区间运算）。

无解时返回 `INCONSISTENT` 及**最早无法延伸的位置**（最小的 `p`，使得位置
`0..p` 不存在任何合法前缀赋值）。

## API

`POST /trajectory`

```json
{
  "modulus": 10,
  "readings": [8, null, 2],
  "minStep": [0, 0],
  "maxStep": [6, 6]
}
```

约束（违反返回 **422**）：

- `modulus`：正整数；
- `readings`：2–300 项，首尾必须已知，已知值满足 `0 <= v < modulus`，其余为
  `null`；仅接受整数/`null`（拒绝浮点、字符串、布尔）；
- `minStep`、`maxStep`：长度均为 `len(readings)-1`，逐项满足
  `0 <= minStep <= maxStep <= 2*modulus`；
- 未知字段一律拒绝。

成功（HTTP 200）：

```json
{
  "status": "OK",
  "absolute": [8, 8, 12],
  "increments": [0, 4],
  "cumulativeWraps": [0, 0, 1]
}
```

无解（HTTP 200）：

```json
{ "status": "INCONSISTENT", "position": 1 }
```

另有 `GET /health`。

## 运行

Docker Compose（Python 3.12 镜像）：

```bash
docker compose up --build
# curl -s localhost:8000/health
```

本地：

```bash
pip install -r requirements.txt
uvicorn app.main:app --reload
pytest -q
```

## 测试

- `tests/test_solver.py`：短序列穷举增量对拍（约 18 万个确定性小实例，穷举
  所有合法增量组合求两级最优）、随机对拍、连续回绕、多个空洞、并列解取字典
  序、最早不可延伸位置、大模数（10⁶⁰）与 300 项性能；
- `tests/test_api.py`：422 校验矩阵、成功/无解响应形态。
