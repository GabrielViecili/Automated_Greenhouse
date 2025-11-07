# 🐰 Integração RabbitMQ - Estufa Inteligente

## 📋 Índice
- [Visão Geral](#visão-geral)
- [Instalação](#instalação)
- [Arquitetura](#arquitetura)
- [Como Usar](#como-usar)
- [Workers](#workers)
- [Testes](#testes)
- [FAQ](#faq)

---

## 🎯 Visão Geral

Esta integração adiciona **RabbitMQ** ao sistema de estufa inteligente, permitindo:

✅ **Processamento assíncrono** de dados dos sensores  
✅ **Notificações** via email/SMS em alertas críticos  
✅ **Analytics** em batch de dados coletados  
✅ **Escalabilidade** - adicione novos workers facilmente  
✅ **Resiliência** - mensagens persistem mesmo se workers caírem  

### Por que RabbitMQ?

```
┌─────────────┐
│   Arduino   │ (coleta dados)
└──────┬──────┘
       │ Serial
       ▼
┌──────────────┐
│ Raspberry Pi │
│   (Flask)    │
└──┬────────┬──┘
   │        │
   │        └─────► WebSocket ────► Dashboard (tempo real)
   │                                      │
   └────► RabbitMQ ─────┬────► Worker Email (notificações)
                        ├────► Worker SMS (alertas críticos)
                        ├────► Worker Analytics (relatórios)
                        └────► Worker ML (futuramente)
```

**Sem RabbitMQ**: Tudo roda no mesmo processo  
**Com RabbitMQ**: Cada tarefa em processo separado, escalável

---

## 🔧 Instalação

### 1. Instalar RabbitMQ

#### **Ubuntu/Debian/Raspberry Pi OS**
```bash
# Atualiza pacotes
sudo apt update

# Instala RabbitMQ
sudo apt install rabbitmq-server -y

# Inicia o serviço
sudo systemctl start rabbitmq-server
sudo systemctl enable rabbitmq-server

# Verifica status
sudo systemctl status rabbitmq-server
```

#### **Windows**
1. Baixe em: https://www.rabbitmq.com/install-windows.html
2. Instale o Erlang primeiro (pré-requisito)
3. Instale o RabbitMQ
4. Inicie o serviço

#### **Docker** (qualquer OS)
```bash
docker run -d \
  --name rabbitmq \
  -p 5672:5672 \
  -p 15672:15672 \
  rabbitmq:3-management
```

### 2. Configurar RabbitMQ

```bash
# Habilita interface web de gerenciamento
sudo rabbitmq-plugins enable rabbitmq_management

# Cria usuário (opcional)
sudo rabbitmqctl add_user greenhouse senha123
sudo rabbitmqctl set_user_tags greenhouse administrator
sudo rabbitmqctl set_permissions -p / greenhouse ".*" ".*" ".*"

# Acesse interface web:
# http://localhost:15672
# Usuário: guest / Senha: guest
```

### 3. Instalar Dependências Python

```bash
# Instala dependências (com RabbitMQ)
pip install -r requirements_rabbitmq.txt

# Ou apenas o RabbitMQ
pip install pika
```

---

## 🏗️ Arquitetura

### Exchanges e Filas

```
┌──────────────────────────────────────────────────────────┐
│                        RabbitMQ                          │
├──────────────────────────────────────────────────────────┤
│                                                          │
│  Exchange: greenhouse.sensors (topic)                   │
│    ├─► Queue: sensor.readings                           │
│    └─► Queue: data.analytics                            │
│                                                          │
│  Exchange: greenhouse.alerts (topic)                    │
│    ├─► Queue: sensor.alerts                             │
│    ├─► Queue: email.notifications (severity=critical)   │
│    └─► Queue: sms.notifications (severity=critical)     │
│                                                          │
│  Exchange: greenhouse.commands (topic)                  │
│    └─► Queue: command.arduino                           │
│                                                          │
└──────────────────────────────────────────────────────────┘
```

### Fluxo de Dados

1. **Arduino** lê sensores → envia JSON via serial
2. **serial_reader.py** recebe dados:
   - Salva no SQLite
   - Envia via WebSocket (dashboard tempo real)
   - **Publica no RabbitMQ**
3. **Workers** consomem do RabbitMQ:
   - Email Worker → envia emails
   - SMS Worker → envia SMS
   - Analytics Worker → processa dados em batch

---

## 🚀 Como Usar

### Modo 1: Com RabbitMQ (Recomendado)

```bash
# Terminal 1: Inicia servidor Flask
python app.py

# Terminal 2: Inicia worker de analytics
python workers.py analytics

# Terminal 3: Inicia worker de email (opcional)
python workers.py email

# Terminal 4: Todos os workers de uma vez
python workers.py all
```

### Modo 2: Sem RabbitMQ (Sistema original)

```bash
# Apenas o servidor Flask (sem workers)
python app.py
```

O sistema detecta automaticamente se RabbitMQ está disponível. Se não estiver, continua funcionando normalmente!

---

## 🔨 Workers

### Worker de Email

**Envia emails em alertas críticos**

```bash
python workers.py email
```

**Configuração** (em `workers.py`):
```python
self.smtp_server = "smtp.gmail.com"
self.smtp_port = 587
self.email_from = "seu-email@gmail.com"
self.email_password = "sua-senha-app"  # Use senha de aplicativo!
self.email_to = ["admin@estufa.com"]
```

**Gmail**: Gere senha de aplicativo em https://myaccount.google.com/apppasswords

### Worker de SMS

**Envia SMS em alertas críticos**

```bash
python workers.py sms
```

**Integração com Twilio**:
```bash
pip install twilio

# Em workers.py
from twilio.rest import Client

client = Client(account_sid, auth_token)
message = client.messages.create(
    body="ALERTA ESTUFA: Umidade baixa!",
    from_='+15017122661',
    to='+5554999999999'
)
```

### Worker de Analytics

**Processa dados em batch**

```bash
python workers.py analytics
```

Analisa a cada 20 leituras:
- Calcula médias, mínimas, máximas
- Detecta padrões anormais
- Gera recomendações
- Pode salvar em banco de analytics
- Treinar modelos ML (futuro)

---

## 🧪 Testes

### Teste 1: Conexão RabbitMQ

```bash
python rabbitmq_config.py
```

Deve exibir:
```
[RABBITMQ] Conectado em localhost:5672
[RABBITMQ] Sensor data publicado: {...}
[RABBITMQ] Alerta publicado: low_soil_moisture - critical
✓ Teste concluído!
```

### Teste 2: Serial Reader com RabbitMQ

```bash
python serial_reader_rabbitmq.py
```

Conecta Arduino e publica dados no RabbitMQ.

### Teste 3: Sistema Completo

```bash
# Terminal 1
python app.py

# Terminal 2  
python workers.py analytics

# Acesse: http://localhost:5000
# Observe logs em ambos terminais
```

### Teste 4: Interface Web do RabbitMQ

1. Acesse: http://localhost:15672
2. Login: guest/guest
3. Vá em **Queues** → veja mensagens
4. Vá em **Exchanges** → veja publicações

---

## 📊 Monitoramento

### Via Interface Web

```
http://localhost:15672
```

- **Overview**: Status geral
- **Queues**: Mensagens em cada fila
- **Exchanges**: Publicações
- **Connections**: Clientes conectados

### Via Código

```python
from rabbitmq_config import RabbitMQManager

rabbitmq = RabbitMQManager()
if rabbitmq.connect():
    # Publique mensagens de teste
    rabbitmq.publish_sensor_data({
        'temp': 25.5,
        'humid': 60,
        'soil': 45,
        'light': 80
    })
```

---

## ❓ FAQ

### 1. **Preciso MESMO de RabbitMQ?**

**Não**. O sistema funciona perfeitamente sem ele. Use RabbitMQ se:
- Tiver múltiplas estufas
- Precisar processar dados pesados
- Quiser notificações externas (email/SMS)
- Planeja escalar o sistema

### 2. **RabbitMQ deixa o sistema mais lento?**

Não! É assíncrono. Dados vão para o RabbitMQ e voltam imediatamente. Workers processam em background.

### 3. **Mensagens se perdem se worker cair?**

Não. Filas são **duráveis** - mensagens persistem no disco.

### 4. **Posso ter múltiplos workers do mesmo tipo?**

Sim! RabbitMQ distribui mensagens automaticamente:

```bash
# Terminal 1
python workers.py analytics

# Terminal 2
python workers.py analytics

# Terminal 3
python workers.py analytics
```

Cada worker processa 1/3 das mensagens.

### 5. **Como desabilitar RabbitMQ temporariamente?**

Em `serial_reader_rabbitmq.py`:
```python
reader = ArduinoReaderWithRabbitMQ(
    callback=on_data_received,
    use_rabbitmq=False  # Desabilitado
)
```

### 6. **RabbitMQ consome muita memória?**

Não. Configuração padrão usa ~40MB RAM. Ajustável em `/etc/rabbitmq/rabbitmq.conf`.

---

## 🎓 Próximos Passos

### 1. **Machine Learning Worker**

```python
class MLPredictionWorker:
    def train_model(self, data):
        # Treina modelo com dados históricos
        pass
    
    def predict_irrigation(self, current_data):
        # Prevê quando irrigar
        pass
```

### 2. **Integração com Cloud**

```python
# Publica para AWS IoT Core
rabbitmq.publish_to_cloud(data)
```

### 3. **Dashboard Externo**

```bash
# Worker que alimenta Grafana/Kibana
python workers.py grafana
```

### 4. **Sistema Multilocal**

```
Estufa A (BR) ──┐
Estufa B (PT) ──┼──► RabbitMQ Cloud ──► Dashboard Central
Estufa C (US) ──┘
```

---

## 📝 Estrutura de Arquivos

```
projeto/
│
├── arduino/
│   ├── greenhouse_sensors.ino
│   └── test_sensors.ino
│
├── raspberry_pi/
│   ├── app.py                          # Servidor Flask
│   ├── serial_reader_rabbitmq.py       # Serial + RabbitMQ (NOVO)
│   ├── rabbitmq_config.py              # Config RabbitMQ (NOVO)
│   ├── workers.py                      # Workers (NOVO)
│   ├── database.py                     # SQLite
│   ├── requirements_rabbitmq.txt       # Dependências (NOVO)
│   └── templates/
│       └── dashboard.html
│
└── README_RABBITMQ.md                  # Este arquivo
```

---

## 🆘 Suporte

### RabbitMQ não inicia

```bash
# Verifica logs
sudo journalctl -u rabbitmq-server -n 50

# Reinicia serviço
sudo systemctl restart rabbitmq-server
```

### Worker não conecta

```bash
# Testa conexão
telnet localhost 5672

# Verifica firewall
sudo ufw allow 5672
```

### Mensagens não chegam

1. Verifique interface web: http://localhost:15672
2. Vá em **Queues** → clique na fila → veja se há mensagens
3. Verifique bindings em **Exchanges**

---

## 📚 Recursos

- **RabbitMQ Docs**: https://www.rabbitmq.com/documentation.html
- **Pika (Python Client)**: https://pika.readthedocs.io/
- **Tutorial RabbitMQ**: https://www.rabbitmq.com/getstarted.html

---

## ✅ Checklist de Instalação

- [ ] RabbitMQ instalado e rodando
- [ ] Interface web acessível (http://localhost:15672)
- [ ] `pip install pika` executado
- [ ] Teste `python rabbitmq_config.py` passou
- [ ] Workers testados individualmente
- [ ] Sistema completo testado

---

**🎉 Pronto! Seu sistema agora é escalável e resiliente com RabbitMQ!**