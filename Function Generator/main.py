from __future__ import annotations

import time

import tkinter as tk
from tkinter import ttk, messagebox

import serial
import serial.tools.list_ports

from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
import matplotlib.ticker as mticker

# 프로젝트 내부 모듈 import
from modules import WaveformGenerator, Quantizer, PacketBuilder, SerialTransport


class FunctionGeneratorApp:
    def __init__(self, root: tk.Tk) -> None:
        """메인 GUI 애플리케이션을 초기화하고, UI/이벤트/초기 프리뷰를 구성한다."""
        self.root: tk.Tk = root
        self.root.title("Python Function Generator")
        self.root.geometry("1580x800")

        self.transport: SerialTransport | None = None
        self.last_samples_analog: list[float] = []
        self.last_samples_dac: list[int] = []

        self._last_tx_time: float | None = None

        self._build_variables()
        self._build_ui()
        self._bind_quantizer_events()
        self._bind_auto_preview()

        self.refresh_ports()
        self._update_connection_ui()
        self._safe_auto_preview()

    def _build_variables(self) -> None:
        """Tkinter 변수와 상태값을 한곳에서 초기화한다."""
        # 시리얼 관련 입력값
        self.port_var = tk.StringVar(value="")
        self.baudrate_var = tk.IntVar(value=115200)

        # 파형 관련 입력값
        self.waveform_var = tk.StringVar(value="Sine")
        self.frequency_var = tk.DoubleVar(value=200.0)
        self.phase_var = tk.DoubleVar(value=0.0)
        self.sample_rate_var = tk.IntVar(value=10000)
        self.duration_var = tk.DoubleVar(value=0.02)
        self.amplitude_var = tk.DoubleVar(value=1.0)
        self.offset_var = tk.DoubleVar(value=0.0)
        self.duty_var = tk.DoubleVar(value=0.5)

        # 양자화 관련 입력값
        self.quant_bits_var = tk.IntVar(value=12)
        self.quant_codes_var = tk.StringVar(value=str(2 ** self.quant_bits_var.get()))

        self.quant_min_var = tk.DoubleVar(value=-1.0)
        self.quant_max_var = tk.DoubleVar(value=1.0)
        self.quant_auto_var = tk.BooleanVar(value=False)

        # 로그 출력 관련 체크 상태값
        self.show_packet_preview_var = tk.BooleanVar(value=True)
        self.max_preview_length_var = tk.IntVar(value=64)
        self.listen_board_response_var = tk.BooleanVar(value=True)
        self.display_latency_var = tk.BooleanVar(value=True)

        # 상태 표시줄 텍스트
        self.status_var = tk.StringVar(value="Ready")

    def _build_ui(self) -> None:
        """전체 UI 프레임과 하위 섹션을 생성하여 배치한다."""
        main_frame = ttk.Frame(self.root, padding=10)
        main_frame.pack(fill="both", expand=True)

        left_frame = ttk.Frame(main_frame)
        left_frame.pack(side="left", fill="y", padx=(0, 10))

        right_frame = ttk.Frame(main_frame)
        right_frame.pack(side="right", fill="both", expand=True)

        self._build_serial_frame(left_frame)
        self._build_waveform_frame(left_frame)
        self._build_quantizer_frame(left_frame)
        self._build_control_frame(left_frame)
        self._build_log_frame(left_frame)

        self._build_plot_frame(right_frame)

        status_bar = ttk.Label(self.root, textvariable=self.status_var, relief="sunken", anchor="w")
        status_bar.pack(side="bottom", fill="x")

    def _build_serial_frame(self, parent: ttk.Frame) -> None:
        """시리얼 포트 선택, baud rate 설정, 연결 버튼 영역을 만든다."""
        frame = ttk.LabelFrame(parent, text="Serial", padding=10)
        frame.pack(fill="x", pady=(0, 10))

        frame.columnconfigure(0, weight=1, uniform="serial_half")
        frame.columnconfigure(1, weight=1, uniform="serial_half")

        left_frame = ttk.Frame(frame, padding=0)
        left_frame.grid(row=0, column=0, rowspan=2, sticky="nsew", padx=(0, 5))

        left_frame.columnconfigure(0, weight=0)
        left_frame.columnconfigure(1, weight=1)

        ttk.Label(left_frame, text="Port").grid(row=0, column=0, sticky="w", pady=(2, 0))
        self.port_combo = ttk.Combobox(
            left_frame,
            textvariable=self.port_var,
            state="readonly",
        )
        self.port_combo.grid(row=0, column=1, sticky="ew", padx=(5, 0), pady=(2, 0))

        ttk.Label(left_frame, text="Baud rate (bit/s)").grid(row=1, column=0, sticky="w", pady=(6, 0))
        ttk.Entry(left_frame, textvariable=self.baudrate_var).grid(
            row=1, column=1, sticky="ew", padx=(5, 0), pady=(6, 0)
        )

        self.refresh_button = ttk.Button(frame, text="Refresh", command=self.refresh_ports)
        self.refresh_button.grid(row=0, column=1, sticky="ew", padx=(5, 0))

        bottom_right = ttk.Frame(frame, padding=0)
        bottom_right.grid(row=1, column=1, sticky="ew", padx=(5, 0), pady=(3, 0))
        bottom_right.columnconfigure(0, weight=1, uniform="serial_btn")
        bottom_right.columnconfigure(1, weight=1, uniform="serial_btn")

        self.connect_button = ttk.Button(bottom_right, text="Connect", command=self.connect_port)
        self.connect_button.grid(row=0, column=0, sticky="ew", padx=(0, 5))

        self.disconnect_button = ttk.Button(bottom_right, text="Disconnect", command=self.disconnect_port)
        self.disconnect_button.grid(row=0, column=1, sticky="ew", padx=(5, 0))

    def _build_waveform_frame(self, parent: ttk.Frame) -> None:
        """파형 종류와 생성 파라미터를 입력하는 UI를 만든다."""
        frame = ttk.LabelFrame(parent, text="Waveform", padding=10)
        frame.pack(fill="x", pady=(0, 10))

        label_width = 16

        type_frame = ttk.Frame(frame, padding=0)
        type_frame.pack(fill="x")

        type_frame.columnconfigure(0, weight=0)
        type_frame.columnconfigure(1, weight=1)

        ttk.Label(type_frame, text="Type", width=label_width).grid(row=0, column=0, sticky="w")
        waveform_combo = ttk.Combobox(
            type_frame,
            textvariable=self.waveform_var,
            values=["Sine", "Square", "Sawtooth", "Sawtooth (Reverse)", "Triangle"],
            state="readonly",
        )
        waveform_combo.grid(row=0, column=1, sticky="ew", padx=(5, 0))
        waveform_combo.bind("<<ComboboxSelected>>", lambda _e: self._update_waveform_ui())

        middle_frame = ttk.Frame(frame, padding=0)
        middle_frame.pack(fill="x", pady=(4, 0))

        middle_frame.columnconfigure(0, weight=1, uniform="wave_mid_half")
        middle_frame.columnconfigure(1, weight=1, uniform="wave_mid_half")

        left_fields = ttk.Frame(middle_frame, padding=0)
        left_fields.grid(row=0, column=0, sticky="nsew", padx=(0, 5))
        left_fields.columnconfigure(0, weight=0)
        left_fields.columnconfigure(1, weight=1)

        right_fields = ttk.Frame(middle_frame, padding=0)
        right_fields.grid(row=0, column=1, sticky="nsew", padx=(5, 0))
        right_fields.columnconfigure(0, weight=0)
        right_fields.columnconfigure(1, weight=1)

        ttk.Label(left_fields, text="Frequency (Hz)", width=label_width).grid(row=0, column=0, sticky="w")
        ttk.Entry(left_fields, textvariable=self.frequency_var).grid(
            row=0, column=1, sticky="ew", padx=(5, 0)
        )

        ttk.Label(left_fields, text="Sample rate (S/s)", width=label_width).grid(row=1, column=0, sticky="w", pady=(4, 0))
        ttk.Entry(left_fields, textvariable=self.sample_rate_var).grid(
            row=1, column=1, sticky="ew", padx=(5, 0), pady=(4, 0)
        )

        ttk.Label(left_fields, text="Amplitude", width=label_width).grid(row=2, column=0, sticky="w", pady=(4, 0))
        ttk.Entry(left_fields, textvariable=self.amplitude_var).grid(
            row=2, column=1, sticky="ew", padx=(5, 0), pady=(4, 0)
        )

        ttk.Label(right_fields, text="Phase (Deg)", width=label_width).grid(row=0, column=0, sticky="w")
        ttk.Entry(right_fields, textvariable=self.phase_var).grid(
            row=0, column=1, sticky="ew", padx=(5, 0)
        )

        ttk.Label(right_fields, text="Duration (s)", width=label_width).grid(row=1, column=0, sticky="w", pady=(4, 0))
        ttk.Entry(right_fields, textvariable=self.duration_var).grid(
            row=1, column=1, sticky="ew", padx=(5, 0), pady=(4, 0)
        )

        ttk.Label(right_fields, text="Offset", width=label_width).grid(row=2, column=0, sticky="w", pady=(4, 0))
        ttk.Entry(right_fields, textvariable=self.offset_var).grid(
            row=2, column=1, sticky="ew", padx=(5, 0), pady=(4, 0)
        )

        duty_frame = ttk.Frame(frame, padding=0)
        duty_frame.pack(fill="x", pady=(4, 0))

        duty_frame.columnconfigure(0, weight=0)
        duty_frame.columnconfigure(1, weight=1)

        self.duty_label = ttk.Label(duty_frame, text="Duty (0~1)", width=label_width)
        self.duty_label.grid(row=0, column=0, sticky="w")

        self.duty_entry = ttk.Entry(duty_frame, textvariable=self.duty_var)
        self.duty_entry.grid(row=0, column=1, sticky="ew", padx=(5, 0))

        button_frame = ttk.Frame(frame, padding=0)
        button_frame.pack(fill="x", pady=(10, 0))
        button_frame.columnconfigure(0, weight=1, uniform="wave_btn")
        button_frame.columnconfigure(1, weight=1, uniform="wave_btn")

        ttk.Button(button_frame, text="Preview", command=self.preview_waveform).grid(
            row=0, column=0, sticky="ew", padx=(0, 5)
        )
        ttk.Button(button_frame, text="Generate", command=self.generate_waveform).grid(
            row=0, column=1, sticky="ew", padx=(5, 0)
        )

        self._update_waveform_ui()

    def _update_waveform_ui(self) -> None:
        """현재 파형 종류에 따라 Duty 입력칸 활성화 상태를 갱신한다."""
        is_square = self.waveform_var.get() == "Square"
        state = "normal" if is_square else "disabled"
        self.duty_entry.configure(state=state)

    def _build_quantizer_frame(self, parent: ttk.Frame) -> None:
        """양자화 비트 수와 샘플링 범위를 설정하는 UI를 만든다."""
        frame = ttk.LabelFrame(parent, text="Quantizer", padding=10)
        frame.pack(fill="x", pady=(0, 10))

        frame.columnconfigure(0, weight=0)
        frame.columnconfigure(1, weight=1, uniform="quant")
        frame.columnconfigure(2, weight=0)
        frame.columnconfigure(3, weight=1, uniform="quant")
        frame.columnconfigure(4, weight=0)
        frame.columnconfigure(5, weight=0)

        ttk.Label(frame, text="Bits").grid(row=0, column=0, sticky="w")

        ttk.Entry(frame, textvariable=self.quant_bits_var, width=10).grid(
            row=0, column=1, columnspan=3, sticky="ew", padx=(5, 10)
        )

        ttk.Label(frame, textvariable=self.quant_codes_var).grid(
            row=0, column=4, columnspan=2, sticky="w"
        )

        ttk.Label(frame, text="Sampling Range").grid(
            row=1, column=0, sticky="w", pady=(8, 0)
        )

        self.quant_min_entry = ttk.Entry(frame, textvariable=self.quant_min_var, width=10)
        self.quant_min_entry.grid(
            row=1, column=1, sticky="ew", padx=(5, 5), pady=(8, 0)
        )

        ttk.Label(frame, text="~").grid(
            row=1, column=2, sticky="ew", pady=(8, 0)
        )

        self.quant_max_entry = ttk.Entry(frame, textvariable=self.quant_max_var, width=10)
        self.quant_max_entry.grid(
            row=1, column=3, sticky="ew", padx=(5, 10), pady=(8, 0)
        )

        ttk.Label(frame, text="Auto").grid(
            row=1, column=4, sticky="e", padx=(4, 0), pady=(8, 0)
        )

        ttk.Checkbutton(frame, variable=self.quant_auto_var).grid(
            row=1, column=5, sticky="e", pady=(8, 0)
        )

    def _bind_quantizer_events(self) -> None:
        """양자화 관련 변수 변경 이벤트를 등록하고 초기 상태를 맞춘다."""
        self.quant_bits_var.trace_add("write", self._on_bits_changed)
        self.quant_auto_var.trace_add("write", self._on_quant_auto_changed)

        watched_wave_vars = [
            self.waveform_var,
            self.frequency_var,
            self.phase_var,
            self.sample_rate_var,
            self.duration_var,
            self.amplitude_var,
            self.offset_var,
            self.duty_var,
        ]
        for var in watched_wave_vars:
            var.trace_add("write", self._on_waveform_params_changed_for_auto_range)

        self._update_codes_field()
        self._update_quantizer_ui_state()

    def _on_bits_changed(self, *_args) -> None:
        """헬퍼: bits 값 변경 시 코드 수 표시를 다시 계산한다."""
        self._update_codes_field()

    def _update_codes_field(self) -> None:
        """헬퍼: 현재 bits 값을 '(N Codes)' 형식의 문자열로 갱신한다."""
        try:
            bits = self.quant_bits_var.get()
            if bits < 1:
                self.quant_codes_var.set("")
                return
            self.quant_codes_var.set(f"({2 ** bits} Codes)")
        except Exception:
            self.quant_codes_var.set("")

    def _on_quant_auto_changed(self, *_args) -> None:
        """헬퍼: Auto 체크 상태 변경에 맞춰 UI와 범위를 갱신한다."""
        self._update_quantizer_ui_state()
        if self.quant_auto_var.get():
            self._auto_set_sampling_range()

    def _update_quantizer_ui_state(self) -> None:
        """헬퍼: Auto 여부에 따라 V min / V max 입력 필드의 상태를 바꾼다."""
        state = "disabled" if self.quant_auto_var.get() else "normal"
        self.quant_min_entry.configure(state=state)
        self.quant_max_entry.configure(state=state)

    def _on_waveform_params_changed_for_auto_range(self, *_args) -> None:
        """헬퍼: Auto 모드일 때 파형 관련 값이 바뀌면 범위를 자동 갱신한다."""
        if not self.quant_auto_var.get():
            return

        try:
            self._auto_set_sampling_range()
        except Exception:
            pass

    def _auto_set_sampling_range(self) -> None:
        """헬퍼: 현재 파형 샘플의 최소/최대값으로 Sampling Range를 자동 설정한다."""
        samples = self._build_waveform()
        if not samples:
            return

        v_min = min(samples)
        v_max = max(samples)

        self.quant_min_var.set(round(v_min, 6))
        self.quant_max_var.set(round(v_max, 6))

    def _validate_quant_range(self) -> None:
        """헬퍼: V max가 V min보다 작지 않은지 검증한다."""
        v_min = self.quant_min_var.get()
        v_max = self.quant_max_var.get()

        if v_max < v_min:
            raise ValueError("V max must not be smaller than V min.")

    def _build_control_frame(self, parent: ttk.Frame) -> None:
        """보드에 제어 패킷을 전송하는 버튼 패널을 만든다."""
        frame = ttk.LabelFrame(parent, text="Control", padding=10)
        frame.pack(fill="x", pady=(0, 10))

        frame.columnconfigure(0, weight=1)
        frame.columnconfigure(1, weight=1)
        frame.columnconfigure(2, weight=0)
        frame.columnconfigure(3, weight=1)
        frame.columnconfigure(4, weight=1)

        self.ping_button = ttk.Button(frame, text="Send PING", command=self.send_ping)
        self.ping_button.grid(row=0, column=0, sticky="ew", padx=2, pady=2)

        self.load_button = ttk.Button(frame, text="Send LOAD", command=self.send_load)
        self.load_button.grid(row=0, column=1, sticky="ew", padx=2, pady=2)

        ttk.Separator(frame, orient="vertical").grid(row=0, column=2, sticky="ns", padx=6)

        self.start_button = ttk.Button(frame, text="Send START", command=self.send_start)
        self.start_button.grid(row=0, column=3, sticky="ew", padx=2, pady=2)

        self.stop_button = ttk.Button(frame, text="Send STOP", command=self.send_stop)
        self.stop_button.grid(row=0, column=4, sticky="ew", padx=2, pady=2)

        frame.columnconfigure(0, weight=1)
        frame.columnconfigure(1, weight=1)

    def _update_connection_ui(self) -> None:
        """연결 상태에 따라 버튼, 체크박스, 입력 필드의 활성화를 갱신한다."""
        connected = self.transport is not None and self.transport.is_open()

        if connected:
            self.connect_button.configure(state="disabled")
            self.disconnect_button.configure(state="normal")

            self.ping_button.configure(state="normal")
            self.load_button.configure(state="normal")
            self.start_button.configure(state="normal")
            self.stop_button.configure(state="normal")

            self.show_packet_preview_check.configure(state="normal")
            self.max_preview_length_entry.configure(state="normal")
            self.listen_board_response_check.configure(state="normal")
            self.display_latency_check.configure(state="normal")
        else:
            self.connect_button.configure(state="normal")
            self.disconnect_button.configure(state="disabled")

            self.ping_button.configure(state="disabled")
            self.load_button.configure(state="disabled")
            self.start_button.configure(state="disabled")
            self.stop_button.configure(state="disabled")

            self.show_packet_preview_check.configure(state="disabled")
            self.max_preview_length_entry.configure(state="disabled")
            self.listen_board_response_check.configure(state="disabled")
            self.display_latency_check.configure(state="disabled")

    def _build_log_frame(self, parent: ttk.Frame) -> None:
        """로그 출력창과 로그 표시 옵션 UI를 만든다."""
        frame = ttk.LabelFrame(parent, text="Log", padding=10)
        frame.pack(fill="both", expand=True)

        option_frame = ttk.Frame(frame, padding=0)
        option_frame.pack(fill="x", pady=(0, 8))

        option_frame.columnconfigure(0, weight=3, uniform="label")
        option_frame.columnconfigure(1, weight=1, uniform="field")
        option_frame.columnconfigure(2, weight=0)
        option_frame.columnconfigure(3, weight=3, uniform="label")
        option_frame.columnconfigure(4, weight=1, uniform="field")

        ttk.Separator(option_frame, orient="vertical").grid(
            row=0, column=2, rowspan=2, sticky="ns", padx=12
        )

        ttk.Label(option_frame, text="Show Packet Preview").grid(
            row=0, column=0, sticky="w"
        )
        self.show_packet_preview_check = ttk.Checkbutton(
            option_frame,
            variable=self.show_packet_preview_var,
        )
        self.show_packet_preview_check.grid(
            row=0, column=1, sticky="e", padx=(6, 0)
        )

        ttk.Label(option_frame, text="Listen Board Response").grid(
            row=0, column=3, sticky="w"
        )
        self.listen_board_response_check = ttk.Checkbutton(
            option_frame,
            variable=self.listen_board_response_var,
            command=self._on_listen_board_response_changed,
        )
        self.listen_board_response_check.grid(
            row=0, column=4, sticky="e", padx=(6, 0)
        )

        ttk.Label(option_frame, text="Max Preview Length (Bytes)").grid(
            row=1, column=0, sticky="w", pady=(6, 0)
        )

        vcmd = (self.root.register(self._validate_positive_int), "%P")
        self.max_preview_length_entry = ttk.Entry(
            option_frame,
            textvariable=self.max_preview_length_var,
            validate="key",
            validatecommand=vcmd,
            width=10,
        )
        self.max_preview_length_entry.grid(
            row=1, column=1, sticky="ew", padx=(6, 0), pady=(6, 0)
        )

        ttk.Label(option_frame, text="Display Response Latency").grid(
            row=1, column=3, sticky="w", pady=(6, 0)
        )
        self.display_latency_check = ttk.Checkbutton(
            option_frame,
            variable=self.display_latency_var,
        )
        self.display_latency_check.grid(
            row=1, column=4, sticky="e", padx=(6, 0), pady=(6, 0)
        )

        self.log_text = tk.Text(frame, height=14, wrap="word")
        self.log_text.pack(fill="both", expand=True)

        self.log_text.tag_configure("system", foreground="black")
        self.log_text.tag_configure("system_error", foreground="red")
        self.log_text.tag_configure("tx", foreground="darkred")
        self.log_text.tag_configure("rx", foreground="darkblue")

    def _on_listen_board_response_changed(self) -> None:
        """헬퍼: 보드 응답 청취 체크 시 조건이 맞으면 폴링을 시작한다."""
        if self._should_poll_serial():
            self._poll_serial_messages()

    def _should_poll_serial(self) -> bool:
        """헬퍼: 보드 응답 폴링이 가능한 상태인지 검사한다."""
        return (
            self.listen_board_response_var.get()
            and self.transport is not None
            and self.transport.is_open()
        )

    def _poll_serial_messages(self) -> None:
        """보드에서 들어오는 줄 단위 응답을 읽어 로그에 기록한다."""
        if not self._should_poll_serial():
            return

        try:
            if self.transport is not None and self.transport.is_open():
                response = self.transport.read_line()
                if response:
                    if self._last_tx_time is not None and self.display_latency_var.get():
                        latency_ms = (time.perf_counter() - self._last_tx_time) * 1000.0
                        self.log(f"Board ({latency_ms:.1f} ms): {response}", kind="rx")
                        self._last_tx_time = None
                    else:
                        self.log(f"Board: {response}", kind="rx")
                        self._last_tx_time = None
        except Exception:
            pass

        if self._should_poll_serial():
            self.root.after(100, self._poll_serial_messages)

    def _validate_positive_int(self, proposed: str) -> bool:
        """헬퍼: 로그 프리뷰 길이 입력이 자연수인지 검증한다."""
        if proposed == "":
            return True

        if not proposed.isdigit():
            return False

        return int(proposed) > 0

    def _log_packet_preview(self, _name: str, packet: bytes) -> None:
        """헬퍼: 설정이 켜져 있으면 패킷을 16진수 프리뷰로 로그에 남긴다."""
        if not self.show_packet_preview_var.get():
            return

        try:
            max_len = self.max_preview_length_var.get()
        except Exception:
            max_len = 64

        if max_len <= 0:
            return

        preview = packet[:max_len]
        hex_text = preview.hex(" ").upper()

        if len(packet) > max_len:
            remaining = len(packet) - max_len
            hex_text += f" ... (+ {remaining} Bytes)"

        self.log(hex_text, kind="tx")

    def log(self, message: str, kind: str = "system") -> None:
        """지정한 종류의 로그를 타임스탬프와 함께 로그 창에 출력한다."""
        timestamp = time.strftime("%H:%M:%S")
        line = f"[{timestamp}] {message}\n"

        self.log_text.insert("end", line, kind)
        self.log_text.see("end")
        self.status_var.set(message)

    def _build_plot_frame(self, parent: ttk.Frame) -> None:
        """파형 미리보기를 표시할 matplotlib 캔버스를 초기화한다."""
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

    def refresh_ports(self) -> None:
        """사용 가능한 시리얼 포트 목록을 새로 읽어 콤보박스에 반영한다."""
        ports = list(serial.tools.list_ports.comports())
        port_names = [p.device for p in ports]
        self.port_combo["values"] = port_names

        if port_names and not self.port_var.get():
            self.port_var.set(port_names[0])
        elif not port_names:
            self.port_var.set("")

        self.log(f"Ports refreshed: {port_names if port_names else 'none'}", kind="system")

    def connect_port(self) -> None:
        """선택한 포트를 열고, PING/PONG 핸드셰이크를 통해 보드 연결을 검증한다."""
        try:
            port = self.port_var.get().strip()
            if not port:
                raise ValueError("포트를 선택하세요.")

            self.transport = SerialTransport(
                port=port,
                baudrate=self.baudrate_var.get(),
                timeout=0.1,
            )
            self.transport.open()
            time.sleep(2.0)

            self.log(f"Port opened: {port}", kind="system")

            if not self._handshake_with_board():
                self.transport.close()
                self.transport = None
                raise RuntimeError(f"No valid board response(PONG) from {port}.")

            self.log(f"Board connected on {port}", kind="system")

            if self._should_poll_serial():
                self._poll_serial_messages()

            self._update_connection_ui()

        except Exception as e:
            messagebox.showerror("Connection Error", str(e))
            self.log(f"Connect failed: {e}", kind="system_error")

            if self.transport is not None:
                try:
                    self.transport.close()
                except Exception:
                    pass
                self.transport = None

            self._update_connection_ui()

    def _handshake_with_board(self) -> bool:
        """헬퍼: 연결 직후 PING을 보내고 PONG 응답으로 유효한 보드인지 확인한다."""
        if self.transport is None or not self.transport.is_open():
            return False

        try:
            packet = PacketBuilder.build_ping_packet()
            self.transport.write_packet(packet)

            deadline = time.time() + 1.0
            while time.time() < deadline:
                response = self.transport.read_line()
                if response and response.strip() == "PONG":
                    return True

            return False
        except Exception:
            return False

    def disconnect_port(self) -> None:
        """현재 열린 시리얼 포트를 닫고 UI 상태를 갱신한다."""
        if self.transport is not None:
            self.transport.close()
            self.log("Disconnected", kind="system")

        self._update_connection_ui()

    def _build_waveform(self) -> list[float]:
        """현재 GUI 입력값을 읽어 선택된 파형의 샘플 리스트를 생성한다."""
        waveform = self.waveform_var.get()
        phase = self.phase_var.get()
        frequency = self.frequency_var.get()
        sample_rate = self.sample_rate_var.get()
        duration = self.duration_var.get()
        amplitude = self.amplitude_var.get()
        offset = self.offset_var.get()
        duty = self.duty_var.get()

        if waveform == "Sine":
            return WaveformGenerator.sine(
                frequency_hz=frequency,
                phase_deg=phase,
                sample_rate_hz=sample_rate,
                duration_sec=duration,
                amplitude=amplitude,
                offset=offset,
            )

        if waveform == "Square":
            return WaveformGenerator.square(
                frequency_hz=frequency,
                phase_deg=phase,
                sample_rate_hz=sample_rate,
                duration_sec=duration,
                amplitude=amplitude,
                duty=duty,
                offset=offset,
            )

        if waveform == "Sawtooth":
            return WaveformGenerator.sawtooth(
                frequency_hz=frequency,
                sample_rate_hz=sample_rate,
                duration_sec=duration,
                amplitude=amplitude,
                phase_deg=phase,
                offset=offset,
            )

        if waveform == "Sawtooth (Reverse)":
            return WaveformGenerator.reverse_sawtooth(
                frequency_hz=frequency,
                sample_rate_hz=sample_rate,
                duration_sec=duration,
                amplitude=amplitude,
                phase_deg=phase,
                offset=offset,
            )

        if waveform == "Triangle":
            return WaveformGenerator.triangle(
                frequency_hz=frequency,
                sample_rate_hz=sample_rate,
                duration_sec=duration,
                amplitude=amplitude,
                phase_deg=phase,
                offset=offset,
            )

        raise ValueError(f"Unsupported waveform: {waveform}")

    def _bind_auto_preview(self) -> None:
        """자동 프리뷰 갱신이 필요한 변수들에 변경 감지 콜백을 등록한다."""
        watched_vars = [
            self.waveform_var,
            self.frequency_var,
            self.phase_var,
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
        """헬퍼: 입력값이 바뀌면 예약된 자동 프리뷰를 재설정한다."""
        if hasattr(self, "_preview_after_id") and self._preview_after_id is not None:
            self.root.after_cancel(self._preview_after_id)

        self._preview_after_id = self.root.after(200, self._safe_auto_preview)

    def _safe_auto_preview(self) -> None:
        """헬퍼: 예외를 무시하면서 현재 파형을 자동 프리뷰로 갱신한다."""
        self._preview_after_id = None
        try:
            analog_values = self._build_waveform()
            self._plot_waveform(analog_values)
            self.status_var.set(f"Preview updated: {len(analog_values)} samples")
        except Exception:
            pass

    def generate_waveform(self) -> None:
        """현재 설정으로 파형을 생성하고 양자화 결과를 내부 버퍼에 저장한다."""
        try:
            analog_values = self._build_waveform()

            self._validate_quant_range()

            quantizer = Quantizer(
                bits=self.quant_bits_var.get(),
                v_min=self.quant_min_var.get(),
                v_max=self.quant_max_var.get(),
            )
            dac_samples = quantizer.quantize(analog_values)

            self.last_samples_analog = analog_values
            self.last_samples_dac = dac_samples

            self.log(
                f"Generated waveform: type={self.waveform_var.get()}, "
                f"samples={len(dac_samples)}, min={min(dac_samples)}, max={max(dac_samples)}"
            )
            self._plot_waveform(analog_values)
        except Exception as e:
            messagebox.showerror("Generate Error", str(e))
            self.log(f"Generate failed: {e}", kind="system_error")

    def preview_waveform(self) -> None:
        """양자화 없이 현재 파형을 미리보기 그래프로 즉시 갱신한다."""
        try:
            analog_values = self._build_waveform()
            self._plot_waveform(analog_values)
            self.log(f"Preview updated: {len(analog_values)} samples")
        except Exception as e:
            messagebox.showerror("Preview Error", str(e))
            self.log(f"Preview failed: {e}", kind="system_error")

    def _plot_waveform(self, samples: list[float]) -> None:
        """헬퍼: 파형 샘플을 시간축/인덱스축과 함께 그래프에 그린다."""
        self.ax.clear()
        self.ax.set_ylabel("Amplitude")
        self.ax.grid(True)

        sample_rate = self.sample_rate_var.get()
        frequency = self.frequency_var.get()
        phase_deg = self.phase_var.get()

        if sample_rate <= 0 or not samples:
            self.canvas.draw()
            return

        t_shift = -phase_deg / (360.0 * frequency) if frequency != 0 else 0.0

        preview_count = min(len(samples), 2000)

        plot_times = [(i / sample_rate) + t_shift for i in range(preview_count)]
        plot_samples = samples[:preview_count]

        self.ax.plot(plot_times, plot_samples, color="red", linewidth=0.9)

        visible_left = 0.0
        visible_right = max(0.0, max(plot_times))
        self.ax.set_xlim(left=visible_left, right=visible_right)

        self.ax.yaxis.set_major_locator(mticker.MaxNLocator(nbins=5))

        self.ax.xaxis.set_label_position("top")
        self.ax.xaxis.tick_top()

        self.figure.canvas.draw()

        ticks = self.ax.get_xticks()
        if len(ticks) >= 2:
            step = abs(ticks[1] - ticks[0])
        else:
            step = 0.01

        use_ms = step < 0.01

        if use_ms:
            self.ax.set_xlabel("Time (ms)")
            self.ax.xaxis.set_major_formatter(
                mticker.FuncFormatter(lambda x, pos: f"{x * 1000:.3g}")
            )
        else:
            self.ax.set_xlabel("Time (s)")
            self.ax.xaxis.set_major_formatter(
                mticker.FuncFormatter(lambda x, pos: f"{x:.3g}")
            )

        def time_to_index(t):
            return (t - t_shift) * sample_rate

        def index_to_time(i):
            return (i / sample_rate) + t_shift

        secax = self.ax.secondary_xaxis("bottom", functions=(time_to_index, index_to_time))
        secax.set_xlabel("Sample Index")

        self.canvas.draw()

    def _require_transport(self) -> SerialTransport:
        """헬퍼: 유효한 시리얼 연결이 없으면 예외를 발생시키고, 있으면 반환한다."""
        if self.transport is None or not self.transport.is_open():
            raise RuntimeError("시리얼 포트가 연결되어 있지 않습니다.")
        return self.transport

    def _mark_tx_time(self) -> None:
        """헬퍼: 최근 송신 시각을 기록해 응답 지연시간 계산에 사용한다."""
        self._last_tx_time = time.perf_counter()

    def send_ping(self) -> None:
        """PING 패킷을 전송하여 보드 응답 및 연결 상태를 확인한다."""
        try:
            transport = self._require_transport()
            packet = PacketBuilder.build_ping_packet()
            self._mark_tx_time()

            self._log_packet_preview("", packet)
            transport.write_packet(packet)
            self.log(f"PING sent ({len(packet)} bytes)", kind="tx")
        except Exception as e:
            messagebox.showerror("PING Error", str(e))
            self.log(f"PING failed: {e}", kind="system_error")

    def send_load(self) -> None:
        """최근 생성된 DAC 샘플을 LOAD 패킷으로 보드에 전송한다."""
        try:
            transport = self._require_transport()

            if not self.last_samples_dac:
                self.generate_waveform()

            if not self.last_samples_dac:
                raise RuntimeError("전송할 샘플이 없습니다.")

            packet = PacketBuilder.build_load_samples_packet(
                sample_rate_hz=self.sample_rate_var.get(),
                samples=self.last_samples_dac,
            )
            self._mark_tx_time()

            transport.write_packet(packet)
            self.log(f"LOAD sent ({len(packet)} bytes, {len(self.last_samples_dac)} samples)", kind="tx")
            self._log_packet_preview("LOAD", packet)
        except Exception as e:
            messagebox.showerror("LOAD Error", str(e))
            self.log(f"LOAD failed: {e}", kind="system_error")

    def send_start(self) -> None:
        """보드에 START 패킷을 보내 저장된 샘플 출력 시작을 요청한다."""
        try:
            transport = self._require_transport()
            packet = PacketBuilder.build_start_packet()
            self._mark_tx_time()

            transport.write_packet(packet)
            self.log(f"START sent ({len(packet)} bytes)", kind="tx")
            self._log_packet_preview("START", packet)
        except Exception as e:
            messagebox.showerror("START Error", str(e))
            self.log(f"START failed: {e}", kind="system_error")

    def send_stop(self) -> None:
        """보드에 STOP 패킷을 보내 현재 파형 출력 중지를 요청한다."""
        try:
            transport = self._require_transport()
            packet = PacketBuilder.build_stop_packet()
            self._mark_tx_time()

            transport.write_packet(packet)
            self.log(f"STOP sent ({len(packet)} bytes)", kind="tx")
            self._log_packet_preview("STOP", packet)
        except Exception as e:
            messagebox.showerror("STOP Error", str(e))
            self.log(f"STOP failed: {e}", kind="system_error")


def main() -> None:
    """Tkinter 앱을 생성하고 메인 이벤트 루프를 시작한다."""
    root = tk.Tk()
    app = FunctionGeneratorApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()