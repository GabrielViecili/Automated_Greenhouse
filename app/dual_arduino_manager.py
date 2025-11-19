import serial
import serial.tools.list_ports
import json
import time
import threading
from database import insert_reading, insert_alert, insert_action
from rabbitmq_config import RabbitMQManager

ALERT_COOLDOWN = 300  

class DualArduinoManager:
    """Gerencia a comunicação serial com dois Arduinos (com auto-reconnect)."""

    def __init__(self, callback=None, use_rabbitmq=True):
        self.port1 = None
        self.port2 = None
        self.ser1 = None
        self.ser2 = None
        self.baudrate = 9600
        self.is_running = False
        self.thread1 = None
        self.thread2 = None
        self.callback = callback
        self.last_sensor_data = {}
        
        self.thresholds = {
            'temp_max': 35.0,
            'temp_min': 15.0,
            'humid_max': 80.0,
            'humid_min': 40.0,
            'soil_max': 80.0,
            'soil_min': 30.0,
            'light_max': 90.0,
            'light_min': 20.0
        }
        
        self.use_rabbitmq = use_rabbitmq
        self.rabbitmq = None
        self.rabbitmq_connected = False
        
        self.last_alert_time_1 = 0
        self.last_alert_time_2 = 0
        
        if self.use_rabbitmq:
            self._init_rabbitmq()

    def _init_rabbitmq(self):
        try:
            self.rabbitmq = RabbitMQManager()
            if self.rabbitmq.connect():
                self.rabbitmq_connected = True
                print("✓ [RabbitMQ] Conectado e pronto para alertas.")
            else:
                print("✗ [RabbitMQ] Falha ao conectar ao RabbitMQ.")
                self.rabbitmq_connected = False
        except Exception as e:
            print(f"✗ [RabbitMQ] Erro crítico ao iniciar RabbitMQ: {e}")
            self.rabbitmq_connected = False

    def find_ports(self):
        ports = serial.tools.list_ports.comports()
        arduino_ports = [port.device for port in ports if 'ACM' in port.device or 'USB' in port.device or 'arduino' in port.description.lower()]
        
        if len(arduino_ports) >= 2:
            arduino_ports.sort()
            self.port1 = arduino_ports[0]
            self.port2 = arduino_ports[1]
            return True
        else:
            print("✗ ERRO: São necessários 2 Arduinos. Encontrado(s):", len(arduino_ports))
            return False

    def connect(self):
        if not self.find_ports():
            if self.rabbitmq_connected:
                self._send_alert('arduino_connection_failed', "Falha CRÍTICA ao iniciar: Nenhum Arduino foi encontrado.", 1)
            return False
        
        try:
            self.ser1 = serial.Serial(self.port1, self.baudrate, timeout=1)
            self.ser2 = serial.Serial(self.port2, self.baudrate, timeout=1)
            time.sleep(2)
            print(f"✓ Arduino 1 (Sensores) conectado em: {self.port1}")
            print(f"✓ Arduino 2 (Teclado) conectado em: {self.port2}")
            return True
        except serial.SerialException as e:
            print(f"✗ ERRO DE CONEXÃO INICIAL: {e}")
            if 'ser1' in locals() and self.ser1: self.ser1.close()
            if 'ser2' in locals() and self.ser2: self.ser2.close()
            self.ser1 = None
            self.ser2 = None
            return True

    def start(self):
        self.is_running = True
        self.thread1 = threading.Thread(target=self._read_from_port_1, daemon=True)
        self.thread1.start()
        self.thread2 = threading.Thread(target=self._read_from_port_2, daemon=True)
        self.thread2.start()
        print("✓ Threads de leitura (com auto-reconnect) iniciadas.")
        time.sleep(1) 
        self.send_thresholds_to_arduino1()

    def stop(self):
        self.is_running = False
        if self.thread1: self.thread1.join()
        if self.thread2: self.thread2.join()
        if self.ser1 and self.ser1.is_open: self.ser1.close()
        if self.ser2 and self.ser2.is_open: self.ser2.close()
        if self.rabbitmq: self.rabbitmq.disconnect()
        print("Conexões e threads encerradas.")

    def _read_from_port_1(self):
        """Lê dados do Arduino 1 (Sensores) com auto-reconnect."""
        print(f"[THREAD 1] Iniciada. Ouvindo Arduino 1 ({self.port1})")
        while self.is_running:
            try:
                if not self.ser1 or not self.ser1.is_open:
                    if self.port1:
                        print(f"🔌 [ARDUINO 1] Tentando (re)conectar em {self.port1}...")
                        self.ser1 = serial.Serial(self.port1, self.baudrate, timeout=1)
                        time.sleep(2)
                        print(f"✓✓ [ARDUINO 1] RECONECTADO em {self.port1}!")
                        self._send_alert('arduino1_reconnected', f"Arduino 1 (Sensores) em {self.port1} RECONECTADO.", 1)
                        self.send_thresholds_to_arduino1()
                    else:
                        time.sleep(5)
                        continue

                if self.ser1.in_waiting > 0:
                    line = self.ser1.readline().decode('utf-8').strip()
                    if line:
                        self._process_arduino1_data(line)
                
            except (serial.SerialException, OSError) as e:
                print(f"🚨 ERRO (ARDUINO 1): {e}")
                self._send_alert('arduino1_timeout', f"Arduino 1 (Sensores) em {self.port1} DESCONECTADO. Erro: {e}", 1)
                if self.ser1:
                    self.ser1.close()
                self.ser1 = None
                time.sleep(5)
            
            except Exception as e:
                print(f"🚨 ERRO INESPERADO (ARDUINO 1): {e}")
                self._send_alert('arduino_connection_error', f"Erro inesperado no Arduino 1 ({self.port1}). Erro: {e}", 1)
                time.sleep(5)

            time.sleep(0.01)

    def _read_from_port_2(self):
        """Lê dados do Arduino 2 (Teclado) com auto-reconnect."""
        print(f"[THREAD 2] Iniciada. Ouvindo Arduino 2 ({self.port2})")
        while self.is_running:
            try:
                if not self.ser2 or not self.ser2.is_open:
                    if self.port2:
                        print(f"🔌 [ARDUINO 2] Tentando (re)conectar em {self.port2}...")
                        self.ser2 = serial.Serial(self.port2, self.baudrate, timeout=1)
                        time.sleep(2)
                        print(f"✓✓ [ARDUINO 2] RECONECTADO em {self.port2}!")
                    else:
                        time.sleep(5)
                        continue

                if self.ser2.in_waiting > 0:
                    line = self.ser2.readline().decode('utf-8').strip()
                    if line:
                        self._process_arduino2_data(line)
                
            except (serial.SerialException, OSError) as e:
                print(f"🚨 ERRO (ARDUINO 2): {e}")
                
                if self.ser2:
                    self.ser2.close()
                self.ser2 = None
                time.sleep(5)
            
            except Exception as e:
                print(f"🚨 ERRO INESPERADO (ARDUINO 2): {e}")
                time.sleep(5)

            time.sleep(0.01)

    def _process_arduino1_data(self, data_line):
        """Processa JSON vindo do Arduino 1 (Sensores)"""
        try:
            data = json.loads(data_line)
            
            if data.get('source') == 'arduino1' and 'temp' in data:
                self.last_sensor_data = data
                insert_reading(data.get('temp'), data.get('humid'), data.get('soil'), data.get('light'))
                self._check_alerts(data.get('temp'), data.get('humid'), data.get('soil'), data.get('light'))
                if self.callback:
                    self.callback(data)
            
            elif 'action' in data:
                self._process_actuator_action(data)
            
            elif 'status' in data and data['status'] == 'arduino1_ready':
                print("✓ Arduino 1 (Sensores) reportou estar pronto. Enviando thresholds...")
                self.send_thresholds_to_arduino1()
            
            elif data.get('source') == 'arduino2_keypad':
                print("✗ [ERRO DE PORTA] Arduino 1 está recebendo dados do Arduino 2! TROQUE OS CABOS USB.")
            
            elif 'response' in data and 'thresholds_updated' in data['response']:
                print(f"✓ [ARDUINO 1] Confirmou atualização de thresholds ({data['response']}).")

        except json.JSONDecodeError:
            print(f"[ARDUINO 1] (Ignorado) {data_line}")

    def _process_arduino2_data(self, data_line):
        """Processa JSON vindo do Arduino 2 (Teclado)"""
        print(f"[ARDUINO 2] {data_line}")
        try:
            data = json.loads(data_line)
            
            if data.get('source') == 'arduino2' and 'thresholds' in data:
                
                print("✓ [SINCRONIZAÇÃO] Novos thresholds recebidos do Arduino 2 (Teclado)")
                
                self.thresholds['temp_max'] = data['thresholds'].get('tempMax', self.thresholds['temp_max'])
                self.thresholds['temp_min'] = data['thresholds'].get('tempMin', self.thresholds['temp_min'])
                self.thresholds['humid_max'] = data['thresholds'].get('umiMax', self.thresholds['humid_max'])
                self.thresholds['humid_min'] = data['thresholds'].get('umiMin', self.thresholds['humid_min'])
                self.thresholds['soil_min'] = data['thresholds'].get('terraMin', self.thresholds['soil_min'])
                self.thresholds['light_min'] = data['thresholds'].get('luzMin', self.thresholds['light_min'])
                
                print(f"✓ [SINCRONIZAÇÃO] Thresholds atualizados: {self.thresholds}")
                
                self.send_thresholds_to_arduino1()
                
            elif 'status' in data and data['status'] == 'arduino2_ready':
                print("✓ Arduino 2 (Teclado) reportou estar pronto.")

            elif data.get('source') == 'arduino1':
                print("✗ [ERRO DE PORTA] Arduino 2 está recebendo dados do Arduino 1! TROQUE OS CABOS USB.")

        except json.JSONDecodeError:
            print(f"[ARDUINO 2] (Ignorado) {data_line}")

    def send_command_to_arduino1(self, command):
        """Envia um comando de texto para o Arduino 1."""
        if self.ser1 and self.ser1.is_open:
            try:
                self.ser1.write(f"{command}\n".encode('utf-8'))
                return True
            except serial.SerialException as e:
                print(f"✗ ERRO ao enviar comando para Ardu1: {e}")
                self.ser1.close()
                self.ser1 = None
                return False
        return False
        
    def send_thresholds_to_arduino1(self):
        """Envia o JSON de thresholds (formato Arduino) para o Arduino 1."""
        if self.ser1 and self.ser1.is_open:
            try:
                arduino_json_payload = {
                    "tempMax": self.thresholds['temp_max'],
                    "tempMin": self.thresholds['temp_min'],
                    "umiMax": self.thresholds['humid_max'],
                    "umiMin": self.thresholds['humid_min'],
                    "terraMin": self.thresholds['soil_min'],
                    "luzMin": self.thresholds['light_min']
                }
                json_string = json.dumps(arduino_json_payload)
                print(f"[CMD ARDU1] Enviando thresholds: {json_string}")
                self.send_command_to_arduino1(json_string)
                return True
            except Exception as e:
                print(f"[MANAGER ERROR] Falha ao enviar thresholds: {e}")
                return False

    def _send_alert(self, type, message, port_num):
        """Envia alerta via RabbitMQ com controle de cooldown."""
        if not self.rabbitmq_connected:
            return

        now = time.time()
        
        if port_num == 1:
            if now - self.last_alert_time_1 > ALERT_COOLDOWN:
                self.last_alert_time_1 = now
                self.rabbitmq.publish_alert({'type': type, 'message': message, 'severity': 'critical'})
                print(f"[RABBITMQ] Alerta (Ardu1) publicado: {type}")
        
        elif port_num == 2:
            if now - self.last_alert_time_2 > ALERT_COOLDOWN:
                self.last_alert_time_2 = now
                self.rabbitmq.publish_alert({'type': type, 'message': message, 'severity': 'critical'})
                print(f"[RABBITMQ] Alerta (Ardu2) publicado: {type}")

    def _check_alerts(self, temp, humid, soil, light):
        """Verifica condições de alerta"""
        try:
            if temp > self.thresholds['temp_max']:
                insert_alert('high_temperature', f'Temp alta: {temp}°C', 'warning')
            
            if temp < self.thresholds['temp_min']:
                insert_alert('low_temperature', f'Temp baixa: {temp}°C', 'warning')
            
            if soil < self.thresholds['soil_min']:
                insert_alert('low_soil_moisture', f'Solo seco: {soil}%', 'critical')
            
            if humid < self.thresholds['humid_min']:
                insert_alert('low_humidity', f'Umidade baixa: {humid}%', 'warning')
        except Exception as e:
            print(f"✗ Erro ao checar alertas: {e}")

    def update_thresholds_from_app(self, new_thresholds_dict):
        """
        Atualiza os thresholds a partir do app.py (website).
        """
        print(f"✓ [SINCRONIZAÇÃO] Novos thresholds recebidos do Website")
        try:
            if 'tempMax' in new_thresholds_dict:
                self.thresholds['temp_max'] = float(new_thresholds_dict['tempMax'])
            if 'tempMin' in new_thresholds_dict:
                self.thresholds['temp_min'] = float(new_thresholds_dict['tempMin'])
            if 'umiMax' in new_thresholds_dict:
                self.thresholds['humid_max'] = float(new_thresholds_dict['umiMax'])
            if 'umiMin' in new_thresholds_dict:
                self.thresholds['humid_min'] = float(new_thresholds_dict['umiMin'])
            if 'terraMin' in new_thresholds_dict:
                self.thresholds['soil_min'] = float(new_thresholds_dict['terraMin'])
            if 'luzMin' in new_thresholds_dict:
                self.thresholds['light_min'] = float(new_thresholds_dict['luzMin'])
            
            print(f"✓ [SINCRONIZAÇÃO] Thresholds atualizados: {self.thresholds}")
            
            self.send_thresholds_to_arduino1()
            
            return True, "Thresholds atualizados com sucesso"
            
        except Exception as e:
            print(f"✗ [SINCRONIZAÇÃO] Erro ao atualizar thresholds: {e}")
            return False, str(e)

    def _process_actuator_action(self, data):
        """
        Processa ações automáticas (JSONs 'action') do Arduino 1
        e envia alertas detalhados para o RabbitMQ.
        """
        action = data.get('action', '')
        reason = data.get('reason', '')
        value = data.get('value', 0)
        
        print(f"✓ [ATUADOR ARDU1] {action} (Motivo: {reason}, Valor: {value})")

        if action == 'pump_auto_on':
            insert_action('pump_auto', 'activated', f'Bomba ligada - Solo: {value}%')
            
            if self.rabbitmq_connected and self.rabbitmq:
                try:
                    self.rabbitmq.publish_alert({
                        'type': 'pump_activated',
                        'message': f'💧 Bomba d\'água LIGADA!\nSolo: {value}% (Limite: {self.thresholds["soil_min"]}%)',
                        'severity': 'info'
                    })
                except: pass

        elif action == 'cooler_auto_on':
            insert_action('cooler_auto', 'activated', f'Cooler ligado - Temp: {value}°C')
            
            if self.rabbitmq_connected and self.rabbitmq:
                try:
                    self.rabbitmq.publish_alert({
                        'type': 'cooler_activated',
                        'message': f'❄️ Cooler LIGADO!\nTemp: {value}°C (Limite: {self.thresholds["temp_max"]}°C)',
                        'severity': 'info'
                    })
                except: pass
        
        elif action == 'cooler_auto_off':
            insert_action('cooler_auto', 'deactivated', f'Cooler desligado - Temp: {value}°C')
            
            if self.rabbitmq_connected and self.rabbitmq:
                try:
                    self.rabbitmq.publish_alert({
                        'type': 'cooler_deactivated',
                        'message': f'✅ Cooler DESLIGADO.\nTemp: {value}°C (Normalizada)',
                        'severity': 'info'
                    })
                except: pass

        elif action == 'light_auto_on':
            insert_action('light_auto', 'activated', f'Fita LED ligada - Luz: {value}%')
            
            if self.rabbitmq_connected and self.rabbitmq:
                try:
                    self.rabbitmq.publish_alert({
                        'type': 'light_activated',
                        'message': f'💡 Fita LED LIGADA!\nLuz: {value}% (Limite: {self.thresholds["light_min"]}%)',
                        'severity': 'info'
                    })
                except: pass
        
        elif action == 'light_auto_off':
            insert_action('light_auto', 'deactivated', f'Fita LED desligada - Luz: {value}%')
            
            if self.rabbitmq_connected and self.rabbitmq:
                try:
                    self.rabbitmq.publish_alert({
                        'type': 'light_deactivated',
                        'message': f'🌞 Fita LED DESLIGADA.\nLuz: {value}% (Suficiente)',
                        'severity': 'info'
                    })
                except: pass
    
    def get_last_data(self):
        return self.last_sensor_data