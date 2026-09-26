"""FastAPI 端点测试：422 校验、成功响应、INCONSISTENT 形态。"""

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def post(payload):
    return client.post("/trajectory", json=payload)


def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_ok_response_shape():
    r = post(
        {
            "modulus": 10,
            "readings": [8, None, 2],
            "minStep": [0, 0],
            "maxStep": [6, 6],
        }
    )
    assert r.status_code == 200
    body = r.json()
    assert body == {
        "status": "OK",
        "absolute": [8, 8, 12],
        "increments": [0, 4],
        "cumulativeWraps": [0, 0, 1],
    }


def test_inconsistent_response():
    r = post(
        {
            "modulus": 10,
            "readings": [1, 9],
            "minStep": [0],
            "maxStep": [3],
        }
    )
    assert r.status_code == 200
    assert r.json() == {"status": "INCONSISTENT", "position": 1}


# ---------------------------------------------------------------------------
# 422：未知字段、数组错长、越界、类型错误、首尾缺失等。
# ---------------------------------------------------------------------------

BASE = {
    "modulus": 10,
    "readings": [1, None, 9],
    "minStep": [0, 0],
    "maxStep": [9, 9],
}


def _expect_422(payload):
    r = post(payload)
    assert r.status_code == 422, r.text


def test_unknown_top_level_field():
    bad = dict(BASE, extra=1)
    _expect_422(bad)


def test_missing_field():
    bad = {k: v for k, v in BASE.items() if k != "modulus"}
    _expect_422(bad)


def test_wrong_array_length_minstep():
    bad = dict(BASE, minStep=[0])
    _expect_422(bad)


def test_wrong_array_length_maxstep():
    bad = dict(BASE, maxStep=[9, 9, 9])
    _expect_422(bad)


def test_readings_too_short():
    bad = dict(BASE, readings=[5], minStep=[], maxStep=[])
    _expect_422(bad)


def test_readings_too_long():
    bad = dict(
        BASE,
        readings=[0] * 301,
        minStep=[0] * 300,
        maxStep=[0] * 300,
    )
    _expect_422(bad)


def test_first_reading_null():
    bad = dict(BASE, readings=[None, 5, 9])
    _expect_422(bad)


def test_last_reading_null():
    bad = dict(BASE, readings=[1, 5, None])
    _expect_422(bad)


def test_reading_out_of_range_high():
    bad = dict(BASE, readings=[1, 10, 9])
    _expect_422(bad)


def test_reading_negative():
    bad = dict(BASE, readings=[-1, None, 9])
    _expect_422(bad)


def test_modulus_zero():
    bad = dict(BASE, modulus=0)
    _expect_422(bad)


def test_step_order_violation():
    bad = dict(BASE, minStep=[5, 0], maxStep=[4, 9])
    _expect_422(bad)


def test_step_exceeds_two_modulus():
    bad = dict(BASE, minStep=[0, 0], maxStep=[21, 9])
    _expect_422(bad)


def test_negative_step():
    bad = dict(BASE, minStep=[-1, 0], maxStep=[9, 9])
    _expect_422(bad)


def test_float_rejected():
    bad = dict(BASE, modulus=10.5)
    _expect_422(bad)


def test_float_integer_like_rejected():
    bad = dict(BASE, minStep=[0.0, 0])
    _expect_422(bad)


def test_string_rejected():
    bad = dict(BASE, modulus="10")
    _expect_422(bad)


def test_bool_rejected():
    bad = dict(BASE, readings=[True, None, 9])
    _expect_422(bad)


def test_null_in_steps_rejected():
    bad = dict(BASE, minStep=[None, 0])
    _expect_422(bad)


def test_nested_unknown_field_inside_readings():
    # readings 元素只能是整数或 null。
    bad = dict(BASE, readings=[1, {"x": 1}, 9])
    _expect_422(bad)


# ---------------------------------------------------------------------------
# 换表交接：成功/无解形态与 422 校验矩阵。
# ---------------------------------------------------------------------------

CO_BASE = {
    "modulus": 10,
    "readings": [8, 2, 1],
    "minStep": [0, 0],
    "maxStep": [10, 10],
    "changeover": {
        "position": 1,
        "newModulus": 7,
        "newStart": 5,
    },
}


