"""请求/响应 Pydantic 模型与跨字段校验。"""

from typing import Annotated

from pydantic import BaseModel, Field, model_validator

# 严格整数：拒绝 1.0、"10"、true 等隐式转换。
StrictInt = Annotated[int, Field(strict=True)]


class TrajectoryRequest(BaseModel):
    model_config = {"extra": "forbid"}

    modulus: StrictInt = Field(ge=1)
    readings: list[StrictInt | None] = Field(min_length=2, max_length=300)
    minStep: list[StrictInt]
    maxStep: list[StrictInt]

    @model_validator(mode="after")
    def _check_constraints(self) -> "TrajectoryRequest":
        n = len(self.readings)
        if len(self.minStep) != n - 1 or len(self.maxStep) != n - 1:
            raise ValueError(
                "minStep and maxStep must each have exactly len(readings) - 1 items"
            )
        # 首尾均已知；其余允许 null。
        if self.readings[0] is None or self.readings[-1] is None:
            raise ValueError("first and last readings are required")
        m = self.modulus
        for v in self.readings:
            if v is not None and not (0 <= v < m):
                raise ValueError("known readings must satisfy 0 <= v < modulus")
        for lo, hi in zip(self.minStep, self.maxStep):
            if not (0 <= lo <= hi <= 2 * m):
                raise ValueError(
                    "each pair must satisfy 0 <= minStep <= maxStep <= 2 * modulus"
                )
        return self


class TrajectoryResponse(BaseModel):
    status: str
    absolute: list[int]
    increments: list[int]
    cumulativeWraps: list[int]
