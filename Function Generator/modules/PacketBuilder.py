import struct
from modules.protocol import *

# -----------------------------
# Packet builder
# -----------------------------

class PacketBuilder:
    @staticmethod
    def checksum16(data: bytes) -> int:
        # 아주 단순한 16비트 체크섬: 모든 바이트 합의 하위 16비트만 사용
        return sum(data) & 0xFFFF

    @classmethod
    def build_ping_packet(cls) -> bytes:
        # PING 명령 패킷 생성
        header = struct.pack(
            "<HBB",
            MAGIC,
            PROTOCOL_VERSION,
            Command.PING,
        )
        checksum = cls.checksum16(header)
        return header + struct.pack("<H", checksum)

    @classmethod
    def build_load_samples_packet(
        cls,
        sample_rate_hz: int,
        samples: list[int],
    ) -> bytes:
        # 샘플 데이터가 비어 있으면 전송할 의미가 없음
        if not samples:
            raise ValueError("samples must not be empty")

        # sample_count 필드가 uint16이므로 최대 65535개까지 허용
        if len(samples) > 65535:
            raise ValueError("sample count exceeds uint16 range")

        # 샘플 배열을 little-endian uint16 바이트열로 직렬화
        samples_blob = struct.pack(f"<{len(samples)}H", *samples)

        # 헤더 구성: 매직, 버전, 명령, 샘플레이트, 샘플 개수
        header = struct.pack(
            "<HBBIH",
            MAGIC,
            PROTOCOL_VERSION,
            Command.LOAD_SAMPLES,
            sample_rate_hz,
            len(samples),
        )

        body = header + samples_blob
        checksum = cls.checksum16(body)

        return body + struct.pack("<H", checksum)

    @classmethod
    def build_start_packet(cls) -> bytes:
        # START 명령 패킷 생성
        body = struct.pack(
            "<HBB",
            MAGIC,
            PROTOCOL_VERSION,
            Command.START,
        )
        checksum = cls.checksum16(body)
        return body + struct.pack("<H", checksum)

    @classmethod
    def build_stop_packet(cls) -> bytes:
        # STOP 명령 패킷 생성
        body = struct.pack(
            "<HBB",
            MAGIC,
            PROTOCOL_VERSION,
            Command.STOP,
        )
        checksum = cls.checksum16(body)
        return body + struct.pack("<H", checksum)