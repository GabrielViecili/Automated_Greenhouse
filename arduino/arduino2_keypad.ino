/*
 * ARDUINO 2 - CONFIGURAÇÃO VIA TECLADO
 * 
 * Conectado à Raspberry Pi via USB Serial
 * 
 * Hardware:
 * - Teclado Matricial 4x3
 * - LCD I2C 0x27
 * - EEPROM (armazena configurações)
 * 
 * Protocolo Serial:
 * ENVIA: JSON com thresholds configurados
 * RECEBE: Comandos da Raspberry Pi
 */

#include <Keypad.h>
#include <Wire.h>
#include <LiquidCrystal_I2C.h>
#include <EEPROM.h>

// === LCD ===
LiquidCrystal_I2C lcd(0x27, 16, 2);

// === TECLADO ===
const byte ROWS = 4;
const byte COLS = 3;

const char keys[ROWS][COLS] = {
  {'1','2','3'},
  {'4','5','6'},
  {'7','8','9'},
  {'*','0','#'}
};

const byte rowPins[ROWS] = {4, 9, 8, 6}; 
const byte colPins[COLS] = {5, 3, 7};

Keypad keypad = Keypad(makeKeymap(keys), rowPins, colPins, ROWS, COLS);

// === ENDEREÇOS EEPROM ===
int addrTempMax = 0;
int addrTempMin = 4;
int addrUmiMax  = 8;
int addrUmiMin  = 12;
int addrLuzMax  = 16;
int addrLuzMin  = 20;
int addrTerraMax = 24;
int addrTerraMin = 28;

// === VARIÁVEIS ===
float tempMax, tempMin, umiMax, umiMin, luzMax, luzMin, terraMax, terraMin;

// ========================================
// FUNÇÕES EEPROM
// ========================================

void salvarFloat(int address, float value) {
  EEPROM.put(address, value);
}

float lerFloat(int address) {
  float value;
  EEPROM.get(address, value);
  if (isnan(value)) return 0;
  return value;
}

// ========================================
// LEITURA DE NÚMERO VIA TECLADO
// ========================================

float lerNumero(const char* mensagem) {
  String valor = "";
  char tecla;
  lcd.clear();
  lcd.print(mensagem);
  lcd.setCursor(0, 1);
  lcd.print("> ");

  while (true) {
    tecla = keypad.getKey();
    if (tecla) {
      if (tecla >= '0' && tecla <= '9') {
        valor += tecla;
        lcd.print(tecla);
      } else if (tecla == '#') {
        if (valor.length() == 0) return -1;
        return valor.toFloat();
      } else if (tecla == '*') {
        return -1;
      }
    }
  }
}

// ========================================
// MOSTRA VALORES
// ========================================

void mostrarValores(const char* nome, float min, float max) {
  lcd.clear();
  lcd.print(nome);
  lcd.setCursor(0, 1);
  lcd.print(min, 1);
  lcd.print(" - ");
  lcd.print(max, 1);
  delay(2000);
}

// ========================================
// ENVIA THRESHOLDS VIA SERIAL
// ========================================

void enviarThresholds() {
  String json = "{\"source\":\"arduino2\",\"thresholds\":{";
  json += "\"tempMax\":" + String(tempMax, 1) + ",";
  json += "\"tempMin\":" + String(tempMin, 1) + ",";
  json += "\"umiMax\":" + String(umiMax, 1) + ",";
  json += "\"umiMin\":" + String(umiMin, 1) + ",";
  json += "\"luzMax\":" + String(luzMax, 1) + ",";
  json += "\"luzMin\":" + String(luzMin, 1) + ",";
  json += "\"terraMax\":" + String(terraMax, 1) + ",";
  json += "\"terraMin\":" + String(terraMin, 1);
  json += "}}";
  
  Serial.println(json);
}

// ========================================
// SETUP
// ========================================

void setup() {
  Serial.begin(9600);
  
  lcd.init();
  lcd.backlight();

  // Lê valores da EEPROM
  tempMax = lerFloat(addrTempMax);
  tempMin = lerFloat(addrTempMin);
  umiMax = lerFloat(addrUmiMax);
  umiMin = lerFloat(addrUmiMin);
  luzMax = lerFloat(addrLuzMax);
  luzMin = lerFloat(addrLuzMin);
  terraMax = lerFloat(addrTerraMax);
  terraMin = lerFloat(addrTerraMin);
  
  // Valores padrão se EEPROM vazia
  if (tempMax == 0) { tempMax = 35.0; salvarFloat(addrTempMax, tempMax); }
  if (tempMin == 0) { tempMin = 15.0; salvarFloat(addrTempMin, tempMin); }
  if (umiMax == 0) { umiMax = 80.0; salvarFloat(addrUmiMax, umiMax); }
  if (umiMin == 0) { umiMin = 40.0; salvarFloat(addrUmiMin, umiMin); }
  if (luzMax == 0) { luzMax = 90.0; salvarFloat(addrLuzMax, luzMax); }
  if (luzMin == 0) { luzMin = 20.0; salvarFloat(addrLuzMin, luzMin); }
  if (terraMax == 0) { terraMax = 80.0; salvarFloat(addrTerraMax, terraMax); }
  if (terraMin == 0) { terraMin = 30.0; salvarFloat(addrTerraMin, terraMin); }

  lcd.clear();
  lcd.print("Arduino Config");
  lcd.setCursor(0, 1);
  lcd.print("Conectando...");
  delay(1500);
  
  // Envia thresholds iniciais
  enviarThresholds();
  
  lcd.clear();
  lcd.print("*1 Temp  *2 Umi");
  lcd.setCursor(0, 1);
  lcd.print("*3 Luz  *4 Terra");
}

