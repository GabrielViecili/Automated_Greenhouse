/*
 * TESTE DE SENSORES E ATUADORES - (VERSÃO FINAL)
 * * CORRIGIDO para hardware real (DHT11, LCD I2C 0x27)
 */

// --- BIBLIOTECAS ---
#include <DHT.h>
#include <Wire.h>               // <-- ADICIONADO
#include <LiquidCrystal_I2C.h>  // <-- ADICIONADO

// --- PINOS DOS SENSORES ---
#define DHT_PIN 2
#define SOIL_MOISTURE_PIN A0
#define LDR_PIN A1

// --- PINOS DOS ATUADORES ---
#define LED_GREEN 8
#define LED_RED 9
#define BUZZER 10
#define RELAY_PIN 11

// --- TIPO DO SENSOR (CORREÇÃO CRÍTICA) ---
#define DHTTYPE DHT11 // <-- CORRIGIDO

// --- CONFIGURAÇÃO DO LCD (Confirmado pelo Scanner) ---
LiquidCrystal_I2C lcd(0x27, 16, 2); // <-- ADICIONADO

DHT dht(DHT_PIN, DHTTYPE);

void setup() {
  Serial.begin(9600);
  
  // Configuração dos pinos
  pinMode(LED_GREEN, OUTPUT);
  pinMode(LED_RED, OUTPUT);
  pinMode(BUZZER, OUTPUT);
  pinMode(RELAY_PIN, OUTPUT);
  
  // Inicia DHT
  dht.begin();
  
  // Inicia LCD
  lcd.init();       // <-- ADICIONADO
  lcd.backlight();  // <-- ADICIONADO

  Serial.println("=================================");
  Serial.println("INICIANDO TESTE COMPLETO (DHT11, I2C)");
  lcd.print("TESTE COMPLETO");
  Serial.println("=================================");
  delay(2000);
}

void loop() {
  Serial.println("\n--- NOVO CICLO DE TESTES ---");
  
  // TESTE 1: LEDs
  Serial.println("[TESTE 1] LEDs");
  digitalWrite(LED_GREEN, HIGH);
  digitalWrite(LED_RED, LOW);
  lcd.clear();
  lcd.print("TESTE: LED Verde");
  delay(1000);
  digitalWrite(LED_GREEN, LOW);
  digitalWrite(LED_RED, HIGH);
  lcd.clear();
  lcd.print("TESTE: LED Verm.");
  delay(1000);
  digitalWrite(LED_RED, LOW);
  
  // TESTE 2: Buzzer
  Serial.println("[TESTE 2] Buzzer");
  lcd.clear();
  lcd.print("TESTE: Buzzer");
  tone(BUZZER, 1000, 500); // Beep
  delay(1000);
  
  // TESTE 3: Relé
  Serial.println("[TESTE 3] Rele");
  lcd.clear();
  lcd.print("TESTE: Rele LIGADO");
  digitalWrite(RELAY_PIN, HIGH);
  delay(2000);
  lcd.clear();
  lcd.print("TESTE: Rele DESL.");
  digitalWrite(RELAY_PIN, LOW);
  delay(1000);
  
  // TESTE 4 & 5: Sensor DHT11
  Serial.println("[TESTE 4/5] Sensor DHT11");
  lcd.clear();
  lcd.print("Lendo DHT11...");
  float temp = dht.readTemperature();
  float humid = dht.readHumidity();
  
  if (isnan(temp) || isnan(humid)) {
    Serial.println("  Falha ao ler o sensor DHT11!");
    lcd.clear();
    lcd.print("Falha no DHT11!");
  } else {
    Serial.print("  Temperatura: ");
    Serial.print(temp);
    Serial.println(" C");
    Serial.print("  Umidade do Ar: ");
    Serial.print(humid);
    Serial.println(" %");
    
    lcd.setCursor(0, 0);
    lcd.print("T:");
    lcd.print(temp, 1);
    lcd.print(" H:");
    lcd.print(humid, 0);
  }
  delay(2000); // DHT precisa de 2s

  // TESTE 6: Sensor de Umidade do Solo
  Serial.println("[TESTE 6] Sensor de Umidade do Solo");
  int soilRaw = analogRead(SOIL_MOISTURE_PIN);
  int soilPercent = map(soilRaw, 1023, 400, 0, 100); // Calibre isto!
  soilPercent = constrain(soilPercent, 0, 100);
  Serial.print("  Valor bruto: ");
  Serial.println(soilRaw);
  Serial.print("  Umidade do Solo: ");
  Serial.print(soilPercent);
  Serial.println(" %");
  
  lcd.setCursor(0, 1);
  lcd.print("Solo:");
  lcd.print(soilPercent);
  lcd.print("% ");
  delay(2000);

  // TESTE 7: Sensor LDR (Luminosidade)
  Serial.println("[TESTE 7] Sensor LDR (Luminosidade)");
  int ldrRaw = analogRead(LDR_PIN);
  int ldrPercent = map(ldrRaw, 900, 100, 0, 100); // Calibre isto!
  ldrPercent = constrain(ldrPercent, 0, 100);
  Serial.print("  Valor bruto: ");
  Serial.println(ldrRaw);
  Serial.print("  Luminosidade: ");
  Serial.print(ldrPercent);
  Serial.println(" %");

  lcd.setCursor(9, 1);
  lcd.print("Luz:");
  lcd.print(ldrPercent);
  
  Serial.println("--- FIM DO CICLO ---");
  delay(3000); 
}