/*
 * ARDUINO 1 - SENSORES/ATUADORES
 * 
 * Conectado à Raspberry Pi via USB Serial
 * 
 * Hardware:
 * - DHT11 no pino 2
 * - Sensor de solo em A0
 * - LDR em A1
 * - LCD I2C 0x27
 * - LEDs (verde=8, vermelho=9)
 * - Buzzer no pino 10
 * - Relé no pino 11
 * 
 * Protocolo Serial:
 * ENVIA: JSON com dados dos sensores
 * RECEBE: Comandos da Raspberry Pi
 */

#include <DHT.h>
#include <Wire.h>
#include <LiquidCrystal_I2C.h>

// === PINOS DOS SENSORES ===
#define DHT_PIN 2
#define SOIL_MOISTURE_PIN A0
#define LDR_PIN A1

// === PINOS DOS ATUADORES ===
#define LED_GREEN 8
#define LED_RED 9
#define BUZZER 10
#define RELAY_PIN 11

// === SENSOR DHT ===
#define DHTTYPE DHT11
DHT dht(DHT_PIN, DHTTYPE);

// === LCD ===
LiquidCrystal_I2C lcd(0x27, 16, 2);

// === INTERVALOS ===
#define INTERVAL_SENSORS 5000  // Lê sensores a cada 5 segundos

unsigned long lastSensorRead = 0;

// === THRESHOLDS (recebidos da Raspberry Pi) ===
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
  pinMode(RELAY_PIN, OUTPUT);
  
  digitalWrite(LED_GREEN, LOW);
  digitalWrite(LED_RED, LOW);
  digitalWrite(RELAY_PIN, LOW);
  
  // Inicia sensores
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
  Serial.println("{\"status\":\"arduino1_ready\"}");
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
  int soilRaw = analogRead(SOIL_MOISTURE_PIN);
  int ldrRaw = analogRead(LDR_PIN);
  
  // Validação do DHT
  if (isnan(temp) || isnan(humid)) {
    temp = lastTemp;
    humid = lastHumid;
    updateLCD(lastTemp, lastHumid, lastSoil, lastLight, true);
    return;
  }
  
  lastTemp = temp;
  lastHumid = humid;
  
  // Calibração
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
  checkConditions(temp, humid, soilPercent);
  
  // Irrigação automática
  if (autoIrrigation && soilPercent < thresholds.terraMin) {
    activateIrrigation(3000);
  }
  
  // Atualiza LCD
  updateLCD(temp, humid, soilPercent, ldrPercent, false);
}

// ========================================
// VERIFICA CONDIÇÕES
// ========================================

void checkConditions(float temp, float humid, int soil) {
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
// IRRIGAÇÃO
// ========================================

void activateIrrigation(int duration) {
  digitalWrite(RELAY_PIN, HIGH);
  updateLCD(lastTemp, lastHumid, lastSoil, lastLight, false);
  delay(duration);
  digitalWrite(RELAY_PIN, LOW);
  updateLCD(lastTemp, lastHumid, lastSoil, lastLight, false);
}

// ========================================
// COMANDOS DA RASPBERRY PI
// ========================================

void handleCommand(String cmd) {
  // Comandos simples
  if (cmd == "IRRIGATE") {
    activateIrrigation(5000);
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
  else if (cmd == "GET_THRESHOLDS") {
    sendThresholds();
  }
  // Comando JSON para atualizar thresholds
  else if (cmd.startsWith("{")) {
    parseThresholdsJSON(cmd);
  }
  
  updateLCD(lastTemp, lastHumid, lastSoil, lastLight, false);
}

// ========================================
// ENVIA THRESHOLDS ATUAIS
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
  // Exemplo: {"tempMax":30,"tempMin":18}
  
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
  
  // Feedback
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
  
  // Linha 2: Solo e Luz
  lcd.setCursor(0, 1);
  lcd.print("S:");
  lcd.print(soil);
  lcd.print("% L:");
  lcd.print(light);
  lcd.print("%");
  
  // Status irrigação
  if (digitalRead(RELAY_PIN) == HIGH) {
    lcd.setCursor(11, 1);
    lcd.print("IRRIG");
  } else if (autoIrrigation) {
    lcd.setCursor(11, 1);
    lcd.print("AUTO");
  }
}