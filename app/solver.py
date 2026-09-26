"""绝对计数轨迹恢复核心算法。

机械累计表只保留模 ``modulus`` 内的读数，因此单次或连续多次跨零回绕后，
直接用读数相减会把正常耗用（绝对计数只增不减）误判成倒退。

把第 ``i`` 个位置的绝对计数写成

    A[i] = residue[i] + wraps[i] * modulus

其中已知位置 ``residue[i]`` 为抄表读数、``wraps[i]`` 为累计回绕次数（非负
整数）；未知位置两者都自由。每一步要求

    minStep[i] <= A[i + 1] - A[i] <= maxStep[i].

记两个相邻已知点 a、b 的读数为 r_a、r_b，回绕次数为 k_{a}、k_b，则段内
总增量

    S = A_b - A_a = m * q + (r_b - r_a),   q = k_b - k_a >= 0.

优化目标（两级）：

1. 先最小化最终绝对计数 ``A[-1]``（等价于最小化最终回绕次数 k_t）；
2. 在此前提下使完整序列 ``A`` 字典序最小——等价于从左到右贪心，每一步在
   仍能延伸出可行后缀时取最小的当前值。

实现只在“回绕次数构成的整数区间”上做线性次数的区间传播与常数次大整数
运算，不枚举绝对计数值本身（绝对值可远超 modulus 的多项式倍）。
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Solved:
    """有解时的恢复结果。"""

    absolute: list[int]
    increments: list[int]
    cumulative_wraps: list[int]


@dataclass(frozen=True)
class Inconsistent:
    """无解：``position`` 是最早无法延伸的位置下标。"""

    position: int


Result = Solved | Inconsistent


def _ceil_div(a: int, b: int) -> int:
    """正数分母的向上取整除法（分子可为负）。"""
    return -((-a) // b)


def solve(
    modulus: int,
    readings: list[int | None],
    min_steps: list[int],
    max_steps: list[int],
) -> Result:
    n = len(readings)
    m = modulus

    known_idx = [i for i, v in enumerate(readings) if v is not None]
    t = len(known_idx)

    # 步长前缀和，段和 O(1)：smin(a,b)=prefix_min[b]-prefix_min[a]。
    prefix_min = [0] * (n + 1)
    prefix_max = [0] * (n + 1)
    for i in range(n - 1):
        prefix_min[i + 1] = prefix_min[i] + min_steps[i]
        prefix_max[i + 1] = prefix_max[i] + max_steps[i]
    prefix_min[n] = prefix_min[n - 1]
    prefix_max[n] = prefix_max[n - 1]

    # 每个已知段 j（j=1..t-1）：known_idx[j-1] -> known_idx[j]。
    seg_qlo = [0] * t      # 段回绕数 q 的下界 ceil((smin-(r_b-r_a))/m)
    seg_qhi = [0] * t      # 段回绕数 q 的上界 floor((smax-(r_b-r_a))/m)
    for j in range(1, t):
        a = known_idx[j - 1]
        b = known_idx[j]
        r_a = readings[a]
        r_b = readings[b]
        smin = prefix_min[b] - prefix_min[a]
        smax = prefix_max[b] - prefix_max[a]
        e = r_b - r_a
        seg_qlo[j] = _ceil_div(smin - e, m)
        seg_qhi[j] = (smax - e) // m
        # smin>=0 且 r_b-r_a <= m-1 保证 qlo>=0（A 单调不减）。
        if seg_qlo[j] > seg_qhi[j]:
            # 段本身就无法在步长范围内凑出总增量；段内未知点总能延伸，
            # 最早无法匹配的是该已知端点（前 j-1 个已知点均可达）。
            return Inconsistent(b)

    # ------------------------------------------------------------------
    # 1) 前向传播：F_j = [loF_j, hiF_j] 为 k_j 的可达整数区间，k_0 = 0。
    # ------------------------------------------------------------------
    lo_f = [0] * t
    hi_f = [0] * t
    for j in range(1, t):
        lo_f[j] = lo_f[j - 1] + seg_qlo[j]
        hi_f[j] = hi_f[j - 1] + seg_qhi[j]
        # seg_qlo<=seg_qhi 已在段构造时检查；区间相加后只会更宽，不会变空。

    # 最小最终绝对计数 ⇔ 最小 k_{t-1} ⇔ loF_{t-1}。
    final_k = lo_f[t - 1]

    # ------------------------------------------------------------------
    # 2) 后向传播：G_j = [loG_j, hiG_j] 由 k_{t-1} = final_k 倒推；
    #    贪心时允许集合 T_j = F_j ∩ G_j（仍是整数区间）。
    # ------------------------------------------------------------------
    lo_g = [0] * t
    hi_g = [0] * t
    lo_g[t - 1] = hi_g[t - 1] = final_k
    for j in range(t - 1, 0, -1):
        lo_g[j - 1] = lo_g[j] - seg_qhi[j]
        hi_g[j - 1] = hi_g[j] - seg_qlo[j]

    # 后缀步长和：suffix_min[i] = sum(min_steps[i:n-1])，i ∈ [0, n-1]。
    suffix_min = [0] * n
    suffix_max = [0] * n
    for i in range(n - 2, -1, -1):
        suffix_min[i] = suffix_min[i + 1] + min_steps[i]
        suffix_max[i] = suffix_max[i + 1] + max_steps[i]

    # ------------------------------------------------------------------
    # 3) 左到右贪心重建。
    #
    # 段内当前边 d_i，已选前缀增量 P（段内 d_a..d_{i-1} 之和），剩余边
    # 总增量 R ∈ [rlo, rhi]（连续整数区间）。段总量
    #     P + d + R = m*x + e,   x = k_b - k_cur（本段回绕数），
    # 且 x ∈ [T_lo - k_cur, T_hi - k_cur]。对固定 x：
    #     d ∈ [m*x - P - rhi + e, m*x - P - rlo + e] ∩ [minStep, maxStep]。
    # 取最小可行 x，再取区间内最小 d，即得字典序最优的当前 A 值。
    # ------------------------------------------------------------------
    absolute: list[int] = [readings[0]]
    increments: list[int] = []

    cur = readings[0]     # 当前绝对计数
    k_cur = 0             # 当前已知点的回绕次数
    P = 0                 # 段内已选增量之和

    for j in range(1, t):
        a = known_idx[j - 1]
        b = known_idx[j]
        e = readings[b] - readings[a]
        t_lo = max(lo_f[j], lo_g[j])
        t_hi = min(hi_f[j], hi_g[j])
        z_lo = t_lo - k_cur
        z_hi = t_hi - k_cur

        for i in range(a, b):
            lo_d = min_steps[i]
            hi_d = max_steps[i]
            if i == b - 1:
                rlo = rhi = 0
            else:
                rlo = suffix_min[i + 1] - suffix_min[b]
                rhi = suffix_max[i + 1] - suffix_max[b]

            # 由存在倍数 m*x 落在 [P+lo_d+rlo-e, P+hi_d+rhi-e] 求 x 范围。
            x_lo = _ceil_div(P + lo_d + rlo - e, m)
            x_hi = (P + hi_d + rhi - e) // m
            x_lo = max(x_lo, z_lo, 0)
            x_hi = min(x_hi, z_hi)

            chosen_d = None
            if x_lo <= x_hi:
                x = x_lo
                # d = m*x + e - P - R，R 取最大 rhi 时 d 最小，取最小 rlo 时最大。
                d_star = max(lo_d, m * x + e - P - rhi)
                if d_star <= min(hi_d, m * x + e - P - rlo):
                    chosen_d = d_star
                    chosen_x = x
            if chosen_d is None:
                # 理论上不可达：区间传播已证明整体可行。防御性处理。
                return Inconsistent(i + 1)

            cur += chosen_d
            increments.append(chosen_d)
            absolute.append(cur)
            P += chosen_d
            if i == b - 1:
                k_cur += chosen_x
                P = 0

    # ------------------------------------------------------------------
    # 4) 每位置累计回绕次数 wraps[i] = floor(A[i] / m)（A_i 非负）。
    # ------------------------------------------------------------------
    cumulative_wraps = [a // m for a in absolute]

    return Solved(
        absolute=absolute,
        increments=increments,
        cumulative_wraps=cumulative_wraps,
    )
