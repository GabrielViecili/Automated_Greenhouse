"""
Workers para processar mensagens do RabbitMQ
Execute cada worker em um processo separado
"""

import sys
import time
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from rabbitmq_config import RabbitMQManager
from typing import Dict
import json
import requests 
import threading

# ==================== WORKER DE EMAIL ====================

class EmailNotificationWorker:
    """
    Worker que consome alertas críticos e envia emails
    Execute: python workers.py email
    """
    
    def __init__(self):
        self.rabbitmq = RabbitMQManager()
        
        # Configurações de email (ajuste conforme seu provedor)
        self.smtp_server = "smtp.gmail.com"
        self.smtp_port = 587
        self.email_from = "seu-email@gmail.com"
        self.email_password = "sua-senha-app"  # Use senha de aplicativo
        self.email_to = ["admin@estufa.com"]
    
    def send_email(self, subject: str, body: str):
        """Envia email usando SMTP"""
        try:
            msg = MIMEMultipart()
            msg['From'] = self.email_from
            msg['To'] = ', '.join(self.email_to)
            msg['Subject'] = subject
            
            msg.attach(MIMEText(body, 'html'))
            
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()
                server.login(self.email_from, self.email_password)
                server.send_message(msg)
            
            print(f"[EMAIL] ✓ Email enviado: {subject}")
            return True
            
        except Exception as e:
            print(f"[EMAIL ERROR] Falha ao enviar email: {e}")
            return False
    
    def process_alert(self, message: Dict):
        """Processa um alerta e envia email"""
        alert_type = message.get('type', 'unknown')
        alert_message = message.get('message', '')
        severity = message.get('severity', 'warning')
        timestamp = message.get('timestamp', '')
        
        print(f"\n[EMAIL WORKER] Processando alerta crítico:")
        print(f"  Tipo: {alert_type}")
        print(f"  Mensagem: {alert_message}")
        print(f"  Severidade: {severity}")
        
        # Monta o email
        subject = f"🚨 ALERTA CRÍTICO - Estufa Inteligente"
        
        body = f"""
        <html>
        <body style="font-family: Arial, sans-serif;">
            <h2 style="color: #ef4444;">⚠️ Alerta Crítico Detectado</h2>
            
            <div style="background: #fee2e2; padding: 20px; border-radius: 10px; margin: 20px 0;">
                <p><strong>Tipo:</strong> {alert_type}</p>
                <p><strong>Mensagem:</strong> {alert_message}</p>
                <p><strong>Severidade:</strong> <span style="color: #ef4444;">{severity.upper()}</span></p>
                <p><strong>Data/Hora:</strong> {timestamp}</p>
            </div>
            
            <h3>Ações Recomendadas:</h3>
            <ul>
                <li>Verificar dashboard em tempo real</li>
                <li>Inspecionar sensores físicos</li>
                <li>Ativar irrigação se necessário</li>
            </ul>
            
            <hr>
            <p style="color: #999; font-size: 12px;">
                Sistema de Monitoramento de Estufa Inteligente<br>
                Este é um email automático - não responda
            </p>
        </body>
        </html>
        """
        
        # Envia email (descomente quando configurar SMTP)
        # self.send_email(subject, body)
        
        # Por enquanto, apenas loga
        print(f"[EMAIL] Email seria enviado para: {self.email_to}")
    
    def start(self):
        """Inicia o worker"""
        print("=" * 60)
        print("EMAIL NOTIFICATION WORKER")
        print("=" * 60)
        print(f"Conectando ao RabbitMQ...")
        
        if self.rabbitmq.connect():
            print(f"✓ Conectado!")
            print(f"Aguardando alertas críticos...\n")
            
            try:
                self.rabbitmq.consume(
                    self.rabbitmq.queues['email_notifications'],
                    self.process_alert
                )
            except KeyboardInterrupt:
                print("\n\n[EMAIL WORKER] Encerrando...")
                self.rabbitmq.disconnect()
        else:
            print("✗ Falha ao conectar RabbitMQ")

# ==================== WORKER DE SMS ====================

