"""FastAPI 纯后端 JSON API。"""

from fastapi import FastAPI

from .models import TrajectoryRequest
from .solver import ChangeoverSpec, Inconsistent, Solved, solve

app = FastAPI(
    title="冷库机械累计表轨迹恢复",
    description=(
        "恢复跨零回绕的机械累计表绝对计数序列：先最小化最终绝对计数，"
        "再取完整序列字典序最小者；无解返回最早无法延伸的位置。"
        "可选的一次换表交接把轨迹按旧/新两台表分段还原。"
    ),
    version="1.1.0",
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/trajectory")
def trajectory(req: TrajectoryRequest) -> dict:
    changeover = None
    if req.changeover is not None:
        changeover = ChangeoverSpec(
            position=req.changeover.position,
            new_modulus=req.changeover.newModulus,
            new_start=req.changeover.newStart,
        )
    result = solve(
        req.modulus,
        req.readings,
        req.minStep,
        req.maxStep,
        changeover=changeover,
    )
    if isinstance(result, Inconsistent):
        return {"status": "INCONSISTENT", "position": result.position}
    assert isinstance(result, Solved)

    if changeover is not None:
        # 任一交接请求不可行时 solver 已整体返回 INCONSISTENT，不会产生
        # 只成功一半的局部轨迹。
        return {
            "status": "OK",
            "absolute": result.absolute,
            "increments": result.increments,
            "oldMeterWraps": result.old_wraps,
            "newMeterWraps": result.new_wraps,
        }
    return {
        "status": "OK",
        "absolute": result.absolute,
        "increments": result.increments,
        "cumulativeWraps": result.cumulative_wraps,
    }
