#include <DHT.h>
#include <Wire.h>
#include <LiquidCrystal_I2C.h>
#include <ArduinoJson.h> 

#define DHT_PIN 2
#define SOIL_PIN A0
#define LDR_PIN A1

#define RELAY_PUMP 10
#define RELAY_COOLER 12
#define RELAY_LIGHT 11

#define RELAY_ON LOW
#define RELAY_OFF HIGH

#define DHTTYPE DHT11
DHT dht(DHT_PIN, DHTTYPE);

LiquidCrystal_I2C lcd(0x27, 16, 2);

#define INTERVAL_SENSORS 5000
unsigned long lastSensorRead = 0;

struct Thresholds {
  float tempMax = 35.0;
  float tempMin = 15.0;
  float umiMax = 80.0;
  float umiMin = 40.0;
  float luzMax = 90.0;
  float luzMin = 20.0;
  float terraMax = 80.0;
  float terraMin = 30.0;
} thresholds;

bool coolerOn = false;
bool lightOn = false;
bool pumpIsOn = false; 
unsigned long pumpStartTime = 0; 
const long PUMP_DURATION = 3000;

float lastTemp = 0;
float lastHumid = 0;
int lastSoil = 0;
int lastLight = 0;

void setup() {
  Serial.begin(9600);
  
  pinMode(RELAY_PUMP, OUTPUT);
  pinMode(RELAY_COOLER, OUTPUT);
  pinMode(RELAY_LIGHT, OUTPUT);
  
  digitalWrite(RELAY_PUMP, RELAY_OFF);
  digitalWrite(RELAY_COOLER, RELAY_OFF);
  digitalWrite(RELAY_LIGHT, RELAY_OFF);

  dht.begin();
  
  lcd.init();
  lcd.backlight();
  lcd.print(F("Arduino Sensores"));
  lcd.setCursor(0, 1);
  lcd.print(F("Conectando..."));
  delay(1500);
  lcd.clear();

  Serial.println(F("{\"status\":\"arduino1_ready\",\"source\":\"arduino1\"}"));
}

void loop() {
  unsigned long now = millis();

  if (Serial.available() > 0) {
    String cmd = Serial.readStringUntil('\n');
    cmd.trim();
    handleCommand(cmd);
  }
  
  if (now - lastSensorRead >= INTERVAL_SENSORS) {
    lastSensorRead = now;
    readAndSendSensorData();
  }

  if (pumpIsOn) {
    if (now - pumpStartTime >= PUMP_DURATION) {
      pumpIsOn = false;
      digitalWrite(RELAY_PUMP, RELAY_OFF);
      updateLCD(lastTemp, lastHumid, lastSoil, lastLight, false);
    }
  }
}

void readAndSendSensorData() {
  float temp = dht.readTemperature();
  float humid = dht.readHumidity();
  int soilRaw = analogRead(SOIL_PIN);
  int ldrRaw = analogRead(LDR_PIN);

  if (isnan(temp) || isnan(humid)) {
    temp = lastTemp;
    humid = lastHumid;
    updateLCD(lastTemp, lastHumid, lastSoil, lastLight, true);
    return;
  }
  
  lastTemp = temp;
  lastHumid = humid;

  int soilPercent = map(soilRaw, 1023, 400, 0, 100);
  soilPercent = constrain(soilPercent, 0, 100);
  int ldrPercent = map(ldrRaw, 100, 900, 0, 100);
  ldrPercent = constrain(ldrPercent, 0, 100);
  
  lastSoil = soilPercent;
  lastLight = ldrPercent;

  String json = "{\"source\":\"arduino1\",";
  json += "\"temp\":" + String(temp, 1) + ",";
  json += "\"humid\":" + String(humid, 0) + ",";
  json += "\"soil\":" + String(soilPercent) + ",";
  json += "\"light\":" + String(ldrPercent) + "}";
  Serial.println(json);
  
  if (soilPercent < thresholds.terraMin && !pumpIsOn) {
    pumpIsOn = true;
    pumpStartTime = millis();
    digitalWrite(RELAY_PUMP, RELAY_ON);
    
    Serial.println(F("{\"action\":\"pump_auto_on\",\"reason\":\"low_soil\"}"));
  }
  
  if (temp > thresholds.tempMax && !coolerOn) {
    setCooler(true);
    Serial.print(F("{\"action\":\"cooler_auto_on\",\"reason\":\"high_temp\",\"value\":"));
    Serial.print(String(temp, 1));
    Serial.println(F("}"));
  } 
  else if (temp < thresholds.tempMax - 2 && coolerOn) {
    setCooler(false);
    Serial.print(F("{\"action\":\"cooler_auto_off\",\"reason\":\"temp_normal\",\"value\":"));
    Serial.print(String(temp, 1));
    Serial.println(F("}"));
  }
  
  if (ldrPercent < thresholds.luzMin && !lightOn) {
    setLight(true);
    Serial.print(F("{\"action\":\"light_auto_on\",\"reason\":\"low_light\",\"value\":"));
    Serial.print(ldrPercent);
    Serial.println(F("}"));
  } 
  else if (ldrPercent > thresholds.luzMin + 10 && lightOn) {
    setLight(false);
    Serial.print(F("{\"action\":\"light_auto_off\",\"reason\":\"light_normal\",\"value\":"));
    Serial.print(ldrPercent);
    Serial.println(F("}"));
  }
  
  updateLCD(temp, humid, soilPercent, ldrPercent, false);
}

