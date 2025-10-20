/*
 * SISTEMA DE MONITORAMENTO DE ESTUFA - ARDUINO
 * Coleta dados dos sensores e envia via Serial para Raspberry Pi
 * Formato JSON: {"temp":25.5,"humid":60,"soil":45,"light":80}
 */

#include <DHT.h>

// Definição dos pinos
#define DHT_PIN 2
#define SOIL_MOISTURE_PIN A0
#define LDR_PIN A1
#define LED_GREEN 8
#define LED_RED 9
#define BUZZER 10
#define RELAY_PIN 11

// Configurações
#define DHTTYPE DHT22
#define INTERVAL 5000  // Intervalo de leitura (5 segundos)

// Thresholds para alertas
#define TEMP_MAX 35.0
#define TEMP_MIN 15.0
#define SOIL_MIN 30
#define HUMID_MIN 40

DHT dht(DHT_PIN, DHTTYPE);

unsigned long lastRead = 0;
bool autoIrrigation = false;

void setup() {
  Serial.begin(9600);
  
  pinMode(LED_GREEN, OUTPUT);
  pinMode(LED_RED, OUTPUT);
  pinMode(BUZZER, OUTPUT);
  pinMode(RELAY_PIN, OUTPUT);
  
  // Estado inicial: tudo desligado
  digitalWrite(LED_GREEN, LOW);
  digitalWrite(LED_RED, LOW);
  digitalWrite(BUZZER, LOW);
  digitalWrite(RELAY_PIN, LOW);
  
  dht.begin();
  
  // Sinaliza inicialização
  for(int i = 0; i < 3; i++) {
    digitalWrite(LED_GREEN, HIGH);
    delay(200);
    digitalWrite(LED_GREEN, LOW);
    delay(200);
  }
  
  Serial.println("{\"status\":\"ready\"}");
}

void loop() {
  // Verifica comandos recebidos da Raspberry Pi
  if (Serial.available() > 0) {
    String command = Serial.readStringUntil('\n');
    command.trim();
    handleCommand(command);
  }
  
  // Leitura dos sensores no intervalo definido
  if (millis() - lastRead >= INTERVAL) {
    lastRead = millis();
    readAndSendData();
  }
}

void readAndSendData() {
  // Leitura dos sensores
  float temp = dht.readTemperature();
  float humid = dht.readHumidity();
  int soilRaw = analogRead(SOIL_MOISTURE_PIN);
  int ldrRaw = analogRead(LDR_PIN);
  
  // Conversão para percentuais
  int soilPercent = map(constrain(soilRaw, 0, 1023), 1023, 0, 0, 100);
  int lightPercent = map(constrain(ldrRaw, 0, 1023), 0, 1023, 0, 100);
  
  // Verifica se DHT está funcionando
  if (isnan(temp) || isnan(humid)) {
    Serial.println("{\"error\":\"DHT sensor failure\"}");
    digitalWrite(LED_RED, HIGH);
    digitalWrite(LED_GREEN, LOW);
    return;
  }
  
  // Envia dados em formato JSON
  Serial.print("{\"temp\":");
  Serial.print(temp, 1);
  Serial.print(",\"humid\":");
  Serial.print(humid, 1);
  Serial.print(",\"soil\":");
  Serial.print(soilPercent);
  Serial.print(",\"light\":");
  Serial.print(lightPercent);
  Serial.println("}");
  
  // Verifica condições e atualiza LEDs
  checkConditions(temp, humid, soilPercent);
  
  // Sistema de irrigação automática
  if (autoIrrigation && soilPercent < SOIL_MIN) {
    activateIrrigation(3000); // Irriga por 3 segundos
  }
}

void checkConditions(float temp, float humid, int soil) {
  bool alert = false;
  
  if (temp > TEMP_MAX || temp < TEMP_MIN) {
    alert = true;
  }
  if (soil < SOIL_MIN) {
    alert = true;
  }
  if (humid < HUMID_MIN) {
    alert = true;
  }
  
  if (alert) {
    digitalWrite(LED_RED, HIGH);
    digitalWrite(LED_GREEN, LOW);
    tone(BUZZER, 1000, 200); // Beep curto
  } else {
    digitalWrite(LED_GREEN, HIGH);
    digitalWrite(LED_RED, LOW);
  }
}

void handleCommand(String cmd) {
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
  else if (cmd == "STATUS") {
    Serial.print("{\"auto_irrigation\":");
    Serial.print(autoIrrigation ? "true" : "false");
    Serial.println("}");
  }
  else if (cmd == "PING") {
    Serial.println("{\"response\":\"pong\"}");
  }
}

void activateIrrigation(int duration) {
  digitalWrite(RELAY_PIN, HIGH);
  digitalWrite(LED_GREEN, HIGH);
  delay(duration);
  digitalWrite(RELAY_PIN, LOW);
}