class SMSNotificationWorker:
    """
    Worker que consome alertas críticos e envia SMS
    Execute: python workers.py sms
    """
    
    def __init__(self):
        self.rabbitmq = RabbitMQManager()
        # Aqui você integraria com Twilio, AWS SNS, etc.
        self.phone_numbers = ["+5554999999999"]
    
    def send_sms(self, message: str):
        """Envia SMS (integrar com Twilio/AWS SNS)"""
        try:
            # Exemplo com Twilio:
            # from twilio.rest import Client
            # client = Client(account_sid, auth_token)
            # message = client.messages.create(
            #     body=message,
            #     from_='+15017122661',
            #     to='+15558675310'
            # )
            
            print(f"[SMS] SMS seria enviado: {message}")
            return True
            
        except Exception as e:
            print(f"[SMS ERROR] Falha ao enviar SMS: {e}")
            return False
    
    def process_alert(self, message: Dict):
        """Processa um alerta e envia SMS"""
        alert_type = message.get('type', 'unknown')
        alert_message = message.get('message', '')
        
        print(f"\n[SMS WORKER] Alerta crítico recebido:")
        print(f"  {alert_type}: {alert_message}")
        
        sms_text = f"ALERTA ESTUFA: {alert_message}"
        self.send_sms(sms_text)
    
    def start(self):
        """Inicia o worker"""
        print("=" * 60)
        print("SMS NOTIFICATION WORKER")
        print("=" * 60)
        
        if self.rabbitmq.connect():
            print("✓ Conectado! Aguardando alertas...\n")
            
            try:
                self.rabbitmq.consume(
                    self.rabbitmq.queues['sms_notifications'],
                    self.process_alert
                )
            except KeyboardInterrupt:
                print("\n\n[SMS WORKER] Encerrando...")
                self.rabbitmq.disconnect()
        else:
            print("✗ Falha ao conectar")


# ================== WORKER DE DISCORD ==================

class DiscordNotificationWorker:
    """
    Worker que consome alertas críticos e envia via Webhook do Discord
    Execute: python workers.py discord
    """
    
    def __init__(self):
        self.rabbitmq = RabbitMQManager()
        self.webhook_url = "https://discord.com/api/webhooks/1438969223572361237/pCmaG6YYOiYrFxqqMk9IXioB6VPt2TYx2q-AV0Yj8dhUTloUobbuh46m65ao35ayXOtV" 
    
    def send_discord_webhook(self, message: Dict):
        """Envia um alerta formatado para o Discord via Webhook"""
        
        alert_type = message.get('type', 'desconhecido')
        alert_message = message.get('message', 'Sem detalhes')
        severity = message.get('severity', 'indefinida').upper()
        timestamp = message.get('timestamp', 'agora')

        # Formata a cor do "embed" baseado na severidade
        colors = {
            'CRITICAL': 15158332, # Vermelho
            'WARNING': 15105570,  # Laranja
            'INFO': 3447003       # Azul
        }
        
        # Cria um "embed" para uma mensagem bonita
        embed = {
            "title": f"🚨 Alerta de Estufa: {alert_type}",
            "color": colors.get(severity, 15158332), # Padrão para vermelho
            "description": f"**{alert_message}**",
            "fields": [
                {"name": "Severidade", "value": severity, "inline": True},
                {"name": "Timestamp", "value": timestamp, "inline": True}
            ],
            "footer": {"text": "Sistema de Monitoramento de Estufa Inteligente"}
        }
        
        # Monta o payload final
        data = {
            "username": "Monitor da Estufa",
            "avatar_url": "https://i.imgur.com/gJt0MS1.png", # Ícone (opcional)
            "embeds": [embed]
        }
        
        try:
            response = requests.post(self.webhook_url, json=data)
            response.raise_for_status() # Lança erro se o status for 4xx ou 5xx
            print(f"[DISCORD] ✓ Alerta enviado: {alert_type}")
            return True
        except requests.exceptions.RequestException as e:
            print(f"[DISCORD ERROR] Falha ao enviar webhook: {e}")
            return False

    def process_alert(self, message: Dict):
        """Processa um alerta e envia para o Discord"""
        print(f"\n[DISCORD WORKER] Alerta crítico recebido:")
        print(f"  Tipo: {message.get('type')}")
        print(f"  Enviando para Discord...")
        
        self.send_discord_webhook(message)
    
    def start(self):
        """Inicia o worker"""
        print("=" * 60)
        print("DISCORD NOTIFICATION WORKER")
        print("=" * 60)
        
        if self.rabbitmq.connect():
            print("✓ Conectado! Aguardando alertas...\n")
            
            try:
                # IMPORTANTE: Veja o Passo 4
                self.rabbitmq.consume(
                    self.rabbitmq.queues['discord_notifications'],
                    self.process_alert
                )
            except KeyboardInterrupt:
                print("\n\n[DISCORD WORKER] Encerrando...")
                self.rabbitmq.disconnect()
        else:
            print("✗ Falha ao conectar")

# ==================== WORKER DE ANALYTICS ====================

