int sensor;
const int delayTime = 1000;
const int pumpPin = 7;

unsigned long lastCheck = 0;
const int checkInterval = 5000; // 5 sec
const int dryThreshold = 600;
const int sensorErrorVal = 1023;

void setup() {
  Serial.begin(9600);
  pinMode(pumpPin, OUTPUT);
  digitalWrite(pumpPin, LOW);
}

void flushSerial() {
  // Discard any stale bytes in the receive buffer
  while (Serial.available() > 0) {
    Serial.read();
  }
}

void runPump(int duration) {
  digitalWrite(pumpPin, HIGH);
  delay(duration);
  digitalWrite(pumpPin, LOW);
  Serial.println("WATERED");
}

void loop() {
    if (millis() - lastCheck < checkInterval) return;
    lastCheck = millis();
  // Check for manual water command from Flask
  if (Serial.available() > 0) {
    String cmd = Serial.readStringUntil('\n');
    cmd.trim();
    if (cmd == "W") {
      runPump(3000);
      flushSerial();  // clear buffer after acting
      return;
    }
  }

  sensor = analogRead(A0);
  Serial.println(sensor);

  if (sensor != sensorErrorVal && sensor > dryThreshold) {
    flushSerial();              // clear any stale "W" before asking
    Serial.println("NEEDSWATER");

    // Wait up to 2000ms for Flask to reply
    unsigned long start = millis();
    String resp = "";
    while (millis() - start < 2000) {
      if (Serial.available() > 0) {
        resp = Serial.readStringUntil('\n');
        resp.trim();
        break;
      }
      delay(50);
    }

    if (resp == "W") {
      runPump(2000);
      flushSerial();
      delay(5000);
    }
    // If no reply or cooldown blocked, do nothing and loop again
  }

  delay(delayTime);
}