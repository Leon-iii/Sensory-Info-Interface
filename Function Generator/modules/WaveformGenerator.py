import math

class WaveformGenerator:
    @staticmethod
    def sine(
        frequency_hz: float,
        phase_deg: float,
        sample_rate_hz: int,
        duration_sec: float,
        amplitude: float = 1.0,
        offset: float = 0.0,
    ) -> list[float]:
        # 전체 샘플 개수 계산
        sample_count = int(sample_rate_hz * duration_sec)
        if sample_count <= 0:
            raise ValueError("sample_count must be positive")
        
        if frequency_hz <= 0:
            raise ValueError("frequency_hz must be positive")


        samples: list[float] = []
        for n in range(sample_count):
            t = n / sample_rate_hz                            # 현재 샘플의 시간 위치
            value = offset + amplitude * math.sin(2.0 * math.pi * frequency_hz * t + phase_deg * math.pi / 180.0)
            samples.append(value)                            # 사인파 샘플 추가

        return samples

    @staticmethod
    def square(
        frequency_hz: float,
        phase_deg: float,
        sample_rate_hz: int,
        duration_sec: float,
        amplitude: float = 1.0,
        duty: float = 0.5,
        offset: float = 0.0,
    ) -> list[float]:
        # 전체 샘플 개수 계산
        sample_count = int(sample_rate_hz * duration_sec)
        if sample_count <= 0:
            raise ValueError("sample_count must be positive")
        
        if frequency_hz <= 0:
            raise ValueError("frequency_hz must be positive")

        samples: list[float] = []
        period = sample_rate_hz / frequency_hz                      # 한 주기가 몇 샘플인지 계산

        phase_offset = phase_deg / 360.0

        for n in range(sample_count):
            phase = ((n % period) / period + phase_offset) % 1.0    # 현재 주기 내 위상(0~1)
            value = offset + (amplitude if phase < duty else -amplitude)
            samples.append(value)                                   # 듀티비 기반 사각파 샘플 추가

        return samples