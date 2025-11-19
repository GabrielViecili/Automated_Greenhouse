from flask import Flask, render_template, jsonify, request
from flask_socketio import SocketIO, emit
from flask_cors import CORS
import json
from datetime import datetime
import threading
import time
import traceback

from database import (
    init_database, 
    insert_reading,
    insert_action,
    get_latest_readings, 
    get_readings_by_timerange,
    get_latest_alerts,
    get_statistics
)

try:
    from dual_arduino_manager import DualArduinoManager
    ARDUINO_AVAILABLE = True
except ImportError:
    print("⚠️  dual_arduino_manager não encontrado - modo sem hardware")
    ARDUINO_AVAILABLE = False

try:
    from rabbitmq_config import RabbitMQManager
    RABBITMQ_AVAILABLE = True
except ImportError:
    print("⚠️  RabbitMQ não disponível")
    RABBITMQ_AVAILABLE = False

app = Flask(__name__)
app.config['SECRET_KEY'] = 'greenhouse_secret_2025'
CORS(app)

socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

arduino_manager = None
arduino_connected = False

def on_arduino_data(data):
    """Callback quando dados chegam do Arduino 1"""
    socketio.emit('sensor_data', data, namespace='/')
    print(f"[WS] Dados emitidos: T:{data.get('temp')}°C H:{data.get('humid')}% S:{data.get('soil')}%")

def init_arduinos():
    """Inicializa conexão com os 2 Arduinos"""
    global arduino_manager, arduino_connected
    
    if not ARDUINO_AVAILABLE:
        print("[APP] ⚠️  Modo sem hardware - DualArduinoManager não disponível")
        return False
    
    try:
        arduino_manager = DualArduinoManager(
            callback=on_arduino_data,
            use_rabbitmq=RABBITMQ_AVAILABLE
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
        traceback.print_exc()
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
        'arduino1': 'connected' if arduino_manager and hasattr(arduino_manager, 'ser1') and arduino_manager.ser1 else 'disconnected',
        'arduino2': 'connected' if arduino_manager and hasattr(arduino_manager, 'ser2') and arduino_manager.ser2 else 'disconnected',
        'timestamp': datetime.now().isoformat()
    })

