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

### 一次换表交接（可选 `changeover`）

两次抄表之间更换机械累计表时，新表从自己的读数起步，但货位真实累计耗用
不归零。请求可携带至多一次换表交接：

- `position`：旧表最后一次读数所在位置 `h`（`1 <= h <= n-2`，两侧都要有
  边），该位置读数必须已知；同一时点新表开表，**交接动作本身耗用为零**；
- `newModulus`：新表模数（可与旧表不同）；
- `newStart`：同一时点新表开表读数 `s`，满足 `0 <= s < newModulus`。

还原规则：

- 位置 `0..h` 按旧模数还原：`A[i] ≡ readings[i] (mod modulus)`；
- 位置 `h..n-1` 从新表开表读数起算：新表表内计数为
  `A[i] - A[h] + s`，即
  `A[i] - A[h] ≡ readings[i] - s (mod newModulus)`；
- 拼接点不产生增量（`A[h]` 唯一），两段都单调不减；新表“清零”只改变表内
  基线（平移量可为负），**绝不会被记成负耗用**；
- `minStep`/`maxStep` 仍逐段约束真实耗用：边 `i < h` 的上界按旧模数
  （`<= 2*modulus`），边 `i >= h` 按新模数（`<= 2*newModulus`）。

两段各自是同一个单表问题：先各取最小末值（二者之和即最小最终绝对计数），
再各自取字典序最小序列，拼出全局两级最优的**一条**单调绝对计数轨迹。

交接位置、开表读数非法（返回 **422**），或旧段、新段任一不可行（返回
`INCONSISTENT` 与全局最早不可延伸位置：新段局部位置加 `h` 映射）时，
都不产生“只成功一半”的局部轨迹。成功时分别返回两台表各自覆盖区间的
回绕次数 `oldMeterWraps`（长度 `h+1`）与 `newMeterWraps`（长度 `n-h`，
开表位置回绕恒为 0）。

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
- `readings`：2–300 项，首尾必须已知，已知值满足 `0 <= v < modulus`
  （有交接时，交接位置之后按 `newModulus` 校验），其余为 `null`；仅接受
  整数/`null`（拒绝浮点、字符串、布尔）；
- `minStep`、`maxStep`：长度均为 `len(readings)-1`，逐项满足
  `0 <= minStep <= maxStep`，且不超过该边所属表的 `2` 倍模数
  （无交接时即 `<= 2*modulus`；有交接时旧表侧边按 `modulus`、
  新表侧边按 `newModulus`）；
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

带换表交接的请求与成功响应（HTTP 200）：

```json
{
  "modulus": 10,
  "readings": [8, 2, 1],
  "minStep": [0, 0],
  "maxStep": [10, 10],
  "changeover": { "position": 1, "newModulus": 7, "newStart": 5 }
}
```

```json
{
  "status": "OK",
  "absolute": [8, 12, 15],
  "increments": [4, 3],
  "oldMeterWraps": [0, 1],
  "newMeterWraps": [0, 1]
}
```

交接不可行时同样返回 `INCONSISTENT` + 全局位置；省略 `changeover`
（或显式 `null`）时请求与响应形态保持原样（仍为 `cumulativeWraps`）。

`changeover` 校验（违反返回 **422**）：

- `position` 为严格整数且 `1 <= position <= len(readings)-2`，该位置
  读数必须已知；
- `newModulus` 为正整数；`newStart` 为严格非负整数且
  `0 <= newStart < newModulus`；
- 交接之后的已知读数须满足 `0 <= v < newModulus`；交接位置及之前仍按
  旧模数校验；`changeover` 内未知字段一律拒绝。

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
- `tests/test_changeover.py`：换表独立穷举对拍（旧/新模数 1–3、长度 3–6、
  全部交接位置、两侧漏抄与开表读数全枚举，约 80 万个确定性小实例）、随机
  对拍（两侧多圈回绕）、新表清零不产生负耗用、旧/新侧各自多圈回绕、交接
  边界（`h=1` 且 `h=n-2`）、任一侧不可行的全局位置映射、新旧大模数
  （10⁶⁰ / 10⁴⁰）与 300 项性能；
- `tests/test_api.py`：422 校验矩阵（含 `changeover` 嵌套校验、按所属表
  分段的读数/步长模数边界）、成功/无解响应形态。
