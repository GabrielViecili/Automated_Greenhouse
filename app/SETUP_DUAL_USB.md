# 🔌 Setup - 2 Arduinos via USB

## 🎯 Nova Arquitetura (MUITO MELHOR!)

```
┌─────────────────────────────────────────────────┐
│           RASPBERRY PI (Flask)                  │
│                                                 │
│  ┌─────────────────────────────────────────┐   │
│  │   dual_arduino_manager.py               │   │
│  │   - Gerencia 2 conexões USB             │   │
│  │   - Sincroniza thresholds               │   │
│  └──────────┬──────────────┬────────────────┘   │
│             │              │                     │
│         USB 1          USB 2                     │
└─────────────┼──────────────┼─────────────────────┘
              │              │
              │              │
    ┌─────────▼────────┐  ┌─▼──────────────────┐
    │  ARDUINO 1       │  │  ARDUINO 2         │
    │  Sensores        │  │  Teclado           │
    │  - DHT11         │  │  - Keypad 4x3      │
    │  - Solo          │  │  - LCD I2C         │
    │  - LDR           │  │  - EEPROM          │
    │  - LCD I2C       │  │                    │
    │  - LEDs/Buzzer   │  │  Envia thresholds  │
    │  - Relé          │  │  via Serial        │
    │                  │  │                    │
    │  Envia sensores  │  │                    │
    │  via Serial      │  │                    │
    └──────────────────┘  └────────────────────┘
```

## ✅ Vantagens vs I2C

| Aspecto | I2C entre Arduinos | 2 USBs na Raspberry Pi |
|---------|-------------------|------------------------|
| **Estabilidade** | ⚠️ Problemas com cabos longos | ✅ Serial USB muito estável |
| **Distância** | ⚠️ Máx 1-2 metros | ✅ Até 5 metros (cabo USB) |
| **Debug** | ⚠️ Difícil depurar | ✅ 2 Serial Monitors |
| **Sincronização** | ⚠️ A cada 30 segundos | ✅ Instantânea |
| **Independência** | ⚠️ Se Arduino 1 trava, perde tudo | ✅ Cada um funciona sozinho |
| **Escalabilidade** | ⚠️ Difícil adicionar mais | ✅ Fácil adicionar Arduino 3, 4... |
| **Complexidade** | 🔧 Código I2C complexo | ✅ Código Serial simples |

---

## 📦 Estrutura de Arquivos

```
GREENHOUSE/
│
├── 📂 app/
│   ├── 📂 templates/
│   │   └── index.html
│   │
│   ├── app.py                      (versão original - 1 Arduino)
│   ├── app_dual.py                 ← NOVO (2 Arduinos USB)
│   ├── database.py
│   ├── dual_arduino_manager.py     ← NOVO
│   └── requirements.txt
│
├── 📂 arduino/
│   ├── arduino1_sensors.ino        ← NOVO (sensores via USB)
│   ├── arduino2_keypad.ino         ← NOVO (teclado via USB)
│   │
│   ├── greenhouse_sensors.ino      (versão antiga)
│   └── test_sensors.ino
│
├── SETUP_DUAL_USB.md              ← Este arquivo
└── README.md
```

---

## 🚀 Instalação Rápida (4 passos)

### 1️⃣ Carregar códigos

**Arduino 1** (Sensores):
```
Arquivo: arduino/arduino1_sensors.ino
Placa: Arduino Uno
```

**Arduino 2** (Teclado):
```
Arquivo: arduino/arduino2_keypad.ino
Placa: Arduino Uno
```

### 2️⃣ Conectar na Raspberry Pi

```
Raspberry Pi
  ├── USB 1 → Arduino 1 (Sensores)
  └── USB 2 → Arduino 2 (Teclado)
```

⚠️ **IMPORTANTE**: 
- **NÃO precisa** conectar SDA/SCL entre eles
- **NÃO precisa** compartilhar GND
- Cada um é totalmente independente!

### 3️⃣ Instalar dependências

```bash
cd app
pip install -r requirements.txt
```

### 4️⃣ Iniciar sistema

```bash
python app_dual.py
```