@app.route('/api/readings/latest')
def api_latest_readings():
    """Últimas leituras do banco"""
    try:
        limit = request.args.get('limit', 10, type=int)
        readings = get_latest_readings(limit)
        return jsonify(readings)
    except Exception as e:
        print(f"[API ERROR] /api/readings/latest: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/readings/history')
def api_readings_history():
    """Histórico de leituras"""
    try:
        hours = request.args.get('hours', 24, type=int)
        readings = get_readings_by_timerange(hours)
        return jsonify(readings)
    except Exception as e:
        print(f"[API ERROR] /api/readings/history: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/history', methods=['GET'])
def get_history_data():
    """Endpoint para alimentar o gráfico com dados históricos"""
    try:
        history = get_readings_by_timerange(hours=24)

        labels = []
        temps = []
        humids = []
        soils = []
        lights = []

        sample_rate = 1
        if len(history) > 200:
            sample_rate = len(history) // 200

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
        print(f"[API ERROR] /api/history: {e}")
        traceback.print_exc()
        return jsonify({"success": False, "message": str(e)}), 500

@app.route('/api/alerts/latest')
def api_latest_alerts():
    """Últimos alertas"""
    try:
        limit = request.args.get('limit', 10, type=int)
        alerts = get_latest_alerts(limit)
        return jsonify(alerts)
    except Exception as e:
        print(f"[API ERROR] /api/alerts/latest: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/statistics')
def api_statistics():
    """Estatísticas gerais"""
    try:
        stats = get_statistics()
        return jsonify(stats)
    except Exception as e:
        print(f"[API ERROR] /api/statistics: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/thresholds', methods=['GET'])
def api_get_thresholds():
    """Retorna thresholds atuais"""
    try:
        if not arduino_connected or not arduino_manager:
            return jsonify({
                'thresholds': {
                    'temp_max': 30.0,
                    'temp_min': 18.0,
                    'humid_max': 80.0,
                    'humid_min': 40.0,
                    'soil_min': 30,
                    'light_min': 20
                },
                'active': False,
                'note': 'Arduinos não conectados - valores padrão'
            })
        
        return jsonify({
            'thresholds': arduino_manager.thresholds,
            'active': True
        })
    except Exception as e:
        print(f"[API ERROR] GET /api/thresholds: {e}")
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/thresholds', methods=['POST'])
def api_set_thresholds():
    """Define thresholds via API"""
    try:
        if not request.is_json:
            return jsonify({
                'success': False,
                'message': 'Content-Type deve ser application/json'
            }), 400
        
        data = request.get_json()
        
        if not data:
            return jsonify({
                'success': False,
                'message': 'Dados JSON inválidos ou vazios'
            }), 400
        
        print(f"[API] POST /api/thresholds recebido: {data}")
        
        if not arduino_connected or not arduino_manager:
            print("[API] Sem Arduino - salvando apenas no banco")
            
            insert_action(
                'thresholds_update',
                'completed',
                f'Thresholds atualizados via web: {json.dumps(data)}'
            )
            
            return jsonify({
                'success': True,
                'message': 'Thresholds salvos (Arduinos offline)',
                'thresholds': data,
                'note': 'Serão aplicados quando Arduinos conectarem'
            })
        
        if hasattr(arduino_manager, 'update_thresholds_from_app'):
            success, message = arduino_manager.update_thresholds_from_app(data)
        else:
            print("[API] Método update_thresholds_from_app não existe - usando fallback")
            
            if 'tempMax' in data:
                arduino_manager.thresholds['temp_max'] = float(data['tempMax'])
            if 'tempMin' in data:
                arduino_manager.thresholds['temp_min'] = float(data['tempMin'])
            if 'umiMin' in data:
                arduino_manager.thresholds['humid_min'] = float(data['umiMin'])
            if 'terraMin' in data:
                arduino_manager.thresholds['soil_min'] = float(data['terraMin'])
            if 'luzMin' in data:
                arduino_manager.thresholds['light_min'] = float(data['luzMin'])
            
            arduino_manager.send_thresholds_to_arduino1()
            
            success = True
            message = "Thresholds atualizados"
        
        if success:
            socketio.emit('thresholds_updated', arduino_manager.thresholds, namespace='/')
            
            return jsonify({
                'success': True,
                'message': message,
                'thresholds': arduino_manager.thresholds
            })
        else:
            return jsonify({
                'success': False,
                'message': message
            }), 500
            
    except Exception as e:
        print(f"[API ERROR] POST /api/thresholds: {e}")
        traceback.print_exc()
        return jsonify({
            'success': False,
            'message': f'Erro no servidor: {str(e)}'
        }), 500

@app.route('/api/command/irrigate', methods=['POST'])
def api_irrigate():
    """Ativa irrigação manual"""
    try:
        if not arduino_connected:
            return jsonify({'error': 'Arduinos não conectados'}), 503
        
        success = arduino_manager.send_command_to_arduino1('IRRIGATE')
        
        if success:
            insert_action('irrigation', 'completed', 'Irrigação manual via API')
            return jsonify({'success': True, 'message': 'Irrigação ativada'})
        else:
            return jsonify({'error': 'Falha ao enviar'}), 500
    except Exception as e:
        print(f"[API ERROR] /api/command/irrigate: {e}")
        return jsonify({'error': str(e)}), 500

# ==================== WEBSOCKET ====================

@socketio.on('connect')
def handle_connect():
    """Cliente conectou ao WebSocket"""
    print(f"[WS] Cliente conectado: {request.sid}")
    
    emit('status_update', {
        'arduino1_status': 'connected' if arduino_manager and hasattr(arduino_manager, 'ser1') and arduino_manager.ser1 else 'disconnected',
        'arduino2_status': 'connected' if arduino_manager and hasattr(arduino_manager, 'ser2') and arduino_manager.ser2 else 'disconnected',
        'thresholds': arduino_manager.thresholds if arduino_manager else {}
    })
    
    if arduino_manager and hasattr(arduino_manager, 'last_sensor_data'):
        emit('sensor_data', arduino_manager.last_sensor_data)

@socketio.on('disconnect')
def handle_disconnect():
    """Cliente desconectou"""
    print(f"[WS] Cliente desconectado: {request.sid}")

@socketio.on('request_data')
def handle_request_data():
    """Cliente solicita dados atuais"""
    if arduino_manager and hasattr(arduino_manager, 'last_sensor_data'):
        emit('sensor_data', arduino_manager.last_sensor_data)
    else:
        emit('sensor_data', {'error': 'Sem dados'})

# ==================== BACKGROUND ====================

def background_tasks():
    """Tarefas em background"""
    if not RABBITMQ_AVAILABLE:
        return
    
    rabbit_for_reports = RabbitMQManager()
    if not rabbit_for_reports.connect():
        print("✗ [BG-TASK] RabbitMQ não disponível")
        return

    last_report_time = time.time()
    REPORT_INTERVAL = 14400

    while True:
        now = time.time()

        if now - last_report_time > REPORT_INTERVAL:
            try:
                stats = get_statistics()
                if stats:
                    message = (
                        f"Resumo das últimas 24h:\n"
                        f"  🌡️ Temp: {stats.get('avg_temperature', 0):.1f}°C\n"
                        f"  💧 Solo: {stats.get('avg_soil_moisture', 0):.0f}%\n"
                        f"  💨 Ar: {stats.get('avg_humidity', 0):.0f}%\n"
                        f"  ☀️ Luz: {stats.get('avg_light_level', 0):.0f}%"
                    )
                    rabbit_for_reports.publish_alert({
                        'type': 'average_report',
                        'message': message,
                        'severity': 'info'
                    })
                last_report_time = now
            except Exception as e:
                print(f"✗ [RABBITMQ] Erro: {e}")

        time.sleep(60)

# ==================== MAIN ====================

if __name__ == '__main__':
    print("=" * 70)
    print(" SISTEMA DE ESTUFA INTELIGENTE")
    print("=" * 70)
    
    print("\n[1/3] Inicializando banco de dados...")
    init_database()
    print("      ✓ Banco pronto!")
    
    print("\n[2/3] Conectando Arduinos...")
    init_arduinos()
    
    print("\n[3/3] Iniciando background...")
    bg_thread = threading.Thread(target=background_tasks, daemon=True)
    bg_thread.start()
    print("      ✓ Background ativo!")
    
    print("\n" + "=" * 70)
    print(" SERVIDOR INICIADO!")
    print("=" * 70)
    print("\n 🌐 Dashboard: http://localhost:5000")
    print(" 📡 API: http://localhost:5000/api/status")
    
    if arduino_connected:
        print(f"\n ✓ Arduino 1: {arduino_manager.port1}")
        print(f" ✓ Arduino 2: {arduino_manager.port2}")
    else:
        print("\n ⚠️  Modo sem hardware")
    
    print("\n" + "=" * 70)
    print(" Pressione Ctrl+C para encerrar")
    print("=" * 70 + "\n")
    
    try:
        socketio.run(
            app, 
            host='0.0.0.0', 
            port=5000, 
            debug=False,
            use_reloader=False,
            allow_unsafe_werkzeug=True
        )
    except KeyboardInterrupt:
        print("\n\n[APP] Encerrando...")
        if arduino_manager:
            arduino_manager.stop()
        print("[APP] ✓ Encerrado!")