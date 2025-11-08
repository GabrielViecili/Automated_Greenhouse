"""
GERENCIADOR DE 2 ARDUINOS
Conecta simultaneamente:
- Arduino 1 (Sensores) na porta USB 1
- Arduino 2 (Teclado) na porta USB 2

Sincroniza thresholds automaticamente entre eles.
"""

import serial
import serial.tools.list_ports
import json
import time
import threading
from database import insert_reading, insert_alert

class DualArduinoManager:
    """Gerencia 2 Arduinos conectados via USB"""
    
    def __init__(self, callback=None):
        """
        Inicializa gerenciador
        
        Args:
            callback: Função chamada quando dados chegam do Arduino 1
        """
        self.callback = callback
        
        # Conexões seriais
        self.arduino1 = None  # Sensores
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
    
    def find_arduinos(self):
        """Encontra automaticamente as 2 portas Arduino"""
        ports = list(serial.tools.list_ports.comports())
        arduino_ports = []
        
        for port in ports:
            if 'ACM' in port.device or 'USB' in port.device or 'COM' in port.device:
                arduino_ports.append(port.device)
        
        if len(arduino_ports) >= 2:
            print(f"[DUAL] Encontrados {len(arduino_ports)} Arduinos:")
            for i, port in enumerate(arduino_ports, 1):
                print(f"  {i}. {port}")
            
            # Identifica qual é qual lendo mensagens iniciais
            return self.identify_arduinos(arduino_ports)
        else:
            print(f"[DUAL ERROR] Apenas {len(arduino_ports)} Arduino(s) encontrado(s)")
            print("  Conecte os 2 Arduinos via USB!")
            return None, None
    
    def identify_arduinos(self, ports):
        """
        Identifica qual porta é Arduino1 (sensores) e qual é Arduino2 (teclado)
        baseado na mensagem inicial
        """
        port_sensors = None
        port_keypad = None
        
        for port in ports:
            try:
                ser = serial.Serial(port, 9600, timeout=2)
                time.sleep(2)  # Aguarda Arduino resetar
                
                # Lê primeiras mensagens
                for _ in range(5):
                    if ser.in_waiting > 0:
                        line = ser.readline().decode('utf-8').strip()
                        print(f"[IDENTIFY] {port}: {line}")
                        
                        # Arduino 1 envia: {"source":"arduino1",...}
                        if '"source":"arduino1"' in line or '"status":"arduino1_ready"' in line:
                            port_sensors = port
                            print(f"  ✓ {port} = Arduino Sensores")
                            break
                        
                        # Arduino 2 envia: {"source":"arduino2",...}
                        elif '"source":"arduino2"' in line:
                            port_keypad = port
                            print(f"  ✓ {port} = Arduino Teclado")
                            break
                    
                    time.sleep(0.5)
                
                ser.close()
                
            except Exception as e:
                print(f"[IDENTIFY ERROR] Erro em {port}: {e}")
        
        return port_sensors, port_keypad
    
    def connect(self):
        """Conecta aos 2 Arduinos"""
        print("[DUAL] Procurando Arduinos...")
        
        self.port1, self.port2 = self.find_arduinos()
        
        if not self.port1 or not self.port2:
            print("[DUAL ERROR] Não foi possível identificar os 2 Arduinos")
            return False
        
        try:
            # Conecta Arduino 1 (Sensores)
            self.arduino1 = serial.Serial(self.port1, 9600, timeout=1)
            time.sleep(2)
            self.arduino1.reset_input_buffer()
            print(f"[DUAL] Arduino 1 (Sensores) conectado em {self.port1}")
            
            # Conecta Arduino 2 (Teclado)
            self.arduino2 = serial.Serial(self.port2, 9600, timeout=1)
            time.sleep(2)
            self.arduino2.reset_input_buffer()
            print(f"[DUAL] Arduino 2 (Teclado) conectado em {self.port2}")
            
            return True
            
        except Exception as e:
            print(f"[DUAL ERROR] Falha na conexão: {e}")
            return False
    
    def disconnect(self):
        """Fecha conexões"""
        self.stop()
        
        if self.arduino1 and self.arduino1.is_open:
            self.arduino1.close()
            print("[DUAL] Arduino 1 desconectado")
        
        if self.arduino2 and self.arduino2.is_open:
            self.arduino2.close()
            print("[DUAL] Arduino 2 desconectado")
    
    def send_command_to_arduino1(self, command):
        """Envia comando para Arduino 1 (Sensores)"""
        try:
            if self.arduino1 and self.arduino1.is_open:
                self.arduino1.write(f"{command}\n".encode())
                print(f"[DUAL → ARD1] {command}")
                return True
            return False
        except Exception as e:
            print(f"[DUAL ERROR] Falha ao enviar para Arduino 1: {e}")
            return False
    
    def send_thresholds_to_arduino1(self, thresholds):
        """Envia thresholds para Arduino 1"""
        try:
            json_data = json.dumps(thresholds)
            return self.send_command_to_arduino1(json_data)
        except Exception as e:
            print(f"[DUAL ERROR] Falha ao enviar thresholds: {e}")
            return False
    
    def start(self):
        """Inicia leitura contínua dos 2 Arduinos"""
        if not self.is_running:
            self.is_running = True
            
            # Thread para Arduino 1 (Sensores)
            self.thread1 = threading.Thread(target=self._read_loop_arduino1, daemon=True)
            self.thread1.start()
            
            # Thread para Arduino 2 (Teclado)
            self.thread2 = threading.Thread(target=self._read_loop_arduino2, daemon=True)
            self.thread2.start()
            
            print("[DUAL] Threads de leitura iniciadas")
    
    def stop(self):
        """Para leitura"""
        self.is_running = False
        
        if self.thread1:
            self.thread1.join(timeout=2)
        if self.thread2:
            self.thread2.join(timeout=2)
        
        print("[DUAL] Threads de leitura paradas")
    
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
                                self._process_sensor_data(data)
                                
                                # Callback para WebSocket
                                if self.callback:
                                    self.callback(data)
                            
                            # Resposta de comando
                            elif 'response' in data:
                                print(f"[ARD1 →] {data}")
                            
                        except json.JSONDecodeError:
                            print(f"[ARD1] {line}")
                
                time.sleep(0.1)
                
            except Exception as e:
                print(f"[DUAL ERROR] Erro ao ler Arduino 1: {e}")
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
                                print(f"[ARD2 →] Novos thresholds recebidos!")
                                self.current_thresholds = data['thresholds']
                                
                                # Atualiza variáveis internas
                                self.thresholds = {
                                    'temp_max': data['thresholds'].get('tempMax', 35.0),
                                    'temp_min': data['thresholds'].get('tempMin', 15.0),
                                    'soil_min': data['thresholds'].get('terraMin', 30),
                                    'humid_min': data['thresholds'].get('umiMin', 40)
                                }
                                
                                # Envia para Arduino 1
                                self.send_thresholds_to_arduino1(data['thresholds'])
                                
                                print(f"  Temp: {self.thresholds['temp_min']}-{self.thresholds['temp_max']}°C")
                                print(f"  Solo: >{self.thresholds['soil_min']}%")
                        
                        except json.JSONDecodeError:
                            print(f"[ARD2] {line}")
                
                time.sleep(0.1)
                
            except Exception as e:
                print(f"[DUAL ERROR] Erro ao ler Arduino 2: {e}")
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
            print(f"[DUAL ERROR] Erro ao processar dados: {e}")
    
    def _check_alerts(self, temp, humid, soil, light):
        """Verifica condições de alerta"""
        if temp > self.thresholds['temp_max']:
            insert_alert('high_temperature', f'Temperatura alta: {temp}°C', 'warning')
        
        if temp < self.thresholds['temp_min']:
            insert_alert('low_temperature', f'Temperatura baixa: {temp}°C', 'warning')
        
        if soil < self.thresholds['soil_min']:
            insert_alert('low_soil_moisture', f'Umidade do solo baixa: {soil}%', 'critical')
        
        if humid < self.thresholds['humid_min']:
            insert_alert('low_humidity', f'Umidade do ar baixa: {humid}%', 'warning')
    
    def get_last_data(self):
        """Retorna últimos dados lidos"""
        return self.last_sensor_data


# ========================================
# TESTE
# ========================================

if __name__ == '__main__':
    print("=" * 60)
    print("TESTE DO GERENCIADOR DUAL ARDUINO")
    print("=" * 60)
    
    def on_data(data):
        print(f"[CALLBACK] Dados: {data}")
    
    manager = DualArduinoManager(callback=on_data)
    
    if manager.connect():
        print("\n✓ Ambos Arduinos conectados!")
        print("Iniciando leitura contínua...\n")
        
        manager.start()
        
        try:
            print("Testando por 60 segundos...")
            print("Configure algo no teclado (Arduino 2) para ver sincronização!\n")
            
            time.sleep(60)
            
            # Testa comandos
            print("\nTestando comandos...")
            manager.send_command_to_arduino1("GET_THRESHOLDS")
            time.sleep(2)
            
        except KeyboardInterrupt:
            print("\n\nInterrompido pelo usuário")
        
        finally:
            manager.disconnect()
    else:
        print("\n✗ Falha ao conectar Arduinos")