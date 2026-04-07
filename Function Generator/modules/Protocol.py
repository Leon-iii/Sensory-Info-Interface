from enum import IntEnum

# 패킷 구조:

# PING: [magic 2B] [version 1B] [cmd 1B] [checksum 2B]
# LOAD_SAMPLES: [magic 2B] [version 1B] [cmd 1B] [sample_rate 4B] [sample_count 2B] [samples 2B * N] [checksum 2B]
# START:[magic 2B] [version 1B] [cmd=START 1B] [checksum 2B]
# STOP: [magic 2B] [version 1B] [cmd=STOP 1B] [checksum 2B]

MAGIC = 0xAA55                   # 패킷 시작을 식별하기 위한 고정 매직 넘버
PROTOCOL_VERSION = 1             # 프로토콜 버전
DEFAULT_TIMEOUT_SEC = 1.0        # 시리얼 읽기 타임아웃 기본값(초)


class Command(IntEnum):
    PING = 0x01                  # 연결 확인용 명령
    LOAD_SAMPLES = 0x02          # 샘플 데이터 전송 명령
    START = 0x03                 # 재생 시작 명령
    STOP = 0x04                  # 재생 중지 명령