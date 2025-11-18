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
from rabbitmq_config import RabbitMQManager

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

# Em app.py
@app.route('/api/thresholds', methods=['POST'])
def update_thresholds(): # Mudei o nome para corresponder ao index.html
    """
    Endpoint para atualizar os thresholds (limites) a partir do website.
    """
    global arduino_manager
    if not arduino_manager:
        return jsonify({"success": False, "message": "Arduino não conectado"}), 500

    data = request.json
    
    # <<< AQUI ESTÁ A CORREÇÃO >>>
    # Chama a função correta no manager, que processa E envia
    success, message = arduino_manager.update_thresholds_from_app(data)
    
    if success:
        socketio.emit('thresholds_updated', arduino_manager.thresholds, broadcast=True)
        return jsonify({"success": True, "message": message})
    else:
        return jsonify({"success": False, "message": message}), 500
    
    # Em app.py

@app.route('/api/history', methods=['GET'])
def get_history_data():
    """
    Endpoint para alimentar o gráfico com dados históricos (últimas 24h).
    """
    try:
        # Busca dados das últimas 24 horas
        history = get_readings_by_timerange(hours=24)

        # Formata os dados para o Chart.js
        # (O Chart.js prefere 'labels' e 'datasets' separados)
        labels = []
        temps = []
        humids = []
        soils = []
        lights = []

        # Para otimizar, podemos pegar apenas 1 a cada N pontos
        # Ex: Se tiver 1000 pontos, só 100.
        sample_rate = 1
        if len(history) > 200: # Se tiver mais de 200 pontos
            sample_rate = len(history) // 200 # Pega ~200 amostras

        for i, reading in enumerate(history):
            if i % sample_rate == 0:
                labels.append(reading['timestamp'])
                temps.append(reading['temperature'])
                humids.append(reading['humidity'])
                soils.append(reading['soil_moisture'])
                lights.append(reading['light_level'])

        return jsonify({
            "success": True,
            "labels": labels,
            "datasets": [
                {"label": "Temperatura", "data": temps},
                {"label": "Umidade Ar", "data": humids},
                {"label": "Umidade Solo", "data": soils},
                {"label": "Luz", "data": lights}
            ]
        })
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


# ==================== WEBSOCKET ====================

@socketio.on('connect')
def handle_connect(auth=None): # <<< MUDANÇA 1: Aceita o argumento 'auth'
    print(f"[WS] Cliente conectado: {request.sid}")
    # Envia status inicial
    emit('status_update', {
        # <<< MUDANÇA 2: Usa .ser1 e .ser2 (como o seu manager v2)
        'arduino1_status': 'connected' if arduino_manager and arduino_manager.ser1 else 'disconnected',
        'arduino2_status': 'connected' if arduino_manager and arduino_manager.ser2 else 'disconnected',
        'thresholds': arduino_manager.thresholds if arduino_manager else {}
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
    """Tarefas que correm em background (ex: limpar DB, enviar relatórios)"""

    # Cria uma nova instância do RabbitMQ SÓ para esta thread
    # Isto é mais seguro do que partilhar a do arduino_manager
    rabbit_for_reports = RabbitMQManager()
    if not rabbit_for_reports.connect():
        print("✗ [BG-TASK] Falha ao conectar ao RabbitMQ para relatórios.")
        rabbit_for_reports = None

    last_report_time = time.time()
    REPORT_INTERVAL = 1800 # 4 horas (em segundos)

    while True:
        now = time.time()

        # --- TAREFA 1: Enviar Relatório de Média ---
        if rabbit_for_reports and (now - last_report_time > REPORT_INTERVAL):
            try:
                stats = get_statistics() # Função do database.py
                if stats:
                    message = (
                        f"Resumo das últimas 24h:\n"
                        f"  🌡️ Temp Média: {stats['avg_temp']:.1f}°C\n"
                        f"  💧 Solo Médio: {stats['avg_soil']:.0f}%\n"
                        f"  💨 Ar Médio: {stats['avg_humidity']:.0f}%\n"
                        f"  ☀️ Luz Média: {stats['avg_light']:.0f}%"
                    )

                    rabbit_for_reports.publish_alert({
                        'type': 'average_report', # Novo tipo
                        'message': message,
                        'severity': 'info' # Não é 'critical'
                    })
                    print(f"✓ [RABBITMQ] Relatório de médias enviado.")

                last_report_time = now
            except Exception as e:
                print(f"✗ [RABBITMQ] Erro ao enviar relatório de médias: {e}")

        # --- TAREFA 2: Limpar DB Antigo ---
        # (Pode adicionar a sua lógica de limpar o DB antigo aqui também)

        time.sleep(60)

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