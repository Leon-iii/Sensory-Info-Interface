from __future__ import annotations

import time

import tkinter as tk
from tkinter import ttk, messagebox

import serial
import serial.tools.list_ports

from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure

# 프로젝트 내부 모듈 import
from modules import WaveformGenerator, Quantizer, PacketBuilder, SerialTransport


class FunctionGeneratorApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root: tk.Tk = root
        self.root.title("Python Function Generator")
        self.root.geometry("1580x720")

        self.transport: SerialTransport | None = None   # 현재 연결된 시리얼 객체
        self.last_samples_analog: list[float] = []      # 최근 생성한 아날로그 파형 샘플
        self.last_samples_dac: list[int] = []           # 최근 양자화한 DAC 코드값

        self._build_variables()                         # Tkinter 변수 초기화
        self._build_ui()                                # 위젯 생성 및 배치
        self._bind_auto_preview()                       # 자동 프리뷰 콜백 등록
        self.refresh_ports()                            # 시작 시 포트 목록 갱신

        self._safe_auto_preview()                       # 시작 시 최초 프리뷰 출력

    def _build_variables(self) -> None:
        # 시리얼 관련 입력값
        self.port_var = tk.StringVar(value="")
        self.baudrate_var = tk.IntVar(value=115200)

        # 파형 관련 입력값
        self.waveform_var = tk.StringVar(value="sine")
        self.frequency_var = tk.DoubleVar(value=200.0)
        self.sample_rate_var = tk.IntVar(value=10000)
        self.duration_var = tk.DoubleVar(value=0.02)
        self.amplitude_var = tk.DoubleVar(value=1.0)
        self.offset_var = tk.DoubleVar(value=0.0)
        self.duty_var = tk.DoubleVar(value=0.5)

        # 양자화 관련 입력값
        self.quant_bits_var = tk.IntVar(value=12)
        self.quant_min_var = tk.DoubleVar(value=-1.0)
        self.quant_max_var = tk.DoubleVar(value=1.0)

        # 상태 표시줄 텍스트
        self.status_var = tk.StringVar(value="Ready")

    def _bind_auto_preview(self) -> None:
        watched_vars = [
            self.waveform_var,
            self.frequency_var,
            self.sample_rate_var,
            self.duration_var,
            self.amplitude_var,
            self.offset_var,
            self.duty_var,
            self.quant_bits_var,
            self.quant_min_var,
            self.quant_max_var,
        ]

        for var in watched_vars:
            var.trace_add("write", self._on_waveform_param_changed)

    def _on_waveform_param_changed(self, *_args) -> None:
        if hasattr(self, "_preview_after_id") and self._preview_after_id is not None:
            self.root.after_cancel(self._preview_after_id)

        self._preview_after_id = self.root.after(200, self._safe_auto_preview)

    def _safe_auto_preview(self) -> None:
        self._preview_after_id = None
        try:
            analog_values = self._build_waveform()
            self._plot_waveform(analog_values)
            self.status_var.set(f"Preview updated: {len(analog_values)} samples")
        except Exception:
            pass

    def _build_ui(self) -> None:
        # 전체 레이아웃용 메인 프레임
        main_frame = ttk.Frame(self.root, padding=10)
        main_frame.pack(fill="both", expand=True)

        # 좌측: 입력/제어 영역, 우측: 그래프 영역
        left_frame = ttk.Frame(main_frame)
        left_frame.pack(side="left", fill="y", padx=(0, 10))

        right_frame = ttk.Frame(main_frame)
        right_frame.pack(side="right", fill="both", expand=True)

        # 좌측 UI 구성
        self._build_serial_frame(left_frame)
        self._build_waveform_frame(left_frame)
        self._build_quantizer_frame(left_frame)
        self._build_control_frame(left_frame)
        self._build_log_frame(left_frame)

        # 우측 그래프 영역 구성
        self._build_plot_frame(right_frame)

        # 하단 상태 표시줄
        status_bar = ttk.Label(self.root, textvariable=self.status_var, relief="sunken", anchor="w")
        status_bar.pack(side="bottom", fill="x")

    def _build_serial_frame(self, parent: ttk.Frame) -> None:
        # 시리얼 포트 설정 영역
        frame = ttk.LabelFrame(parent, text="Serial", padding=10)
        frame.pack(fill="x", pady=(0, 10))

        ttk.Label(frame, text="Port").grid(row=0, column=0, sticky="w")
        self.port_combo = ttk.Combobox(frame, textvariable=self.port_var, state="readonly", width=24)
        self.port_combo.grid(row=0, column=1, sticky="ew", padx=5)
        ttk.Button(frame, text="Refresh", command=self.refresh_ports).grid(row=0, column=2, padx=5)

        ttk.Label(frame, text="Baud rate").grid(row=1, column=0, sticky="w", pady=(8, 0))
        ttk.Entry(frame, textvariable=self.baudrate_var, width=12).grid(row=1, column=1, sticky="w", padx=5, pady=(8, 0))

        ttk.Button(frame, text="Connect", command=self.connect_port).grid(row=2, column=0, pady=(10, 0), sticky="ew")
        ttk.Button(frame, text="Disconnect", command=self.disconnect_port).grid(row=2, column=1, pady=(10, 0), sticky="ew")

        frame.columnconfigure(1, weight=1)

    def _build_waveform_frame(self, parent: ttk.Frame) -> None:
        # 파형 파라미터 입력 영역
        frame = ttk.LabelFrame(parent, text="Waveform", padding=10)
        frame.pack(fill="x", pady=(0, 10))

        ttk.Label(frame, text="Type").grid(row=0, column=0, sticky="w")
        waveform_combo = ttk.Combobox(
            frame,
            textvariable=self.waveform_var,
            values=["sine", "square"],
            state="readonly",
            width=12,
        )
        waveform_combo.grid(row=0, column=1, sticky="ew", padx=5)
        waveform_combo.bind("<<ComboboxSelected>>", lambda _e: self._update_waveform_ui())

        ttk.Label(frame, text="Frequency (Hz)").grid(row=1, column=0, sticky="w")
        ttk.Entry(frame, textvariable=self.frequency_var).grid(row=1, column=1, sticky="ew", padx=5)

        ttk.Label(frame, text="Sample rate (S/s)").grid(row=2, column=0, sticky="w")
        ttk.Entry(frame, textvariable=self.sample_rate_var).grid(row=2, column=1, sticky="ew", padx=5)

        ttk.Label(frame, text="Duration (s)").grid(row=3, column=0, sticky="w")
        ttk.Entry(frame, textvariable=self.duration_var).grid(row=3, column=1, sticky="ew", padx=5)

        ttk.Label(frame, text="Amplitude").grid(row=4, column=0, sticky="w")
        ttk.Entry(frame, textvariable=self.amplitude_var).grid(row=4, column=1, sticky="ew", padx=5)

        ttk.Label(frame, text="Offset").grid(row=5, column=0, sticky="w")
        ttk.Entry(frame, textvariable=self.offset_var).grid(row=5, column=1, sticky="ew", padx=5)

        # 사각파 전용 Duty 입력칸
        self.duty_label = ttk.Label(frame, text="Duty (0~1)")
        self.duty_label.grid(row=6, column=0, sticky="w")
        self.duty_entry = ttk.Entry(frame, textvariable=self.duty_var)
        self.duty_entry.grid(row=6, column=1, sticky="ew", padx=5)

        ttk.Button(frame, text="Preview", command=self.preview_waveform).grid(row=7, column=0, pady=(10, 0), sticky="ew")
        ttk.Button(frame, text="Generate", command=self.generate_waveform).grid(row=7, column=1, pady=(10, 0), sticky="ew")

        frame.columnconfigure(1, weight=1)
        self._update_waveform_ui()  # 초기 선택값에 맞춰 Duty 입력칸 활성화 여부 반영

    def _build_quantizer_frame(self, parent: ttk.Frame) -> None:
        # 양자화 파라미터 입력 영역
        frame = ttk.LabelFrame(parent, text="Quantizer", padding=10)
        frame.pack(fill="x", pady=(0, 10))

        ttk.Label(frame, text="Bits").grid(row=0, column=0, sticky="w")
        ttk.Entry(frame, textvariable=self.quant_bits_var).grid(row=0, column=1, sticky="ew", padx=5)

        ttk.Label(frame, text="V min").grid(row=1, column=0, sticky="w")
        ttk.Entry(frame, textvariable=self.quant_min_var).grid(row=1, column=1, sticky="ew", padx=5)

        ttk.Label(frame, text="V max").grid(row=2, column=0, sticky="w")
        ttk.Entry(frame, textvariable=self.quant_max_var).grid(row=2, column=1, sticky="ew", padx=5)

        frame.columnconfigure(1, weight=1)

    def _build_control_frame(self, parent: ttk.Frame) -> None:
        # 보드로 보낼 명령 버튼 영역
        frame = ttk.LabelFrame(parent, text="Control", padding=10)
        frame.pack(fill="x", pady=(0, 10))

        ttk.Button(frame, text="Send PING", command=self.send_ping).grid(row=0, column=0, sticky="ew", padx=2, pady=2)
        ttk.Button(frame, text="Send LOAD", command=self.send_load).grid(row=0, column=1, sticky="ew", padx=2, pady=2)
        ttk.Button(frame, text="Send START", command=self.send_start).grid(row=1, column=0, sticky="ew", padx=2, pady=2)
        ttk.Button(frame, text="Send STOP", command=self.send_stop).grid(row=1, column=1, sticky="ew", padx=2, pady=2)

        frame.columnconfigure(0, weight=1)
        frame.columnconfigure(1, weight=1)

    def _build_log_frame(self, parent: ttk.Frame) -> None:
        # 로그 출력창 영역
        frame = ttk.LabelFrame(parent, text="Log", padding=10)
        frame.pack(fill="both", expand=True)

        self.log_text = tk.Text(frame, height=14, wrap="word")
        self.log_text.pack(fill="both", expand=True)

    def _build_plot_frame(self, parent: ttk.Frame) -> None:
        # matplotlib 그래프 삽입 영역
        frame = ttk.LabelFrame(parent, text="Preview", padding=10)
        frame.pack(fill="both", expand=True)

        self.figure = Figure(figsize=(7, 5), dpi=100)
        self.ax = self.figure.add_subplot(111)
        self.ax.set_title("Waveform Preview")
        self.ax.set_xlabel("Sample Index")
        self.ax.set_ylabel("Amplitude")
        self.ax.grid(True)

        self.canvas = FigureCanvasTkAgg(self.figure, master=frame)
        self.canvas.get_tk_widget().pack(fill="both", expand=True)

    def _update_waveform_ui(self) -> None:
        # 사각파일 때만 Duty 입력칸 활성화
        is_square = self.waveform_var.get() == "square"
        state = "normal" if is_square else "disabled"
        self.duty_entry.configure(state=state)

    def log(self, message: str) -> None:
        # 로그창과 상태표시줄에 메시지 출력
        timestamp = time.strftime("%H:%M:%S")
        self.log_text.insert("end", f"[{timestamp}] {message}\n")
        self.log_text.see("end")
        self.status_var.set(message)

    def refresh_ports(self) -> None:
        # 현재 시스템의 시리얼 포트 목록 조회
        ports = list(serial.tools.list_ports.comports())
        port_names = [p.device for p in ports]
        self.port_combo["values"] = port_names

        # 현재 선택 포트가 없으면 첫 번째 포트를 기본 선택
        if port_names and not self.port_var.get():
            self.port_var.set(port_names[0])

        self.log(f"Ports refreshed: {port_names if port_names else 'none'}")

    def connect_port(self) -> None:
        try:
            port = self.port_var.get().strip()
            if not port:
                raise ValueError("포트를 선택하세요.")

            # 시리얼 포트 연결
            self.transport = SerialTransport(
                port=port,
                baudrate=self.baudrate_var.get(),
            )
            self.transport.open()
            time.sleep(2.0)  # 일부 보드는 포트 오픈 직후 리셋됨
            self.log(f"Connected to {port}")
        except Exception as e:
            messagebox.showerror("Connection Error", str(e))
            self.log(f"Connect failed: {e}")

    def disconnect_port(self) -> None:
        # 시리얼 포트 연결 해제
        if self.transport is not None:
            self.transport.close()
            self.log("Disconnected")

    def _build_waveform(self) -> list[float]:
        # GUI 입력값을 읽어서 실제 파형 샘플 리스트 생성
        waveform = self.waveform_var.get()
        frequency = self.frequency_var.get()
        sample_rate = self.sample_rate_var.get()
        duration = self.duration_var.get()
        amplitude = self.amplitude_var.get()
        offset = self.offset_var.get()
        duty = self.duty_var.get()

        if waveform == "sine":
            return WaveformGenerator.sine(
                frequency_hz=frequency,
                sample_rate_hz=sample_rate,
                duration_sec=duration,
                amplitude=amplitude,
                offset=offset,
            )

        if waveform == "square":
            return WaveformGenerator.square(
                frequency_hz=frequency,
                sample_rate_hz=sample_rate,
                duration_sec=duration,
                amplitude=amplitude,
                duty=duty,
                offset=offset,
            )

        raise ValueError(f"Unsupported waveform: {waveform}")

    def generate_waveform(self) -> None:
        try:
            # 파형 생성
            analog_values = self._build_waveform()

            # DAC 코드값으로 양자화
            quantizer = Quantizer(
                bits=self.quant_bits_var.get(),
                v_min=self.quant_min_var.get(),
                v_max=self.quant_max_var.get(),
            )
            dac_samples = quantizer.quantize(analog_values)

            # 최근 생성 결과 저장
            self.last_samples_analog = analog_values
            self.last_samples_dac = dac_samples

            self.log(
                f"Generated waveform: type={self.waveform_var.get()}, "
                f"samples={len(dac_samples)}, min={min(dac_samples)}, max={max(dac_samples)}"
            )
            self._plot_waveform(analog_values)
        except Exception as e:
            messagebox.showerror("Generate Error", str(e))
            self.log(f"Generate failed: {e}")

    def preview_waveform(self) -> None:
        try:
            # 양자화 없이 파형만 미리보기
            analog_values = self._build_waveform()
            self._plot_waveform(analog_values)
            self.log(f"Preview updated: {len(analog_values)} samples")
        except Exception as e:
            messagebox.showerror("Preview Error", str(e))
            self.log(f"Preview failed: {e}")

    def _plot_waveform(self, samples: list[float]) -> None:
        # 그래프 영역 초기화
        self.ax.clear()
        self.ax.set_title("Waveform Preview")
        self.ax.set_xlabel("Sample Index")
        self.ax.set_ylabel("Amplitude")
        self.ax.grid(True)

        # 너무 많은 샘플은 앞부분만 일부 표시
        preview_count = min(len(samples), 2000)
        self.ax.plot(range(preview_count), samples[:preview_count])

        self.canvas.draw()

    def _require_transport(self) -> SerialTransport:
        # 포트가 연결되어 있는지 확인
        if self.transport is None or not self.transport.is_open():
            raise RuntimeError("시리얼 포트가 연결되어 있지 않습니다.")
        return self.transport

    def send_ping(self) -> None:
        try:
            # 연결 확인용 PING 패킷 전송
            transport = self._require_transport()
            packet = PacketBuilder.build_ping_packet()
            transport.write_packet(packet)
            self.log(f"PING sent ({len(packet)} bytes)")
        except Exception as e:
            messagebox.showerror("PING Error", str(e))
            self.log(f"PING failed: {e}")

    def send_load(self) -> None:
        try:
            transport = self._require_transport()

            # 아직 샘플이 없으면 먼저 생성
            if not self.last_samples_dac:
                self.generate_waveform()

            if not self.last_samples_dac:
                raise RuntimeError("전송할 샘플이 없습니다.")

            # 샘플 데이터 패킷 전송
            packet = PacketBuilder.build_load_samples_packet(
                sample_rate_hz=self.sample_rate_var.get(),
                samples=self.last_samples_dac,
            )
            transport.write_packet(packet)
            self.log(f"LOAD sent ({len(packet)} bytes, {len(self.last_samples_dac)} samples)")
        except Exception as e:
            messagebox.showerror("LOAD Error", str(e))
            self.log(f"LOAD failed: {e}")

    def send_start(self) -> None:
        try:
            # 재생 시작 패킷 전송
            transport = self._require_transport()
            packet = PacketBuilder.build_start_packet()
            transport.write_packet(packet)
            self.log(f"START sent ({len(packet)} bytes)")
        except Exception as e:
            messagebox.showerror("START Error", str(e))
            self.log(f"START failed: {e}")

    def send_stop(self) -> None:
        try:
            # 재생 정지 패킷 전송
            transport = self._require_transport()
            packet = PacketBuilder.build_stop_packet()
            transport.write_packet(packet)
            self.log(f"STOP sent ({len(packet)} bytes)")
        except Exception as e:
            messagebox.showerror("STOP Error", str(e))
            self.log(f"STOP failed: {e}")


def main() -> None:
    # Tkinter 앱 시작점
    root = tk.Tk()
    app = FunctionGeneratorApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()