Saída esperada:
```
==============================================================
SISTEMA DE ESTUFA INTELIGENTE - 2 ARDUINOS
==============================================================

[1/3] Inicializando banco de dados...
[DATABASE] Banco de dados inicializado: greenhouse.db

[2/3] Conectando aos 2 Arduinos...
  - Arduino 1: Sensores/Atuadores
  - Arduino 2: Teclado/Configuração
[DUAL] Procurando Arduinos...
[DUAL] Encontrados 2 Arduinos:
  1. /dev/ttyACM0
  2. /dev/ttyACM1
[IDENTIFY] /dev/ttyACM0: {"status":"arduino1_ready"}
  ✓ /dev/ttyACM0 = Arduino Sensores
[IDENTIFY] /dev/ttyACM1: {"source":"arduino2","thresholds":...}
  ✓ /dev/ttyACM1 = Arduino Teclado
[DUAL] Arduino 1 (Sensores) conectado em /dev/ttyACM0
[DUAL] Arduino 2 (Teclado) conectado em /dev/ttyACM1
[APP] ✓ 2 Arduinos conectados e iniciados!

[3/3] Iniciando tasks em background...

==============================================================
SERVIDOR INICIADO!
==============================================================
Acesse: http://localhost:5000
WebSocket: ws://localhost:5000

✓ Status dos Arduinos:
  Arduino 1 (Sensores): /dev/ttyACM0
  Arduino 2 (Teclado):  /dev/ttyACM1

Dica: Configure thresholds no teclado (Arduino 2)
      e veja a sincronização automática!
==============================================================
```

---

## 🎮 Como Usar

### Via Dashboard Web

1. Acesse: `http://[IP_RASPBERRY]:5000`
2. Veja sensores em tempo real
3. Controle irrigação
4. Veja alertas

### Via Teclado (Arduino 2)

```
*1  → Configurar Temperatura
      Ex: *1 → 30 → # → 18 → #
      (Max=30°C, Min=18°C)

*2  → Configurar Umidade do Ar
*3  → Configurar Luminosidade
*4  → Configurar Umidade do Solo

#1  → Consultar Temperatura configurada
#2  → Consultar Umidade configurada
#3  → Consultar Luz configurada
#4  → Consultar Solo configurado
```

### Fluxo de Sincronização

```
1. Usuário pressiona *1 no teclado
2. Arduino 2 pede Max e Min
3. Usuário digita valores
4. Arduino 2 salva na EEPROM
5. Arduino 2 envia JSON via Serial:
   {"source":"arduino2","thresholds":{"tempMax":30,"tempMin":18,...}}
6. Raspberry Pi recebe
7. Raspberry Pi extrai thresholds
8. Raspberry Pi envia para Arduino 1 via Serial
9. Arduino 1 atualiza thresholds internos
10. Arduino 1 usa novos limites IMEDIATAMENTE
11. LCD do Arduino 1 mostra "Thresholds OK!"
```

⚡ **Instantâneo!** Sem esperar 30 segundos!

---

## 🔧 Comandos Via API

### Listar Thresholds Atuais

```bash
curl http://localhost:5000/api/thresholds
```

Resposta:
```json
{
  "thresholds": {
    "tempMax": 30,
    "tempMin": 18,
    "umiMax": 80,
    "umiMin": 40,
    "terraMax": 80,
    "terraMin": 30
  }
}
```

### Atualizar Thresholds (via API)

```bash
curl -X POST http://localhost:5000/api/thresholds \
  -H "Content-Type: application/json" \
  -d '{
    "tempMax": 32,
    "tempMin": 16
  }'
```

⚠️ **Nota**: Arduino 2 (teclado) tem prioridade. Se usuário configurar via teclado, sobrescreve a API.

### Ativar Irrigação

```bash
curl -X POST http://localhost:5000/api/command/irrigate
```

### Status do Sistema

```bash
curl http://localhost:5000/api/status
```

Resposta:
```json
{
  "status": "online",
  "arduino_connected": true,
  "arduino1": "connected",
  "arduino2": "connected",
  "timestamp": "2025-11-07T15:30:00"
}
```

---

## 🐛 Troubleshooting

### Problema: "Apenas 1 Arduino encontrado"

**Solução**:
1. Confirme que **2 USBs** estão conectados
2. Execute: `ls /dev/ttyACM* /dev/ttyUSB*`
3. Deve listar 2 portas

### Problema: "Não foi possível identificar os 2 Arduinos"

**Causa**: Mensagens iniciais não foram lidas corretamente.

**Solução**:
1. Desconecte e reconecte os USBs
2. Aguarde 3 segundos
3. Inicie `python app_dual.py` novamente

