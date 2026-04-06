import serial

from modules.protocol import DEFAULT_TIMEOUT_SEC

class SerialTransport:
    def __init__(self, port: str, baudrate: int = 115200, timeout: float = DEFAULT_TIMEOUT_SEC) -> None:
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self.ser: serial.Serial | None = None               # 실제 시리얼 객체는 open()에서 생성

    def open(self) -> None:
        # 시리얼 포트 열기
        self.ser = serial.Serial(
            port=self.port,
            baudrate=self.baudrate,
            timeout=self.timeout,
        )

    def close(self) -> None:
        # 포트가 열려 있으면 닫기
        if self.ser is not None and self.ser.is_open:
            self.ser.close()

    def write_packet(self, packet: bytes) -> None:
        # 포트가 안 열려 있으면 송신 불가
        if self.ser is None or not self.ser.is_open:
            raise RuntimeError("serial port is not open")

        self.ser.write(packet)                              # 패킷 전송
        self.ser.flush()                                    # 버퍼를 즉시 밀어냄

    def read_line(self) -> str:
        # 포트가 안 열려 있으면 수신 불가
        if self.ser is None or not self.ser.is_open:
            raise RuntimeError("serial port is not open")

        raw = self.ser.readline()                           # 줄 단위 수신
        return raw.decode("utf-8", errors="replace").strip()