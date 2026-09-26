"""FastAPI 纯后端 JSON API。"""

from fastapi import FastAPI

from .models import TrajectoryRequest
from .solver import Inconsistent, Solved, solve

app = FastAPI(
    title="冷库机械累计表轨迹恢复",
    description=(
        "恢复跨零回绕的机械累计表绝对计数序列：先最小化最终绝对计数，"
        "再取完整序列字典序最小者；无解返回最早无法延伸的位置。"
    ),
    version="1.0.0",
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/trajectory")
def trajectory(req: TrajectoryRequest) -> dict:
    result = solve(req.modulus, req.readings, req.minStep, req.maxStep)
    if isinstance(result, Inconsistent):
        return {"status": "INCONSISTENT", "position": result.position}
    assert isinstance(result, Solved)
    return {
        "status": "OK",
        "absolute": result.absolute,
        "increments": result.increments,
        "cumulativeWraps": result.cumulative_wraps,
    }