// ========================================
// LOOP PRINCIPAL
// ========================================

void loop() {
  // Processa comandos da Raspberry Pi
  if (Serial.available() > 0) {
    String cmd = Serial.readStringUntil('\n');
    cmd.trim();
    
    if (cmd == "GET_THRESHOLDS") {
      enviarThresholds();
    }
  }
  
  // Processa teclado
  char tecla = keypad.getKey();
  if (!tecla) return;

  // ========== CONFIGURAR (*1, *2, *3, *4) ==========
  if (tecla == '*') {
    char prox = 0;
    while (!prox) prox = keypad.getKey();

    switch (prox) {
      case '1': { // Temperatura
        float max = lerNumero("Temp MAX:");
        if (max != -1) { 
          tempMax = max; 
          salvarFloat(addrTempMax, max);
        }

        float min = lerNumero("Temp MIN:");
        if (min != -1) { 
          tempMin = min; 
          salvarFloat(addrTempMin, min);
        }

        mostrarValores("Temp:", tempMin, tempMax);
        
        // Envia para Raspberry Pi
        enviarThresholds();
        
        lcd.clear();
        lcd.print("Config enviada!");
        delay(1500);
        break;
      }

      case '2': { // Umidade
        float max = lerNumero("Umi MAX:");
        if (max != -1) { 
          umiMax = max; 
          salvarFloat(addrUmiMax, max);
        }

        float min = lerNumero("Umi MIN:");
        if (min != -1) { 
          umiMin = min; 
          salvarFloat(addrUmiMin, min);
        }

        mostrarValores("Umi:", umiMin, umiMax);
        enviarThresholds();
        
        lcd.clear();
        lcd.print("Config enviada!");
        delay(1500);
        break;
      }

      case '3': { // Luz
        float max = lerNumero("Luz MAX:");
        if (max != -1) { 
          luzMax = max; 
          salvarFloat(addrLuzMax, max);
        }

        float min = lerNumero("Luz MIN:");
        if (min != -1) { 
          luzMin = min; 
          salvarFloat(addrLuzMin, min);
        }

        mostrarValores("Luz:", luzMin, luzMax);
        enviarThresholds();
        
        lcd.clear();
        lcd.print("Config enviada!");
        delay(1500);
        break;
      }

      case '4': { // Terra
        float max = lerNumero("Terra MAX:");
        if (max != -1) { 
          terraMax = max; 
          salvarFloat(addrTerraMax, max);
        }

        float min = lerNumero("Terra MIN:");
        if (min != -1) { 
          terraMin = min; 
          salvarFloat(addrTerraMin, min);
        }

        mostrarValores("Terra:", terraMin, terraMax);
        enviarThresholds();
        
        lcd.clear();
        lcd.print("Config enviada!");
        delay(1500);
        break;
      }

      default:
        lcd.clear();
        lcd.print("Comando invalido");
        delay(1000);
        break;
    }

    lcd.clear();
    lcd.print("*1 Temp  *2 Umi");
    lcd.setCursor(0, 1);
    lcd.print("*3 Luz  *4 Terra");
  }

  // ========== CONSULTAR (#1, #2, #3, #4) ==========
  if (tecla == '#') {
    char prox = 0;
    while (!prox) prox = keypad.getKey();

    switch (prox) {
      case '1': mostrarValores("Temp:", tempMin, tempMax); break;
      case '2': mostrarValores("Umi:", umiMin, umiMax); break;
      case '3': mostrarValores("Luz:", luzMin, luzMax); break;
      case '4': mostrarValores("Terra:", terraMin, terraMax); break;
      default:
        lcd.clear();
        lcd.print("Comando invalido");
        delay(1000);
        break;
    }

    lcd.clear();
    lcd.print("*1 Temp  *2 Umi");
    lcd.setCursor(0, 1);
    lcd.print("*3 Luz  *4 Terra");
  }
}