class DataAnalyticsWorker:
    """
    Worker que processa dados de sensores em batch para analytics
    Execute: python workers.py analytics
    """
    
    def __init__(self):
        self.rabbitmq = RabbitMQManager()
        self.buffer = []
        self.buffer_size = 20  # Analisa a cada 20 leituras
    
    def process_data(self, message: Dict):
        """Processa dados de sensores"""
        data = message.get('data', {})
        timestamp = message.get('timestamp', '')
        
        self.buffer.append({
            'timestamp': timestamp,
            'temp': data.get('temp', 0),
            'humid': data.get('humid', 0),
            'soil': data.get('soil', 0),
            'light': data.get('light', 0)
        })
        
        print(f"[ANALYTICS] Buffer: {len(self.buffer)}/{self.buffer_size}")
        
        if len(self.buffer) >= self.buffer_size:
            self.analyze_batch()
            self.buffer = []
    
    def analyze_batch(self):
        """Analisa lote de dados"""
        if not self.buffer:
            return
        
        print("\n" + "=" * 60)
        print(f"ANÁLISE DE {len(self.buffer)} LEITURAS")
        print("=" * 60)
        
        # Calcula estatísticas
        temps = [d['temp'] for d in self.buffer]
        humids = [d['humid'] for d in self.buffer]
        soils = [d['soil'] for d in self.buffer]
        lights = [d['light'] for d in self.buffer]
        
        stats = {
            'temperatura': {
                'média': sum(temps) / len(temps),
                'mín': min(temps),
                'máx': max(temps)
            },
            'umidade_ar': {
                'média': sum(humids) / len(humids),
                'mín': min(humids),
                'máx': max(humids)
            },
            'umidade_solo': {
                'média': sum(soils) / len(soils),
                'mín': min(soils),
                'máx': max(soils)
            },
            'luminosidade': {
                'média': sum(lights) / len(lights),
                'mín': min(lights),
                'máx': max(lights)
            }
        }
        
        for sensor, values in stats.items():
            print(f"\n{sensor.upper()}:")
            print(f"  Média: {values['média']:.1f}")
            print(f"  Mínima: {values['mín']:.1f}")
            print(f"  Máxima: {values['máx']:.1f}")
        
        # Detecta padrões
        self.detect_patterns(stats)
        
        print("\n" + "=" * 60 + "\n")
    
    def detect_patterns(self, stats):
        """Detecta padrões nos dados"""
        print("\nPADRÕES DETECTADOS:")
        
        # Temperatura instável
        temp_range = stats['temperatura']['máx'] - stats['temperatura']['mín']
        if temp_range > 5:
            print(f"  ⚠️  Temperatura instável (variação de {temp_range:.1f}°C)")
        
        # Solo consistentemente baixo
        if stats['umidade_solo']['média'] < 35:
            print(f"  🚨 Umidade do solo consistentemente baixa ({stats['umidade_solo']['média']:.1f}%)")
            print(f"     Recomendação: Verificar sistema de irrigação")
        
        # Boa condição
        if (20 <= stats['temperatura']['média'] <= 30 and
            stats['umidade_solo']['média'] > 40 and
            stats['umidade_ar']['média'] > 50):
            print(f"  ✓ Condições ideais detectadas!")
    
    def start(self):
        """Inicia o worker"""
        print("=" * 60)
        print("DATA ANALYTICS WORKER")
        print("=" * 60)
        
        if self.rabbitmq.connect():
            print("✓ Conectado! Processando dados...\n")
            
            try:
                self.rabbitmq.consume(
                    self.rabbitmq.queues['data_analytics'],
                    self.process_data
                )
            except KeyboardInterrupt:
                print("\n\n[ANALYTICS WORKER] Encerrando...")
                if self.buffer:
                    print("Processando últimos dados do buffer...")
                    self.analyze_batch()
                self.rabbitmq.disconnect()
        else:
            print("✗ Falha ao conectar")

# ==================== MAIN ====================

def main():
    if len(sys.argv) < 2:
        print("""
USO: python workers.py [worker_type]

Workers disponíveis:
  email      - Envia emails para alertas críticos
  sms        - Envia SMS para alertas críticos
  discord    - Envia alertas para o Discord
  analytics  - Processa dados de sensores em batch
  all        - Inicia todos os workers (em threads separadas)

Exemplos:
  python workers.py email
  python workers.py analytics
        """)
        return
    
    worker_type = sys.argv[1].lower()
    
    if worker_type == 'email':
        worker = EmailNotificationWorker()
        worker.start()
    
    elif worker_type == 'sms':
        worker = SMSNotificationWorker()
        worker.start()

    elif worker_type == 'discord':
        worker = DiscordNotificationWorker()
        worker.start()
    
    elif worker_type == 'analytics':
        worker = DataAnalyticsWorker()
        worker.start()
    
    elif worker_type == 'all':
        import threading
        
        print("Iniciando todos os workers...\n")
        
        workers = [
            EmailNotificationWorker(),
            SMSNotificationWorker(),
            DataAnalyticsWorker(),
            DiscordNotificationWorker()
        ]
        
        threads = []
        for worker in workers:
            thread = threading.Thread(target=worker.start, daemon=True)
            thread.start()
            threads.append(thread)
            time.sleep(1)  # Delay entre inicializações
        
        try:
            for thread in threads:
                thread.join()
        except KeyboardInterrupt:
            print("\n\nEncerrando todos os workers...")
    
    else:
        print(f"Worker desconhecido: {worker_type}")
        print("Use: email, sms, discord, analytics, ou all")

if __name__ == '__main__':
    main()