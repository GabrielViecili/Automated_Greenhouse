import pika
import json
import time
from datetime import datetime
from typing import Callable, Dict, Any

class RabbitMQManager:
    """Gerenciador de conexão e publicação no RabbitMQ"""
    
    def __init__(self, host='localhost', port=5672, username='guest', password='guest'):
        """
        Inicializa conexão com RabbitMQ
        
        Args:
            host: Endereço do servidor RabbitMQ
            port: Porta do RabbitMQ
            username: Usuário
            password: Senha
        """
        self.host = host
        self.port = port
        self.credentials = pika.PlainCredentials(username, password)
        self.connection = None
        self.channel = None
        
        # Definição das exchanges e filas
        self.exchanges = {
            'sensor_data': 'greenhouse.sensors',      # Dados dos sensores
            'alerts': 'greenhouse.alerts',            # Alertas do sistema
            'commands': 'greenhouse.commands',        # Comandos para Arduino
            'logs': 'greenhouse.logs'                 # Logs do sistema
        }
        
        self.queues = {
            'sensor_readings': 'queue.sensor.readings',
            'sensor_alerts': 'queue.sensor.alerts',
            'email_notifications': 'queue.notifications.email',
            'sms_notifications': 'queue.notifications.sms',
            'data_analytics': 'queue.analytics.data',
            'command_arduino': 'queue.commands.arduino'
        }
    
    def connect(self):
        """Estabelece conexão com RabbitMQ"""
        try:
            connection_params = pika.ConnectionParameters(
                host=self.host,
                port=self.port,
                credentials=self.credentials,
                heartbeat=600,
                blocked_connection_timeout=300
            )
            
            self.connection = pika.BlockingConnection(connection_params)
            self.channel = self.connection.channel()
            
            # Declara exchanges
            for exchange_type, exchange_name in self.exchanges.items():
                self.channel.exchange_declare(
                    exchange=exchange_name,
                    exchange_type='topic',
                    durable=True
                )
            
            # Declara filas
            for queue_name in self.queues.values():
                self.channel.queue_declare(
                    queue=queue_name,
                    durable=True
                )
            
            # Bindings (conecta exchanges às filas)
            self._setup_bindings()
            
            print(f"[RABBITMQ] Conectado em {self.host}:{self.port}")
            return True
            
        except Exception as e:
            print(f"[RABBITMQ ERROR] Falha na conexão: {e}")
            return False
    
    def _setup_bindings(self):
        """Configura bindings entre exchanges e filas"""
        bindings = [
            # Dados de sensores vão para múltiplas filas
            (self.exchanges['sensor_data'], self.queues['sensor_readings'], 'sensor.#'),
            (self.exchanges['sensor_data'], self.queues['data_analytics'], 'sensor.#'),
            
            # Alertas vão para notificações
            (self.exchanges['alerts'], self.queues['sensor_alerts'], 'alert.#'),
            (self.exchanges['alerts'], self.queues['email_notifications'], 'alert.critical'),
            (self.exchanges['alerts'], self.queues['sms_notifications'], 'alert.critical'),
            
            # Comandos para Arduino
            (self.exchanges['commands'], self.queues['command_arduino'], 'command.#')
        ]
        
        for exchange, queue, routing_key in bindings:
            self.channel.queue_bind(
                exchange=exchange,
                queue=queue,
                routing_key=routing_key
            )
    
    def publish_sensor_data(self, data: Dict[str, Any]):
        """
        Publica dados dos sensores
        
        Args:
            data: Dicionário com dados dos sensores (temp, humid, soil, light)
        """
        try:
            message = {
                'timestamp': datetime.now().isoformat(),
                'data': data,
                'source': 'arduino'
            }
            
            self.channel.basic_publish(
                exchange=self.exchanges['sensor_data'],
                routing_key='sensor.reading',
                body=json.dumps(message),
                properties=pika.BasicProperties(
                    delivery_mode=2,  # Mensagem persistente
                    content_type='application/json'
                )
            )
            
            print(f"[RABBITMQ] Sensor data publicado: {data}")
            
        except Exception as e:
            print(f"[RABBITMQ ERROR] Falha ao publicar: {e}")
    
    def publish_alert(self, alert_type: str, message: str, severity: str = 'warning'):
        """
        Publica um alerta
        
        Args:
            alert_type: Tipo do alerta
            message: Mensagem do alerta
            severity: Severidade (warning, critical)
        """
        try:
            alert_data = {
                'timestamp': datetime.now().isoformat(),
                'type': alert_type,
                'message': message,
                'severity': severity
            }
            
            routing_key = f'alert.{severity}'
            
            self.channel.basic_publish(
                exchange=self.exchanges['alerts'],
                routing_key=routing_key,
                body=json.dumps(alert_data),
                properties=pika.BasicProperties(
                    delivery_mode=2,
                    content_type='application/json',
                    priority=9 if severity == 'critical' else 5
                )
            )
            
            print(f"[RABBITMQ] Alerta publicado: {alert_type} - {severity}")
            
        except Exception as e:
            print(f"[RABBITMQ ERROR] Falha ao publicar alerta: {e}")
    
    def publish_command(self, command: str, details: Dict = None):
        """
        Publica comando para Arduino
        
        Args:
            command: Comando a ser enviado
            details: Detalhes adicionais do comando
        """
        try:
            command_data = {
                'timestamp': datetime.now().isoformat(),
                'command': command,
                'details': details or {}
            }
            
            self.channel.basic_publish(
                exchange=self.exchanges['commands'],
                routing_key='command.arduino',
                body=json.dumps(command_data),
                properties=pika.BasicProperties(
                    delivery_mode=2,
                    content_type='application/json'
                )
            )
            
            print(f"[RABBITMQ] Comando publicado: {command}")
            
        except Exception as e:
            print(f"[RABBITMQ ERROR] Falha ao publicar comando: {e}")
    
    def consume(self, queue_name: str, callback: Callable):
        """
        Consome mensagens de uma fila
        
        Args:
            queue_name: Nome da fila
            callback: Função a ser chamada para cada mensagem
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
                queue=queue_name,
                on_message_callback=on_message
            )
            
            print(f"[RABBITMQ] Consumindo da fila: {queue_name}")
            self.channel.start_consuming()
            
        except Exception as e:
            print(f"[RABBITMQ ERROR] Erro ao consumir: {e}")
    
    def disconnect(self):
        """Fecha conexão com RabbitMQ"""
        try:
            if self.connection and not self.connection.is_closed:
                self.connection.close()
                print("[RABBITMQ] Conexão fechada")
        except Exception as e:
            print(f"[RABBITMQ ERROR] Erro ao fechar conexão: {e}")


# Worker de exemplo para processar notificações por email
class EmailNotificationWorker:
    """Worker que consome alertas críticos e envia emails"""
    
    def __init__(self, rabbitmq_manager: RabbitMQManager):
        self.rabbitmq = rabbitmq_manager
    
    def process_alert(self, message: Dict):
        """Processa um alerta e envia email"""
        print(f"\n[EMAIL WORKER] Processando alerta:")
        print(f"  Tipo: {message.get('type')}")
        print(f"  Mensagem: {message.get('message')}")
        print(f"  Severidade: {message.get('severity')}")
        print(f"  Timestamp: {message.get('timestamp')}")
        
        # Aqui você implementaria o envio real de email
        # usando SMTP, SendGrid, AWS SES, etc.
        print(f"[EMAIL] Email enviado para admin@estufa.com")
    
    def start(self):
        """Inicia o worker"""
        print("[EMAIL WORKER] Iniciando...")
        self.rabbitmq.consume(
            self.rabbitmq.queues['email_notifications'],
            self.process_alert
        )


# Worker de exemplo para analytics
class DataAnalyticsWorker:
    """Worker que processa dados para analytics"""
    
    def __init__(self, rabbitmq_manager: RabbitMQManager):
        self.rabbitmq = rabbitmq_manager
        self.buffer = []
        self.buffer_size = 10
    
    def process_data(self, message: Dict):
        """Processa dados de sensores"""
        data = message.get('data', {})
        self.buffer.append(data)
        
        if len(self.buffer) >= self.buffer_size:
            self.analyze_batch()
            self.buffer = []
    
    def analyze_batch(self):
        """Analisa lote de dados"""
        if not self.buffer:
            return
        
        # Calcula médias
        avg_temp = sum(d.get('temp', 0) for d in self.buffer) / len(self.buffer)
        avg_humid = sum(d.get('humid', 0) for d in self.buffer) / len(self.buffer)
        avg_soil = sum(d.get('soil', 0) for d in self.buffer) / len(self.buffer)
        
        print(f"\n[ANALYTICS] Análise de {len(self.buffer)} leituras:")
        print(f"  Temp média: {avg_temp:.1f}°C")
        print(f"  Umidade ar média: {avg_humid:.1f}%")
        print(f"  Umidade solo média: {avg_soil:.1f}%")
        
        # Aqui você poderia:
        # - Salvar em banco de dados de analytics
        # - Treinar modelos ML
        # - Gerar relatórios
        # - Detectar padrões
    
    def start(self):
        """Inicia o worker"""
        print("[ANALYTICS WORKER] Iniciando...")
        self.rabbitmq.consume(
            self.rabbitmq.queues['data_analytics'],
            self.process_data
        )


if __name__ == '__main__':
    # Teste de conexão
    print("=== TESTE RABBITMQ ===\n")
    
    manager = RabbitMQManager()
    
    if manager.connect():
        # Publica dados de teste
        manager.publish_sensor_data({
            'temp': 25.5,
            'humid': 60,
            'soil': 45,
            'light': 80
        })
        
        # Publica alerta de teste
        manager.publish_alert(
            'low_soil_moisture',
            'Umidade do solo abaixo de 30%',
            'critical'
        )
        
        time.sleep(1)
        manager.disconnect()
        
        print("\n✓ Teste concluído!")
    else:
        print("\n✗ Falha no teste")