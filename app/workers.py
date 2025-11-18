"""
WORKER DE NOTIFICAÇÕES - APENAS DISCORD
Execute: python workers.py
"""

import sys
import time
import requests
from rabbitmq_config import RabbitMQManager
from typing import Dict

class DiscordNotificationWorker:
    """
    Worker que consome alertas críticos e envia para Discord
    """
    
    def __init__(self, webhook_url=None):
        self.rabbitmq = RabbitMQManager()
        
        # Configure seu Webhook do Discord aqui
        # Tutorial: Discord > Server Settings > Integrations > Webhooks > New Webhook
        self.webhook_url = webhook_url or "https://discord.com/api/webhooks/1438969223572361237/pCmaG6YYOiYrFxqqMk9IXioB6VPt2TYx2q-AV0Yj8dhUTloUobbuh46m65ao35ayXOtV"
        
        # Emojis para diferentes tipos de alerta
        self.emoji_map = {
            'arduino_connection_failed': '🔌',
            'arduino_connection_error': '❌',
            'arduino1_timeout': '🚨',
            'arduino2_timeout': '⚠️',
            'dht11_failure': '🌡️',
            'soil_sensor_failure': '💧',
            'ldr_sensor_failure': '☀️',
            'high_temperature': '🔥',
            'low_temperature': '❄️',
            'low_soil_moisture': '🌵',
            'low_humidity': '💨',
            'pump_activated': '💧',
            'cooler_activated': '❄️',
            'cooler_deactivated': '✅',
            'light_activated': '💡',
            'light_deactivated': '🌞',
            'system_reconnected': '✅',
            'critical': '🚨',
            'warning': '⚠️',
            'info': 'ℹ️',
            'average_report': '📊'
        }
        
        # Cores para embeds (formato decimal)
        self.color_map = {
            'critical': 16711680,  # Vermelho
            'warning': 16776960,   # Amarelo
            'info': 3447003        # Azul
        }
    
    def send_discord_notification(self, alert: Dict):
        """Envia notificação para Discord via Webhook"""
        try:
            alert_type = alert.get('type', 'unknown')
            message = alert.get('message', 'Sem mensagem')
            severity = alert.get('severity', 'info')
            timestamp = alert.get('timestamp', '')
            
            # Seleciona emoji
            emoji = self.emoji_map.get(alert_type, self.emoji_map.get(severity, '📢'))
            
            # Seleciona cor
            color = self.color_map.get(severity, 3447003)
            
            # Monta embed do Discord
            embed = {
                "title": f"{emoji} Alerta do Sistema de Estufa",
                "description": message,
                "color": color,
                "fields": [
                    {
                        "name": "Tipo",
                        "value": alert_type.replace('_', ' ').title(),
                        "inline": True
                    },
                    {
                        "name": "Severidade",
                        "value": severity.upper(),
                        "inline": True
                    },
                    {
                        "name": "Horário",
                        "value": timestamp,
                        "inline": False
                    }
                ],
                "footer": {
                    "text": "Sistema de Monitoramento de Estufa Inteligente"
                }
            }
            
            # Payload do webhook
            payload = {
                "username": "Estufa Bot",
                "embeds": [embed]
            }
            
            # Envia para Discord
            response = requests.post(
                self.webhook_url,
                json=payload,
                timeout=10
            )
            
            if response.status_code == 204:
                print(f"[DISCORD] ✓ Notificação enviada: {alert_type}")
                return True
            else:
                print(f"[DISCORD] ✗ Erro ao enviar: {response.status_code}")
                return False
                
        except Exception as e:
            print(f"[DISCORD ERROR] Falha ao enviar notificação: {e}")
            return False
    
    def process_alert(self, message: Dict):
        """Processa um alerta crítico"""
        print("\n" + "=" * 60)
        print("🚨 ALERTA CRÍTICO RECEBIDO")
        print("=" * 60)
        print(f"Tipo: {message.get('type')}")
        print(f"Mensagem: {message.get('message')}")
        print(f"Severidade: {message.get('severity')}")
        print(f"Timestamp: {message.get('timestamp')}")
        print("=" * 60)
        
        # Envia para Discord
        self.send_discord_notification(message)
    
    def start(self):
        """Inicia o worker"""
        print("=" * 60)
        print("WORKER DE NOTIFICAÇÕES DISCORD")
        print("=" * 60)
        
        # Verifica webhook
        if self.webhook_url == "YOUR_DISCORD_WEBHOOK_URL_HERE":
            print("\n⚠️  ATENÇÃO: Configure o Webhook do Discord!")
            print("\n1. Vá para seu servidor Discord")
            print("2. Server Settings > Integrations > Webhooks")
            print("3. Create Webhook")
            print("4. Copy Webhook URL")
            print("5. Cole no código abaixo:\n")
            print("   webhook_url = 'https://discord.com/api/webhooks/...'")
            print("\n" + "=" * 60)
            
            # Continua mesmo assim (para testes)
        
        if self.rabbitmq.connect():
            print("✓ RabbitMQ conectado!")
            print("Aguardando alertas críticos...\n")
            
            try:
                self.rabbitmq.consume(self.process_alert)
            except KeyboardInterrupt:
                print("\n\n[WORKER] Encerrando...")
                self.rabbitmq.disconnect()
        else:
            print("✗ Falha ao conectar ao RabbitMQ")
            print("\nVerifique se o RabbitMQ está rodando:")
            print("  sudo systemctl status rabbitmq-server")

