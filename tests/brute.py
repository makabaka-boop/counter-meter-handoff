"""短序列穷举对拍的参考实现。

在步长取值范围很小的实例上直接 DFS 枚举所有增量组合，构造两级目标
（先最小化最终绝对计数，再最小化完整序列字典序）下的标准答案，
并计算“最早无法延伸的位置”，供与高效实现逐一比对。
"""

from __future__ import annotations


def brute_solve(modulus, readings, min_steps, max_steps):
    """返回 ("ok", absolute) 或 ("inconsistent", position)。"""
    n = len(readings)
    m = modulus
    best = None  # (final_value, tuple(A))

    def dfs(i, A):
        nonlocal best
        v = readings[i]
        if v is not None and A[-1] % m != v:
            return
        if i == n - 1:
            key = (A[-1], tuple(A))
            if best is None or key < best:
                best = key
            return
        for d in range(min_steps[i], max_steps[i] + 1):
            A.append(A[-1] + d)
            dfs(i + 1, A)
            A.pop()

    dfs(0, [readings[0]])
    if best is None:
        return ("inconsistent", earliest_blocked(modulus, readings, min_steps, max_steps))
    return ("ok", list(best[1]))


def prefix_feasible(modulus, readings, min_steps, max_steps, p):
    """位置 0..p 的前缀是否存在合法赋值（p 处若已知须匹配读数）。"""
    n = len(readings)
    m = modulus

    def dfs(i, A):
        v = readings[i]
        if v is not None and A[-1] % m != v:
            return False
        if i == p:
            return True
        for d in range(min_steps[i], max_steps[i] + 1):
            A.append(A[-1] + d)
            if dfs(i + 1, A):
                A.pop()
                return True
            A.pop()
        return False

    return dfs(0, [readings[0]])


def earliest_blocked(modulus, readings, min_steps, max_steps):
    n = len(readings)
    for p in range(1, n):
        if not prefix_feasible(modulus, readings, min_steps, max_steps, p):
            return p
    return None


def brute_solve_changeover(modulus, readings, min_steps, max_steps, co):
    """换表版穷举。co = (position, new_modulus, new_start)。

    两级目标：先最小化最终真实绝对计数 A[-1]，再取完整序列字典序最小。
    返回 ("ok", absolute) 或 ("inconsistent", position)。
    """
    n = len(readings)
    h, m_new, start = co
    best = None  # (final_value, tuple(A))

    def residue_ok(i, A):
        v = readings[i]
        if v is None:
            return True
        if i <= h:
            return A[i] % modulus == v
        return (A[i] - A[h]) % m_new == (v - start) % m_new

    def dfs(i, A):
        nonlocal best
        if not residue_ok(i, A):
            return
        if i == n - 1:
            key = (A[-1], tuple(A))
            if best is None or key < best:
                best = key
            return
        for d in range(min_steps[i], max_steps[i] + 1):
            A.append(A[-1] + d)
            dfs(i + 1, A)
            A.pop()

    dfs(0, [readings[0]])
    if best is None:
        return (
            "inconsistent",
            earliest_blocked_changeover(
                modulus, readings, min_steps, max_steps, co
            ),
        )
    return ("ok", list(best[1]))


def prefix_feasible_changeover(modulus, readings, min_steps, max_steps, co, p):
    """换表版：位置 0..p 的前缀是否存在合法赋值。"""
    h, m_new, start = co

    def dfs(i, A):
        v = readings[i]
        if v is not None:
            if i <= h:
                if A[-1] % modulus != v:
                    return False
            elif (A[-1] - A[h]) % m_new != (v - start) % m_new:
                return False
        if i == p:
            return True
        for d in range(min_steps[i], max_steps[i] + 1):
            A.append(A[-1] + d)
            if dfs(i + 1, A):
                A.pop()
                return True
            A.pop()
        return False

    return dfs(0, [readings[0]])


def earliest_blocked_changeover(modulus, readings, min_steps, max_steps, co):
    n = len(readings)
    for p in range(1, n):
        if not prefix_feasible_changeover(
            modulus, readings, min_steps, max_steps, co, p
        ):
            return p
    return None
