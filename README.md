# 🌿 Sistema de Estufa Inteligente

Sistema IoT completo para monitoramento e controle automatizado de estufas, com arquitetura escalável usando 2 Arduinos, Raspberry Pi, dashboard web em tempo real e mensageria via RabbitMQ.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

---

## 📋 Índice

- [Visão Geral](#-visão-geral)
- [Arquitetura](#-arquitetura)
- [Componentes](#-componentes)
- [Instalação](#-instalação)
- [Configuração](#-configuração)
- [Uso](#-uso)
- [API REST](#-api-rest)
- [RabbitMQ](#-rabbitmq-opcional)
- [Troubleshooting](#-troubleshooting)
- [Equipe](#-equipe)

---

## 🎯 Visão Geral

Sistema que monitora e controla automaticamente:
- **Temperatura e umidade do ar** (DHT11/DHT22)
- **Umidade do solo** (sensor capacitivo)
- **Luminosidade** (LDR)
- **Irrigação automática** (relé bomba d'água)
- **Ventilação** (relé cooler)
- **Iluminação** (relé fita LED)

### Objetivos

**Geral:** Criar um sistema inteligente que promova condições ideais para crescimento de plantas, otimizando recursos naturais.

**Específicos:**
- Coletar dados ambientais em tempo real
- Armazenar leituras em banco de dados persistente
- Exibir informações em dashboard web responsivo
- Controlar atuadores de forma manual e automática
- Enviar alertas em situações críticas

### Diferenciais

✅ Arquitetura dual Arduino (estável e escalável)  
✅ Comunicação via USB (mais confiável que I2C)  
✅ Configuração via teclado físico (sem necessidade de recompilação)  
✅ Dashboard web em tempo real (WebSocket)  
✅ Banco de dados persistente (SQLite)  
✅ Processamento assíncrono opcional (RabbitMQ)  
✅ Baixo custo (~R$ 997)  

---

## 🏗️ Arquitetura

### Arquitetura Dual Arduino (Recomendada)

```
┌─────────────────────────────────────────────────┐
│           RASPBERRY PI (Flask Server)           │
│                                                 │
│  ┌─────────────────────────────────────────┐   │
│  │   dual_arduino_manager.py               │   │
│  │   - Gerencia 2 conexões USB             │   │
│  │   - Sincroniza thresholds               │   │
│  │   - WebSocket para dashboard            │   │
│  └──────────┬──────────────┬────────────────┘   │
│         USB 1          USB 2                     │
└─────────────┼──────────────┼─────────────────────┘
              │              │
    ┌─────────▼────────┐  ┌─▼──────────────────┐
    │  ARDUINO 1       │  │  ARDUINO 2         │
    │  Sensores        │  │  Configuração      │
    │  • DHT11         │  │  • Keypad 4x3      │
    │  • Solo          │  │  • LCD I2C         │
    │  • LDR           │  │  • EEPROM          │
    │  • LCD I2C       │  │                    │
    │  • Relés (3x)    │  │  Define limites    │
    │  • LEDs/Buzzer   │  │  via teclado       │
    └──────────────────┘  └────────────────────┘
```

### Fluxo de Dados

```
Sensores → Arduino 1 → USB → Raspberry Pi → SQLite
                                    ↓
                              WebSocket → Dashboard
                                    ↓
                            RabbitMQ (opcional) → Workers
```

**Vantagens vs I2C:**
| Aspecto | I2C | USB Dual |
|---------|-----|----------|
| Estabilidade | ⚠️ Problemas com cabos longos | ✅ Serial USB estável |
| Distância | ⚠️ Máx 1-2m | ✅ Até 5m |
| Debug | ⚠️ Difícil | ✅ 2 Serial Monitors |
| Sincronização | ⚠️ A cada 30s | ✅ Instantânea |
| Independência | ⚠️ Dependência total | ✅ Funcionam separados |

---

## 💻 Componentes

### Hardware

| Componente | Quantidade | Função | Valor |
|------------|------------|--------|-------|
| Raspberry Pi 4 (8GB) | 1 | Servidor central | R$ 845,00 |
| Arduino Uno R3 | 2 | Sensores + Config | R$ 160,00 |
| DHT11 | 1 | Temp/umidade ar | R$ 7,27 |
| Sensor Solo | 1 | Umidade solo | R$ 52,44 |
| LDR | 1 | Luminosidade | R$ 3,64 |
| LCD I2C 16x2 | 2 | Display | R$ 40,00 |
| Keypad 4x3 | 1 | Configuração | R$ 15,00 |
| Módulo Relé 3 canais | 1 | Atuadores | R$ 25,00 |
| Buzzer | 1 | Alertas sonoros | R$ 2,00 |
| LEDs | 2 | Indicadores | R$ 1,00 |
| Protoboard 400 | 1 | Montagem | R$ 8,46 |
| **TOTAL** | - | - | **R$ 996,81** |

### Software

- **Python 3.8+** (Flask, Flask-SocketIO, PySerial)
- **SQLite** (banco de dados)
- **RabbitMQ** (opcional - mensageria)
- **Arduino IDE** (desenvolvimento firmware)

---

## 🚀 Instalação

### 1. Preparar Raspberry Pi

```bash
# Atualizar sistema
sudo apt update && sudo apt upgrade -y

# Instalar dependências
sudo apt install python3 python3-pip git -y

# Clonar projeto
git clone https://github.com/seu-usuario/greenhouse.git
cd greenhouse

# Instalar bibliotecas Python
pip3 install -r requirements.txt
```

**requirements.txt:**
```
flask==3.0.0
flask-socketio==5.3.5
flask-cors==4.0.0
pyserial==3.5
pika==1.3.2  # apenas se usar RabbitMQ
```

### 2. Carregar Códigos Arduino

**Arduino 1 - Sensores:**
```
Arquivo: arduino/arduino1_sensors.ino
Placa: Arduino Uno
Porta: Qualquer (auto-detectada)
```

**Arduino 2 - Teclado:**
```
Arquivo: arduino/arduino2_keypad.ino
Placa: Arduino Uno
Porta: Qualquer (auto-detectada)
```

### 3. Conectar Hardware

```
Raspberry Pi
  ├── USB 1 → Arduino 1 (Sensores)
  └── USB 2 → Arduino 2 (Teclado)
```

⚠️ **Não precisa conectar SDA/SCL entre Arduinos!**

### 4. Iniciar Sistema

```bash
cd app
python3 app.py
```

Acesse: `http://[IP-DA-RASPBERRY]:5000`

---

## ⚙️ Configuração

### Via Teclado (Arduino 2)

**Configurar Limites:**
```
*1 → Temperatura
     Exemplo: *1 → 30# → 18#
     (Max=30°C, Min=18°C)

*2 → Umidade do ar
*3 → Luminosidade
*4 → Umidade do solo
```

**Consultar Valores:**
```
#1 → Ver temperatura configurada
#2 → Ver umidade
#3 → Ver luz
#4 → Ver solo
```

### Via Dashboard Web

1. Acesse: `http://[IP]:5000`
2. Clique em "Configurações"
3. Ajuste os sliders
4. Clique em "Salvar"

### Via API

```bash
curl -X POST http://localhost:5000/api/thresholds \
  -H "Content-Type: application/json" \
  -d '{
    "tempMax": 32,
    "tempMin": 16,
    "soilMin": 30
  }'
```

### Calibração de Sensores

**Sensor de Solo:**

Edite `arduino1_sensors.ino`:
```cpp
int soilPercent = map(soilRaw, 1023, 400, 0, 100);
//                             ^^^^  ^^^
//                             seco  molhado
```

**Como calibrar:**
1. Sensor no ar → anote valor
2. Sensor na água → anote valor
3. Ajuste os números no `map()`

**LDR:**
```cpp
int ldrPercent = map(ldrRaw, 900, 100, 0, 100);
//                           ^^^  ^^^
//                         escuro claro
```

---

## 🎮 Uso

### Dashboard Web

**Visualização em Tempo Real:**
- Temperatura/Umidade ar
- Umidade solo
- Luminosidade
- Status dos atuadores

**Controles Manuais:**
- Irrigar agora
- Ligar/desligar cooler
- Ligar/desligar iluminação

**Gráficos Históricos:**
- Últimas 24 horas
- Últimos 7 dias
- Exportar CSV

### Modo Automático

O sistema ativa automaticamente:

**Irrigação:**
```
SE umidade_solo < limite_minimo
ENTÃO ligar_bomba por 5 segundos
```

**Ventilação:**
```
SE temperatura > limite_maximo
ENTÃO ligar_cooler
```

**Iluminação:**
```
SE luminosidade < limite_minimo E hora_dia
ENTÃO ligar_luz
```

### Alertas

**LEDs Indicadores:**
- Verde: Sistema OK
- Vermelho: Alerta ativo

**Buzzer:**
- 1 bip: Ação executada
- 3 bips: Alerta crítico

**LCD:**
- Linha 1: Valores atuais
- Linha 2: Status/alertas

---

## 📡 API REST

### Endpoints Principais

#### Status do Sistema
```http
GET /api/status

Response:
{
  "status": "online",
  "arduino1": "connected",
  "arduino2": "connected",
  "timestamp": "2025-11-18T10:30:00"
}
```

#### Leituras Atuais
```http
GET /api/readings/latest?limit=10

Response:
{
  "readings": [
    {
      "id": 1,
      "temperature": 25.5,
      "humidity": 60,
      "soil_moisture": 45,
      "light_level": 80,
      "timestamp": "2025-11-18T10:30:00"
    }
  ]
}
```

#### Histórico
```http
GET /api/readings/history?hours=24

Response:
{
  "period": "24h",
  "count": 288,
  "readings": [...]
}
```

#### Controle de Irrigação
```http
POST /api/command/irrigate

Response:
{
  "status": "success",
  "message": "Irrigação ativada por 5 segundos"
}
```

#### Controle de Cooler
```http
POST /api/command/cooler
Content-Type: application/json

{
  "state": "ON"  // ou "OFF"
}
```

#### Controle de Luz
```http
POST /api/command/light
Content-Type: application/json

{
  "state": "ON"  // ou "OFF"
}
```

#### Atualizar Limites
```http
POST /api/thresholds
Content-Type: application/json

{
  "tempMax": 30,
  "tempMin": 18,
  "humidMax": 80,
  "humidMin": 40,
  "soilMin": 30,
  "lightMin": 40
}
```

### WebSocket

```javascript
const socket = io('http://[IP]:5000');

// Receber dados dos sensores
socket.on('sensor_data', (data) => {
  console.log(data);
  // {temp: 25.5, humid: 60, soil: 45, light: 80}
});

// Receber alertas
socket.on('alert', (alert) => {
  console.log(alert);
  // {type: 'low_soil', message: '...', severity: 'warning'}
});

// Enviar comando
socket.emit('send_command', {command: 'IRRIGATE'});
```

---

## 🐰 RabbitMQ (Opcional)

### Quando Usar?

Use RabbitMQ se você precisa de:
- ✅ Processamento assíncrono pesado
- ✅ Múltiplas estufas (escalabilidade)
- ✅ Notificações externas (email/SMS)
- ✅ Analytics em batch
- ✅ Machine Learning

⚠️ **O sistema funciona perfeitamente SEM RabbitMQ!**

### Instalação

```bash
# Ubuntu/Raspberry Pi
sudo apt install rabbitmq-server -y
sudo systemctl enable rabbitmq-server
sudo systemctl start rabbitmq-server

# Habilitar interface web
sudo rabbitmq-plugins enable rabbitmq_management

# Acessar: http://localhost:15672
# User: guest / Pass: guest
```

### Arquitetura com RabbitMQ

```
Arduino → Raspberry Pi ─┬→ WebSocket → Dashboard (tempo real)
                        │
                        └→ RabbitMQ ─┬→ Worker Email
                                     ├→ Worker SMS
                                     ├→ Worker Analytics
                                     └→ Worker ML (futuro)
```

### Workers Disponíveis

**Worker de Analytics:**
```bash
python workers.py analytics
```
Processa dados em batch, calcula estatísticas, detecta padrões.

**Worker de Email:**
```bash
python workers.py email
```
Envia notificações por email em alertas críticos.

**Worker de SMS:**
```bash
python workers.py sms
```
Envia SMS via Twilio em emergências.

**Todos os Workers:**
```bash
python workers.py all
```

### Configuração de Email

Edite `workers.py`:
```python
self.smtp_server = "smtp.gmail.com"
self.email_from = "seu-email@gmail.com"
self.email_password = "sua-senha-app"  # Gere em myaccount.google.com/apppasswords
self.email_to = ["admin@estufa.com"]
```

---

## 💾 Banco de Dados

### SQLite (Padrão)

Banco: `greenhouse_data.db` (criado automaticamente)

**Tabelas:**
- `readings`: Leituras dos sensores
- `alerts`: Histórico de alertas
- `actions`: Ações executadas
- `config`: Configurações

**Consultas Úteis:**
```bash
sqlite3 greenhouse_data.db
```

```sql
-- Últimas leituras
SELECT * FROM readings ORDER BY timestamp DESC LIMIT 10;

-- Estatísticas 24h
SELECT 
  AVG(temperature) as temp_avg,
  AVG(humidity) as humid_avg,
  AVG(soil_moisture) as soil_avg
FROM readings
WHERE timestamp >= datetime('now', '-24 hours');

-- Alertas recentes
SELECT * FROM alerts ORDER BY timestamp DESC LIMIT 10;
```

**Limpeza Automática:**
```python
from database import clear_old_data
clear_old_data(days=30)  # Remove dados > 30 dias
```

### Migrar para PostgreSQL

```bash
# Instalar PostgreSQL
sudo apt install postgresql postgresql-contrib -y
pip3 install psycopg2-binary

# Criar banco
sudo -u postgres createdb greenhouse_db
```

Modifique `database.py` para usar `psycopg2`.

---

## 🔧 Troubleshooting

### Arduinos não detectados

```bash
# Listar portas USB
ls /dev/ttyACM* /dev/ttyUSB*

# Ver logs
dmesg | grep tty

# Adicionar permissões
sudo usermod -a -G dialout $USER
# (relogar após executar)
```

### Dashboard não atualiza

1. Verifique console do navegador (F12)
2. Confirme WebSocket conectado
3. Veja logs: `python3 app.py`

### Banco de dados corrompido

```bash
# Backup
cp greenhouse_data.db greenhouse_data.db.backup

# Verificar
sqlite3 greenhouse_data.db "PRAGMA integrity_check;"

# Recriar (PERDA DE DADOS!)
rm greenhouse_data.db
python3 -c "from database import init_database; init_database()"
```

### Thresholds não sincronizam

```bash
# Monitor Arduino 1
python -m serial.tools.miniterm /dev/ttyACM0 9600

# Monitor Arduino 2
python -m serial.tools.miniterm /dev/ttyACM1 9600

# Configure algo no teclado
# Deve aparecer JSON em Arduino 2
# e "Thresholds OK!" em Arduino 1
```

### RabbitMQ não inicia

```bash
# Status
sudo systemctl status rabbitmq-server

# Reiniciar
sudo systemctl restart rabbitmq-server

# Logs
sudo journalctl -u rabbitmq-server -n 50
```

---

## 🚀 Autostart (Opcional)

### Iniciar com Raspberry Pi

```bash
sudo nano /etc/systemd/system/greenhouse.service
```

```ini
[Unit]
Description=Sistema Estufa Inteligente
After=network.target

[Service]
Type=simple
User=pi
WorkingDirectory=/home/pi/greenhouse
ExecStart=/usr/bin/python3 /home/pi/greenhouse/app/app.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable greenhouse.service
sudo systemctl start greenhouse.service
sudo systemctl status greenhouse.service
```

---

## 📊 Estrutura do Projeto

```
greenhouse/
│
├── arduino/
│   ├── arduino1_sensors.ino       # Arduino sensores/atuadores
│   ├── arduino2_keypad.ino        # Arduino configuração
│   └── test_sensors.ino           # Testes individuais
│
├── app/
│   ├── templates/
│   │   └── index.html             # Dashboard web
│   │
│   ├── app.py                     # Servidor Flask
│   ├── database.py                # SQLite manager
│   ├── dual_arduino_manager.py    # Gerenciador 2 Arduinos
│   ├── workers.py                 # RabbitMQ workers
│   ├── rabbitmq_config.py         # Config RabbitMQ
│   └── requirements.txt           # Dependências Python
│
├── docs/
│   ├── SETUP_DUAL_USB.md          # Setup USB dual
│   ├── README_RABBITMQ.md         # Guia RabbitMQ
│   └── API.md                     # Documentação API
│
├── LICENSE
└── README.md                      # Este arquivo
```

---

## 🎓 Equipe

| Nome | Email | Função | Responsabilidades |
|------|-------|--------|-------------------|
| **Alan Scheibler** | 1130556@atitus.edu.br | Eng. Hardware | Montagem física, sensores |
| **Arthur Dezingrini** | 1135044@atitus.edu.br | Dev Front-end | Dashboard, interface |
| **Bruno Serena** | 1129601@atitus.edu.br | Documentação | Manuais, guias |
| **Gabriel Viecili** | 1135192@atitus.edu.br | Dev Back-end | Servidor, banco de dados |

---

## 🎯 Próximas Melhorias

- [ ] App mobile (React Native)
- [ ] Gráficos históricos avançados (Chart.js)
- [ ] Predição ML de irrigação (TensorFlow)
- [ ] Câmera com detecção de pragas (OpenCV)
- [ ] Controle remoto via internet (ngrok/Cloudflare)
- [ ] Integração Google Calendar (lembretes)
- [ ] Relatórios PDF automáticos
- [ ] Sistema multi-estufa (várias localizações)

---

## 📚 Recursos

- **Documentação Arduino**: https://www.arduino.cc/reference
- **Flask Docs**: https://flask.palletsprojects.com/
- **RabbitMQ Tutorials**: https://www.rabbitmq.com/getstarted.html
- **Raspberry Pi**: https://www.raspberrypi.org/documentation/

---

## ⚠️ Principais Riscos

- Falta de sensores adicionais para controle mais preciso
- Instabilidade na comunicação entre hardware e servidor
- Necessidade de calibração periódica dos sensores
- Tempo limitado para testes e ajustes finais

---

## 📄 Licença

MIT License - Livre para uso e modificação.

---

## ✅ Checklist de Instalação

- [ ] RaspberryPi configurada e atualizada
- [ ] 2 Arduinos com códigos carregados
- [ ] Sensores calibrados e testados
- [ ] Banco de dados criado
- [ ] Dashboard acessível via rede
- [ ] WebSocket funcionando
- [ ] Controles manuais testados
- [ ] Modo automático testado
- [ ] Sistema rodando por 1 hora sem erros

---

*Para dúvidas, abra uma issue no GitHub ou consulte os comentários no código.*

## 🧩 Projetos Similares

- [Projeto Estufa - Arduino Uno](https://www.febrace.org/)
- [Estufa Inteligente - FEBRACE](https://www.febrace.org/)
- **Diferencial:** Integração simples com Flask e SQLite, baixo custo e fácil expansão para uso educacional.

---