# ==================== TESTE ====================

def test_discord_webhook(webhook_url):
    """Testa o webhook do Discord"""
    print("\n" + "=" * 60)
    print("TESTE DE WEBHOOK DISCORD")
    print("=" * 60)
    
    try:
        # Envia mensagem de teste
        payload = {
            "username": "Estufa Bot - TESTE",
            "embeds": [{
                "title": "🧪 Teste de Conexão",
                "description": "Se você está vendo esta mensagem, o webhook está funcionando!",
                "color": 3066993,  # Verde
                "fields": [
                    {
                        "name": "Status",
                        "value": "✅ Conectado",
                        "inline": True
                    }
                ]
            }]
        }
        
        response = requests.post(webhook_url, json=payload, timeout=10)
        
        if response.status_code == 204:
            print("✅ Webhook funcionando! Verifique seu canal Discord.")
            return True
        else:
            print(f"❌ Erro: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ Erro ao testar webhook: {e}")
        return False

# ==================== MAIN ====================

def main():
    if len(sys.argv) < 2:
        print("""
USO: python workers.py [comando] [webhook_url]

Comandos:
  start              - Inicia worker de Discord
  test <webhook_url> - Testa webhook do Discord

Exemplos:
  python workers.py start
  python workers.py test https://discord.com/api/webhooks/123/abc
  
Configurar Webhook:
  1. Edite este arquivo (workers.py)
  2. Linha ~20: webhook_url = "SEU_WEBHOOK_AQUI"
  3. Salve e execute: python workers.py start
        """)
        return
    
    command = sys.argv[1].lower()
    
    if command == 'start':
        # Webhook pode ser passado como argumento ou configurado no código
        webhook_url = sys.argv[2] if len(sys.argv) > 2 else None
        worker = DiscordNotificationWorker(webhook_url=webhook_url)
        worker.start()
    
    elif command == 'test':
        if len(sys.argv) < 3:
            print("❌ Erro: Forneça o webhook URL")
            print("Uso: python workers.py test <webhook_url>")
            return
        
        webhook_url = sys.argv[2]
        test_discord_webhook(webhook_url)
    
    else:
        print(f"❌ Comando desconhecido: {command}")
        print("Use: start ou test")

if __name__ == '__main__':
    main()