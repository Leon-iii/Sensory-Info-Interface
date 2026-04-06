from dataclasses import dataclass
from typing import Iterable

@dataclass(frozen=True)
class Quantizer:
    bits: int = 12
    v_min: float = -1.0
    v_max: float = 1.0

    def quantize(self, values: Iterable[float]) -> list[int]:
        # 양자화 대상 전압 범위가 올바른지 검사
        if self.v_max <= self.v_min:
            raise ValueError("v_max must be greater than v_min")

        max_code = (1 << self.bits) - 1                      # 예: 12bit면 4095
        result: list[int] = []

        for v in values:
            clamped = min(max(v, self.v_min), self.v_max)   # 범위를 벗어난 값은 잘라냄
            normalized = (clamped - self.v_min) / (self.v_max - self.v_min)
            code = round(normalized * max_code)             # 실수값을 DAC 코드값으로 변환
            result.append(code)

        return result