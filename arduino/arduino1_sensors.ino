/*
 * ARDUINO 1 - SENSORES/ATUADORES (VERSÃO REFINADA)
 * 
 * Hardware:
 * - DHT11 no pino 2
 * - Sensor de solo em A0
 * - LDR em A1
 * - LCD I2C 0x27 (16x2)
 * - LED Verde no pino 8
 * - LED Vermelho no pino 9
 * - Buzzer no pino 10
 * - Relé BOMBA no pino 11
 * - Relé COOLER no pino 12
 * - Relé FITA LED no pino 13
 * 
 * Comandos aceitos via Serial:
 * - IRRIGATE: Ativa bomba por 5s
 * - AUTO_ON/AUTO_OFF: Irrigação automática
 * - COOLER_ON/COOLER_OFF: Liga/desliga cooler
 * - LIGHT_ON/LIGHT_OFF: Liga/desliga fita LED
 * - GET_THRESHOLDS: Retorna thresholds atuais
 * - JSON de thresholds: Atualiza limites
 */

#include <DHT.h>
#include <Wire.h>
#include <LiquidCrystal_I2C.h>

// === PINOS SENSORES ===
#define DHT_PIN 2
#define SOIL_PIN A0
#define LDR_PIN A1

// === PINOS ATUADORES ===
#define LED_GREEN 8
#define LED_RED 9
#define BUZZER 10
#define RELAY_PUMP 11      // Bomba d'água
#define RELAY_COOLER 12    // Cooler/Ventilador
#define RELAY_LIGHT 13     // Fita LED

// === DHT ===
#define DHTTYPE DHT11
DHT dht(DHT_PIN, DHTTYPE);

// === LCD ===
LiquidCrystal_I2C lcd(0x27, 16, 2);

// === INTERVALOS ===
#define INTERVAL_SENSORS 5000  // Lê sensores a cada 5s

unsigned long lastSensorRead = 0;

// === THRESHOLDS (atualizáveis) ===
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

// === ESTADO ===
bool autoIrrigation = false;
bool coolerOn = false;
bool lightOn = false;

float lastTemp = 0;
float lastHumid = 0;
int lastSoil = 0;
int lastLight = 0;

// ========================================
// SETUP
// ========================================

void setup() {
  Serial.begin(9600);
  
  // Configura pinos
  pinMode(LED_GREEN, OUTPUT);
  pinMode(LED_RED, OUTPUT);
  pinMode(BUZZER, OUTPUT);
  pinMode(RELAY_PUMP, OUTPUT);
  pinMode(RELAY_COOLER, OUTPUT);
  pinMode(RELAY_LIGHT, OUTPUT);
  
  // Estado inicial (tudo desligado)
  digitalWrite(LED_GREEN, LOW);
  digitalWrite(LED_RED, LOW);
  digitalWrite(RELAY_PUMP, LOW);
  digitalWrite(RELAY_COOLER, LOW);
  digitalWrite(RELAY_LIGHT, LOW);
  
  // Inicia DHT
  dht.begin();
  
  // Inicia LCD
  lcd.init();
  lcd.backlight();
  lcd.print("Arduino Sensores");
  lcd.setCursor(0, 1);
  lcd.print("Conectando...");
  delay(1500);
  lcd.clear();
  
  // Envia mensagem de boot
  Serial.println("{\"status\":\"arduino1_ready\",\"source\":\"arduino1\"}");
}

// ========================================
// LOOP PRINCIPAL
// ========================================

void loop() {
  unsigned long now = millis();
  
  // Tarefa 1: Processar comandos da Raspberry Pi
  if (Serial.available() > 0) {
    String cmd = Serial.readStringUntil('\n');
    cmd.trim();
    handleCommand(cmd);
  }
  
  // Tarefa 2: Ler sensores e enviar dados
  if (now - lastSensorRead >= INTERVAL_SENSORS) {
    lastSensorRead = now;
    readAndSendSensorData();
  }
}

// ========================================
// LEITURA DE SENSORES
// ========================================

