#include <Arduino.h>

// -----------------------------
// Protocol constants
// -----------------------------
static const uint16_t MAGIC = 0xAA55;
static const uint8_t PROTOCOL_VERSION = 2;

enum Command : uint8_t {
  CMD_PING = 0x01,
  CMD_LOAD_SAMPLES = 0x02,
  CMD_START = 0x03,
  CMD_STOP = 0x04
};

// 프로토타입용 버퍼 크기
// uint16_t 샘플 1024개 = 2048 bytes
static const uint16_t MAX_SAMPLES = 1024;

uint16_t sampleBuffer[MAX_SAMPLES];
uint32_t currentSampleRate = 0;
uint16_t currentSampleCount = 0;

// -----------------------------
// Global Variables
// -----------------------------

bool isPlaying = false;
uint16_t playIndex = 0;
unsigned long nextMicros = 0;

uint8_t currentBits = 12;
uint8_t currentFlags = 0;
float currentVMin = -1.0f;
float currentVMax = 1.0f;

// -----------------------------
// Utility: little-endian readers
// -----------------------------
uint16_t readU16LE(const uint8_t* p) {
  return (uint16_t)p[0] | ((uint16_t)p[1] << 8);
}

uint32_t readU32LE(const uint8_t* p) {
  return (uint32_t)p[0]
       | ((uint32_t)p[1] << 8)
       | ((uint32_t)p[2] << 16)
       | ((uint32_t)p[3] << 24);
}

float readF32LE(const uint8_t* p) {
  union {
    uint32_t u;
    float f;
  } conv;

  conv.u = (uint32_t)p[0]
         | ((uint32_t)p[1] << 8)
         | ((uint32_t)p[2] << 16)
         | ((uint32_t)p[3] << 24);

  return conv.f;
}

// Python 쪽 checksum16과 동일
uint16_t checksum16(const uint8_t* data, size_t len) {
  uint32_t sum = 0;
  for (size_t i = 0; i < len; ++i) {
    sum += data[i];
  }
  return (uint16_t)(sum & 0xFFFF);
}

// 지정 바이트 수를 정확히 읽는다.
// 실패하면 false.
bool readExact(uint8_t* buffer, size_t len) {
  size_t got = Serial.readBytes((char*)buffer, len);
  return got == len;
}

// -----------------------------
// Command handlers
// -----------------------------
void handlePing(const uint8_t* header, uint16_t receivedChecksum) {
  uint16_t calc = checksum16(header, 4);
  if (calc != receivedChecksum) {
    Serial.println("ERR PING CHECKSUM");
    return;
  }

  Serial.println("PONG");
}

void handleStart(const uint8_t* header, uint16_t receivedChecksum) {
  uint16_t calc = checksum16(header, 4);
  if (calc != receivedChecksum) {
    Serial.println("ERR START CHECKSUM");
    return;
  }

  if (currentSampleCount == 0) {
    Serial.println("ERR NO SAMPLES");
    return;
  }

  playIndex = 0;
  isPlaying = true;       // Play
  nextMicros = micros();

  Serial.println("START OK");
}

void handleStop(const uint8_t* header, uint16_t receivedChecksum) {
  uint16_t calc = checksum16(header, 4);
  if (calc != receivedChecksum) {
    Serial.println("ERR STOP CHECKSUM");
    return;
  }

  isPlaying = false;    // Stop
  analogWrite(A0, 0);

  Serial.println("STOP OK");
}

