"""
SCRIPT DE TESTE DO SISTEMA
Execute antes de rodar app.py para verificar se tudo está OK
"""

import os
import sys
import time

def print_header(text):
    """Imprime cabeçalho formatado"""
    print("\n" + "=" * 70)
    print(f" {text}")
    print("=" * 70 + "\n")

def test_imports():
    """Testa se todas as bibliotecas estão instaladas"""
    print_header("TESTE 1: Importações")
    
    errors = []
    
    try:
        import flask
        print("✓ Flask instalado")
    except ImportError:
        errors.append("Flask não instalado: pip install flask")
    
    try:
        import flask_socketio
        print("✓ Flask-SocketIO instalado")
    except ImportError:
        errors.append("Flask-SocketIO não instalado: pip install flask-socketio")
    
    try:
        import flask_cors
        print("✓ Flask-CORS instalado")
    except ImportError:
        errors.append("Flask-CORS não instalado: pip install flask-cors")
    
    try:
        import serial
        print("✓ PySerial instalado")
    except ImportError:
        errors.append("PySerial não instalado: pip install pyserial")
    
    try:
        import pika
        print("✓ Pika (RabbitMQ) instalado")
    except ImportError:
        print("⚠️  Pika não instalado (opcional): pip install pika")
    
    if errors:
        print("\n❌ ERROS encontrados:")
        for error in errors:
            print(f"   {error}")
        return False
    else:
        print("\n✅ Todas as bibliotecas necessárias estão instaladas!")
        return True

def test_database():
    """Testa criação e acesso ao banco de dados"""
    print_header("TESTE 2: Banco de Dados")
    
    try:
        from database import init_database, insert_reading, get_latest_readings
        
        # Inicializa
        print("Inicializando banco...")
        init_database()
        
        # Insere dado de teste
        print("Inserindo leitura de teste...")
        reading_id = insert_reading(25.5, 60.0, 45, 80)
        
        if reading_id:
            print(f"✓ Leitura inserida (ID: {reading_id})")
        
        # Busca dados
        print("Buscando leituras...")
        readings = get_latest_readings(5)
        print(f"✓ {len(readings)} leituras encontradas")
        
        # Verifica se arquivo existe
        if os.path.exists('greenhouse_data.db'):
            size = os.path.getsize('greenhouse_data.db') / 1024
            print(f"✓ Banco de dados: greenhouse_data.db ({size:.1f} KB)")
        
        print("\n✅ Banco de dados funcionando!")
        return True
        
    except Exception as e:
        print(f"\n❌ ERRO no banco de dados: {e}")
        return False

def test_serial_ports():
    """Testa detecção de portas seriais"""
    print_header("TESTE 3: Portas Seriais (Arduinos)")
    
    try:
        import serial.tools.list_ports
        
        ports = list(serial.tools.list_ports.comports())
        
        if not ports:
            print("⚠️  Nenhuma porta serial encontrada!")
            print("   Conecte os Arduinos via USB")
            return False
        
        arduino_ports = []
        for port in ports:
            if 'ACM' in port.device or 'USB' in port.device or 'COM' in port.device:
                arduino_ports.append(port)
                print(f"✓ Arduino detectado: {port.device}")
                print(f"  Descrição: {port.description}")
        
        if len(arduino_ports) >= 2:
            print(f"\n✅ {len(arduino_ports)} Arduinos detectados!")
            return True
        elif len(arduino_ports) == 1:
            print(f"\n⚠️  Apenas 1 Arduino detectado!")
            print("   Conecte o segundo Arduino via USB")
            return False
        else:
            print("\n❌ Nenhum Arduino detectado!")
            return False
        
    except Exception as e:
        print(f"\n❌ ERRO ao buscar portas: {e}")
        return False

def test_rabbitmq():
    """Testa conexão com RabbitMQ (opcional)"""
    print_header("TESTE 4: RabbitMQ (Opcional)")
    
    try:
        from rabbitmq_config import RabbitMQManager
        
        print("Tentando conectar ao RabbitMQ...")
        rabbitmq = RabbitMQManager()
        
        if rabbitmq.connect():
            print("✓ RabbitMQ conectado!")
            
            # Publica alerta de teste
            rabbitmq.publish_alert({
                'type': 'system_test',
                'message': 'Teste de conexão',
                'severity': 'info'
            })
            print("✓ Alerta de teste publicado")
            
            rabbitmq.disconnect()
            print("\n✅ RabbitMQ funcionando!")
            return True
        else:
            print("\n⚠️  RabbitMQ não disponível")
            print("   Sistema funcionará sem ele (alertas apenas no SQLite)")
            return True  # Não é erro crítico
        
    except ImportError:
        print("\n⚠️  Biblioteca Pika não instalada")
        print("   RabbitMQ é opcional. Sistema funcionará sem ele.")
        return True
    except Exception as e:
        print(f"\n⚠️  RabbitMQ não disponível: {e}")
        print("   Sistema funcionará sem ele")
        return True

