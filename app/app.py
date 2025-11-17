"""
SISTEMA DE ESTUFA INTELIGENTE - SERVIDOR PRINCIPAL
- Gerencia 2 Arduinos via USB
- WebSocket para dashboard em tempo real
- RabbitMQ APENAS para alertas críticos de falha
- Banco de dados persistente

WORKERS DISCORD:
  Execute em terminal separado: python workers.py start
"""

from flask import Flask, render_template, jsonify, request
from flask_socketio import SocketIO, emit
from flask_cors import CORS
import json
from datetime import datetime
import threading
import time
import os

# Importações locais
from database import (
    init_database, 
    insert_reading,
    insert_action,
    get_latest_readings, 
    get_readings_by_timerange,
    get_latest_alerts,
    get_statistics
)
from dual_arduino_manager import DualArduinoManager

# Workers Discord são executados separadamente
# NÃO são importados aqui

app = Flask(__name__)
app.config['SECRET_KEY'] = 'greenhouse_secret_2025'
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*")

# Gerenciador global dos Arduinos
arduino_manager = None
arduino_connected = False

def on_arduino_data(data):
    """Callback quando dados chegam do Arduino 1 (sensores)"""
    # Emite dados em tempo real via WebSocket para todos clientes
    socketio.emit('sensor_data', data)
    print(f"[WS] Dados emitidos: T:{data.get('temp')}°C H:{data.get('humid')}% S:{data.get('soil')}%")

def init_arduinos():
    """Inicializa conexão com os 2 Arduinos"""
    global arduino_manager, arduino_connected
    
    try:
        # use_rabbitmq=True apenas para alertas críticos de falha
        arduino_manager = DualArduinoManager(
            callback=on_arduino_data,
            use_rabbitmq=True  
        )
        
        if arduino_manager.connect():
            arduino_manager.start()
            arduino_connected = True
            print("[APP] ✓ 2 Arduinos conectados!")
            return True
        else:
            print("[APP] ✗ Falha ao conectar Arduinos")
            arduino_connected = False
            return False
    except Exception as e:
        print(f"[APP ERROR] Erro ao inicializar: {e}")
        arduino_connected = False
        return False

# ==================== ROTAS HTTP ====================

@app.route('/')
def index():
    """Página principal do dashboard"""
    return render_template('index.html')

@app.route('/api/status')
def api_status():
    """Status do sistema"""
    return jsonify({
        'status': 'online',
        'arduino_connected': arduino_connected,
        'arduino1': 'connected' if arduino_manager and arduino_manager.arduino1 else 'disconnected',
        'arduino2': 'connected' if arduino_manager and arduino_manager.arduino2 else 'disconnected',
        'timestamp': datetime.now().isoformat()
    })

@app.route('/api/readings/latest')
def api_latest_readings():
    """Últimas leituras do banco"""
    limit = request.args.get('limit', 10, type=int)
    readings = get_latest_readings(limit)
    return jsonify(readings)

@app.route('/api/readings/history')
def api_readings_history():
    """Histórico de leituras"""
    hours = request.args.get('hours', 24, type=int)
    readings = get_readings_by_timerange(hours)
    return jsonify(readings)

@app.route('/api/alerts/latest')
def api_latest_alerts():
    """Últimos alertas"""
    limit = request.args.get('limit', 10, type=int)
    alerts = get_latest_alerts(limit)
    return jsonify(alerts)

@app.route('/api/statistics')
def api_statistics():
    """Estatísticas gerais"""
    stats = get_statistics()
    return jsonify(stats)

@app.route('/api/thresholds', methods=['GET'])
def api_get_thresholds():
    """Retorna thresholds atuais"""
    if not arduino_connected:
        return jsonify({'error': 'Arduinos não conectados'}), 503
    
    return jsonify({
        'thresholds': arduino_manager.current_thresholds,
        'active': arduino_manager.thresholds
    })

@app.route('/api/thresholds', methods=['POST'])
def api_set_thresholds():
    """Define thresholds (Arduino 2 tem prioridade)"""
    if not arduino_connected:
        return jsonify({'error': 'Arduinos não conectados'}), 503
    
    data = request.get_json()
    success = arduino_manager.send_thresholds_to_arduino1(data)
    
    if success:
        return jsonify({
            'success': True, 
            'message': 'Thresholds atualizados',
            'note': 'Arduino 2 pode sobrescrever via teclado'
        })
    else:
        return jsonify({'error': 'Falha ao enviar'}), 500

@app.route('/api/command/irrigate', methods=['POST'])
def api_irrigate():
    """Ativa irrigação manual"""
    if not arduino_connected:
        return jsonify({'error': 'Arduinos não conectados'}), 503
    
    success = arduino_manager.send_command_to_arduino1('IRRIGATE')
    
    if success:
        insert_action('irrigation', 'completed', 'Irrigação manual via API')
        return jsonify({'success': True, 'message': 'Irrigação ativada'})
    else:
        return jsonify({'error': 'Falha ao enviar'}), 500

@app.route('/api/command/cooler', methods=['POST'])
def api_cooler():
    """Liga/desliga cooler"""
    if not arduino_connected:
        return jsonify({'error': 'Arduinos não conectados'}), 503
    
    data = request.get_json()
    state = data.get('state', 'ON')  # ON ou OFF
    
    command = f'COOLER_{state}'
    success = arduino_manager.send_command_to_arduino1(command)
    
    if success:
        insert_action('cooler', 'completed', f'Cooler {state}')
        return jsonify({'success': True, 'message': f'Cooler {state}'})
    else:
        return jsonify({'error': 'Falha ao enviar'}), 500

