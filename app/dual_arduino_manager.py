"""
GERENCIADOR DE 2 ARDUINOS - VERSÃO REFINADA
- Arduino 1: Sensores (DHT11, Solo, LDR) + Atuadores (Bomba, Cooler, LED)
- Arduino 2: Teclado 4x3 + LCD para configuração
- RabbitMQ APENAS para alertas críticos de falha de conexão
"""

import serial
import serial.tools.list_ports
import json
import time
import threading
from database import insert_reading, insert_alert

# RabbitMQ opcional (apenas para alertas de falha)
try:
    from rabbitmq_config import RabbitMQManager
    RABBITMQ_AVAILABLE = True
except ImportError:
    RABBITMQ_AVAILABLE = False
    print("[MANAGER] RabbitMQ não disponível - continuando sem ele")

class DualArduinoManager:
    """Gerencia 2 Arduinos via USB"""
    
    def __init__(self, callback=None, use_rabbitmq=False):
        """
        Args:
            callback: Função chamada quando dados chegam do Arduino 1
            use_rabbitmq: Se True, publica alertas de falha no RabbitMQ
        """
        self.callback = callback
        
        # Conexões seriais
        self.arduino1 = None  # Sensores/Atuadores
        self.arduino2 = None  # Teclado
        self.port1 = None
        self.port2 = None
        
        # Threads
        self.is_running = False
        self.thread1 = None
        self.thread2 = None
        
        # Últimos dados
        self.last_sensor_data = {}
        self.current_thresholds = {}
        
        # Thresholds padrão
        self.thresholds = {
            'temp_max': 35.0,
            'temp_min': 15.0,
            'soil_min': 30,
            'humid_min': 40
        }
        
        # Monitoramento de falhas
        self.arduino1_fail_count = 0
        self.arduino2_fail_count = 0
        self.last_data_time = time.time()
        
        # RabbitMQ (apenas para alertas de falha)
        self.use_rabbitmq = use_rabbitmq and RABBITMQ_AVAILABLE
        self.rabbitmq = None
        self.rabbitmq_connected = False
        
        if self.use_rabbitmq:
            self._init_rabbitmq()
    
    def _init_rabbitmq(self):
        """Inicializa RabbitMQ apenas para alertas de falha"""
        try:
            self.rabbitmq = RabbitMQManager()
            if self.rabbitmq.connect():
                self.rabbitmq_connected = True
                print("[MANAGER] RabbitMQ conectado (alertas de falha)")
            else:
                print("[MANAGER] RabbitMQ indisponível")
                self.rabbitmq_connected = False
        except Exception as e:
            print(f"[MANAGER] Erro RabbitMQ: {e}")
            self.rabbitmq_connected = False
    
    def find_arduinos(self):
        """Encontra automaticamente as portas USB dos Arduinos"""
        ports = list(serial.tools.list_ports.comports())
        arduino_ports = []
        
        for port in ports:
            if 'ACM' in port.device or 'USB' in port.device or 'COM' in port.device:
                arduino_ports.append(port.device)
        
        if len(arduino_ports) >= 2:
            print(f"[MANAGER] {len(arduino_ports)} Arduinos encontrados:")
            for i, port in enumerate(arduino_ports, 1):
                print(f"  {i}. {port}")
            
            return self.identify_arduinos(arduino_ports)
        else:
            print(f"[MANAGER] Apenas {len(arduino_ports)} Arduino(s) encontrado(s)")
            print("  Conecte os 2 Arduinos via USB!")
            
            # Alerta crítico via RabbitMQ
            if self.rabbitmq_connected:
                self.rabbitmq.publish_alert({
                    'type': 'arduino_connection_failed',
                    'message': f'Apenas {len(arduino_ports)} Arduino(s) detectado(s)',
                    'severity': 'critical'
                })
            
            return None, None
    
    def identify_arduinos(self, ports):
        """Identifica qual porta é Arduino1 e qual é Arduino2"""
        port_sensors = None
        port_keypad = None
        
        for port in ports:
            try:
                ser = serial.Serial(port, 9600, timeout=2)
                time.sleep(2)
                
                # Lê mensagens iniciais
                for _ in range(5):
                    if ser.in_waiting > 0:
                        line = ser.readline().decode('utf-8').strip()
                        print(f"[IDENTIFY] {port}: {line}")
                        
                        if '"source":"arduino1"' in line or '"status":"arduino1_ready"' in line:
                            port_sensors = port
                            print(f"  ✓ {port} = Arduino Sensores")
                            break
                        
                        elif '"source":"arduino2"' in line:
                            port_keypad = port
                            print(f"  ✓ {port} = Arduino Teclado")
                            break
                    
                    time.sleep(0.5)
                
                ser.close()
                
            except Exception as e:
                print(f"[IDENTIFY ERROR] {port}: {e}")
        
        return port_sensors, port_keypad
    
    def connect(self):
        """Conecta aos 2 Arduinos"""
        print("[MANAGER] Procurando Arduinos...")
        
        self.port1, self.port2 = self.find_arduinos()
        
        if not self.port1 or not self.port2:
            print("[MANAGER] ✗ Falha ao identificar os 2 Arduinos")
            return False
        
        try:
            # Arduino 1 (Sensores)
            self.arduino1 = serial.Serial(self.port1, 9600, timeout=1)
            time.sleep(2)
            self.arduino1.reset_input_buffer()
            print(f"[MANAGER] ✓ Arduino 1 em {self.port1}")
            
            # Arduino 2 (Teclado)
            self.arduino2 = serial.Serial(self.port2, 9600, timeout=1)
            time.sleep(2)
            self.arduino2.reset_input_buffer()
            print(f"[MANAGER] ✓ Arduino 2 em {self.port2}")
            
            return True
            
        except Exception as e:
            print(f"[MANAGER ERROR] Falha na conexão: {e}")
            
            # Alerta via RabbitMQ
            if self.rabbitmq_connected:
                self.rabbitmq.publish_alert({
                    'type': 'arduino_connection_error',
                    'message': str(e),
                    'severity': 'critical'
                })
            
            return False
    
    def disconnect(self):
        """Fecha conexões"""
        self.stop()
        
        if self.arduino1 and self.arduino1.is_open:
            self.arduino1.close()
            print("[MANAGER] Arduino 1 desconectado")
        
        if self.arduino2 and self.arduino2.is_open:
            self.arduino2.close()
            print("[MANAGER] Arduino 2 desconectado")
        
        if self.rabbitmq_connected and self.rabbitmq:
            self.rabbitmq.disconnect()
    
    def send_command_to_arduino1(self, command):
        """Envia comando para Arduino 1"""
        try:
            if self.arduino1 and self.arduino1.is_open:
                self.arduino1.write(f"{command}\n".encode())
                print(f"[→ ARD1] {command}")
                return True
            return False
        except Exception as e:
            print(f"[MANAGER ERROR] Falha ao enviar: {e}")
            return False
    
    def send_thresholds_to_arduino1(self, thresholds):
        """Envia thresholds para Arduino 1"""
        try:
            json_data = json.dumps(thresholds)
            return self.send_command_to_arduino1(json_data)
        except Exception as e:
            print(f"[MANAGER ERROR] Falha ao enviar thresholds: {e}")
            return False
    
    def start(self):
        """Inicia leitura contínua"""
        if not self.is_running:
            self.is_running = True
            
            self.thread1 = threading.Thread(target=self._read_loop_arduino1, daemon=True)
            self.thread1.start()
            
            self.thread2 = threading.Thread(target=self._read_loop_arduino2, daemon=True)
            self.thread2.start()
            
            print("[MANAGER] Threads de leitura iniciadas")
    
    def stop(self):
        """Para leitura"""
        self.is_running = False
        
        if self.thread1:
            self.thread1.join(timeout=2)
        if self.thread2:
            self.thread2.join(timeout=2)
        
        print("[MANAGER] Threads paradas")
    
    def _read_loop_arduino1(self):
        """Loop de leitura do Arduino 1 (Sensores)"""
        while self.is_running:
            try:
                if self.arduino1 and self.arduino1.in_waiting > 0:
                    line = self.arduino1.readline().decode('utf-8').strip()
                    
                    if line:
                        try:
                            data = json.loads(line)
                            
                            # Dados de sensores
                            if 'temp' in data and 'humid' in data:
                                self.last_sensor_data = data
                                self.last_data_time = time.time()
                                self.arduino1_fail_count = 0  # Reset contador
                                
                                self._process_sensor_data(data)
                                
                                if self.callback:
                                    self.callback(data)
                            
                            # Resposta de comando
                            elif 'response' in data:
                                print(f"[ARD1 ←] {data}")
                        
                        except json.JSONDecodeError:
                            print(f"[ARD1] {line}")
                
                # Detecta timeout (sem dados por 30s)
                if time.time() - self.last_data_time > 30:
                    self.arduino1_fail_count += 1
                    
                    if self.arduino1_fail_count == 1:  # Alerta apenas na primeira vez
                        print("[MANAGER] ⚠️ Arduino 1 sem resposta há 30s!")
                        
                        if self.rabbitmq_connected:
                            self.rabbitmq.publish_alert({
                                'type': 'arduino1_timeout',
                                'message': 'Arduino 1 (sensores) não envia dados há 30s',
                                'severity': 'critical'
                            })
                        
                        insert_alert(
                            'arduino1_timeout',
                            'Arduino 1 não envia dados',
                            'critical'
                        )
                
                time.sleep(0.1)
                
            except Exception as e:
                print(f"[MANAGER ERROR] Erro ao ler Arduino 1: {e}")
                time.sleep(1)
    
    def _read_loop_arduino2(self):
        """Loop de leitura do Arduino 2 (Teclado)"""
        while self.is_running:
            try:
                if self.arduino2 and self.arduino2.in_waiting > 0:
                    line = self.arduino2.readline().decode('utf-8').strip()
                    
                    if line:
                        try:
                            data = json.loads(line)
                            
                            # Thresholds configurados
                            if 'thresholds' in data:
                                print(f"[ARD2 ←] Novos thresholds!")
                                self.current_thresholds = data['thresholds']
                                
                                # Atualiza internamente
                                self.thresholds = {
                                    'temp_max': data['thresholds'].get('tempMax', 35.0),
                                    'temp_min': data['thresholds'].get('tempMin', 15.0),
                                    'soil_min': data['thresholds'].get('terraMin', 30),
                                    'humid_min': data['thresholds'].get('umiMin', 40)
                                }
                                
                                # Sincroniza com Arduino 1
                                self.send_thresholds_to_arduino1(data['thresholds'])
                                
                                print(f"  Temp: {self.thresholds['temp_min']}-{self.thresholds['temp_max']}°C")
                                print(f"  Solo: >{self.thresholds['soil_min']}%")
                        
                        except json.JSONDecodeError:
                            print(f"[ARD2] {line}")
                
                time.sleep(0.1)
                
            except Exception as e:
                print(f"[MANAGER ERROR] Erro ao ler Arduino 2: {e}")
                time.sleep(1)
    
    def _process_sensor_data(self, data):
        """Processa dados dos sensores"""
        try:
            temp = data.get('temp', 0)
            humid = data.get('humid', 0)
            soil = data.get('soil', 0)
            light = data.get('light', 0)
            
            # Salva no banco
            insert_reading(temp, humid, soil, light)
            
            # Verifica alertas
            self._check_alerts(temp, humid, soil, light)
            
            print(f"[SENSORES] T:{temp}°C H:{humid}% S:{soil}% L:{light}%")
            
        except Exception as e:
            print(f"[MANAGER ERROR] Erro ao processar: {e}")
    
    def _check_alerts(self, temp, humid, soil, light):
        """Verifica condições de alerta"""
        # Temperatura alta
        if temp > self.thresholds['temp_max']:
            insert_alert('high_temperature', f'Temp alta: {temp}°C', 'warning')
        
        # Temperatura baixa
        if temp < self.thresholds['temp_min']:
            insert_alert('low_temperature', f'Temp baixa: {temp}°C', 'warning')
        
        # Solo seco (crítico)
        if soil < self.thresholds['soil_min']:
            insert_alert('low_soil_moisture', f'Solo seco: {soil}%', 'critical')
        
        # Umidade baixa
        if humid < self.thresholds['humid_min']:
            insert_alert('low_humidity', f'Umidade baixa: {humid}%', 'warning')
    
    def get_last_data(self):
        """Retorna últimos dados lidos"""
        return self.last_sensor_data


# ==================== TESTE ====================

if __name__ == '__main__':
    print("=" * 60)
    print("TESTE DO GERENCIADOR DUAL")
    print("=" * 60)
    
    def on_data(data):
        print(f"[CALLBACK] {data}")
    
    manager = DualArduinoManager(callback=on_data, use_rabbitmq=True)
    
    if manager.connect():
        print("\n✓ Ambos Arduinos conectados!")
        print("Testando por 60 segundos...\n")
        
        manager.start()
        
        try:
            time.sleep(60)
            
            # Testa comandos
            print("\nTestando comandos...")
            manager.send_command_to_arduino1("IRRIGATE")
            time.sleep(3)
            manager.send_command_to_arduino1("COOLER_ON")
            time.sleep(3)
            manager.send_command_to_arduino1("LIGHT_ON")
            time.sleep(3)
            
        except KeyboardInterrupt:
            print("\n\nInterrompido")
        
        finally:
            manager.disconnect()
    else:
        print("\n✗ Falha ao conectar")