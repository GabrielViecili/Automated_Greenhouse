import serial
import serial.tools.list_ports
import json
import time
import threading
from database import insert_reading, insert_alert
from rabbitmq_config import RabbitMQManager

class ArduinoReaderWithRabbitMQ:
    """
    Leitor serial do Arduino integrado com RabbitMQ
    Mantém compatibilidade com sistema existente
    """
    
    def __init__(self, port=None, baudrate=9600, callback=None, use_rabbitmq=True):
        """
        Inicializa o leitor serial do Arduino com RabbitMQ
        
        Args:
            port: Porta serial
            baudrate: Taxa de transmissão
            callback: Função a ser chamada quando novos dados chegarem (WebSocket)
            use_rabbitmq: Se True, publica dados no RabbitMQ também
        """
        self.port = port
        self.baudrate = baudrate
        self.callback = callback
        self.serial_connection = None
        self.is_running = False
        self.thread = None
        self.last_data = {}
        
        # RabbitMQ
        self.use_rabbitmq = use_rabbitmq
        self.rabbitmq = None
        self.rabbitmq_connected = False
        
        if self.use_rabbitmq:
            self._init_rabbitmq()
        
        # Thresholds para alertas
        self.thresholds = {
            'temp_max': 35.0,
            'temp_min': 15.0,
            'soil_min': 30,
            'humid_min': 40
        }
    
    def _init_rabbitmq(self):
        """Inicializa conexão com RabbitMQ"""
        try:
            self.rabbitmq = RabbitMQManager()
            if self.rabbitmq.connect():
                self.rabbitmq_connected = True
                print("[SERIAL] RabbitMQ integrado com sucesso!")
            else:
                print("[SERIAL] RabbitMQ não disponível - continuando sem ele")
                self.rabbitmq_connected = False
        except Exception as e:
            print(f"[SERIAL] Erro ao conectar RabbitMQ: {e}")
            self.rabbitmq_connected = False
    
    def find_arduino_port(self):
        """Encontra automaticamente a porta do Arduino"""
        ports = serial.tools.list_ports.comports()
        for port in ports:
            if 'ACM' in port.device or 'USB' in port.device or 'COM' in port.device:
                print(f"[SERIAL] Arduino encontrado em: {port.device}")
                return port.device
        return None
    
    def connect(self):
        """Estabelece conexão com o Arduino"""
        try:
            if not self.port:
                self.port = self.find_arduino_port()
                
            if not self.port:
                print("[SERIAL ERROR] Nenhuma porta Arduino encontrada!")
                return False
            
            self.serial_connection = serial.Serial(
                port=self.port,
                baudrate=self.baudrate,
                timeout=1
            )
            
            time.sleep(2)
            self.serial_connection.reset_input_buffer()
            
            print(f"[SERIAL] Conectado em {self.port} @ {self.baudrate} baud")
            return True
            
        except serial.SerialException as e:
            print(f"[SERIAL ERROR] Falha na conexão: {e}")
            return False
    
    def disconnect(self):
        """Fecha a conexão serial e RabbitMQ"""
        self.stop()
        
        if self.serial_connection and self.serial_connection.is_open:
            self.serial_connection.close()
            print("[SERIAL] Conexão serial fechada")
        
        if self.rabbitmq_connected and self.rabbitmq:
            self.rabbitmq.disconnect()
            print("[SERIAL] RabbitMQ desconectado")
    
    def send_command(self, command):
        """
        Envia comando para o Arduino
        Se RabbitMQ estiver ativo, publica o comando também
        """
        try:
            if self.serial_connection and self.serial_connection.is_open:
                self.serial_connection.write(f"{command}\n".encode())
                print(f"[SERIAL] Comando enviado: {command}")
                
                # Publica no RabbitMQ
                if self.rabbitmq_connected:
                    self.rabbitmq.publish_command(command, {
                        'sent_at': time.time(),
                        'via': 'serial'
                    })
                
                return True
            return False
        except Exception as e:
            print(f"[SERIAL ERROR] Falha ao enviar comando: {e}")
            return False
    
    def read_data(self):
        """Lê e processa dados do Arduino"""
        try:
            if self.serial_connection and self.serial_connection.in_waiting > 0:
                line = self.serial_connection.readline().decode('utf-8').strip()
                
                if line:
                    try:
                        data = json.loads(line)
                        self.last_data = data
                        
                        # Processa dados de sensores
                        if all(k in data for k in ['temp', 'humid', 'soil', 'light']):
                            self._process_sensor_data(data)
                        
                        # Callback original (WebSocket)
                        if self.callback:
                            self.callback(data)
                        
                        return data
                        
                    except json.JSONDecodeError:
                        print(f"[SERIAL] Dados não-JSON recebidos: {line}")
                        return None
            
            return None
            
        except Exception as e:
            print(f"[SERIAL ERROR] Erro na leitura: {e}")
            return None
    
    def _process_sensor_data(self, data):
        """
        Processa dados dos sensores:
        1. Salva no banco SQLite (sistema original)
        2. Publica no RabbitMQ (novo)
        3. Verifica alertas
        """
        try:
            temp = data['temp']
            humid = data['humid']
            soil = data['soil']
            light = data['light']
            
            # 1. Salva no banco de dados (original)
            insert_reading(temp, humid, soil, light)
            
            # 2. Publica no RabbitMQ (novo)
            if self.rabbitmq_connected:
                self.rabbitmq.publish_sensor_data(data)
            
            # 3. Verifica condiçõess de alerta
            self._check_alerts(temp, humid, soil, light)
            
            print(f"[SENSOR] T:{temp}°C H:{humid}% S:{soil}% L:{light}%")
            
        except KeyError as e:
            print(f"[SERIAL ERROR] Dados incompletos: {e}")
    
    def _check_alerts(self, temp, humid, soil, light):
        """
        Verifica se há condições de alerta
        Salva no banco E publica no RabbitMQ
        """
        alerts = []
        
        if temp > self.thresholds['temp_max']:
            alert = {
                'type': 'high_temperature',
                'message': f'Temperatura alta: {temp}°C',
                'severity': 'warning'
            }
            alerts.append(alert)
        
        if temp < self.thresholds['temp_min']:
            alert = {
                'type': 'low_temperature',
                'message': f'Temperatura baixa: {temp}°C',
                'severity': 'warning'
            }
            alerts.append(alert)
        
        if soil < self.thresholds['soil_min']:
            alert = {
                'type': 'low_soil_moisture',
                'message': f'Umidade do solo baixa: {soil}%',
                'severity': 'critical'
            }
            alerts.append(alert)
        
        if humid < self.thresholds['humid_min']:
            alert = {
                'type': 'low_humidity',
                'message': f'Umidade do ar baixa: {humid}%',
                'severity': 'warning'
            }
            alerts.append(alert)
        
        # Processa cada alerta
        for alert in alerts:
            # Salva no banco (original)
            insert_alert(alert['type'], alert['message'], alert['severity'])
            
            # Publica no RabbitMQ (novo)
            if self.rabbitmq_connected:
                self.rabbitmq.publish_alert(
                    alert['type'],
                    alert['message'],
                    alert['severity']
                )
    
    def start(self):
        """Inicia a leitura contínua em uma thread separada"""
        if not self.is_running:
            self.is_running = True
            self.thread = threading.Thread(target=self._read_loop, daemon=True)
            self.thread.start()
            print("[SERIAL] Thread de leitura iniciada")
    
    def stop(self):
        """Para a leitura contínua"""
        self.is_running = False
        if self.thread:
            self.thread.join(timeout=2)
            print("[SERIAL] Thread de leitura parada")
    
    def _read_loop(self):
        """Loop de leitura contínua (executado em thread)"""
        while self.is_running:
            self.read_data()
            time.sleep(0.1)
    
    def get_last_data(self):
        """Retorna os últimos dados lidos"""
        return self.last_data


def list_available_ports():
    """Lista todas as portas seriais disponíveis"""
    ports = serial.tools.list_ports.comports()
    print("\nPortas seriais disponíveis:")
    for i, port in enumerate(ports, 1):
        print(f"{i}. {port.device} - {port.description}")
    return [port.device for port in ports]


if __name__ == '__main__':
    print("=== TESTE DO LEITOR SERIAL COM RABBITMQ ===\n")
    
    list_available_ports()
    
    def on_data_received(data):
        print(f"[CALLBACK] Dados recebidos -> {data}")
    
    # Cria instância com RabbitMQ
    reader = ArduinoReaderWithRabbitMQ(
        callback=on_data_received,
        use_rabbitmq=True
    )
    
    if reader.connect():
        print("\nIniciando leitura contínua...")
        print("Pressione Ctrl+C para interromper\n")
        
        reader.start()
        
        try:
            time.sleep(30)
            
            print("\nEnviando comandos de teste...")
            reader.send_command("IRRIGATE")
            time.sleep(5)
            
        except KeyboardInterrupt:
            print("\n\nInterrompido pelo usuário")
        
        finally:
            reader.disconnect()
    else:
        print("Falha ao conectar com Arduino")