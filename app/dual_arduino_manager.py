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
    
def _process_actuator_action(self, data):
        """
        Processa ações automáticas dos atuadores e envia notificações
        """
        action = data.get('action', '')
        reason = data.get('reason', '')
        value = data.get('value', 0)
        
        print(f"[ATUADOR] {action} - {reason} (valor: {value})")
        
        # ========== BOMBA D'ÁGUA ==========
        if action == 'pump_auto_on':
            insert_action('pump_auto', 'activated', f'Bomba ligada - Solo: {value}%')
            
            if self.rabbitmq_connected and self.rabbitmq:
                try:
                    self.rabbitmq.publish_alert({
                        'type': 'pump_activated',
                        'message': f'💧 Bomba d\'água LIGADA automaticamente!\n\n🌱 Umidade do Solo: {value}%\n📊 Limite Mínimo: {self.thresholds["soil_min"]}%\n\n✅ Irrigação em andamento...',
                        'severity': 'info'
                    })
                except:
                    pass
        
        # ========== COOLER ==========
        elif action == 'cooler_auto_on':
            insert_action('cooler_auto', 'activated', f'Cooler ligado - Temp: {value}°C')
            
            if self.rabbitmq_connected and self.rabbitmq:
                try:
                    self.rabbitmq.publish_alert({
                        'type': 'cooler_activated',
                        'message': f'❄️ Cooler LIGADO automaticamente!\n\n🌡️ Temperatura: {value}°C\n📊 Limite Máximo: {self.thresholds["temp_max"]}°C\n\n✅ Sistema de resfriamento ativo.',
                        'severity': 'info'
                    })
                except:
                    pass
        
        elif action == 'cooler_auto_off':
            insert_action('cooler_auto', 'deactivated', f'Cooler desligado - Temp: {value}°C')
            
            if self.rabbitmq_connected and self.rabbitmq:
                try:
                    self.rabbitmq.publish_alert({
                        'type': 'cooler_deactivated',
                        'message': f'✅ Cooler DESLIGADO automaticamente!\n\n🌡️ Temperatura: {value}°C\n📊 Temperatura normalizada (< {self.thresholds["temp_max"]}°C)\n\n😎 Ambiente resfriado com sucesso.',
                        'severity': 'info'
                    })
                except:
                    pass
        
        # ========== FITA LED ==========
        elif action == 'light_auto_on':
            insert_action('light_auto', 'activated', f'Fita LED ligada - Luz: {value}%')
            
            if self.rabbitmq_connected and self.rabbitmq:
                try:
                    self.rabbitmq.publish_alert({
                        'type': 'light_activated',
                        'message': f'💡 Fita LED LIGADA automaticamente!\n\n☀️ Luminosidade: {value}%\n📊 Limite Mínimo: {self.thresholds.get("luz_min", 20)}%\n\n✅ Iluminação suplementar ativa.',
                        'severity': 'info'
                    })
                except:
                    pass
        
        elif action == 'light_auto_off':
            insert_action('light_auto', 'deactivated', f'Fita LED desligada - Luz: {value}%')
            
            if self.rabbitmq_connected and self.rabbitmq:
                try:
                    self.rabbitmq.publish_alert({
                        'type': 'light_deactivated',
                        'message': f'🌞 Fita LED DESLIGADA automaticamente!\n\n☀️ Luminosidade: {value}%\n📊 Luz natural suficiente\n\n✅ Economia de energia.',
                        'severity': 'info'
                    })
                except:
                    pass
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
        self.last_arduino2_time = time.time()
        
        # Monitoramento de falhas de sensores (NOVO)
        self.dht_fail_count = 0
        self.last_dht_alert = 0  # Timestamp do último alerta DHT
        self.sensor_fail_counts = {
            'dht': 0,
            'soil': 0,
            'ldr': 0
        }
        self.last_sensor_alerts = {
            'dht': 0,
            'soil': 0,
            'ldr': 0
        }
        
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
                print("[MANAGER] ✓ RabbitMQ conectado (alertas de falha)")
            else:
                print("[MANAGER] ⚠️  RabbitMQ indisponível - continuando sem ele")
                self.rabbitmq_connected = False
        except Exception as e:
            print(f"[MANAGER] ⚠️  RabbitMQ não disponível: {e}")
            print("[MANAGER] Sistema funcionará normalmente (alertas apenas no SQLite)")
            self.rabbitmq_connected = False
            self.rabbitmq = None
    
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
                print(f"[IDENTIFY] Testando {port}...")
                ser = serial.Serial(port, 9600, timeout=3)
                time.sleep(3)  # Aumentado para 3s (Arduino precisa resetar)
                
                # Limpa buffer primeiro
                ser.reset_input_buffer()
                time.sleep(1)
                
                # Lê mensagens por até 10 segundos
                start_time = time.time()
                identified = False
                
                while time.time() - start_time < 10 and not identified:
                    if ser.in_waiting > 0:
                        try:
                            line = ser.readline().decode('utf-8', errors='ignore').strip()
                            
                            if line:
                                print(f"  {port}: {line[:80]}")  # Mostra primeiros 80 chars
                                
                                # Arduino 1 envia dados de sensores ou status
                                if ('"source":"arduino1"' in line or 
                                    '"status":"arduino1_ready"' in line or
                                    ('"temp"' in line and '"humid"' in line)):
                                    port_sensors = port
                                    print(f"  ✓ {port} = Arduino 1 (Sensores)")
                                    identified = True
                                    break
                                
                                # Arduino 2 envia thresholds
                                elif ('"source":"arduino2"' in line or
                                      '"thresholds"' in line):
                                    port_keypad = port
                                    print(f"  ✓ {port} = Arduino 2 (Teclado)")
                                    identified = True
                                    break
                        except:
                            pass
                    
                    time.sleep(0.3)
                
                if not identified:
                    print(f"  ⚠️  {port}: Nenhuma identificação clara (timeout)")
                
                ser.close()
                
            except Exception as e:
                print(f"[IDENTIFY ERROR] {port}: {e}")
        
        # Se não identificou ambos, tenta uma abordagem alternativa
        if not port_sensors or not port_keypad:
            print("\n[IDENTIFY] Tentativa alternativa...")
            
            # Ordena portas e INVERTE
            ports_sorted = sorted(ports, reverse=True)  # INVERTIDO
            if len(ports_sorted) >= 2:
                port_sensors = ports_sorted[0]
                port_keypad = ports_sorted[1]
                print(f"  {port_sensors} → Arduino 1 (Sensores)")
                print(f"  {port_keypad} → Arduino 2 (Teclado)")
        
        # FORÇA INVERSÃO (descomente se necessário)
        # port_sensors, port_keypad = port_keypad, port_sensors
        
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
            if self.rabbitmq_connected and self.rabbitmq:
                try:
                    self.rabbitmq.publish_alert({
                        'type': 'arduino_connection_error',
                        'message': str(e),
                        'severity': 'critical'
                    })
                except:
                    pass  # Ignora erro do RabbitMQ
            
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
            try:
                self.rabbitmq.disconnect()
            except:
                pass  # Ignora erro ao desconectar
    
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
                            
                            # Ações automáticas dos atuadores (NOVO)
                            elif 'action' in data:
                                self._process_actuator_action(data)
                            
                            # Resposta de comando
                            elif 'response' in data:
                                print(f"[ARD1 ←] {data}")
                        
                        except json.JSONDecodeError:
                            print(f"[ARD1] {line}")
                
                # Detecta timeout (sem dados por 60s = 1 minuto)
                if time.time() - self.last_data_time > 60:  # ← ALTERADO PARA 60s
                    self.arduino1_fail_count += 1
                    
                    if self.arduino1_fail_count == 1:  # Alerta apenas na primeira vez
                        print("[MANAGER] 🚨 Arduino 1 sem resposta há 1 minuto!")
                        
                        # Salva no banco
                        insert_alert(
                            'arduino1_timeout',
                            'Arduino 1 (sensores) não envia dados há 1 minuto',
                            'critical'
                        )
                        
                        # Publica no RabbitMQ → Discord
                        if self.rabbitmq_connected and self.rabbitmq:
                            try:
                                self.rabbitmq.publish_alert({
                                    'type': 'arduino1_timeout',
                                    'message': '🔌 Arduino 1 (sensores) desconectado há 1 minuto! Verifique a conexão USB.',
                                    'severity': 'critical'
                                })
                                print("[MANAGER] ✓ Alerta enviado para Discord")
                            except:
                                pass  # Ignora erro do RabbitMQ
                
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
                        self.last_arduino2_time = time.time()  # ← ATUALIZA TIMESTAMP
                        self.arduino2_fail_count = 0  # ← RESETA CONTADOR
                        
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
                
                # ← NOVO: Detecta timeout do Arduino 2 (1 minuto sem dados)
                if time.time() - self.last_arduino2_time > 60:
                    self.arduino2_fail_count += 1
                    
                    if self.arduino2_fail_count == 1:  # Alerta apenas na primeira vez
                        print("[MANAGER] 🚨 Arduino 2 sem resposta há 1 minuto!")
                        
                        # Salva no banco
                        insert_alert(
                            'arduino2_timeout',
                            'Arduino 2 (teclado) não responde há 1 minuto',
                            'warning'
                        )
                        
                        # Publica no RabbitMQ → Discord
                        if self.rabbitmq_connected and self.rabbitmq:
                            try:
                                self.rabbitmq.publish_alert({
                                    'type': 'arduino2_timeout',
                                    'message': '⌨️ Arduino 2 (teclado) desconectado há 1 minuto! Configurações podem não funcionar.',
                                    'severity': 'warning'
                                })
                                print("[MANAGER] ✓ Alerta Arduino 2 enviado para Discord")
                            except:
                                pass
                
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
            
            # Valida dados dos sensores (NOVO)
            self._validate_sensor_data(temp, humid, soil, light)
            
            # Salva no banco
            insert_reading(temp, humid, soil, light)
            
            # Verifica alertas de thresholds
            self._check_alerts(temp, humid, soil, light)
            
            print(f"[SENSORES] T:{temp}°C H:{humid}% S:{soil}% L:{light}%")
            
        except Exception as e:
            print(f"[MANAGER ERROR] Erro ao processar: {e}")
    
    def _validate_sensor_data(self, temp, humid, soil, light):
        """
        Valida dados dos sensores e envia alertas se houver problema
        Usa debounce para não enviar spam (1 alerta a cada 5 minutos por sensor)
        """
        current_time = time.time()
        alert_cooldown = 300  # 5 minutos entre alertas do mesmo tipo
        
        # 1. Valida DHT11 (temperatura e umidade)
        if temp == 0 or humid == 0 or temp < -40 or temp > 80 or humid > 100:
            self.sensor_fail_counts['dht'] += 1
            
            # Envia alerta após 3 leituras ruins consecutivas
            if (self.sensor_fail_counts['dht'] >= 3 and 
                current_time - self.last_sensor_alerts['dht'] > alert_cooldown):
                
                print("[MANAGER] 🚨 DHT11 com falha!")
                
                insert_alert(
                    'dht11_failure',
                    f'Sensor DHT11 com falha! Temp={temp}°C, Umid={humid}%. Verifique conexões.',
                    'critical'
                )
                
                if self.rabbitmq_connected and self.rabbitmq:
                    try:
                        self.rabbitmq.publish_alert({
                            'type': 'dht11_failure',
                            'message': f'🌡️ Sensor DHT11 com FALHA!\n\nLeituras anormais detectadas:\n• Temperatura: {temp}°C\n• Umidade: {humid}%\n\n⚠️ Verifique:\n• Conexão do sensor no pino 2\n• Alimentação 5V\n• Sensor danificado',
                            'severity': 'critical'
                        })
                        print("[MANAGER] ✓ Alerta DHT11 enviado para Discord")
                    except:
                        pass
                
                self.last_sensor_alerts['dht'] = current_time
                self.sensor_fail_counts['dht'] = 0  # Reset contador
        else:
            # Reset contador se dados voltaram ao normal
            if self.sensor_fail_counts['dht'] > 0:
                self.sensor_fail_counts['dht'] -= 1
        
        # 2. Valida Sensor de Solo (0-100%)
        if soil < 0 or soil > 100:
            self.sensor_fail_counts['soil'] += 1
            
            if (self.sensor_fail_counts['soil'] >= 3 and 
                current_time - self.last_sensor_alerts['soil'] > alert_cooldown):
                
                print("[MANAGER] 🚨 Sensor de Solo com falha!")
                
                insert_alert(
                    'soil_sensor_failure',
                    f'Sensor de solo com leitura inválida: {soil}%',
                    'warning'
                )
                
                if self.rabbitmq_connected and self.rabbitmq:
                    try:
                        self.rabbitmq.publish_alert({
                            'type': 'soil_sensor_failure',
                            'message': f'💧 Sensor de Umidade do Solo com problema!\n\nLeitura: {soil}% (fora do range 0-100%)\n\n⚠️ Verifique:\n• Conexão no pino A0\n• Calibração do sensor\n• Sensor em curto ou desconectado',
                            'severity': 'warning'
                        })
                        print("[MANAGER] ✓ Alerta Solo enviado para Discord")
                    except:
                        pass
                
                self.last_sensor_alerts['soil'] = current_time
                self.sensor_fail_counts['soil'] = 0
        else:
            if self.sensor_fail_counts['soil'] > 0:
                self.sensor_fail_counts['soil'] -= 1
        
        # 3. Valida LDR (0-100%)
        if light < 0 or light > 100:
            self.sensor_fail_counts['ldr'] += 1
            
            if (self.sensor_fail_counts['ldr'] >= 3 and 
                current_time - self.last_sensor_alerts['ldr'] > alert_cooldown):
                
                print("[MANAGER] 🚨 Sensor LDR com falha!")
                
                insert_alert(
                    'ldr_sensor_failure',
                    f'Sensor LDR com leitura inválida: {light}%',
                    'warning'
                )
                
                if self.rabbitmq_connected and self.rabbitmq:
                    try:
                        self.rabbitmq.publish_alert({
                            'type': 'ldr_sensor_failure',
                            'message': f'☀️ Sensor de Luminosidade (LDR) com problema!\n\nLeitura: {light}% (fora do range 0-100%)\n\n⚠️ Verifique:\n• Conexão no pino A1\n• Resistor pull-down (10kΩ)\n• LDR danificado',
                            'severity': 'warning'
                        })
                        print("[MANAGER] ✓ Alerta LDR enviado para Discord")
                    except:
                        pass
                
                self.last_sensor_alerts['ldr'] = current_time
                self.sensor_fail_counts['ldr'] = 0
        else:
            if self.sensor_fail_counts['ldr'] > 0:
                self.sensor_fail_counts['ldr'] -= 1
    
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