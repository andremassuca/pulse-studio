// Pulse Studio firmware for Arduino Uno + XD-58C pulse sensor.
//
// Wiring: S -> A0, + -> 5V, - -> GND.
//
// Samples A0 at a fixed 500 Hz (timed with micros(), no delay() in the loop)
// and streams text over serial at 115200 baud. Two formats:
//
// Compact format, for the desktop app (the default):
//   <t_us>,<adc16>          one sample
//   <t_us>,<adc16>,1        same, and a beat was confirmed around here
//   # ...                   comment line (banner, stats), ignored by the app
// t_us is the scheduled sample time in microseconds since the stream started
// (it wraps after about 71 minutes, the host handles that). adc16 is the sum
// of 16 consecutive ADC readings (0-16368): oversampling gives about two extra
// bits, which matters because the pulse is only a few ADC counts wide on this
// sensor. Divide by 16 to get counts.
//
// Serial Plotter format, for the Arduino IDE (send P once, see below):
//   Pulse:<filtered signal x40>,Peak:<marker>,BPM:<beats per minute>
// Pulse is the pulse wave after the same 0.6-3.5 Hz band-pass filter the app
// uses, shown 120 ms late so that each detected peak can be marked exactly on
// top of it. Peak is a spike at every confirmed peak. BPM is the moving
// average of the last 6 intervals, and 0 while the beats are not steady.
//
// The LED on pin 13 blinks on every confirmed beat, so the sensor can be
// checked without a computer. Everything else (quality, HRV, display) is done
// by the desktop app.
//
// Serial commands (one character):
//   C  compact format for the desktop app (the default)
//   P  Serial Plotter format. The choice is stored in EEPROM, so it survives
//      the reset that opening the port causes. Send P once from the Serial
//      Monitor (or press "Plotter mode" in the app), close it, then open the
//      Serial Plotter. The desktop app sends C by itself when it connects.
//   V  print the banner again
//
// Close the Serial Monitor/Plotter before opening the desktop app: the COM
// port can only have one owner.

#include <EEPROM.h>

#define FW_VERSION "1.3.0"

const uint8_t PIN_SENSOR = A0;
const uint8_t PIN_LED = 13;

const unsigned long BAUD = 115200;
const uint32_t SAMPLE_PERIOD_US = 2000;  // 500 Hz
const uint32_t RESYNC_AFTER_US = 10000;  // give up catching up after 5 periods
const uint32_t STATS_EVERY_MS = 10000;
const uint8_t OVERSAMPLE = 16;
const uint8_t PLOT_EVERY = 5;  // Serial Plotter prints at 100 Hz

const int EEPROM_MODE_ADDR = 0;
const uint8_t MODE_PLOTTER = 'P';

// Band-pass 0.6-3.5 Hz, order 2, as two biquads (b0 b1 b2 a1 a2). Same design
// as the desktop app: Butterworth, 500 Hz.
const float SOS[2][5] = {
  {3.236388363e-04f, 6.472776726e-04f, 3.236388363e-04f, -1.957025839e+00f, 9.585247301e-01f},
  {1.000000000e+00f, -2.000000000e+00f, 1.000000000e+00f, -1.990792947e+00f, 9.908644611e-01f},
};
float z1[2], z2[2];

// Peak detection: a sample is a peak when it is the largest of the 120 ms
// before and after it. The filtered signal is kept in a ring of 121 values
// (counts x256) and the middle one is judged.
const uint8_t HALF = 60;
const uint8_t WIN = 2 * HALF + 1;
int16_t ring[WIN];
uint8_t ringHead = 0;  // next slot to write, also the oldest value
uint32_t sampleCount = 0;

const float MIN_PEAK = 0.6f;       // counts
const float REL_THRESHOLD = 0.4f;  // of the recent signal level
const uint16_t WARMUP_SAMPLES = 1500;  // 3 s
const uint16_t MIN_INTERVAL = 150;     // 300 ms, in samples
const uint16_t MAX_INTERVAL = 1000;    // 2 s
const uint8_t LED_ON_MS = 60;

float level = 0.0f;  // decaying maximum of the filtered signal
float baseline = 0.0f;
uint32_t lastPeakN = 0;
bool havePeak = false;
uint16_t prevDt = 0;
uint16_t ibis[6];
uint8_t ibiCount = 0, ibiNext = 0;
uint8_t outliers = 0;
uint32_t lastValidMs = 0;
int bpm = 0;

