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
