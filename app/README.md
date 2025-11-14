# Sistema de Estufa Inteligente

Sistema completo de monitoramento e controle de estufa com 2 Arduinos, Raspberry Pi, dashboard web em tempo real e alertas via RabbitMQ.

---

## 📋 Componentes

### **Arduino 1 - Sensores/Atuadores**
- **Sensores:**
  - DHT11 (temperatura e umidade do ar)
  - Sensor de umidade do solo
  - LDR (luminosidade)
- **Atuadores:**
  - Relé bomba d'água
  - Relé cooler/ventilador
  - Relé fita LED
  - LCD I2C 16x2 (0x27)
  - LEDs indicadores (verde/vermelho)
  - Buzzer

### **Arduino 2 - Configuração**
- Teclado matricial 4x3
- LCD I2C 16x2 (0x27)
- EEPROM (armazenamento de thresholds)

### **Raspberry Pi**
- Servidor Flask
- WebSocket em tempo real
- Banco de dados SQLite
- RabbitMQ (apenas alertas críticos)

---

## 🔧 Instalação

### **1. Configurar Raspberry Pi**

```bash
# Atualizar sistema
sudo apt update && sudo apt upgrade -y

# Instalar Python e dependências
sudo apt install python3 python3-pip -y

# Instalar RabbitMQ (opcional, apenas para alertas)
sudo apt install rabbitmq-server -y
sudo systemctl enable rabbitmq-server
sudo systemctl start rabbitmq-server

# Criar pasta do projeto
mkdir ~/greenhouse
cd ~/greenhouse

# Instalar dependências Python
pip3 install flask flask-socketio flask-cors pyserial pika
```

### **2. Upload dos códigos Arduino**

**Arduino 1:**
- Arquivo: `arduino1_sensors.ino`
- Upload via Arduino IDE
- Conectar via USB na Raspberry Pi

**Arduino 2:**
- Arquivo: `arduino2_keypad.ino` (do seu projeto original)
- Upload via Arduino IDE
- Conectar via USB na Raspberry Pi

### **3. Copiar arquivos Python para Raspberry Pi**

Copie estes arquivos para `~/greenhouse/`:
- `app.py`
- `database.py`
- `dual_arduino_manager.py`
- `rabbitmq_config.py` (opcional)
- `index.html` → `templates/index.html`

```bash
# Criar pasta templates
mkdir ~/greenhouse/templates

# Mover index.html
mv index.html ~/greenhouse/templates/
```

---

## 🚀 Execução

### **Modo Normal (sem RabbitMQ)**

```bash
cd ~/greenhouse
python3 app.py
```

Acesse: `http://<IP_DA_RASPBERRY>:5000`

### **Modo Completo (com RabbitMQ)**

**Terminal 1 - Servidor principal:**
```bash
python3 app.py
```

**Terminal 2 - Worker de alertas (opcional):**
```bash
python3 rabbitmq_config.py worker
```

---

## 📊 Banco de Dados

### **SQLite Persistente**

O banco `greenhouse_data.db` é criado automaticamente e **mantém dados entre execuções**.

**Tabelas:**
- `readings`: Leituras dos sensores
- `alerts`: Alertas do sistema
- `actions`: Ações executadas
- `config`: Configurações

**Consultar dados:**
```bash
sqlite3 greenhouse_data.db
```

```sql
-- Ver últimas leituras
SELECT * FROM readings ORDER BY timestamp DESC LIMIT 10;

-- Ver alertas
SELECT * FROM alerts ORDER BY timestamp DESC LIMIT 10;

-- Estatísticas
SELECT 
  AVG(temperature) as temp_avg,
  AVG(humidity) as humid_avg,
  AVG(soil_moisture) as soil_avg
FROM readings
WHERE timestamp >= datetime('now', '-24 hours');
```

**Limpeza (opcional):**
```python
from database import clear_old_data
clear_old_data(days=30)  # Remove dados com mais de 30 dias
```

### **Migrar para PostgreSQL (opcional)**

Se quiser usar PostgreSQL em vez de SQLite:

```bash
# Instalar PostgreSQL
sudo apt install postgresql postgresql-contrib -y

# Instalar driver Python
pip3 install psycopg2-binary

# Criar banco
sudo -u postgres createdb greenhouse_db
```

Depois modifique `database.py` para usar `psycopg2` em vez de `sqlite3`.

---

## 🔌 API REST

### **Status do Sistema**
```http
GET /api/status
```

### **Leituras**
```http
GET /api/readings/latest?limit=10
GET /api/readings/history?hours=24
```

### **Alertas**
```http
GET /api/alerts/latest?limit=10
```

### **Controles**
```http
POST /api/command/irrigate
POST /api/command/cooler
  Body: {"state": "ON"}  # ou "OFF"
  
POST /api/command/light
  Body: {"state": "ON"}  # ou "OFF"
  
POST /api/command/auto_irrigation
  Body: {"enable": true}  # ou false
```

### **Thresholds**
```http
GET /api/thresholds
POST /api/thresholds
  Body: {"tempMax": 30, "tempMin": 18, ...}
```