uint32_t startUs, nextUs, lastStatsMs, ledOffMs;
uint32_t drops = 0, resyncs = 0;
bool plotterMode = false;
bool markerPending = false;
float markerValue = 0.0f;
uint8_t plotCounter = 0;

void printBanner() {
  Serial.print(F("# pulse_sensor fw="));
  Serial.print(F(FW_VERSION));
  Serial.println(F(" fs=500 baud=115200 format=t_us,adc16[,beat] oversample=16"));
}

int32_t readOversampled() {
  int32_t sum = 0;
  for (uint8_t i = 0; i < OVERSAMPLE; i++) sum += analogRead(PIN_SENSOR);
  return sum;
}

float bandpass(float x) {
  for (uint8_t s = 0; s < 2; s++) {
    float y = SOS[s][0] * x + z1[s];
    z1[s] = SOS[s][1] * x - SOS[s][3] * y + z2[s];
    z2[s] = SOS[s][2] * x - SOS[s][4] * y;
    x = y;
  }
  return x;
}

void resetIntervals() {
  ibiCount = 0;
  ibiNext = 0;
  outliers = 0;
  prevDt = 0;
}

void pushInterval(uint16_t dt) {
  ibis[ibiNext] = dt;
  ibiNext = (ibiNext + 1) % 6;
  if (ibiCount < 6) ibiCount++;
}

float meanInterval() {
  float sum = 0;
  for (uint8_t i = 0; i < ibiCount; i++) sum += ibis[i];
  return ibiCount ? sum / ibiCount : 0;
}

// A peak was confirmed at sample number n. Decide whether it is a beat and
// whether its interval can be trusted. Returns true for a trusted beat.
bool registerPeak(uint32_t n, uint32_t nowMs) {
  if (!havePeak) {
    havePeak = true;
    lastPeakN = n;
    return false;
  }
  uint16_t dt = n - lastPeakN;
  uint16_t minDt = MIN_INTERVAL;
  if (ibiCount >= 3 && meanInterval() / 2 > minDt) minDt = meanInterval() / 2;
  if (dt < minDt) return false;  // too soon: a notch or noise, not a beat
  lastPeakN = n;
  if (dt > MAX_INTERVAL) {
    resetIntervals();
    return false;
  }

  bool valid;
  if (ibiCount < 3) {
    // No history yet: trust an interval only if it agrees with the one before.
    valid = prevDt != 0 && abs((int)dt - (int)prevDt) <= 0.3f * prevDt;
    prevDt = dt;
    if (valid) pushInterval(dt);
  } else {
    float ref = meanInterval();
    valid = fabs(dt - ref) <= 0.3f * ref;
    if (valid) {
      outliers = 0;
      pushInterval(dt);
    } else if (++outliers >= 3) {
      resetIntervals();  // the rhythm really changed
      pushInterval(dt);
      valid = true;
    }
  }
  if (valid) lastValidMs = nowMs;
  return valid;
}

void updateBpm(uint32_t nowMs) {
  bpm = 0;
  if (ibiCount < 3 || nowMs - lastValidMs > 3000) return;
  float mean = meanInterval();
  float var = 0;
  for (uint8_t i = 0; i < ibiCount; i++) var += (ibis[i] - mean) * (ibis[i] - mean);
  if (sqrt(var / ibiCount) / mean > 0.20f) return;  // intervals scattered: show nothing
  bpm = (int)(60000.0f / (mean * 2.0f) + 0.5f);     // an interval sample is 2 ms
}

// Feeds one filtered sample (in counts). Returns the filtered value that sits
// in the middle of the window (what the Serial Plotter shows) and tells through
// `beat` whether that sample is a trusted beat.
float processSample(float y, uint32_t nowMs, bool &beat, bool &peak) {
  beat = false;
  peak = false;
  if (y > level) level = y; else level *= 0.9996f;  // about 5 s memory

  int32_t q = (int32_t)(y * 256.0f);
  if (q > 32000) q = 32000;
  if (q < -32000) q = -32000;
  ring[ringHead] = (int16_t)q;
  ringHead = (ringHead + 1) % WIN;
  sampleCount++;
  if (sampleCount < WIN) return 0.0f;

  // The oldest value is at ringHead; the middle one is HALF steps later.
  uint8_t mid = (ringHead + HALF) % WIN;
  int16_t centre = ring[mid];
  bool isMax = true;
  uint8_t idx = ringHead;
  for (uint8_t i = 0; i < WIN && isMax; i++) {
    if (i != HALF) {
      int16_t v = ring[idx];
      if (i < HALF ? (v >= centre) : (v > centre)) isMax = false;
    }
    idx++;
    if (idx == WIN) idx = 0;
  }
  float height = centre / 256.0f;
  float threshold = REL_THRESHOLD * level;
  if (threshold < MIN_PEAK) threshold = MIN_PEAK;
  if (isMax && height >= threshold && sampleCount > WARMUP_SAMPLES) {
    uint32_t n = sampleCount - HALF;
    peak = true;
    beat = registerPeak(n, nowMs);
  }
  return height;
}

