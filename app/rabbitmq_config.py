"""
RABBITMQ - APENAS PARA ALERTAS CRÍTICOS
- Falhas de conexão com Arduinos
- Timeout de sensores
- Erros críticos do sistema

NÃO é usado para dados normais (isso fica no WebSocket + SQLite)
"""

import pika
import json
from datetime import datetime

class RabbitMQManager:
    """Gerenciador simplificado - apenas alertas críticos"""
    
    def __init__(self, host='localhost', port=5672, username='guest', password='guest'):
        """
        Args:
            host: Endereço do RabbitMQ
            port: Porta (padrão 5672)
            username: Usuário
            password: Senha
        """
        self.host = host
        self.port = port
        self.credentials = pika.PlainCredentials(username, password)
        self.connection = None
        self.channel = None
        
        # Apenas 1 exchange e 1 fila (simplificado)
        self.exchange_name = 'greenhouse.critical_alerts'
        self.queue_name = 'queue.critical_alerts'
    
    def connect(self):
        """Conecta ao RabbitMQ"""
        try:
            params = pika.ConnectionParameters(
                host=self.host,
                port=self.port,
                credentials=self.credentials,
                heartbeat=600,
                blocked_connection_timeout=300
            )
            
            self.connection = pika.BlockingConnection(params)
            self.channel = self.connection.channel()
            
            # Declara exchange
            self.channel.exchange_declare(
                exchange=self.exchange_name,
                exchange_type='topic',
                durable=True
            )
            
            # Declara fila
            self.channel.queue_declare(
                queue=self.queue_name,
                durable=True
            )
            
            # Binding
            self.channel.queue_bind(
                exchange=self.exchange_name,
                queue=self.queue_name,
                routing_key='alert.critical'
            )
            
            print(f"[RABBITMQ] Conectado em {self.host}:{self.port}")
            print(f"[RABBITMQ] Exchange: {self.exchange_name}")
            print(f"[RABBITMQ] Fila: {self.queue_name}")
            return True
            
        except Exception as e:
            print(f"[RABBITMQ ERROR] Falha: {e}")
            return False
    
    def publish_alert(self, alert_data):
        """
        Publica alerta crítico
        
        Args:
            alert_data: Dict com {type, message, severity, ...}
        """
        try:
            # Verifica se está conectado
            if not self.connection or self.connection.is_closed:
                print(f"[RABBITMQ] Não conectado - pulando alerta: {alert_data.get('type')}")
                return
            
            message = {
                'timestamp': datetime.now().isoformat(),
                'type': alert_data.get('type', 'unknown'),
                'message': alert_data.get('message', ''),
                'severity': alert_data.get('severity', 'critical'),
                'source': 'greenhouse_system'
            }
            
            self.channel.basic_publish(
                exchange=self.exchange_name,
                routing_key='alert.critical',
                body=json.dumps(message),
                properties=pika.BasicProperties(
                    delivery_mode=2,  # Persistente
                    content_type='application/json',
                    priority=9
                )
            )
            
            print(f"[RABBITMQ] Alerta publicado: {alert_data.get('type')}")
            
        except Exception as e:
            print(f"[RABBITMQ ERROR] Falha ao publicar: {e}")
    
    def consume(self, callback):
        """
        Consome alertas da fila
        
        Args:
            callback: Função a ser chamada para cada alerta
        """
        try:
            def on_message(ch, method, properties, body):
                try:
                    message = json.loads(body)
                    callback(message)
                    ch.basic_ack(delivery_tag=method.delivery_tag)
                except Exception as e:
                    print(f"[RABBITMQ ERROR] Erro no callback: {e}")
                    ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)
            
            self.channel.basic_qos(prefetch_count=1)
            self.channel.basic_consume(
                queue=self.queue_name,
                on_message_callback=on_message
            )
            
            print(f"[RABBITMQ] Consumindo da fila: {self.queue_name}")
            print("[RABBITMQ] Aguardando alertas críticos...")
            self.channel.start_consuming()
            
        except Exception as e:
            print(f"[RABBITMQ ERROR] Erro ao consumir: {e}")
    
    def disconnect(self):
        """Fecha conexão"""
        try:
            if self.connection and not self.connection.is_closed:
                self.connection.close()
                print("[RABBITMQ] Conexão fechada")
        except Exception as e:
            print(f"[RABBITMQ ERROR] Erro ao fechar: {e}")


# ==================== WORKER EXEMPLO ====================

class AlertConsumerWorker:
    """
    Worker que consome alertas críticos
    Execute em processo separado: python -c "from rabbitmq_config import AlertConsumerWorker; AlertConsumerWorker().start()"
    """
    
    def __init__(self):
        self.rabbitmq = RabbitMQManager()
    
    def process_alert(self, message):
        """Processa um alerta crítico"""
        print("\n" + "=" * 60)
        print("🚨 ALERTA CRÍTICO RECEBIDO")
        print("=" * 60)
        print(f"Tipo: {message.get('type')}")
        print(f"Mensagem: {message.get('message')}")
        print(f"Severidade: {message.get('severity')}")
        print(f"Timestamp: {message.get('timestamp')}")
        print("=" * 60 + "\n")
        
        # Aqui você pode:
        # - Enviar email
        # - Enviar SMS
        # - Notificação push
        # - Acionar alarme físico
        # - Registrar em log externo
    
    def start(self):
        """Inicia o worker"""
        print("=" * 60)
        print("WORKER DE ALERTAS CRÍTICOS")
        print("=" * 60)
        
        if self.rabbitmq.connect():
            print("✓ Conectado! Aguardando alertas...\n")
            
            try:
                self.rabbitmq.consume(self.process_alert)
            except KeyboardInterrupt:
                print("\n\n[WORKER] Encerrando...")
                self.rabbitmq.disconnect()
        else:
            print("✗ Falha ao conectar")


# ==================== TESTE ====================

if __name__ == '__main__':
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == 'worker':
        # Modo worker
        worker = AlertConsumerWorker()
        worker.start()
    else:
        # Teste de publicação
        print("=" * 60)
        print("TESTE RABBITMQ - ALERTA CRÍTICO")
        print("=" * 60)
        
        manager = RabbitMQManager()
        
        if manager.connect():
            # Publica alerta de teste
            manager.publish_alert({
                'type': 'test_alert',
                'message': 'Teste de alerta crítico do sistema',
                'severity': 'critical'
            })
            
            print("\n✓ Alerta publicado!")
            print("\nPara consumir, execute:")
            print("  python rabbitmq_config.py worker")
            
            manager.disconnect()
        else:
            print("\n✗ Falha no teste")
            print("\nVerifique se o RabbitMQ está rodando:")
            print("  sudo systemctl status rabbitmq-server")
            print("  ou")
            print("  docker ps (se estiver usando Docker)")