def test_file_structure():
    """Verifica estrutura de arquivos"""
    print_header("TESTE 5: Estrutura de Arquivos")
    
    required_files = [
        'app.py',
        'database.py',
        'dual_arduino_manager.py'
    ]
    
    optional_files = [
        'rabbitmq_config.py',
        'templates/index.html'
    ]
    
    all_ok = True
    
    print("Arquivos obrigatórios:")
    for file in required_files:
        if os.path.exists(file):
            print(f"  ✓ {file}")
        else:
            print(f"  ❌ {file} NÃO ENCONTRADO!")
            all_ok = False
    
    print("\nArquivos opcionais:")
    for file in optional_files:
        if os.path.exists(file):
            print(f"  ✓ {file}")
        else:
            print(f"  ⚠️  {file} não encontrado")
    
    if all_ok:
        print("\n✅ Todos arquivos obrigatórios presentes!")
        return True
    else:
        print("\n❌ Arquivos faltando!")
        return False

def test_arduino_communication():
    """Testa comunicação básica com Arduino"""
    print_header("TESTE 6: Comunicação com Arduino (Opcional)")
    
    try:
        import serial
        import serial.tools.list_ports
        
        ports = list(serial.tools.list_ports.comports())
        arduino_ports = [p.device for p in ports if 'ACM' in p.device or 'USB' in p.device or 'COM' in p.device]
        
        if not arduino_ports:
            print("⚠️  Nenhum Arduino conectado para teste")
            return True
        
        # Testa primeira porta
        port = arduino_ports[0]
        print(f"Testando comunicação com {port}...")
        
        try:
            ser = serial.Serial(port, 9600, timeout=3)
            time.sleep(2)  # Aguarda Arduino resetar
            
            print("Aguardando dados...")
            start = time.time()
            received = False
            
            while time.time() - start < 10:  # Tenta por 10s
                if ser.in_waiting > 0:
                    line = ser.readline().decode('utf-8').strip()
                    print(f"✓ Dados recebidos: {line[:50]}...")
                    received = True
                    break
                time.sleep(0.5)
            
            ser.close()
            
            if received:
                print("\n✅ Arduino respondendo!")
                return True
            else:
                print("\n⚠️  Arduino não enviou dados")
                print("   Verifique se o código está carregado")
                return True  # Não é erro crítico
                
        except Exception as e:
            print(f"\n⚠️  Erro ao testar Arduino: {e}")
            return True
        
    except Exception as e:
        print(f"\n❌ ERRO: {e}")
        return False

def run_all_tests():
    """Executa todos os testes"""
    print("\n" + "=" * 70)
    print(" SCRIPT DE TESTE - SISTEMA DE ESTUFA INTELIGENTE")
    print("=" * 70)
    
    results = {
        'Importações': test_imports(),
        'Banco de Dados': test_database(),
        'Portas Seriais': test_serial_ports(),
        'RabbitMQ': test_rabbitmq(),
        'Estrutura de Arquivos': test_file_structure(),
        'Comunicação Arduino': test_arduino_communication()
    }
    
    # Resumo
    print_header("RESUMO DOS TESTES")
    
    for test_name, result in results.items():
        status = "✅ PASSOU" if result else "❌ FALHOU"
        print(f"{test_name}: {status}")
    
    # Resultado final
    critical_tests = ['Importações', 'Banco de Dados', 'Portas Seriais', 'Estrutura de Arquivos']
    critical_passed = all(results[t] for t in critical_tests)
    
    print("\n" + "=" * 70)
    if critical_passed:
        print(" ✅ SISTEMA PRONTO PARA USO!")
        print("=" * 70)
        print("\nPróximo passo:")
        print("  python3 app.py")
    else:
        print(" ❌ SISTEMA COM PROBLEMAS!")
        print("=" * 70)
        print("\nCorrija os erros acima antes de rodar app.py")
    print()

if __name__ == '__main__':
    run_all_tests()