void setup() {
  pinMode(PIN_LED, OUTPUT);
  digitalWrite(PIN_LED, LOW);
  Serial.begin(BAUD);
  plotterMode = (EEPROM.read(EEPROM_MODE_ADDR) == MODE_PLOTTER);

  // ADC clock 250 kHz (prescaler 64): 16 readings take about 0.8 ms.
  ADCSRA = (ADCSRA & ~0x07) | 0x06;

  // The first readings after a reset can be far off. Let the input settle and
  // take the starting level from a real average.
  delay(50);
  for (uint8_t i = 0; i < 8; i++) analogRead(PIN_SENSOR);
  int32_t acc = 0;
  for (uint8_t i = 0; i < 32; i++) acc += readOversampled();
  baseline = acc / 32.0f / 16.0f;

  if (!plotterMode) printBanner();
  lastStatsMs = millis();
  startUs = micros();
  nextUs = startUs;
}

void loop() {
  uint32_t nowUs = micros();
  if ((int32_t)(nowUs - nextUs) >= 0) {
    uint32_t stampUs = nextUs - startUs;
    if (nowUs - nextUs > RESYNC_AFTER_US) {
      nextUs = nowUs + SAMPLE_PERIOD_US;
      resyncs++;
    } else {
      nextUs += SAMPLE_PERIOD_US;
    }

    int32_t raw16 = readOversampled();
    uint32_t nowMs = millis();
    bool beat, peak;
    float shown = processSample(bandpass(raw16 / 16.0f - baseline), nowMs, beat, peak);
    updateBpm(nowMs);

    if (beat) {
      digitalWrite(PIN_LED, HIGH);
      ledOffMs = nowMs + LED_ON_MS;
    }
    if (peak) {
      markerPending = true;
      markerValue = shown;
    }

    if (plotterMode) {
      // Print at 100 Hz. A marker waits for the next printed line.
      if (++plotCounter >= PLOT_EVERY) {
        plotCounter = 0;
        if (Serial.availableForWrite() >= 40) {
          Serial.print(F("Pulse:"));
          Serial.print(shown * 40.0f, 1);
          Serial.print(F(",Peak:"));
          Serial.print(markerPending ? markerValue * 40.0f : 0.0f, 1);
          Serial.print(F(",BPM:"));
          Serial.println(bpm);
          markerPending = false;
        } else {
          drops++;
        }
      }
    } else {
      // Never block on a full serial buffer: drop the line and count it. The
      // gap is visible in the timestamps.
      if (Serial.availableForWrite() >= 26) {
        Serial.print(stampUs);
        Serial.print(',');
        Serial.print(raw16);
        if (beat) Serial.print(F(",1"));
        Serial.println();
      } else {
        drops++;
      }
      markerPending = false;
    }
  }

  uint32_t nowMs = millis();
  if (ledOffMs != 0 && (int32_t)(nowMs - ledOffMs) >= 0) {
    digitalWrite(PIN_LED, LOW);
    ledOffMs = 0;
  }

  if (nowMs - lastStatsMs >= STATS_EVERY_MS) {
    lastStatsMs = nowMs;
    if (!plotterMode && Serial.availableForWrite() >= 40) {
      Serial.print(F("# stats drops="));
      Serial.print(drops);
      Serial.print(F(" resyncs="));
      Serial.println(resyncs);
    }
  }

  if (Serial.available() > 0) {
    char c = Serial.read();
    if (c == 'V' || c == 'v') printBanner();
    if (c == 'P' || c == 'p') {
      EEPROM.update(EEPROM_MODE_ADDR, MODE_PLOTTER);
      plotterMode = true;
    }
    if (c == 'C' || c == 'c') {
      EEPROM.update(EEPROM_MODE_ADDR, 'C');
      plotterMode = false;
      printBanner();
    }
  }
}
