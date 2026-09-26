"""请求/响应 Pydantic 模型与跨字段校验。"""

from typing import Annotated

from pydantic import BaseModel, Field, model_validator

# 严格整数：拒绝 1.0、"10"、true 等隐式转换。
StrictInt = Annotated[int, Field(strict=True)]


class Changeover(BaseModel):
    """一次换表交接（可选，整个请求至多一次）。"""

    model_config = {"extra": "forbid"}

    # 旧表最后一次读数所在位置（同一时点新表开表，交接耗用为零）。
    position: StrictInt
    # 新表模数（可与旧表不同）。
    newModulus: StrictInt = Field(ge=1)
    # 同一时点的新表开表读数：0 <= newStart < newModulus。
    newStart: StrictInt = Field(ge=0)


class TrajectoryRequest(BaseModel):
    model_config = {"extra": "forbid"}

    modulus: StrictInt = Field(ge=1)
    readings: list[StrictInt | None] = Field(min_length=2, max_length=300)
    minStep: list[StrictInt]
    maxStep: list[StrictInt]
    changeover: Changeover | None = None

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

        co = self.changeover
        if co is not None:
            # 交接必须是内部位置：两侧都至少有一段步长。
            if not (1 <= co.position <= n - 2):
                raise ValueError(
                    "changeover.position must satisfy 1 <= position <= len(readings) - 2"
                )
            # 旧表最后一次读数必须已知。
            if self.readings[co.position] is None:
                raise ValueError(
                    "reading at changeover.position is required (old meter's last "
                    "reading)"
                )
            if not (0 <= co.newStart < co.newModulus):
                raise ValueError(
                    "changeover.newStart must satisfy 0 <= newStart < newModulus"
                )

        m = self.modulus
        for i, v in enumerate(self.readings):
            if v is None:
                continue
            # 交接位置及之前按旧模数还原；交接之后按新模数校验。
            effective_m = (
                co.newModulus
                if co is not None and i > co.position
                else m
            )
            if not (0 <= v < effective_m):
                raise ValueError(
                    "known readings must satisfy 0 <= v < the modulus of the meter "
                    "covering that position"
                )
        for i, (lo, hi) in enumerate(zip(self.minStep, self.maxStep)):
            # 边 i 连接位置 i -> i+1：i < h 属旧表侧，i >= h 属新表侧。
            bound_m = (
                co.newModulus
                if co is not None and i >= co.position
                else m
            )
            if not (0 <= lo <= hi <= 2 * bound_m):
                raise ValueError(
                    "each pair must satisfy 0 <= minStep <= maxStep <= 2 * modulus "
                    "of the meter covering that segment"
                )
        return self


class TrajectoryResponse(BaseModel):
    status: str
    absolute: list[int]
    increments: list[int]
    cumulativeWraps: list[int]


class ChangeoverTrajectoryResponse(BaseModel):
    status: str
    absolute: list[int]
    increments: list[int]
    # 旧表覆盖位置 0..h；新表覆盖位置 h..n-1（h 处各自为开表段首项，回绕 0）。
    oldMeterWraps: list[int]
    newMeterWraps: list[int]
