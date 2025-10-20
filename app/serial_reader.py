import serial
import serial.tools.list_ports
import json
import time
import threading
from database import insert_reading, insert_alert

class ArduinoReader:
    def __init__(self, port=None, baudrate=9600, callback=None):
        """
        Inicializa o leitor serial do Arduino
        
        Args:
            port: Porta serial (ex: '/dev/ttyACM0' ou 'COM3')
            baudrate: Taxa de transmissão (padrão: 9600)
            callback: Função a ser chamada quando novos dados chegarem
        """
        self.port = port
        self.baudrate = baudrate
        self.callback = callback
        self.serial_connection = None
        self.is_running = False
        self.thread = None
        self.last_data = {}
        
        # Thresholds para alertas
        self.thresholds = {
            'temp_max': 35.0,
            'temp_min': 15.0,
            'soil_min': 30,
            'humid_min': 40
        }
        
    def find_arduino_port(self):
        """Encontra automaticamente a porta do Arduino"""
        ports = serial.tools.list_ports.comports()
        for port in ports:
            # Arduino geralmente aparece como 'ttyACM' ou 'ttyUSB' no Linux
            # ou 'COM' no Windows
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
            
            # Aguarda Arduino resetar
            time.sleep(2)
            
            # Limpa buffer
            self.serial_connection.reset_input_buffer()
            
            print(f"[SERIAL] Conectado em {self.port} @ {self.baudrate} baud")
            return True
            
        except serial.SerialException as e:
            print(f"[SERIAL ERROR] Falha na conexão: {e}")
            return False
    
    def disconnect(self):
        """Fecha a conexão serial"""
        self.stop()
        if self.serial_connection and self.serial_connection.is_open:
            self.serial_connection.close()
            print("[SERIAL] Conexão fechada")
    
    def send_command(self, command):
        """Envia comando para o Arduino"""
        try:
            if self.serial_connection and self.serial_connection.is_open:
                self.serial_connection.write(f"{command}\n".encode())
                print(f"[SERIAL] Comando enviado: {command}")
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
                        # Tenta parsear JSON
                        data = json.loads(line)
                        self.last_data = data
                        
                        # Processa dados de sensores
                        if all(k in data for k in ['temp', 'humid', 'soil', 'light']):
                            self._process_sensor_data(data)
                        
                        # Se houver callback, chama ele
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
        """Processa dados dos sensores, salva no banco e verifica alertas"""
        try:
            temp = data['temp']
            humid = data['humid']
            soil = data['soil']
            light = data['light']
            
            # Salva no banco de dados
            insert_reading(temp, humid, soil, light)
            
            # Verifica condições de alerta
            self._check_alerts(temp, humid, soil, light)
            
            print(f"[SENSOR] T:{temp}°C H:{humid}% S:{soil}% L:{light}%")
            
        except KeyError as e:
            print(f"[SERIAL ERROR] Dados incompletos: {e}")
    
    def _check_alerts(self, temp, humid, soil, light):
        """Verifica se há condições de alerta"""
        if temp > self.thresholds['temp_max']:
            insert_alert('high_temperature', 
                        f'Temperatura alta: {temp}°C', 
                        'warning')
        
        if temp < self.thresholds['temp_min']:
            insert_alert('low_temperature', 
                        f'Temperatura baixa: {temp}°C', 
                        'warning')
        
        if soil < self.thresholds['soil_min']:
            insert_alert('low_soil_moisture', 
                        f'Umidade do solo baixa: {soil}%', 
                        'critical')
        
        if humid < self.thresholds['humid_min']:
            insert_alert('low_humidity', 
                        f'Umidade do ar baixa: {humid}%', 
                        'warning')
    
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
            time.sleep(0.1)  # Pequeno delay para não sobrecarregar CPU
    
    def get_last_data(self):
        """Retorna os últimos dados lidos"""
        return self.last_data


# Funções auxiliares para uso rápido
def list_available_ports():
    """Lista todas as portas seriais disponíveis"""
    ports = serial.tools.list_ports.comports()
    print("\nPortas seriais disponíveis:")
    for i, port in enumerate(ports, 1):
        print(f"{i}. {port.device} - {port.description}")
    return [port.device for port in ports]


if __name__ == '__main__':
    # Teste do leitor serial
    print("=== TESTE DO LEITOR SERIAL ===\n")
    
    # Lista portas disponíveis
    list_available_ports()
    
    # Callback de exemplo
    def on_data_received(data):
        print(f"Callback: Dados recebidos -> {data}")
    
    # Cria instância do leitor
    reader = ArduinoReader(callback=on_data_received)
    
    # Tenta conectar
    if reader.connect():
        print("\nIniciando leitura contínua por 30 segundos...")
        print("Pressione Ctrl+C para interromper\n")
        
        reader.start()
        
        try:
            # Mantém rodando por 30 segundos
            time.sleep(30)
            
            # Teste de comandos
            print("\nEnviando comandos de teste...")
            reader.send_command("PING")
            time.sleep(1)
            reader.send_command("STATUS")
            time.sleep(5)
            
        except KeyboardInterrupt:
            print("\n\nInterrompido pelo usuário")
        
        finally:
            reader.disconnect()
    else:
        print("Falha ao conectar com Arduino")