void setCooler(bool state) {
  coolerOn = state;
  digitalWrite(RELAY_COOLER, state ? RELAY_ON : RELAY_OFF);
  Serial.println(state ? F("{\"response\":\"cooler_on\"}") : F("{\"response\":\"cooler_off\"}"));
  updateLCD(lastTemp, lastHumid, lastSoil, lastLight, false);
}

void setLight(bool state) {
  lightOn = state;
  digitalWrite(RELAY_LIGHT, state ? RELAY_ON : RELAY_OFF);
  Serial.println(state ? F("{\"response\":\"light_on\"}") : F("{\"response\":\"light_off\"}"));
  updateLCD(lastTemp, lastHumid, lastSoil, lastLight, false);
}


void handleCommand(String cmd) {
  
  if (cmd == F("IRRIGATE")) {
    if (!pumpIsOn) { 
      pumpIsOn = true;
      pumpStartTime = millis();
      digitalWrite(RELAY_PUMP, RELAY_ON);
      Serial.println(F("{\"response\":\"irrigation_started\"}"));
    }
  }
  
  else if (cmd == F("COOLER_ON")) {
    setCooler(true);
  }
  else if (cmd == F("COOLER_OFF")) {
    setCooler(false);
  }
  else if (cmd == F("LIGHT_ON")) {
    setLight(true);
  }
  else if (cmd == F("LIGHT_OFF")) {
    setLight(false);
  }
  else if (cmd == F("GET_THRESHOLDS")) {
    sendThresholds();
  }
  else if (cmd.startsWith("{")) {
    parseThresholdsJSON(cmd);
  }
  
  updateLCD(lastTemp, lastHumid, lastSoil, lastLight, false);
}

void sendThresholds() {
  String json = "{\"source\":\"arduino1\",\"thresholds\":{";
  json += "\"tempMax\":" + String(thresholds.tempMax, 1) + ",";
  json += "\"tempMin\":" + String(thresholds.tempMin, 1) + ",";
  json += "\"umiMax\":" + String(thresholds.umiMax, 1) + ",";
  json += "\"umiMin\":" + String(thresholds.umiMin, 1) + ",";
  json += "\"luzMax\":" + String(thresholds.luzMax, 1) + ",";
  json += "\"luzMin\":" + String(thresholds.luzMin, 1) + ",";
  json += "\"terraMax\":" + String(thresholds.terraMax, 1) + ",";
  json += "\"terraMin\":" + String(thresholds.terraMin, 1);
  json += "}}";
  Serial.println(json);
}

void parseThresholdsJSON(String json) {
  StaticJsonDocument<128> doc; 
  DeserializationError error = deserializeJson(doc, json);

  if (error) {
    lcd.clear();
    lcd.print(F("Falha no JSON!")); 
    Serial.print(F("{\"response\":\"json_parse_error\", \"detail\":\""));
    Serial.print(error.c_str());
    Serial.println(F("\"}"));
    delay(1000);
    return;
  }

  if (doc.containsKey("tempMax")) {
    thresholds.tempMax = doc["tempMax"].as<float>();
  }
  if (doc.containsKey("tempMin")) {
    thresholds.tempMin = doc["tempMin"].as<float>();
  }
  if (doc.containsKey("umiMax")) {
    thresholds.umiMax = doc["umiMax"].as<float>();
  }
  if (doc.containsKey("umiMin")) {
    thresholds.umiMin = doc["umiMin"].as<float>();
  }
  if (doc.containsKey("terraMin")) {
    thresholds.terraMin = doc["terraMin"].as<float>();
  }

  if (doc.containsKey("luzMin")) {
    thresholds.luzMin = doc["luzMin"].as<float>();
  }

  lcd.clear();
  lcd.print(F("JSON OK! (v7)"));
  delay(1000);

  Serial.println(F("{\"response\":\"thresholds_updated_v7\"}"));
}

void updateLCD(float temp, float humid, int soil, int light, bool dhtError) {
  lcd.clear();
  
  if (dhtError) {
    lcd.print(F("Falha DHT11!"));
    return;
  }
  
  lcd.setCursor(0, 0);
  lcd.print(F("T:"));
  lcd.print(temp, 1);
  lcd.print(F("C H:"));
  lcd.print(humid, 0);
  lcd.print(F("%"));
  
  lcd.setCursor(0, 1);
  lcd.print(F("S:"));
  lcd.print(soil);
  lcd.print(F("%"));

  if (pumpIsOn) { I
    lcd.setCursor(7, 1);
    lcd.print(F("BOMB"));
  } else if (coolerOn) {
    lcd.setCursor(7, 1);
    lcd.print(F("COOL"));
  } else if (lightOn) {
    lcd.setCursor(7, 1);
    lcd.print(F("LED"));
  }
  
  lcd.setCursor(12, 1);
  lcd.print(F("L:"));
  lcd.print(light);
}