void readAndSendSensorData() {
  // Lê sensores
  float temp = dht.readTemperature();
  float humid = dht.readHumidity();
  int soilRaw = analogRead(SOIL_PIN);
  int ldrRaw = analogRead(LDR_PIN);
  
  // Validação DHT
  if (isnan(temp) || isnan(humid)) {
    temp = lastTemp;
    humid = lastHumid;
    updateLCD(lastTemp, lastHumid, lastSoil, lastLight, true);
    return;
  }
  
  lastTemp = temp;
  lastHumid = humid;
  
  // Calibração (ajuste conforme seu hardware)
  int soilPercent = map(soilRaw, 1023, 400, 0, 100);
  soilPercent = constrain(soilPercent, 0, 100);
  int ldrPercent = map(ldrRaw, 900, 100, 0, 100);
  ldrPercent = constrain(ldrPercent, 0, 100);
  
  lastSoil = soilPercent;
  lastLight = ldrPercent;
  
  // Monta JSON
  String json = "{\"source\":\"arduino1\",";
  json += "\"temp\":" + String(temp, 1) + ",";
  json += "\"humid\":" + String(humid, 0) + ",";
  json += "\"soil\":" + String(soilPercent) + ",";
  json += "\"light\":" + String(ldrPercent) + "}";
  
  Serial.println(json);
  
  // Checa condições
  checkConditions(temp, humid, soilPercent, ldrPercent);
  
  // Irrigação automática
  if (autoIrrigation && soilPercent < thresholds.terraMin) {
    activatePump(3000);
  }
  
  // Cooler automático (temperatura alta)
  if (temp > thresholds.tempMax && !coolerOn) {
    setCooler(true);
  } else if (temp < thresholds.tempMax - 2 && coolerOn) {
    setCooler(false);
  }
  
  // Luz automática (baixa luminosidade)
  if (ldrPercent < thresholds.luzMin && !lightOn) {
    setLight(true);
  } else if (ldrPercent > thresholds.luzMin + 10 && lightOn) {
    setLight(false);
  }
  
  // Atualiza LCD
  updateLCD(temp, humid, soilPercent, ldrPercent, false);
}

// ========================================
// VERIFICA CONDIÇÕES
// ========================================

void checkConditions(float temp, float humid, int soil, int light) {
  bool alert = false;
  
  if (temp > thresholds.tempMax || temp < thresholds.tempMin) { alert = true; }
  if (humid > thresholds.umiMax || humid < thresholds.umiMin) { alert = true; }
  if (soil < thresholds.terraMin) { alert = true; }
  
  if (alert) {
    digitalWrite(LED_RED, HIGH);
    digitalWrite(LED_GREEN, LOW);
    tone(BUZZER, 1000, 200);
  } else {
    digitalWrite(LED_GREEN, HIGH);
    digitalWrite(LED_RED, LOW);
  }
}

// ========================================
// CONTROLE DE ATUADORES
// ========================================

void activatePump(int duration) {
  digitalWrite(RELAY_PUMP, HIGH);
  updateLCD(lastTemp, lastHumid, lastSoil, lastLight, false);
  delay(duration);
  digitalWrite(RELAY_PUMP, LOW);
  updateLCD(lastTemp, lastHumid, lastSoil, lastLight, false);
}

void setCooler(bool state) {
  coolerOn = state;
  digitalWrite(RELAY_COOLER, state ? HIGH : LOW);
  Serial.println(state ? "{\"response\":\"cooler_on\"}" : "{\"response\":\"cooler_off\"}");
  updateLCD(lastTemp, lastHumid, lastSoil, lastLight, false);
}

void setLight(bool state) {
  lightOn = state;
  digitalWrite(RELAY_LIGHT, state ? HIGH : LOW);
  Serial.println(state ? "{\"response\":\"light_on\"}" : "{\"response\":\"light_off\"}");
  updateLCD(lastTemp, lastHumid, lastSoil, lastLight, false);
}

// ========================================
// COMANDOS DA RASPBERRY PI
// ========================================

