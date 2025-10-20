/*
 * TESTE DE SENSORES - ESTUFA INTELIGENTE
 * Este código testa todos os sensores e atuadores individualmente
 * Ideal para verificar conexões antes da integração completa
 */

// Definição dos pinos
#define DHT_PIN 2           // Sensor DHT22 (temperatura e umidade do ar)
#define SOIL_MOISTURE_PIN A0 // Sensor de umidade do solo (analógico)
#define LDR_PIN A1          // LDR - Sensor de luminosidade (analógico)
#define LED_GREEN 8         // LED Verde (tudo OK)
#define LED_RED 9           // LED Vermelho (alerta)
#define BUZZER 10           // Buzzer para alertas
#define RELAY_PIN 11        // Relé para bomba d'água

// Biblioteca DHT (instale via Library Manager: "DHT sensor library" by Adafruit)
#include <DHT.h>

#define DHTTYPE DHT22
DHT dht(DHT_PIN, DHTTYPE);

void setup() {
  Serial.begin(9600);
  
  // Configuração dos pinos
  pinMode(LED_GREEN, OUTPUT);
  pinMode(LED_RED, OUTPUT);
  pinMode(BUZZER, OUTPUT);
  pinMode(RELAY_PIN, OUTPUT);
  
  // Inicializa DHT
  dht.begin();
  
  Serial.println("=================================");
  Serial.println("TESTE DE SENSORES - ESTUFA IoT");
  Serial.println("=================================");
  delay(2000);
}

void loop() {
  Serial.println("\n--- INICIANDO TESTES ---");
  
  // TESTE 1: LED Verde
  Serial.println("\n[TESTE 1] LED Verde (3 piscadas)");
  for(int i = 0; i < 3; i++) {
    digitalWrite(LED_GREEN, HIGH);
    delay(300);
    digitalWrite(LED_GREEN, LOW);
    delay(300);
  }
  
  // TESTE 2: LED Vermelho
  Serial.println("[TESTE 2] LED Vermelho (3 piscadas)");
  for(int i = 0; i < 3; i++) {
    digitalWrite(LED_RED, HIGH);
    delay(300);
    digitalWrite(LED_RED, LOW);
    delay(300);
  }
  
  // TESTE 3: Buzzer
  Serial.println("[TESTE 3] Buzzer (2 beeps)");
  for(int i = 0; i < 2; i++) {
    digitalWrite(BUZZER, HIGH);
    delay(200);
    digitalWrite(BUZZER, LOW);
    delay(300);
  }
  
  // TESTE 4: Relé (Bomba d'água simulada)
  Serial.println("[TESTE 4] Relé - Liga por 2 segundos");
  digitalWrite(RELAY_PIN, HIGH);
  digitalWrite(LED_GREEN, HIGH);
  delay(2000);
  digitalWrite(RELAY_PIN, LOW);
  digitalWrite(LED_GREEN, LOW);
  Serial.println("  Relé desligado");
  
  // TESTE 5: Sensor DHT22 (Temperatura e Umidade)
  Serial.println("[TESTE 5] Leitura DHT22");
  float temp = dht.readTemperature();
  float humid = dht.readHumidity();
  
  if (isnan(temp) || isnan(humid)) {
    Serial.println("  ERRO: Falha na leitura do DHT22!");
    Serial.println("  Verifique conexões: VCC, GND e DATA no pino 2");
  } else {
    Serial.print("  Temperatura: ");
    Serial.print(temp);
    Serial.println(" °C");
    Serial.print("  Umidade do Ar: ");
    Serial.print(humid);
    Serial.println(" %");
  }
  
  // TESTE 6: Sensor de Umidade do Solo
  Serial.println("[TESTE 6] Sensor de Umidade do Solo");
  int soilRaw = analogRead(SOIL_MOISTURE_PIN);
  int soilPercent = map(soilRaw, 1023, 0, 0, 100); // Inverte: solo seco = 0%, úmido = 100%
  Serial.print("  Valor bruto: ");
  Serial.println(soilRaw);
  Serial.print("  Umidade do Solo: ");
  Serial.print(soilPercent);
  Serial.println(" %");
  
  // TESTE 7: Sensor LDR (Luminosidade)
  Serial.println("[TESTE 7] Sensor LDR (Luminosidade)");
  int ldrRaw = analogRead(LDR_PIN);
  int ldrPercent = map(ldrRaw, 0, 1023, 0, 100);
  Serial.print("  Valor bruto: ");
  Serial.println(ldrRaw);
  Serial.print("  Luminosidade: ");
  Serial.print(ldrPercent);
  Serial.println(" %");
  
  // Feedback visual baseado nas leituras
  Serial.println("\n[FEEDBACK VISUAL]");
  if (!isnan(temp) && !isnan(humid) && soilPercent > 20) {
    Serial.println("  Status: OK - LED Verde ligado");
    digitalWrite(LED_GREEN, HIGH);
    digitalWrite(LED_RED, LOW);
  } else {
    Serial.println("  Status: ALERTA - LED Vermelho + Buzzer");
    digitalWrite(LED_GREEN, LOW);
    digitalWrite(LED_RED, HIGH);
    digitalWrite(BUZZER, HIGH);
    delay(500);
    digitalWrite(BUZZER, LOW);
  }
  
  Serial.println("\n=== Aguardando 10 segundos para próximo teste ===");
  delay(10000);
  digitalWrite(LED_GREEN, LOW);
  digitalWrite(LED_RED, LOW);
}