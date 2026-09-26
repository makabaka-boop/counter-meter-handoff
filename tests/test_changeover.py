"""一次换表交接的对拍与边界测试。

旧表在位置 h 末次抄表（读数已知），新表同点开表（newStart 可为任意
0..m_new-1）。真实计数轨迹 A 单调不减：

- i <= h：A[i] ≡ readings[i] (mod m_old)
- i >  h：A[i] - A[h] ≡ readings[i] - newStart (mod m_new)

穷举对拍直接枚举全部步长，以“先最小末值、再字典序最小”为标准答案，
覆盖两侧漏抄、多圈回绕、交接边界（h=1 / h=n-2）与新旧模数任意组合。
"""

import itertools
import random

from app.solver import ChangeoverSpec, Inconsistent, Solved, solve

from .brute import (
    brute_solve_changeover,
    earliest_blocked_changeover,
)


def check_changeover(
    m_old, readings, min_steps, max_steps, h, m_new, start
):
    """跑高效实现并完整校验返回结构与分段回绕。"""
    co = ChangeoverSpec(
        position=h, new_modulus=m_new, new_start=start
    )
    res = solve(
        m_old, list(readings), list(min_steps), list(max_steps), changeover=co
    )
    n = len(readings)
    if isinstance(res, Inconsistent):
        assert res.position == earliest_blocked_changeover(
            m_old, readings, min_steps, max_steps, (h, m_new, start)
        )
        return res
    assert isinstance(res, Solved)
    assert res.cumulative_wraps is None
    assert len(res.absolute) == n
    assert len(res.increments) == n - 1
    assert res.old_wraps is not None and len(res.old_wraps) == h + 1
    assert res.new_wraps is not None and len(res.new_wraps) == n - h
    # 重建一致性。
    A = [readings[0]]
    for d in res.increments:
        A.append(A[-1] + d)
    assert A == res.absolute
    # 步长区间。
    for i, d in enumerate(res.increments):
        assert min_steps[i] <= d <= max_steps[i]
    # 非负、单调不减（交接处也不能产生负耗用）。
    assert all(a >= 0 for a in res.absolute)
    assert all(res.absolute[i] <= res.absolute[i + 1] for i in range(n - 1))
    # 旧表侧读数与回绕。
    for i in range(0, h + 1):
        v = readings[i]
        if v is not None:
            assert res.absolute[i] % m_old == v
    assert res.old_wraps == [a // m_old for a in res.absolute[: h + 1]]
    assert res.old_wraps[0] == 0
    # 新表侧：表内计数 = A[i]-A[h]+start，回绕 = floor((A[i]-A[h]+start)/m_new)。
    assert res.new_wraps[0] == 0
    g0 = res.absolute[h]
    for j, i in enumerate(range(h, n)):
        gauge = res.absolute[i] - g0 + start
        if i > h:
            v = readings[i]
            if v is not None:
                assert gauge % m_new == v
        else:
            assert gauge % m_new == start
        assert res.new_wraps[j] == gauge // m_new
    return res


# ---------------------------------------------------------------------------
# 小规模独立穷举：旧模数、新模数、交接位置、读数（含两侧漏抄）、步长全覆盖
# 式抽样；步长维度按 (m_old,m_new,n) 固定抽样，读数/交接维度全枚举。
# ---------------------------------------------------------------------------

def _compare_with_brute(m_old, readings, min_steps, max_steps, h, m_new, start):
    """高效实现与穷举参考逐一比对（含最早不可延伸位置）。"""
    res = check_changeover(m_old, readings, min_steps, max_steps, h, m_new, start)
    ref = brute_solve_changeover(
        m_old, readings, min_steps, max_steps, (h, m_new, start)
    )
    if ref[0] == "inconsistent":
        assert isinstance(res, Inconsistent)
        assert res.position == ref[1]
    else:
        assert isinstance(res, Solved), (
            f"m_old={m_old} m_new={m_new} readings={readings} "
            f"steps={list(zip(min_steps, max_steps))} h={h} start={start}"
        )
        assert res.absolute == ref[1], (
            f"m_old={m_old} m_new={m_new} readings={readings} "
            f"steps={list(zip(min_steps, max_steps))} h={h} start={start}"
        )


def test_exhaustive_changeover_small():
    count = 0
    for m_old in range(1, 4):
        for m_new in range(1, 4):
            for n in range(3, 7):
                for h in range(1, n - 1):
                    # 各边步长模式池（旧边按 2*m_old、新边按 2*m_new 封顶）。
                    modes_by_edge = []
                    for i in range(n - 1):
                        mb = 2 * (m_old if i < h else m_new)
                        modes = [
                            (lo, hi)
                            for lo in range(0, 3)
                            for hi in range(lo, min(mb, lo + 2) + 1)
                        ]
                        modes_by_edge.append(modes)
                    all_combos = list(itertools.product(*modes_by_edge))
                    if len(all_combos) <= 400:
                        combos = all_combos
                    else:
                        # 步长维度确定性抽样；读数/开表读数/交接位置维度全枚举。
                        # 边数多时 DFS 较深，少抽一些，把总量压在百万级以内。
                        sample_k = 36 if n <= 5 else 12
                        rng_s = random.Random(
                            hash((m_old, m_new, n, h)) & 0xFFFFFFFF
                        )
                        combos = rng_s.sample(all_combos, sample_k)

                    # 读数槽位：位置 0、h 已知（旧表侧），n-1 已知（新表侧）；
                    # 其余槽位按所属侧取合法读数或 null（两侧漏抄全覆盖）。
                    slot_choices = []
                    for i in range(n):
                        if i == 0 or i == h:
                            slot_choices.append(list(range(m_old)))
                        elif i == n - 1:
                            slot_choices.append(list(range(m_new)))
                        elif i < h:
                            slot_choices.append(list(range(m_old)) + [None])
                        else:
                            slot_choices.append(list(range(m_new)) + [None])
                    for readings in itertools.product(*slot_choices):
                        for start in range(m_new):
                            for combo in combos:
                                min_steps = [c[0] for c in combo]
                                max_steps = [c[1] for c in combo]
                                _compare_with_brute(
                                    m_old,
                                    list(readings),
                                    min_steps,
                                    max_steps,
                                    h,
                                    m_new,
                                    start,
                                )
                                count += 1
    assert count > 200_000


# ---------------------------------------------------------------------------
# 随机对拍（稍大范围，含新表侧多圈回绕）。
# ---------------------------------------------------------------------------

def test_random_changeover_medium():
    rng = random.Random(4242)
    for _ in range(400):
        m_old = rng.randrange(1, 7)
        m_new = rng.randrange(1, 7)
        n = rng.randrange(3, 9)
        h = rng.randrange(1, n - 1)
        readings = [None] * n
        readings[0] = rng.randrange(m_old)
        readings[h] = rng.randrange(m_old)
        readings[-1] = rng.randrange(m_new)
        for i in range(1, n - 1):
            if i == h:
                continue
            if i < h:
                readings[i] = (
                    None if rng.random() < 0.5 else rng.randrange(m_old)
                )
            else:
                readings[i] = (
                    None if rng.random() < 0.5 else rng.randrange(m_new)
                )
        start = rng.randrange(m_new)
        min_steps, max_steps = [], []
        for i in range(n - 1):
            mb = 2 * (m_old if i < h else m_new)
            hi_cap = min(4, mb)
            lo = rng.randrange(0, hi_cap + 1)
            hi = lo + rng.randrange(0, min(4, mb - lo) + 1)
            min_steps.append(lo)
            max_steps.append(hi)
        res = check_changeover(
            m_old, readings, min_steps, max_steps, h, m_new, start
        )
        ref = brute_solve_changeover(
            m_old, readings, min_steps, max_steps, (h, m_new, start)
        )
        if ref[0] == "inconsistent":
            assert isinstance(res, Inconsistent)
            assert res.position == ref[1]
        else:
            assert isinstance(res, Solved)
            assert res.absolute == ref[1]


# ---------------------------------------------------------------------------
# 手工场景。
# ---------------------------------------------------------------------------

def test_basic_changeover_two_meters():
    # 旧表 m=10：[8, 2] 一步 [0,10] ⇒ 总量 4+10q，最小 q=0 ⇒ d=4，A[h]=12。
    # 新表 m=7，开表读数 5，位置 2 读数 1：表内增量 (1-5) mod 7 = 3，
    # 步长 [0,10] 最小 d=3。A=[8,12,15]。
    res = solve(
        10,
        [8, 2, 1],
        [0, 0],
        [10, 10],
        ChangeoverSpec(position=1, new_modulus=7, new_start=5),
    )
    assert isinstance(res, Solved)
    assert res.absolute == [8, 12, 15]
    assert res.increments == [4, 3]
    assert res.old_wraps == [0, 1]
    # 新表表内：5（圈0）-> 8（圈1，读数1）。
    assert res.new_wraps == [0, 1]


def test_new_meter_reset_is_not_negative_consumption():
    # 旧表走到 A[h]=12（读数2，圈1）；新表开表读数 0（清零）。
    # 交接处增量必须为 0：A 不跳变、不出现负耗用。
    res = solve(
        10,
        [8, 2, 3],
        [4, 3],
        [4, 3],
        ChangeoverSpec(position=1, new_modulus=10, new_start=0),
    )
    assert isinstance(res, Solved)
    assert res.absolute == [8, 12, 15]
    assert res.increments == [4, 3]
    assert all(d >= 0 for d in res.increments)
    assert res.old_wraps == [0, 1]
    # 表内 0 -> 3，未回绕。
    assert res.new_wraps == [0, 0]


def test_changeover_new_side_multi_wrap():
    # 旧段：[0, 0]，d=0，A[h]=0。
    # 新表 m=10 开表 9，末读数 0，三条新边各 [0,20]：表内增量 (0-9) mod 10=1，
    # 最小总量 1（1+10q，q=0 可行）⇒ 字典序 [0,0,1]。
    res = solve(
        10,
        [0, 0, None, None, 0],
        [0, 0, 0, 0],
        [0, 20, 20, 20],
        ChangeoverSpec(position=1, new_modulus=10, new_start=9),
    )
    assert isinstance(res, Solved)
    assert res.absolute == [0, 0, 0, 0, 1]
    assert res.increments == [0, 0, 0, 1]
    # 新表覆盖位置 1..4；表内 9,9,9,10；末点圈 1（读数0）。
    assert res.new_wraps == [0, 0, 0, 1]


def test_changeover_old_side_multi_wrap():
    # 旧表 m=5：[2, ?, ?, 3] 三步各 [4,10]，h=3：A[h]=18（圈3）。
    # 新表 m=6 开表 1，末读 2，d∈[0,12]：最小增量 1 ⇒ A 末值 19。
    res = solve(
        5,
        [2, None, None, 3, 2],
        [4, 4, 4, 0],
        [10, 10, 10, 12],
        ChangeoverSpec(position=3, new_modulus=6, new_start=1),
    )
    assert isinstance(res, Solved)
    assert res.absolute[:4] == [2, 6, 10, 18]
    assert res.absolute[-1] == 19
    assert res.old_wraps == [0, 1, 2, 3]
    # 表内 1 -> 2，无回绕。
    assert res.new_wraps == [0, 0]


def test_changeover_boundary_h_first_and_last():
    # n=3，h=1 既是最早也是最晚交接位置。
    res = solve(
        4,
        [3, 1, 0],
        [0, 0],
        [8, 8],
        ChangeoverSpec(position=1, new_modulus=3, new_start=2),
    )
    assert isinstance(res, Solved)
    # 旧段：3 -> 1（m4）：增量 2（表内 3->5）；A[h]=5。
    # 新段：表内 2 -> 0（m3）：增量 1；A 末值 6。
    assert res.absolute == [3, 5, 6]
    assert res.old_wraps == [0, 1]
    assert res.new_wraps == [0, 1]  # 表内 2 -> 3（读数0，圈1）


def test_changeover_missed_readings_both_sides():
    # 旧侧空洞 + 新侧空洞：旧 m=10 [8,?,2] 步长 [0,6]x2
    # ⇒ 旧段总量 4（0,4）。新 m=10 开表 2，末读 5，[?,5] 步 [0,6]x2，
    # 表内总量 3 ⇒ 字典序 (0,3)。
    res = solve(
        10,
        [8, None, 2, None, 5],
        [0, 0, 0, 0],
        [6, 6, 6, 6],
        ChangeoverSpec(position=2, new_modulus=10, new_start=2),
    )
    assert isinstance(res, Solved)
    assert res.absolute == [8, 8, 12, 12, 15]
    assert res.increments == [0, 4, 0, 3]
    assert res.old_wraps == [0, 0, 1]
    assert res.new_wraps == [0, 0, 0]


def test_changeover_infeasible_old_side():
    # 旧表 m=10：[1, 9] 单步 [0,3]：需求 8+10q 无解；位置 1（=h）。
    res = solve(
        10,
        [1, 9, 0],
        [0, 0],
        [3, 10],
        ChangeoverSpec(position=1, new_modulus=10, new_start=0),
    )
    assert isinstance(res, Inconsistent)
    assert res.position == 1


def test_changeover_infeasible_new_side_maps_global_position():
    # 旧段可行；新表 m=10 开表 0，[0, ?, 9] 两步各 [0,3]：
    # 总量需 9+10q > 6 无解，最早不可延伸是全局位置 3（新段局部 2）。
    res = solve(
        10,
        [0, 0, None, 9],
        [0, 0, 0],
        [0, 3, 3],
        ChangeoverSpec(position=1, new_modulus=10, new_start=0),
    )
    assert isinstance(res, Inconsistent)
    assert res.position == 3


def test_changeover_infeasible_at_new_known_interior():
    # 新表段内部已知点不可达：m=10 开表0，位置2读9，单步 [0,3]。
    res = solve(
        10,
        [0, 5, 9, 0],
        [5, 0, 0],
        [5, 3, 0],
        ChangeoverSpec(position=1, new_modulus=10, new_start=0),
    )
    assert isinstance(res, Inconsistent)
    assert res.position == 2


def test_changeover_lex_min_across_both_segments():
    # 旧 m=10 [0,?,0]，两步 [3,6]：总量 10，字典序 (3,7)……
    # 参照 test_tie_lexicographic 三洞结构；这里两边各验证贪心独立成立。
    # 旧侧两步 [3,6]：总量 10（q=1 唯一）⇒ (3,7)？剩余边1 [3,6]：
    # d0 最小 3，d1=7 > 6 不可行 ⇒ d0=4，d1=6。
    res_old = solve(
        10,
        [0, None, 0, 0],
        [3, 3, 0],
        [6, 6, 0],
        ChangeoverSpec(position=2, new_modulus=10, new_start=0),
    )
    assert isinstance(res_old, Solved)
    assert res_old.increments == [4, 6, 0]
    assert res_old.absolute == [0, 4, 10, 10]


def test_changeover_huge_moduli():
    # 大模数对拍边界：旧模数 10^60，新模数 10^40。
    mo = 10**60
    mn = 10**40
    # 旧：mo-1 -> 2，一步 [0,2mo]：d=3（不回绕，A[h]=mo+2）。
    # 新：开表 mn-1，末读 0，一步 [0,2mn]：表内增量 1（回绕1圈）。
    res = solve(
        mo,
        [mo - 1, 2, 0],
        [0, 0],
        [2 * mo, 2 * mn],
        ChangeoverSpec(position=1, new_modulus=mn, new_start=mn - 1),
    )
    assert isinstance(res, Solved)
    assert res.absolute == [mo - 1, mo + 2, mo + 3]
    assert res.increments == [3, 1]
    assert res.old_wraps == [0, 1]
    assert res.new_wraps == [0, 1]


def test_changeover_modulus_one_either_side():
    # 旧模数 1（读数恒 0），新模数 1。
    res = solve(
        1,
        [0, 0, 0],
        [0, 2],
        [0, 2],
        ChangeoverSpec(position=1, new_modulus=1, new_start=0),
    )
    assert isinstance(res, Solved)
    assert res.absolute == [0, 0, 2]
    assert res.increments == [0, 2]
    assert res.old_wraps == [0, 0]
    assert res.new_wraps == [0, 2]


def test_no_changeover_response_unchanged_fields():
    # 省略 changeover 时结果字段与原单表求解完全一致。
    res = solve(10, [8, None, 2], [0, 0], [6, 6])
    assert isinstance(res, Solved)
    assert res.absolute == [8, 8, 12]
    assert res.cumulative_wraps == [0, 0, 1]
    assert res.old_wraps is None and res.new_wraps is None


def test_changeover_three_hundred_positions_performance():
    # 300 项、两侧大模数、两侧均有漏抄：只要求快速给出合法解或 INCONSISTENT。
    n = 300
    h = 150
    m_old = 10**30
    m_new = 10**28
    rng = random.Random(17)
    readings = [None] * n
    readings[0] = 0
    readings[h] = rng.randrange(m_old)
    readings[-1] = rng.randrange(m_new)
    for i in range(1, n - 1):
        if i == h:
            continue
        if rng.random() < 0.3:
            readings[i] = rng.randrange(m_old if i < h else m_new)
    min_steps = [m_old if i < h else m_new for i in range(n - 1)]
    max_steps = [m_old + 2 if i < h else m_new + 2 for i in range(n - 1)]
    res = solve(
        m_old,
        readings,
        min_steps,
        max_steps,
        ChangeoverSpec(position=h, new_modulus=m_new, new_start=0),
    )
    if isinstance(res, Solved):
        assert len(res.absolute) == n
        assert len(res.old_wraps) == h + 1
        assert len(res.new_wraps) == n - h
        assert all(
            min_steps[i] <= res.increments[i] <= max_steps[i]
            for i in range(n - 1)
        )
        assert all(
            res.absolute[i] <= res.absolute[i + 1] for i in range(n - 1)
        )
        for i, v in enumerate(readings):
            if v is None:
                continue
            if i <= h:
                assert res.absolute[i] % m_old == v
            else:
                assert (res.absolute[i] - res.absolute[h]) % m_new == v
    else:
        assert isinstance(res, Inconsistent)
        assert 0 <= res.position < n