def test_changeover_ok_response_shape():
    r = post(CO_BASE)
    assert r.status_code == 200, r.text
    assert r.json() == {
        "status": "OK",
        "absolute": [8, 12, 15],
        "increments": [4, 3],
        "oldMeterWraps": [0, 1],
        "newMeterWraps": [0, 1],
    }


def test_changeover_inconsistent_response():
    # 旧段 1 -> 9 单步 [0,3] 不可行，最早位置 1（即交接点）。
    payload = {
        "modulus": 10,
        "readings": [1, 9, 0],
        "minStep": [0, 0],
        "maxStep": [3, 10],
        "changeover": {"position": 1, "newModulus": 10, "newStart": 0},
    }
    r = post(payload)
    assert r.status_code == 200
    assert r.json() == {"status": "INCONSISTENT", "position": 1}


def test_explicit_null_changeover_keeps_old_shape():
    payload = dict(BASE, changeover=None)
    r = post(payload)
    assert r.status_code == 200, r.text
    assert set(r.json()) == {
        "status",
        "absolute",
        "increments",
        "cumulativeWraps",
    }


def _expect_422_co(**overrides):
    payload = {**CO_BASE, "changeover": {**CO_BASE["changeover"], **overrides}}
    r = post(payload)
    assert r.status_code == 422, r.text


def test_changeover_position_zero():
    # n=3：必须 1 <= position <= 1。
    _expect_422_co(position=0)


def test_changeover_position_at_last():
    _expect_422_co(position=2)


def test_changeover_impossible_when_only_two_readings():
    # n=2 没有内部位置，任何交接位置都非法。
    payload = {
        "modulus": 10,
        "readings": [1, 9],
        "minStep": [0],
        "maxStep": [9],
        "changeover": {"position": 0, "newModulus": 10, "newStart": 0},
    }
    _expect_422(payload)
    payload["changeover"]["position"] = 1
    _expect_422(payload)


def test_changeover_position_negative():
    _expect_422_co(position=-1)


def test_changeover_reading_at_position_null():
    bad = dict(CO_BASE, readings=[8, None, 1])
    _expect_422(bad)


def test_changeover_new_start_too_large():
    _expect_422_co(newStart=7)


def test_changeover_new_start_negative():
    _expect_422_co(newStart=-1)


def test_changeover_new_modulus_zero():
    _expect_422_co(newModulus=0)


def test_changeover_unknown_nested_field():
    bad = dict(CO_BASE)
    bad["changeover"] = {**CO_BASE["changeover"], "extra": 1}
    _expect_422(bad)


def test_changeover_missing_nested_field():
    bad = dict(CO_BASE)
    bad["changeover"] = {"position": 1, "newModulus": 7}
    _expect_422(bad)


def test_changeover_float_position_rejected():
    _expect_422_co(position=1.0)


def test_changeover_bool_new_start_rejected():
    _expect_422_co(newStart=True)


def test_changeover_string_modulus_rejected():
    _expect_422_co(newModulus="7")


def test_reading_past_h_validated_against_new_modulus():
    # 读数 7 对旧模数 10 合法，但新模数为 7，位置 2 越界。
    bad = dict(CO_BASE, readings=[8, 2, 7])
    _expect_422(bad)


def test_reading_before_h_validated_against_old_modulus():
    # 新模数 7 允许 8 以下，但位置 0 属旧表（m=10 也允许 8）——
    # 改用旧模数 6 才能拒绝位置 0 的 8。
    bad = dict(
        CO_BASE,
        modulus=6,
        readings=[8, 2, 1],
        maxStep=[12, 10],
    )
    _expect_422(bad)


def test_step_past_h_bound_uses_new_modulus():
    # 边 1（新表侧）上限 10 <= 2*10 但 > 2*7。
    bad = dict(
        CO_BASE,
        changeover={"position": 1, "newModulus": 7, "newStart": 5},
    )
    # CO_BASE 自身 maxStep=10 已 > 14? 否（10<=14），放大到 15 拒绝。
    bad = dict(bad, maxStep=[10, 15])
    _expect_422(bad)


def test_step_before_h_bound_uses_old_modulus():
    # 边 0（旧表侧）上限 21 > 2*10；新模数取 20 不影响旧边判定。
    bad = dict(
        CO_BASE,
        maxStep=[21, 10],
        changeover={"position": 1, "newModulus": 20, "newStart": 5},
    )
    _expect_422(bad)