@app.route('/api/command/light', methods=['POST'])
def api_light():
    """Liga/desliga fita LED"""
    if not arduino_connected:
        return jsonify({'error': 'Arduinos não conectados'}), 503
    
    data = request.get_json()
    state = data.get('state', 'ON')  # ON ou OFF
    
    command = f'LIGHT_{state}'
    success = arduino_manager.send_command_to_arduino1(command)
    
    if success:
        insert_action('light', 'completed', f'Fita LED {state}')
        return jsonify({'success': True, 'message': f'Fita LED {state}'})
    else:
        return jsonify({'error': 'Falha ao enviar'}), 500

@app.route('/api/command/auto_irrigation', methods=['POST'])
def api_auto_irrigation():
    """Liga/desliga irrigação automática"""
    if not arduino_connected:
        return jsonify({'error': 'Arduinos não conectados'}), 503
    
    data = request.get_json()
    enable = data.get('enable', True)
    
    command = 'AUTO_ON' if enable else 'AUTO_OFF'
    success = arduino_manager.send_command_to_arduino1(command)
    
    if success:
        status = 'habilitada' if enable else 'desabilitada'
        insert_action('auto_irrigation_toggle', 'completed', f'Irrigação automática {status}')
        return jsonify({'success': True, 'message': f'Irrigação automática {status}'})
    else:
        return jsonify({'error': 'Falha ao enviar'}), 500

# ==================== WEBSOCKET ====================

@socketio.on('connect')
def handle_connect():
    """Cliente conectou"""
    print(f"[WS] Cliente conectado: {request.sid}")
    
    # Envia dados atuais imediatamente
    if arduino_manager and arduino_manager.last_sensor_data:
        emit('sensor_data', arduino_manager.last_sensor_data)
    
    emit('connection_status', {
        'connected': True,
        'arduino1_status': 'connected' if arduino_manager and arduino_manager.arduino1 else 'disconnected',
        'arduino2_status': 'connected' if arduino_manager and arduino_manager.arduino2 else 'disconnected'
    })

@socketio.on('disconnect')
def handle_disconnect():
    """Cliente desconectou"""
    print(f"[WS] Cliente desconectado: {request.sid}")

@socketio.on('request_data')
def handle_request_data():
    """Cliente solicita dados atuais"""
    if arduino_manager and arduino_manager.last_sensor_data:
        emit('sensor_data', arduino_manager.last_sensor_data)
    else:
        emit('sensor_data', {'error': 'Sem dados'})

@socketio.on('send_command')
def handle_send_command(data):
    """Comando via WebSocket"""
    command = data.get('command', '')
    print(f"[WS] Comando: {command}")
    
    if not arduino_connected:
        emit('command_response', {'error': 'Arduinos não conectados'})
        return
    
    if arduino_manager.send_command_to_arduino1(command):
        emit('command_response', {'success': True, 'command': command})
    else:
        emit('command_response', {'error': 'Falha ao enviar'})

# ==================== BACKGROUND ====================

def background_tasks():
    """Tasks em background - monitora conexão"""
    reconnect_attempts = 0
    
    while True:
        time.sleep(30)  # Verifica a cada 30s
        
        global arduino_connected
        
        if not arduino_connected and reconnect_attempts < 10:
            print(f"[BG] Tentativa de reconexão {reconnect_attempts + 1}/10...")
            if init_arduinos():
                reconnect_attempts = 0
                print("[BG] ✓ Reconectado!")
            else:
                reconnect_attempts += 1
                print(f"[BG] ✗ Falha. Próxima tentativa em 30s...")

# ==================== MAIN ====================

if __name__ == '__main__':
    print("=" * 70)
    print(" SISTEMA DE ESTUFA INTELIGENTE - SERVIDOR PRINCIPAL")
    print("=" * 70)
    
    # 1. Banco de dados
    print("\n[1/3] Inicializando banco de dados...")
    init_database()
    print("      ✓ Banco pronto!")
    
    # 2. Arduinos
    print("\n[2/3] Conectando aos 2 Arduinos...")
    print("      - Arduino 1: Sensores/Atuadores (DHT11, Solo, LDR, Relés)")
    print("      - Arduino 2: Teclado/Configuração (LCD + Teclado 4x3)")
    
    init_arduinos()
    
    # 3. Background
    print("\n[3/3] Iniciando monitoramento em background...")
    bg_thread = threading.Thread(target=background_tasks, daemon=True)
    bg_thread.start()
    print("      ✓ Background ativo!")
    
    # Status final
    print("\n" + "=" * 70)
    print(" SERVIDOR INICIADO!")
    print("=" * 70)
    print("\n 🌐 Dashboard: http://localhost:5000")
    print(" 🔌 WebSocket: ws://localhost:5000")
    
    if arduino_connected:
        print("\n ✓ Status dos Arduinos:")
        print(f"   Arduino 1 (Sensores): {arduino_manager.port1}")
        print(f"   Arduino 2 (Teclado):  {arduino_manager.port2}")
        print("\n 💡 Configure thresholds no teclado (Arduino 2)")
    else:
        print("\n ⚠️  Arduinos não conectados")
        print("    Verifique conexões USB e tente novamente")
    
    print("\n" + "=" * 70)
    print(" Pressione Ctrl+C para encerrar")
    print("=" * 70 + "\n")
    
    try:
        socketio.run(
            app, 
            host='0.0.0.0', 
            port=5000, 
            debug=False,  # Desativa reload automático
            use_reloader=False
        )
    except KeyboardInterrupt:
        print("\n\n[APP] Encerrando servidor...")
        if arduino_manager:
            arduino_manager.disconnect()
        print("[APP] ✓ Servidor encerrado!")