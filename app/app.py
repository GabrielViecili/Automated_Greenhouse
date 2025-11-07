from flask import Flask, render_template, jsonify, request
from flask_socketio import SocketIO, emit
from flask_cors import CORS
from serial_reader import ArduinoReader
import json
from datetime import datetime
import threading
import time
import os

from database import (
    init_database, 
    insert_reading, 
    insert_action,
    get_latest_readings, 
    get_readings_by_timerange,
    get_latest_alerts,
    get_statistics
)
from serial_reader import ArduinoReader

try:
    from serial_reader_rabbitmq import ArduinoReaderWithRabbitMQ as ArduinoReader
    print("[APP] Usando versão com RabbitMQ")
except ImportError:
    from serial_reader import ArduinoReader
    print("[APP] Usando versão original (sem RabbitMQ)")

app = Flask(__name__)
app.config['SECRET_KEY'] = 'greenhouse_secret_2025'
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*")

# Instância global do leitor Arduino
arduino = None
arduino_connected = False

def on_arduino_data(data):
    """Callback chamado quando dados chegam do Arduino"""
    # Emite dados em tempo real via WebSocket para todos os clientes conectados
    socketio.emit('sensor_data', data, broadcast=True)
    print(f"[WEBSOCKET] Dados emitidos: {data}")

def init_arduino():
    """Inicializa conexão com Arduino"""
    global arduino, arduino_connected
    
    try:
        arduino = ArduinoReader(callback=on_arduino_data)
        if arduino.connect():
            arduino.start()
            arduino_connected = True
            print("[APP] Arduino conectado e iniciado!")
            return True
        else:
            print("[APP] Falha ao conectar com Arduino")
            arduino_connected = False
            return False
    except Exception as e:
        print(f"[APP ERROR] Erro ao inicializar Arduino: {e}")
        arduino_connected = False
        return False

# ==================== ROTAS HTTP ====================

@app.route('/')
def index():
    """Página principal do dashboard"""
    return render_template('dashboard.html')

@app.route('/api/status')
def api_status():
    """Retorna status do sistema"""
    return jsonify({
        'status': 'online',
        'arduino_connected': arduino_connected,
        'timestamp': datetime.now().isoformat()
    })

@app.route('/api/readings/latest')
def api_latest_readings():
    """Retorna as últimas leituras"""
    limit = request.args.get('limit', 10, type=int)
    readings = get_latest_readings(limit)
    return jsonify(readings)

@app.route('/api/readings/history')
def api_readings_history():
    """Retorna histórico de leituras"""
    hours = request.args.get('hours', 24, type=int)
    readings = get_readings_by_timerange(hours)
    return jsonify(readings)

@app.route('/api/alerts/latest')
def api_latest_alerts():
    """Retorna os últimos alertas"""
    limit = request.args.get('limit', 10, type=int)
    alerts = get_latest_alerts(limit)
    return jsonify(alerts)

@app.route('/api/statistics')
def api_statistics():
    """Retorna estatísticas do sistema"""
    stats = get_statistics()
    return jsonify(stats)

@app.route('/api/command/irrigate', methods=['POST'])
def api_irrigate():
    """Comando para ativar irrigação"""
    if not arduino_connected:
        return jsonify({'error': 'Arduino não conectado'}), 503
    
    success = arduino.send_command('IRRIGATE')
    if success:
        insert_action('irrigation', 'completed', 'Irrigação manual ativada via API')
        return jsonify({'success': True, 'message': 'Irrigação ativada'})
    else:
        return jsonify({'error': 'Falha ao enviar comando'}), 500

