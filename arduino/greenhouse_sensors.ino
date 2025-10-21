/*
 * SISTEMA DE MONITORAMENTO DE ESTUFA - ARDUINO (VERSÃO FINAL)
 * * CORRIGIDO para hardware real (DHT11, LCD I2C 0x27)
 * * Coleta dados dos sensores, envia JSON para a Pi, controla atuadores.
 */

// --- BIBLIOTECAS ---
#include <DHT.h>
#include <Wire.h>               // <-- ADICIONADO
#include <LiquidCrystal_I2C.h>  // <-- ADICIONADO

// --- PINOS DOS SENSORES ---
#define DHT_PIN 2
#define SOIL_MOISTURE_PIN A0
#define LDR_PIN A1

// --- PINOS DOS ATUADORES (do seu ficheiro original) ---
#define LED_GREEN 8
#define LED_RED 9
#define BUZZER 10
#define RELAY_PIN 11

// --- TIPO DO SENSOR (CORREÇÃO CRÍTICA DA SUA FOTO) ---
#define DHTTYPE DHT11 // <-- CORRIGIDO (era DHT22)

// --- CONFIGURAÇÃO DO LCD (Confirmado pelo Scanner) ---
LiquidCrystal_I2C lcd(0x27, 16, 2); // <-- ADICIONADO

// --- CONFIGURAÇÕES GERAIS ---
#define INTERVAL 5000  // Intervalo de leitura (5 segundos)

// Thresholds para alertas
#define TEMP_MAX 35.0
#define TEMP_MIN 15.0
#define SOIL_MIN 30
#define HUMID_MIN 40

DHT dht(DHT_PIN, DHTTYPE);

unsigned long lastRead = 0;
bool autoIrrigation = false;

// Variáveis globais para guardar os últimos valores lidos
float lastTemp = 0;
float lastHumid = 0;
int lastSoil = 0;
int lastLight = 0;

void setup() {
  // 1. Inicia Serial para a Raspberry Pi
  Serial.begin(9600);
  
  // 2. Configura pinos dos atuadores
  pinMode(LED_GREEN, OUTPUT);
  pinMode(LED_RED, OUTPUT);
  pinMode(BUZZER, OUTPUT);
  pinMode(RELAY_PIN, OUTPUT);
  
  digitalWrite(LED_GREEN, LOW);
  digitalWrite(LED_RED, LOW);
  digitalWrite(RELAY_PIN, LOW);
  
  // 3. Inicia sensor DHT
  dht.begin();
  
  // 4. Inicia LCD I2C // <-- ADICIONADO
  lcd.init();
  lcd.backlight();
  lcd.print("Estufa Conectada");
  lcd.setCursor(0, 1);
  lcd.print("Aguardando Pi...");
  delay(1500);
  lcd.clear();
}

void loop() {
  // Tarefa 1: Checar comandos da Raspberry Pi
  if (Serial.available() > 0) {
    String cmd = Serial.readStringUntil('\n');
    cmd.trim();
    handleCommand(cmd);
  }

  // Tarefa 2: Ler sensores e enviar dados
  unsigned long now = millis();
  if (now - lastRead > INTERVAL) {
    lastRead = now;
    
    // Leitura dos sensores
    float temp = dht.readTemperature();
    float humid = dht.readHumidity();
    int soilRaw = analogRead(SOIL_MOISTURE_PIN);
    int ldrRaw = analogRead(LDR_PIN);

    // Validação do DHT (se falhar, usa a última leitura válida)
    if (isnan(temp) || isnan(humid)) {
      temp = lastTemp;
      humid = lastHumid;
      // Não enviar JSON se a leitura do DHT falhar
    } else {
      lastTemp = temp;
      lastHumid = humid;
      
      // Calibração (você disse que ia refinar)
      int soilPercent = map(soilRaw, 1023, 400, 0, 100); 
      soilPercent = constrain(soilPercent, 0, 100);
      int ldrPercent = map(ldrRaw, 900, 100, 0, 100);
      ldrPercent = constrain(ldrPercent, 0, 100);
      
      lastSoil = soilPercent; // Atualiza o global
      lastLight = ldrPercent; // Atualiza o global

      // Monta o JSON
      String json = "{\"temp\":" + String(temp, 1) + 
                    ",\"humid\":" + String(humid, 0) + 
                    ",\"soil\":" + String(soilPercent) + 
                    ",\"light\":" + String(ldrPercent) + "}";
      
      // Envia para a Pi
      Serial.println(json);

      // Checa condições locais (LEDs, Buzzer)
      checkConditions(temp, humid, soilPercent);
      
      // Sistema de irrigação automática
      if (autoIrrigation && soilPercent < SOIL_MIN) {
        activateIrrigation(3000); // Irriga por 3 segundos
      }
    }
    
    // ATUALIZA O DISPLAY LCD (quer falhe ou não)
    updateLCD(lastTemp, lastHumid, lastSoil, lastLight, isnan(temp));
  }
}

// ---- FUNÇÃO PARA ATUALIZAR O LCD ---- // <-- ADICIONADA
void updateLCD(float temp, float humid, int soil, int light, bool dhtError) {
  lcd.clear();
  
  if(dhtError) {
    lcd.print("Falha no DHT11!");
    return;
  }
  
  // Linha 1: Temp e Humidade Ar
  lcd.setCursor(0, 0);
  lcd.print("T:");
  lcd.print(temp, 1);
  lcd.print("C H:");
  lcd.print(humid, 0);
  lcd.print("%");
  
  // Linha 2: Solo e Luz
  lcd.setCursor(0, 1);
  lcd.print("Solo:");
  lcd.print(soil);
  lcd.print("% Luz:");
  lcd.print(light);
  lcd.print("%");
  
  // Mostra status da irrigação
  if (digitalRead(RELAY_PIN) == HIGH) {
    lcd.setCursor(10, 1); // Posição do "Luz:"
    lcd.print("IRRIG!");
  } else if (autoIrrigation) {
    lcd.setCursor(10, 1); // Posição do "Luz:"
    lcd.print("(AUTO)");
  }
}

// --- FUNÇÕES DE ATUADORES (do seu ficheiro original) ---

void checkConditions(float temp, float humid, int soil) {
  bool alert = false;
  if (temp > TEMP_MAX || temp < TEMP_MIN) { alert = true; }
  if (soil < SOIL_MIN) { alert = true; }
  if (humid < HUMID_MIN) { alert = true; }
  
  if (alert) {
    digitalWrite(LED_RED, HIGH);
    digitalWrite(LED_GREEN, LOW);
    tone(BUZZER, 1000, 200);
  } else {
    digitalWrite(LED_GREEN, HIGH);
    digitalWrite(LED_RED, LOW);
  }
}

// (Função que faltava no seu ficheiro original)
void activateIrrigation(int duration) {
  digitalWrite(RELAY_PIN, HIGH);
  updateLCD(lastTemp, lastHumid, lastSoil, lastLight, false); // Atualiza LCD
  delay(duration);
  digitalWrite(RELAY_PIN, LOW);
  updateLCD(lastTemp, lastHumid, lastSoil, lastLight, false); // Atualiza LCD
}

void handleCommand(String cmd) {
  if (cmd == "IRRIGATE") {
    activateIrrigation(5000); // Irriga por 5 seg
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
  updateLCD(lastTemp, lastHumid, lastSoil, lastLight, false); // Atualiza LCD
}