import sqlite3
from datetime import datetime
import os

DATABASE_NAME = 'greenhouse.db'

def init_database():
    """Inicializa o banco de dados e cria as tabelas se não existirem"""
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS readings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            temperature REAL NOT NULL,
            humidity REAL NOT NULL,
            soil_moisture INTEGER NOT NULL,
            light_level INTEGER NOT NULL
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS alerts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            alert_type TEXT NOT NULL,
            message TEXT NOT NULL,
            severity TEXT DEFAULT 'warning'
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS actions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            action_type TEXT NOT NULL,
            status TEXT DEFAULT 'completed',
            details TEXT
        )
    ''')
    
    conn.commit()
    conn.close()
    print(f"[DATABASE] Banco de dados inicializado: {DATABASE_NAME}")

def insert_reading(temperature, humidity, soil_moisture, light_level):
    """Insere uma nova leitura de sensores"""
    try:
        conn = sqlite3.connect(DATABASE_NAME)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO readings (temperature, humidity, soil_moisture, light_level)
            VALUES (?, ?, ?, ?)
        ''', (temperature, humidity, soil_moisture, light_level))
        
        conn.commit()
        reading_id = cursor.lastrowid
        conn.close()
        return reading_id
    except Exception as e:
        print(f"[DATABASE ERROR] Falha ao inserir leitura: {e}")
        return None

def insert_alert(alert_type, message, severity='warning'):
    """Insere um novo alerta"""
    try:
        conn = sqlite3.connect(DATABASE_NAME)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO alerts (alert_type, message, severity)
            VALUES (?, ?, ?)
        ''', (alert_type, message, severity))
        
        conn.commit()
        alert_id = cursor.lastrowid
        conn.close()
        return alert_id
    except Exception as e:
        print(f"[DATABASE ERROR] Falha ao inserir alerta: {e}")
        return None

def insert_action(action_type, status='completed', details=None):
    """Registra uma ação realizada"""
    try:
        conn = sqlite3.connect(DATABASE_NAME)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO actions (action_type, status, details)
            VALUES (?, ?, ?)
        ''', (action_type, status, details))
        
        conn.commit()
        action_id = cursor.lastrowid
        conn.close()
        return action_id
    except Exception as e:
        print(f"[DATABASE ERROR] Falha ao registrar ação: {e}")
        return None

def get_latest_readings(limit=10):
    """Retorna as últimas N leituras"""
    try:
        conn = sqlite3.connect(DATABASE_NAME)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT * FROM readings
            ORDER BY timestamp DESC
            LIMIT ?
        ''', (limit,))
        
        rows = cursor.fetchall()
        conn.close()
        
        return [dict(row) for row in rows]
    except Exception as e:
        print(f"[DATABASE ERROR] Falha ao buscar leituras: {e}")
        return []

def get_readings_by_timerange(hours=24):
    """Retorna leituras das últimas N horas"""
    try:
        conn = sqlite3.connect(DATABASE_NAME)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT * FROM readings
            WHERE timestamp >= datetime('now', '-' || ? || ' hours')
            ORDER BY timestamp ASC
        ''', (hours,))
        
        rows = cursor.fetchall()
        conn.close()
        
        return [dict(row) for row in rows]
    except Exception as e:
        print(f"[DATABASE ERROR] Falha ao buscar leituras por tempo: {e}")
        return []

def get_latest_alerts(limit=10):
    """Retorna os últimos N alertas"""
    try:
        conn = sqlite3.connect(DATABASE_NAME)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT * FROM alerts
            ORDER BY timestamp DESC
            LIMIT ?
        ''', (limit,))
        
        rows = cursor.fetchall()
        conn.close()
        
        return [dict(row) for row in rows]
    except Exception as e:
        print(f"[DATABASE ERROR] Falha ao buscar alertas: {e}")
        return []

def get_statistics():
    """Retorna estatísticas gerais do sistema"""
    try:
        conn = sqlite3.connect(DATABASE_NAME)
        cursor = conn.cursor()
        
        stats = {}
        
        cursor.execute('SELECT COUNT(*) FROM readings')
        stats['total_readings'] = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(*) FROM alerts')
        stats['total_alerts'] = cursor.fetchone()[0]
        
        cursor.execute('''
            SELECT 
                AVG(temperature) as avg_temp,
                AVG(humidity) as avg_humid,
                AVG(soil_moisture) as avg_soil,
                AVG(light_level) as avg_light
            FROM readings
            WHERE timestamp >= datetime('now', '-24 hours')
        ''')
        
        averages = cursor.fetchone()
        stats['avg_temperature'] = round(averages[0], 1) if averages[0] else 0
        stats['avg_humidity'] = round(averages[1], 1) if averages[1] else 0
        stats['avg_soil_moisture'] = round(averages[2], 1) if averages[2] else 0
        stats['avg_light_level'] = round(averages[3], 1) if averages[3] else 0
        
        conn.close()
        return stats
    except Exception as e:
        print(f"[DATABASE ERROR] Falha ao buscar estatísticas: {e}")
        return {}

def clear_old_data(days=30):
    """Remove dados mais antigos que N dias"""
    try:
        conn = sqlite3.connect(DATABASE_NAME)
        cursor = conn.cursor()
        
        cursor.execute('''
            DELETE FROM readings
            WHERE timestamp < datetime('now', '-' || ? || ' days')
        ''', (days,))
        
        deleted = cursor.rowcount
        conn.commit()
        conn.close()
        
        print(f"[DATABASE] {deleted} leituras antigas removidas")
        return deleted
    except Exception as e:
        print(f"[DATABASE ERROR] Falha ao limpar dados antigos: {e}")
        return 0

if __name__ == '__main__':
    print("Inicializando banco de dados...")
    init_database()
    
    print("Inserindo dados de teste...")
    insert_reading(25.5, 60.0, 45, 80)
    insert_alert('low_soil_moisture', 'Umidade do solo baixa', 'warning')
    insert_action('irrigation', 'completed', 'Irrigação manual ativada')
    
    print("\nÚltimas leituras:")
    for reading in get_latest_readings(5):
        print(reading)
    
    print("\nÚltimos alertas:")
    for alert in get_latest_alerts(5):
        print(alert)
    
    print("\nEstatísticas:")
    print(get_statistics())