@app.route('/api/command/auto_irrigation', methods=['POST'])
def api_auto_irrigation():
    """Ativa/desativa irrigação automática"""
    if not arduino_connected:
        return jsonify({'error': 'Arduino não conectado'}), 503
    
    data = request.get_json()
    enable = data.get('enable', True)
    
    command = 'AUTO_ON' if enable else 'AUTO_OFF'
    success = arduino.send_command(command)
    
    if success:
        status = 'habilitada' if enable else 'desabilitada'
        insert_action('auto_irrigation_toggle', 'completed', f'Irrigação automática {status}')
        return jsonify({'success': True, 'message': f'Irrigação automática {status}'})
    else:
        return jsonify({'error': 'Falha ao enviar comando'}), 500

@app.route('/api/command/custom', methods=['POST'])
def api_custom_command():
    """Envia comando customizado para Arduino"""
    if not arduino_connected:
        return jsonify({'error': 'Arduino não conectado'}), 503
    
    data = request.get_json()
    command = data.get('command', '')
    
    if not command:
        return jsonify({'error': 'Comando vazio'}), 400
    
    success = arduino.send_command(command)
    if success:
        return jsonify({'success': True, 'message': 'Comando enviado'})
    else:
        return jsonify({'error': 'Falha ao enviar comando'}), 500

# ==================== WEBSOCKET EVENTS ====================

@socketio.on('connect')
def handle_connect():
    """Cliente WebSocket conectou"""
    print(f"[WEBSOCKET] Cliente conectado: {request.sid}")
    
    # Envia último dado disponível para o novo cliente
    if arduino and arduino.last_data:
        emit('sensor_data', arduino.last_data)
    
    emit('connection_status', {
        'connected': True,
        'arduino_status': arduino_connected
    })

@socketio.on('disconnect')
def handle_disconnect():
    """Cliente WebSocket desconectou"""
    print(f"[WEBSOCKET] Cliente desconectado: {request.sid}")

@socketio.on('request_data')
def handle_request_data():
    """Cliente solicita dados atuais"""
    if arduino and arduino.last_data:
        emit('sensor_data', arduino.last_data)
    else:
        emit('sensor_data', {'error': 'Nenhum dado disponível'})

@socketio.on('send_command')
def handle_send_command(data):
    """Recebe comando via WebSocket"""
    command = data.get('command', '')
    print(f"[WEBSOCKET] Comando recebido: {command}")
    
    if not arduino_connected:
        emit('command_response', {'error': 'Arduino não conectado'})
        return
    
    if arduino.send_command(command):
        emit('command_response', {'success': True, 'command': command})
    else:
        emit('command_response', {'error': 'Falha ao enviar comando'})

# ==================== FUNÇÕES DE INICIALIZAÇÃO ====================

def background_tasks():
    """Tasks em background (simulação quando Arduino não está disponível)"""
    while True:
        time.sleep(10)
        
        # Se não tiver Arduino conectado, tenta reconectar
        if not arduino_connected:
            print("[APP] Tentando reconectar Arduino...")
            init_arduino()

# ==================== MAIN ====================

if __name__ == '__main__':
    print("=" * 50)
    print("SISTEMA DE MONITORAMENTO DE ESTUFA INTELIGENTE")
    print("=" * 50)
    
    # Inicializa banco de dados
    print("\n[1/3] Inicializando banco de dados...")
    init_database()
    
    # Inicializa Arduino
    print("[2/3] Conectando ao Arduino...")
    init_arduino()
    
    # Inicia tasks em background
    print("[3/3] Iniciando tasks em background...")
    bg_thread = threading.Thread(target=background_tasks, daemon=True)
    bg_thread.start()
    
    # Inicia servidor
    print("\n" + "=" * 50)
    print("SERVIDOR INICIADO!")
    print("Acesse: http://localhost:5000")
    print("WebSocket disponível em: ws://localhost:5000")
    print("=" * 50 + "\n")
    
    try:
        socketio.run(app, host='0.0.0.0', port=5000, debug=True, use_reloader=False)
    except KeyboardInterrupt:
        print("\n\n[APP] Encerrando servidor...")
        if arduino:
            arduino.disconnect()
        print("[APP] Servidor encerrado!")