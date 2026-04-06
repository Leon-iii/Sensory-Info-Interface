from __future__ import annotations

import time

from modules import WaveformGenerator, Quantizer, PacketBuilder, SerialTransport
from modules.Protocol import *

# -----------------------------
# Example application flow
# -----------------------------

def main() -> None:
    # ---- User-configurable parameters ----
    port = "COM3"           # Windows 예시. Linux면 "/dev/ttyACM0" 같은 형태
    baudrate = 115200
    sample_rate_hz = 10000
    frequency_hz = 1000.0
    duration_sec = 0.02     # 20 ms 길이의 파형 생성
    waveform = "sine"

    # ---- Step 1: Generate waveform ----
    if waveform == "sine":
        analog_values = WaveformGenerator.sine(
            frequency_hz=frequency_hz,
            sample_rate_hz=sample_rate_hz,
            duration_sec=duration_sec,
            amplitude=1.0,
            offset=0.0,
        )
    elif waveform == "square":
        analog_values = WaveformGenerator.square(
            frequency_hz=frequency_hz,
            sample_rate_hz=sample_rate_hz,
            duration_sec=duration_sec,
            amplitude=1.0,
            offset=0.0,
        )
    else:
        raise ValueError(f"unsupported waveform: {waveform}")

    # ---- Step 2: Quantize to DAC code ----
    quantizer = Quantizer(bits=12, v_min=-1.0, v_max=1.0)
    dac_samples = quantizer.quantize(analog_values)        # 실수 파형 -> 12비트 DAC 코드

    # ---- Step 3: Build packets ----
    ping_packet = PacketBuilder.build_ping_packet()        # 연결 확인용
    load_packet = PacketBuilder.build_load_samples_packet(
        sample_rate_hz=sample_rate_hz,
        samples=dac_samples,
    )
    start_packet = PacketBuilder.build_start_packet()      # 재생 시작
    stop_packet = PacketBuilder.build_stop_packet()        # 재생 정지

    # 생성 결과와 패킷 크기 출력
    print(f"Generated {len(dac_samples)} samples")
    print(f"PING packet bytes: {len(ping_packet)}")
    print(f"LOAD packet bytes: {len(load_packet)}")
    print(f"START packet bytes: {len(start_packet)}")
    print(f"STOP packet bytes: {len(stop_packet)}")

    # ---- Step 4: Send through serial ----
    transport = SerialTransport(port=port, baudrate=baudrate)

    try:
        transport.open()
        time.sleep(2.0)  # 일부 보드는 포트 오픈 직후 자동 리셋되므로 잠시 대기

        transport.write_packet(ping_packet)
        print("PING sent")

        transport.write_packet(load_packet)
        print("LOAD_SAMPLES sent")

        transport.write_packet(start_packet)
        print("START sent")

        # 필요 시 보드 응답 읽기
        # response = transport.read_line()
        # print("Board:", response)

        time.sleep(1.0)  # 1초 동안 재생한다고 가정

        transport.write_packet(stop_packet)
        print("STOP sent")

    finally:
        transport.close()   # 예외가 나도 포트는 닫도록 보장


if __name__ == "__main__":
    main()