void handleLoadSamples(const uint8_t* header) {
  // 추가 헤더:
  // sample_rate(4) + sample_count(2) + bits(1) + flags(1) + v_min(4) + v_max(4)
  uint8_t meta[16];
  if (!readExact(meta, sizeof(meta))) {
    Serial.println("ERR LOAD META TIMEOUT");
    return;
  }

  uint32_t sampleRate = readU32LE(&meta[0]);
  uint16_t sampleCount = readU16LE(&meta[4]);
  uint8_t bits = meta[6];
  uint8_t flags = meta[7];
  float vMin = readF32LE(&meta[8]);
  float vMax = readF32LE(&meta[12]);

  if (sampleCount == 0) {
    Serial.println("ERR LOAD EMPTY");
    return;
  }

  if (sampleCount > MAX_SAMPLES) {
    Serial.println("ERR LOAD TOO MANY SAMPLES");
    return;
  }

  if (bits < 1 || bits > 16) {
    Serial.println("ERR LOAD BAD BITS");
    return;
  }

  if (vMax < vMin) {
    Serial.println("ERR LOAD BAD RANGE");
    return;
  }

  const size_t sampleBytes = (size_t)sampleCount * 2;
  uint8_t rawSamples[MAX_SAMPLES * 2];

  if (!readExact(rawSamples, sampleBytes)) {
    Serial.println("ERR LOAD SAMPLE TIMEOUT");
    return;
  }

  uint8_t checksumBytes[2];
  if (!readExact(checksumBytes, 2)) {
    Serial.println("ERR LOAD CHECKSUM TIMEOUT");
    return;
  }

  uint16_t receivedChecksum = readU16LE(checksumBytes);

  // checksum 계산용 body 조립:
  // [magic 2][version 1][cmd 1][meta 16][samples...]
  const size_t bodyLen = 4 + 16 + sampleBytes;
  uint8_t body[4 + 16 + MAX_SAMPLES * 2];

  memcpy(body, header, 4);
  memcpy(body + 4, meta, 16);
  memcpy(body + 20, rawSamples, sampleBytes);

  uint16_t calc = checksum16(body, bodyLen);
  if (calc != receivedChecksum) {
    Serial.println("ERR LOAD CHECKSUM");
    return;
  }

  for (uint16_t i = 0; i < sampleCount; ++i) {
    sampleBuffer[i] = readU16LE(&rawSamples[i * 2]);
  }

  currentSampleRate = sampleRate;
  currentSampleCount = sampleCount;
  currentBits = bits;
  currentFlags = flags;
  currentVMin = vMin;
  currentVMax = vMax;

  Serial.print("LOAD OK rate=");
  Serial.print(currentSampleRate);
  Serial.print(" count=");
  Serial.print(currentSampleCount);
  Serial.print(" bits=");
  Serial.print(currentBits);
  Serial.print(" range=[");
  Serial.print(currentVMin, 6);
  Serial.print(", ");
  Serial.print(currentVMax, 6);
  Serial.println("]");

  Serial.print("First samples: ");
  uint16_t preview = min((uint16_t)8, currentSampleCount);
  for (uint16_t i = 0; i < preview; ++i) {
    Serial.print(sampleBuffer[i]);
    if (i + 1 < preview) {
      Serial.print(", ");
    }
  }
  Serial.println();

  // 첫 샘플을 원래 수치 범위로 역변환해서 확인 출력
  if (currentSampleCount > 0) {
    float reconstructed =
      currentVMin +
      (float(sampleBuffer[0]) / float((1UL << currentBits) - 1)) *
      (currentVMax - currentVMin);

    Serial.print("First sample reconstructed=");
    Serial.println(reconstructed, 6);
  }
}

// -----------------------------
// Setup / loop
// -----------------------------
void setup() {
  Serial.begin(115200);
  Serial.setTimeout(200);

  delay(2000);

  analogWriteResolution(12);
  analogWrite(A0, 0);

  Serial.println("UNO R4 parser ready");
}

void loop() {
  // ---- DAC 재생 루틴 ----
  if (isPlaying && currentSampleCount > 0 && currentSampleRate > 0) {
    unsigned long interval = 1000000UL / currentSampleRate;
    unsigned long now = micros();

    if ((long)(now - nextMicros) >= 0) {
      analogWrite(A0, sampleBuffer[playIndex]);

      playIndex++;
      if (playIndex >= currentSampleCount) {
        playIndex = 0;  // 반복 재생
      }

      nextMicros += interval;
    }
  }

  // ---- 기존 패킷 파서 ----
  if (Serial.available() < 4) {
    return;
  }

  uint8_t header[4];
  if (!readExact(header, sizeof(header))) {
    return;
  }

  uint16_t magic = readU16LE(&header[0]);
  uint8_t version = header[2];
  uint8_t cmd = header[3];

  if (magic != MAGIC) {
    Serial.println("ERR BAD MAGIC");
    return;
  }

  if (version != PROTOCOL_VERSION) {
    Serial.println("ERR BAD VERSION");
    return;
  }

  if (cmd == CMD_PING || cmd == CMD_START || cmd == CMD_STOP) {
    uint8_t checksumBytes[2];
    if (!readExact(checksumBytes, 2)) {
      Serial.println("ERR SHORT CMD CHECKSUM TIMEOUT");
      return;
    }

    uint16_t receivedChecksum = readU16LE(checksumBytes);

    if (cmd == CMD_PING) {
      handlePing(header, receivedChecksum);
    } else if (cmd == CMD_START) {
      handleStart(header, receivedChecksum);
    } else {
      handleStop(header, receivedChecksum);
    }
    return;
  }

  if (cmd == CMD_LOAD_SAMPLES) {
    handleLoadSamples(header);
    return;
  }

  Serial.print("ERR UNKNOWN CMD ");
  Serial.println(cmd);
}