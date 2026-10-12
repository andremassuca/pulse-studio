// Pulse Studio firmware for Arduino Uno + XD-58C pulse sensor.
//
// Wiring: S -> A0, + -> 5V, - -> GND.
//
// Samples A0 at a fixed 500 Hz (timed with micros(), no delay()) and streams
// compact text lines over serial at 115200 baud:
//
//   <t_us>,<adc>          one sample
//   <t_us>,<adc>,1        same, and the on-board detector flagged a beat here
//   # ...                 comment line (banner, stats), ignored by the app
//
// t_us is the scheduled sample time in microseconds since the stream started
// (it wraps after about 71 minutes, the host handles that). adc is 0-1023.
//
// The LED on pin 13 blinks on every beat found by a simple detector, so the
// sensor can be checked without a computer. All the real signal processing
// (filtering, peak detection, HRV, quality) is done in the desktop app.
//
// Serial commands (one character):
//   V  print the banner again
//
// Close the Serial Monitor/Plotter before opening the desktop app: the COM
// port can only have one owner.

#define FW_VERSION "1.0.0"

// Set to 1 to print "Signal:<adc>,Beat:<0|400>" for the Arduino Serial Plotter
// instead of the compact format. The desktop app needs the compact format.
#define PLOTTER_MODE 0

const uint8_t PIN_SENSOR = A0;
const uint8_t PIN_LED = 13;

const unsigned long BAUD = 115200;
const uint32_t SAMPLE_PERIOD_US = 2000;  // 500 Hz
const uint32_t RESYNC_AFTER_US = 10000;  // give up catching up after 5 periods
const uint32_t STATS_EVERY_MS = 10000;

// Beat detector (fixed point, signal scaled by 16).
const uint8_t SMOOTH_SHIFT = 2;          // ~8 ms smoothing
const uint8_t BASELINE_SHIFT = 9;        // ~1 s baseline
const uint8_t ENVELOPE_DECAY_SHIFT = 11; // ~4 s amplitude memory
const int32_t MIN_ENVELOPE = 16 * 6;     // below 6 ADC counts: no pulse
const uint16_t REFRACTORY_MS = 300;
const uint16_t WARMUP_MS = 1500;
const uint16_t LED_ON_MS = 60;

uint32_t startUs;
uint32_t nextUs;
uint32_t lastStatsMs;
uint32_t drops = 0;
uint32_t resyncs = 0;

int32_t smooth16;
int32_t baseline16;
int32_t envelope16;
int32_t prevX16;
uint32_t lastBeatMs;
uint32_t ledOffMs;
uint32_t warmupEndMs;

void printBanner() {
  Serial.print(F("# pulse_sensor fw="));
  Serial.print(F(FW_VERSION));
  Serial.println(F(" fs=500 baud=115200 format=t_us,adc[,beat]"));
}

// Returns true when the sample is judged to be the rising edge of a beat.
bool detectBeat(int raw, uint32_t nowMs) {
  int32_t raw16 = (int32_t)raw << 4;
  smooth16 += (raw16 - smooth16) >> SMOOTH_SHIFT;
  baseline16 += (smooth16 - baseline16) >> BASELINE_SHIFT;
  int32_t x16 = smooth16 - baseline16;

  if (x16 > envelope16) {
    envelope16 = x16;
  } else {
    envelope16 -= envelope16 >> ENVELOPE_DECAY_SHIFT;
  }

  bool beat = false;
  if (nowMs >= warmupEndMs && envelope16 > MIN_ENVELOPE) {
    int32_t threshold16 = (envelope16 * 9) >> 4;  // 56% of the recent peak
    if (prevX16 < threshold16 && x16 >= threshold16 &&
        nowMs - lastBeatMs > REFRACTORY_MS) {
      beat = true;
      lastBeatMs = nowMs;
    }
  }
  prevX16 = x16;
  return beat;
}

void setup() {
  pinMode(PIN_LED, OUTPUT);
  digitalWrite(PIN_LED, LOW);
  Serial.begin(BAUD);

  int first = analogRead(PIN_SENSOR);
  smooth16 = baseline16 = (int32_t)first << 4;
  envelope16 = 0;
  prevX16 = 0;
  lastBeatMs = 0;
  ledOffMs = 0;

  printBanner();

  uint32_t nowMs = millis();
  warmupEndMs = nowMs + WARMUP_MS;
  lastStatsMs = nowMs;
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

    int raw = analogRead(PIN_SENSOR);
    uint32_t nowMs = millis();
    bool beat = detectBeat(raw, nowMs);

    if (beat) {
      digitalWrite(PIN_LED, HIGH);
      ledOffMs = nowMs + LED_ON_MS;
    }

    // Never block on a full serial buffer: drop the line and count it. The
    // gap is visible in the timestamps.
    if (Serial.availableForWrite() >= 24) {
#if PLOTTER_MODE
      Serial.print(F("Signal:"));
      Serial.print(raw);
      Serial.print(F(",Beat:"));
      Serial.println(beat ? 400 : 0);
#else
      Serial.print(stampUs);
      Serial.print(',');
      Serial.print(raw);
      if (beat) Serial.print(F(",1"));
      Serial.println();
#endif
    } else {
      drops++;
    }
  }

  uint32_t nowMs = millis();
  if (ledOffMs != 0 && (int32_t)(nowMs - ledOffMs) >= 0) {
    digitalWrite(PIN_LED, LOW);
    ledOffMs = 0;
  }

  if (nowMs - lastStatsMs >= STATS_EVERY_MS) {
    lastStatsMs = nowMs;
#if !PLOTTER_MODE
    if (Serial.availableForWrite() >= 40) {
      Serial.print(F("# stats drops="));
      Serial.print(drops);
      Serial.print(F(" resyncs="));
      Serial.println(resyncs);
    }
#endif
  }

  if (Serial.available() > 0) {
    char c = Serial.read();
    if (c == 'V' || c == 'v') printBanner();
  }
}
