/*
 * ARDUINO 1 - SENSORES/ATUADORES (v6 - Bomba Não-Bloqueante)
 * - Remove LEDs e Buzzer para poupar memória.
 * - Lógica da bomba corrigida para ser 100% automática
 * e não usar delay().
 */

#include <DHT.h>
#include <Wire.h>
#include <LiquidCrystal_I2C.h>
#include <ArduinoJson.h> 

// === PINOS SENSORES ===
#define DHT_PIN 2
#define SOIL_PIN A0
#define LDR_PIN A1

// === PINOS ATUADORES ===
// LEDs e Buzzer removidos
#define RELAY_PUMP 10
#define RELAY_COOLER 12
#define RELAY_LIGHT 11

// Lógica Invertida
#define RELAY_ON LOW
#define RELAY_OFF HIGH

// === DHT ===
#define DHTTYPE DHT11
DHT dht(DHT_PIN, DHTTYPE);

// === LCD ===
LiquidCrystal_I2C lcd(0x27, 16, 2);

// === INTERVALOS ===
#define INTERVAL_SENSORS 5000
unsigned long lastSensorRead = 0;

// === THRESHOLDS ===
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

// === ESTADO (BOMBA CORRIGIDA) ===
// bool autoIrrigation foi removido
bool coolerOn = false;
bool lightOn = false;
bool pumpIsOn = false; // <<< Novo estado para a bomba
unsigned long pumpStartTime = 0; // <<< Novo temporizador da bomba
const long PUMP_DURATION = 3000; // Tempo que a bomba fica ligada (3s)

float lastTemp = 0;
float lastHumid = 0;
int lastSoil = 0;
int lastLight = 0;


// ========================================
// SETUP
// ========================================
void setup() {
  Serial.begin(9600);
  
  // Configura pinos (LEDs e Buzzer removidos)
  pinMode(RELAY_PUMP, OUTPUT);
  pinMode(RELAY_COOLER, OUTPUT);
  pinMode(RELAY_LIGHT, OUTPUT);
  
  // Estado inicial
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

// ========================================
// LOOP PRINCIPAL (BOMBA CORRIGIDA)
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

  // <<< MUDANÇA AQUI: TAREFA 3 >>>
  // Tarefa 3: Gerir o temporizador da bomba (não-bloqueante)
  if (pumpIsOn) {
    // A bomba está ligada. Vê se já deu o tempo.
    if (now - pumpStartTime >= PUMP_DURATION) {
      // Deu o tempo. Desliga a bomba.
      pumpIsOn = false; // Desliga o estado
      digitalWrite(RELAY_PUMP, RELAY_OFF); // Desliga o relé
      updateLCD(lastTemp, lastHumid, lastSoil, lastLight, false); // Atualiza LCD
    }
  }
}

// ========================================
// LEITURA DE SENSORES (BOMBA CORRIGIDA)
// ========================================
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
  
  // Função checkConditions() removida (não é mais necessária)

  // ========================================
  // AUTOMAÇÕES BASEADAS NOS THRESHOLDS
  // ========================================
  
  // <<< MUDANÇA AQUI: BOMBA "QUE NEM AS OUTRAS" >>>
  // 1. IRRIGAÇÃO AUTOMÁTICA (Sem trava, sem delay)
  if (soilPercent < thresholds.terraMin && !pumpIsOn) {
    // Liga a bomba (mas não bloqueia!)
    pumpIsOn = true;
    pumpStartTime = millis(); // Marca a hora que ligou
    digitalWrite(RELAY_PUMP, RELAY_ON);
    
    Serial.println(F("{\"action\":\"pump_auto_on\",\"reason\":\"low_soil\"}"));
  }
  
  // 2. COOLER AUTOMÁTICO (Sem mudança)
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
  
  // 3. FITA LED AUTOMÁTICA (Sem mudança)
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

// ========================================
// VERIFICA CONDIÇÕES (REMOVIDO)
// ========================================
// void checkConditions(...) foi removida.


// ========================================
// CONTROLE DE ATUADORES (BOMBA REMOVIDA)
// ========================================

// <<< MUDANÇA AQUI: activatePump() foi removida >>>

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

// ========================================
// COMANDOS DA RASPBERRY PI (BOMBA CORRIGIDA)
// ========================================
void handleCommand(String cmd) {
  
  // <<< MUDANÇA AQUI: Comandos da Bomba corrigidos >>>
  if (cmd == F("IRRIGATE")) {
    if (!pumpIsOn) { // Só liga se não estiver ligada
      pumpIsOn = true;
      pumpStartTime = millis();
      digitalWrite(RELAY_PUMP, RELAY_ON);
      Serial.println(F("{\"response\":\"irrigation_started\"}"));
    }
  }
  // Comandos AUTO_ON e AUTO_OFF removidos
  
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

// ========================================
// ENVIA THRESHOLDS (Sem mudança)
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
// RECEBE THRESHOLDS VIA JSON (Sem mudança)
// ========================================
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

  // === MUDANÇA CRÍTICA AQUI: MÉTODO MAIS SEGURO ===
  // Em vez de usar o operador '|', vamos checar cada chave.
  // Isto é mais robusto e fácil de depurar.

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

  // <<< AQUI ESTÁ A CORREÇÃO DO MEU BUG 'lZuzMin' >>>
  if (doc.containsKey("luzMin")) {
    thresholds.luzMin = doc["luzMin"].as<float>();
  }

  lcd.clear();
  lcd.print(F("JSON OK! (v7)")); // Atualizado para v7
  delay(1000);

  Serial.println(F("{\"response\":\"thresholds_updated_v7\"}"));
}

// ========================================
// ATUALIZA LCD (BOMBA CORRIGIDA)
// ========================================
void updateLCD(float temp, float humid, int soil, int light, bool dhtError) {
  lcd.clear();
  
  if (dhtError) {
    lcd.print(F("Falha DHT11!"));
    return;
  }
  
  // Linha 1
  lcd.setCursor(0, 0);
  lcd.print(F("T:"));
  lcd.print(temp, 1);
  lcd.print(F("C H:"));
  lcd.print(humid, 0);
  lcd.print(F("%"));
  
  // Linha 2
  lcd.setCursor(0, 1);
  lcd.print(F("S:"));
  lcd.print(soil);
  lcd.print(F("%"));

  // Status dos atuadores (Bomba corrigida, AUTO removido)
  if (pumpIsOn) { // <<< MUDANÇA AQUI
    lcd.setCursor(7, 1);
    lcd.print(F("BOMB"));
  } else if (coolerOn) {
    lcd.setCursor(7, 1);
    lcd.print(F("COOL"));
  } else if (lightOn) {
    lcd.setCursor(7, 1);
    lcd.print(F("LED"));
  }
  // "AUTO" foi removido
  
  lcd.setCursor(12, 1);
  lcd.print(F("L:"));
  lcd.print(light);
}