void handleCommand(String cmd) {
  // Irrigação
  if (cmd == "IRRIGATE") {
    activatePump(5000);
    Serial.println("{\"response\":\"irrigation_started\"}");
  }
  else if (cmd == "AUTO_ON") {
    autoIrrigation = true;
    Serial.println("{\"response\":\"auto_irrigation_enabled\"}");
  }
  else if (cmd == "AUTO_OFF") {
    autoIrrigation = false;
    Serial.println("{\"response\":\"auto_irrigation_disabled\"}");
  }
  
  // Cooler
  else if (cmd == "COOLER_ON") {
    setCooler(true);
  }
  else if (cmd == "COOLER_OFF") {
    setCooler(false);
  }
  
  // Fita LED
  else if (cmd == "LIGHT_ON") {
    setLight(true);
  }
  else if (cmd == "LIGHT_OFF") {
    setLight(false);
  }
  
  // Thresholds
  else if (cmd == "GET_THRESHOLDS") {
    sendThresholds();
  }
  else if (cmd.startsWith("{")) {
    parseThresholdsJSON(cmd);
  }
  
  updateLCD(lastTemp, lastHumid, lastSoil, lastLight, false);
}

// ========================================
// ENVIA THRESHOLDS
// ========================================

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

// ========================================
// RECEBE THRESHOLDS VIA JSON
// ========================================

void parseThresholdsJSON(String json) {
  // Parsing simples (você pode usar ArduinoJson para parsing robusto)
  if (json.indexOf("\"tempMax\"") > 0) {
    int pos = json.indexOf("\"tempMax\":") + 10;
    thresholds.tempMax = json.substring(pos, json.indexOf(",", pos)).toFloat();
  }
  if (json.indexOf("\"tempMin\"") > 0) {
    int pos = json.indexOf("\"tempMin\":") + 10;
    thresholds.tempMin = json.substring(pos, json.indexOf(",", pos)).toFloat();
  }
  if (json.indexOf("\"umiMax\"") > 0) {
    int pos = json.indexOf("\"umiMax\":") + 10;
    thresholds.umiMax = json.substring(pos, json.indexOf(",", pos)).toFloat();
  }
  if (json.indexOf("\"umiMin\"") > 0) {
    int pos = json.indexOf("\"umiMin\":") + 10;
    thresholds.umiMin = json.substring(pos, json.indexOf(",", pos)).toFloat();
  }
  if (json.indexOf("\"terraMin\"") > 0) {
    int pos = json.indexOf("\"terraMin\":") + 10;
    thresholds.terraMin = json.substring(pos, json.indexOf(",", pos)).toFloat();
  }
  
  lcd.clear();
  lcd.print("Thresholds OK!");
  delay(1000);
  
  Serial.println("{\"response\":\"thresholds_updated\"}");
}

// ========================================
// ATUALIZA LCD
// ========================================

void updateLCD(float temp, float humid, int soil, int light, bool dhtError) {
  lcd.clear();
  
  if (dhtError) {
    lcd.print("Falha DHT11!");
    return;
  }
  
  // Linha 1: Temp e Umidade Ar
  lcd.setCursor(0, 0);
  lcd.print("T:");
  lcd.print(temp, 1);
  lcd.print("C H:");
  lcd.print(humid, 0);
  lcd.print("%");
  
  // Linha 2: Solo e status
  lcd.setCursor(0, 1);
  lcd.print("S:");
  lcd.print(soil);
  lcd.print("%");
  
  // Status dos atuadores
  if (digitalRead(RELAY_PUMP) == HIGH) {
    lcd.setCursor(7, 1);
    lcd.print("BOMB");
  } else if (coolerOn) {
    lcd.setCursor(7, 1);
    lcd.print("COOL");
  } else if (lightOn) {
    lcd.setCursor(7, 1);
    lcd.print("LED");
  } else if (autoIrrigation) {
    lcd.setCursor(7, 1);
    lcd.print("AUTO");
  }
  
  // Luminosidade
  lcd.setCursor(12, 1);
  lcd.print("L:");
  lcd.print(light);
}