---

## 🌐 WebSocket

Conecte ao WebSocket para receber dados em tempo real:

```javascript
const socket = io('http://<IP_RASPBERRY>:5000');

// Receber dados dos sensores
socket.on('sensor_data', (data) => {
  console.log(data); // {temp, humid, soil, light}
});

// Enviar comando
socket.emit('send_command', {command: 'IRRIGATE'});
```

---

## 🐰 RabbitMQ (Alertas Críticos)

**O RabbitMQ é usado APENAS para:**
- Falhas de conexão com Arduinos
- Timeout de sensores (sem dados por 30s)
- Erros críticos do sistema

**Dados normais vão para:** WebSocket + SQLite

### **Configurar alertas por email**

Edite `rabbitmq_config.py`:

```python
class AlertConsumerWorker:
    def __init__(self):
        self.smtp_server = "smtp.gmail.com"
        self.email_from = "seu-email@gmail.com"
        self.email_password = "sua-senha-app"
        self.email_to = ["admin@estufa.com"]
    
    def process_alert(self, message):
        # Seu código de envio de email aqui
        self.send_email(
            subject=f"🚨 Alerta: {message['type']}",
            body=message['message']
        )
```

---

## ⚙️ Configuração via Teclado (Arduino 2)

**Configurar thresholds:**
- `*1` → Temperatura (min/max)
- `*2` → Umidade do ar (min/max)
- `*3` → Luminosidade (min/max)
- `*4` → Umidade do solo (min/max)

**Consultar valores:**
- `#1` → Ver temperatura
- `#2` → Ver umidade
- `#3` → Ver luminosidade
- `#4` → Ver solo

**Exemplo:**
1. Pressione `*1`
2. Digite `30` + `#` (temp máxima)
3. Digite `18` + `#` (temp mínima)
4. Valores são salvos na EEPROM e enviados para Arduino 1

---

## 🔍 Troubleshooting

### **Arduinos não detectados**
```bash
# Listar portas USB
ls /dev/ttyACM* /dev/ttyUSB*

# Ver logs do sistema
dmesg | grep tty
```

### **RabbitMQ não inicia**
```bash
# Status
sudo systemctl status rabbitmq-server

# Reiniciar
sudo systemctl restart rabbitmq-server

# Logs
sudo tail -f /var/log/rabbitmq/rabbit@*.log
```

### **Banco de dados corrompido**
```bash
# Fazer backup
cp greenhouse_data.db greenhouse_data.db.backup

# Verificar integridade
sqlite3 greenhouse_data.db "PRAGMA integrity_check;"

# Recriar (PERDA DE DADOS!)
rm greenhouse_data.db
python3 -c "from database import init_database; init_database()"
```

### **Dashboard não atualiza**
1. Verifique console do navegador (F12)
2. Confirme que WebSocket conectou
3. Veja logs do servidor: `python3 app.py`

---

## 📈 Calibração dos Sensores

### **Sensor de Solo**

Edite no Arduino 1:

```cpp
// Valores de calibração (ajuste conforme seu sensor)
int soilPercent = map(soilRaw, 1023, 400, 0, 100);
//                             ^^^^  ^^^
//                             seco  molhado
```

**Como calibrar:**
1. Sensor no ar (seco) → anote valor
2. Sensor na água → anote valor
3. Ajuste os números no `map()`

### **LDR (Luminosidade)**

```cpp
int ldrPercent = map(ldrRaw, 900, 100, 0, 100);
//                           ^^^  ^^^
//                           escuro claro
```

---

## 🚀 Autostart (Iniciar com Raspberry Pi)

### **Criar serviço systemd**

```bash
sudo nano /etc/systemd/system/greenhouse.service
```

Conteúdo:

```ini
[Unit]
Description=Sistema de Estufa Inteligente
After=network.target rabbitmq-server.service

[Service]
Type=simple
User=pi
WorkingDirectory=/home/pi/greenhouse
ExecStart=/usr/bin/python3 /home/pi/greenhouse/app.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Ativar:

```bash
sudo systemctl enable greenhouse.service
sudo systemctl start greenhouse.service
sudo systemctl status greenhouse.service
```

Ver logs:
```bash
sudo journalctl -u greenhouse.service -f
```

---

## 📝 Logs

**Ativar logs detalhados:**

```python
# No app.py
import logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler('greenhouse.log'),
        logging.StreamHandler()
    ]
)
```

---

## 🎯 Próximas Melhorias

- [ ] App mobile (React Native)
- [ ] Gráficos históricos avançados
- [ ] Predição ML de irrigação
- [ ] Controle remoto via internet
- [ ] Câmera com detecção de pragas
- [ ] Integração com Google Calendar
- [ ] Relatórios PDF automáticos

---

## 📄 Licença

MIT License - Livre para uso e modificação

---

## 👤 Autor

Seu Nome - Estufa Inteligente 2025

---

**Dúvidas?** Abra uma issue no GitHub ou consulte os comentários nos códigos.