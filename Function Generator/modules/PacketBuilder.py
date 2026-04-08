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
        cls: type["PacketBuilder"],
        sample_rate_hz: int,
        samples: list[int],
        bits: int,
        v_min: float,
        v_max: float,
        flags: int = 0,
    ) -> bytes:
        if not samples:
            raise ValueError("samples must not be empty")

        if len(samples) > 65535:
            raise ValueError("sample count exceeds uint16 range")

        if not (1 <= bits <= 16):
            raise ValueError("bits must be between 1 and 16")

        samples_blob: bytes = struct.pack(f"<{len(samples)}H", *samples)

        # header:
        # magic(2) version(1) cmd(1)
        # sample_rate(4) sample_count(2) bits(1) flags(1) v_min(4) v_max(4)
        header: bytes = struct.pack(
            "<HBBIHBBff",
            MAGIC,
            PROTOCOL_VERSION,
            Command.LOAD_SAMPLES,
            sample_rate_hz,
            len(samples),
            bits,
            flags,
            v_min,
            v_max,
        )

        body: bytes = header + samples_blob
        checksum: int = cls.checksum16(body)

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