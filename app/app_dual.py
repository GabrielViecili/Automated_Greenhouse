"""
SERVIDOR FLASK COM 2 ARDUINOS
- Arduino 1: Sensores/Atuadores
- Arduino 2: Teclado/Configuração
"""

from flask import Flask, render_template, jsonify, request
from flask_socketio import SocketIO, emit
from flask_cors import CORS
import json
from datetime import datetime
import threading
import time

from database import (
    init_database, 
    insert_action,
    get_latest_readings, 
    get_readings_by_timerange,
    get_latest_alerts,
    get_statistics
)
from dual_arduino_manager import DualArduinoManager

app = Flask(__name__)
app.config['SECRET_KEY'] = 'greenhouse_secret_2025'
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*")

# Instância global do gerenciador
arduino_manager = None
arduino_connected = False

def on_arduino_data(data):
    """Callback quando dados chegam do Arduino 1"""
    socketio.emit('sensor_data', data, broadcast=True)
    print(f"[WEBSOCKET] Dados emitidos: {data}")

def init_arduinos():
    """Inicializa conexão com os 2 Arduinos"""
    global arduino_manager, arduino_connected
    
    try:
        arduino_manager = DualArduinoManager(callback=on_arduino_data)
        
        if arduino_manager.connect():
            arduino_manager.start()
            arduino_connected = True
            print("[APP] ✓ 2 Arduinos conectados e iniciados!")
            return True
        else:
            print("[APP] ✗ Falha ao conectar com Arduinos")
            arduino_connected = False
            return False
    except Exception as e:
        print(f"[APP ERROR] Erro ao inicializar Arduinos: {e}")
        arduino_connected = False
        return False

# ==================== ROTAS HTTP ====================

@app.route('/')
def index():
    """Página principal"""
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
    """Últimas leituras"""
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
    """Estatísticas do sistema"""
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
    """
    Define thresholds manualmente (via API)
    Arduino 2 tem prioridade (via teclado)
    """
    if not arduino_connected:
        return jsonify({'error': 'Arduinos não conectados'}), 503
    
    data = request.get_json()
    
    # Envia para Arduino 1
    success = arduino_manager.send_thresholds_to_arduino1(data)
    
    if success:
        return jsonify({
            'success': True, 
            'message': 'Thresholds atualizados',
            'note': 'Arduino 2 (teclado) pode sobrescrever estes valores'
        })
    else:
        return jsonify({'error': 'Falha ao enviar thresholds'}), 500

@app.route('/api/command/irrigate', methods=['POST'])
def api_irrigate():
    """Ativa irrigação"""
    if not arduino_connected:
        return jsonify({'error': 'Arduinos não conectados'}), 503
    
    success = arduino_manager.send_command_to_arduino1('IRRIGATE')
    
    if success:
        insert_action('irrigation', 'completed', 'Irrigação manual via API')
        return jsonify({'success': True, 'message': 'Irrigação ativada'})
    else:
        return jsonify({'error': 'Falha ao enviar comando'}), 500

@app.route('/api/command/auto_irrigation', methods=['POST'])
def api_auto_irrigation():
    """Ativa/desativa irrigação automática"""
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
        return jsonify({'error': 'Falha ao enviar comando'}), 500

@app.route('/api/command/custom', methods=['POST'])
def api_custom_command():
    """Comando customizado para Arduino 1"""
    if not arduino_connected:
        return jsonify({'error': 'Arduinos não conectados'}), 503
    
    data = request.get_json()
    command = data.get('command', '')
    
    if not command:
        return jsonify({'error': 'Comando vazio'}), 400
    
    success = arduino_manager.send_command_to_arduino1(command)
    
    if success:
        return jsonify({'success': True, 'message': 'Comando enviado'})
    else:
        return jsonify({'error': 'Falha ao enviar comando'}), 500

# ==================== WEBSOCKET EVENTS ====================

@socketio.on('connect')
def handle_connect():
    """Cliente conectou"""
    print(f"[WEBSOCKET] Cliente conectado: {request.sid}")
    
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
    print(f"[WEBSOCKET] Cliente desconectado: {request.sid}")

@socketio.on('request_data')
def handle_request_data():
    """Cliente solicita dados"""
    if arduino_manager and arduino_manager.last_sensor_data:
        emit('sensor_data', arduino_manager.last_sensor_data)
    else:
        emit('sensor_data', {'error': 'Nenhum dado disponível'})

@socketio.on('send_command')
def handle_send_command(data):
    """Comando via WebSocket"""
    command = data.get('command', '')
    print(f"[WEBSOCKET] Comando: {command}")
    
    if not arduino_connected:
        emit('command_response', {'error': 'Arduinos não conectados'})
        return
    
    if arduino_manager.send_command_to_arduino1(command):
        emit('command_response', {'success': True, 'command': command})
    else:
        emit('command_response', {'error': 'Falha ao enviar comando'})

# ==================== BACKGROUND TASKS ====================

def background_tasks():
    """Tasks em background"""
    while True:
        time.sleep(10)
        
        if not arduino_connected:
            print("[APP] Tentando reconectar Arduinos...")
            init_arduinos()

# ==================== MAIN ====================

if __name__ == '__main__':
    print("=" * 60)
    print("SISTEMA DE ESTUFA INTELIGENTE - 2 ARDUINOS")
    print("=" * 60)
    
    # Banco de dados
    print("\n[1/3] Inicializando banco de dados...")
    init_database()
    
    # Arduinos
    print("[2/3] Conectando aos 2 Arduinos...")
    print("  - Arduino 1: Sensores/Atuadores")
    print("  - Arduino 2: Teclado/Configuração")
    init_arduinos()
    
    # Background
    print("[3/3] Iniciando tasks em background...")
    bg_thread = threading.Thread(target=background_tasks, daemon=True)
    bg_thread.start()
    
    # Servidor
    print("\n" + "=" * 60)
    print("SERVIDOR INICIADO!")
    print("=" * 60)
    print("Acesse: http://localhost:5000")
    print("WebSocket: ws://localhost:5000")
    
    if arduino_connected:
        print("\n✓ Status dos Arduinos:")
        print(f"  Arduino 1 (Sensores): {arduino_manager.port1}")
        print(f"  Arduino 2 (Teclado):  {arduino_manager.port2}")
        print("\nDica: Configure thresholds no teclado (Arduino 2)")
        print("      e veja a sincronização automática!")
    else:
        print("\n⚠️  Arduinos não conectados")
        print("   Verifique conexões USB")
    
    print("=" * 60 + "\n")
    
    try:
        socketio.run(app, host='0.0.0.0', port=5000, debug=True, use_reloader=False)
    except KeyboardInterrupt:
        print("\n\n[APP] Encerrando servidor...")
        if arduino_manager:
            arduino_manager.disconnect()
        print("[APP] Servidor encerrado!")