### Problema: Thresholds não sincronizam

**Diagnóstico**:
```bash
# Terminal 1: Monitor Arduino 2
python -m serial.tools.miniterm /dev/ttyACM1 9600

# Configure algo no teclado
# Deve aparecer: {"source":"arduino2","thresholds":...}

# Terminal 2: Monitor Arduino 1
python -m serial.tools.miniterm /dev/ttyACM0 9600

# Deve aparecer: Thresholds OK!
```

### Problema: Serial Monitor não abre

```bash
# Adicione seu usuário ao grupo dialout
sudo usermod -a -G dialout $USER

# Reinicie sessão
```

---

## 📊 Logs e Debug

### Ver logs em tempo real

```bash
# Inicia servidor com logs detalhados
python app_dual.py 2>&1 | tee greenhouse.log
```

### Testar gerenciador isoladamente

```bash
# Testa apenas o dual_arduino_manager.py
python dual_arduino_manager.py
```

Saída esperada:
```
==============================================================
TESTE DO GERENCIADOR DUAL ARDUINO
==============================================================
[DUAL] Procurando Arduinos...
[DUAL] Encontrados 2 Arduinos:
  1. /dev/ttyACM0
  2. /dev/ttyACM1
...
✓ Ambos Arduinos conectados!
Iniciando leitura contínua...

Testando por 60 segundos...
Configure algo no teclado (Arduino 2) para ver sincronização!

[SENSORES] T:25.5°C H:60% S:45% L:80%
[ARD2 →] Novos thresholds recebidos!
  Temp: 18-30°C
  Solo: >35%
[DUAL → ARD1] {"tempMax":30,"tempMin":18,...}
```

---

## 🎓 Comparação: I2C vs USB

### Código I2C (complexo)

```cpp
// Arduino 1
Wire.requestFrom(I2C_SLAVE_ADDR, 32);
byte buffer[4];
for (int i = 0; i < 4; i++) buffer[i] = Wire.read();
memcpy(&thresholds.tempMax, buffer, 4);
// ... mais 28 bytes ...

// Arduino 2
void requestEvent() {
  byte buffer[4];
  memcpy(buffer, &tempMax, 4);
  Wire.write(buffer, 4);
  // ... enviar 8 floats ...
}
```

### Código USB (simples)

```cpp
// Arduino 1
void parseThresholdsJSON(String json) {
  // Parse JSON diretamente
  thresholds.tempMax = extractValue(json, "tempMax");
}

// Arduino 2
void enviarThresholds() {
  String json = "{\"tempMax\":" + String(tempMax) + "}";
  Serial.println(json);
}
```

✅ **Muito mais simples!**

---

## 🚀 Extensões Futuras

### Adicionar Arduino 3 (Câmera)

```python
# dual_arduino_manager.py → triple_arduino_manager.py
self.arduino3 = serial.Serial('/dev/ttyACM2', 9600)
```

### Adicionar Arduino 4 (Ventilação)

```python
# Basta adicionar mais uma conexão USB!
```

### Sistema Multi-Estufa

```python
# estufa1/
#   arduino1_sensores.py
#   arduino2_teclado.py

# estufa2/
#   arduino1_sensores.py
#   arduino2_teclado.py

# Central Raspberry Pi recebe todos via USB Hub
```

---

## ✅ Checklist

Antes de colocar em produção:

- [ ] 2 Arduinos carregados com códigos corretos
- [ ] 2 USBs conectados na Raspberry Pi
- [ ] `python dual_arduino_manager.py` funciona
- [ ] `python app_dual.py` inicia sem erros
- [ ] Dashboard mostra dados em tempo real
- [ ] Configurar threshold no teclado sincroniza instantaneamente
- [ ] Irrigação manual funciona
- [ ] Irrigação automática funciona
- [ ] Sistema rodando por 1 hora sem problemas

---

## 📚 Arquivos de Referência

- **arduino1_sensors.ino**: Código do Arduino de sensores
- **arduino2_keypad.ino**: Código do Arduino de teclado
- **dual_arduino_manager.py**: Gerenciador Python
- **app_dual.py**: Servidor Flask atualizado

---

**🎉 Sistema muito mais robusto e fácil de manter!**

A arquitetura USB é superior em todos os aspectos comparada ao I2C entre Arduinos.