"""
SCRIPT PARA TESTAR IDENTIFICAÇÃO DOS ARDUINOS
Ajuda a diagnosticar problemas de conexão
"""

import serial
import serial.tools.list_ports
import time

def list_ports():
    """Lista todas as portas USB"""
    print("=" * 60)
    print("PORTAS USB DISPONÍVEIS")
    print("=" * 60)
    
    ports = list(serial.tools.list_ports.comports())
    
    if not ports:
        print("❌ Nenhuma porta USB encontrada!")
        return []
    
    arduino_ports = []
    
    for i, port in enumerate(ports, 1):
        is_arduino = 'ACM' in port.device or 'USB' in port.device or 'COM' in port.device
        marker = "✓" if is_arduino else " "
        
        print(f"{marker} {i}. {port.device}")
        print(f"   Descrição: {port.description}")
        print(f"   Fabricante: {port.manufacturer if port.manufacturer else 'N/A'}")
        print()
        
        if is_arduino:
            arduino_ports.append(port.device)
    
    return arduino_ports

def test_port(port, duration=10):
    """Testa uma porta específica"""
    print("\n" + "=" * 60)
    print(f"TESTANDO: {port}")
    print("=" * 60)
    
    try:
        print(f"Abrindo conexão serial ({port}, 9600 baud)...")
        ser = serial.Serial(port, 9600, timeout=2)
        
        print(f"Aguardando {duration}s (Arduino pode resetar)...")
        time.sleep(3)
        
        # Limpa buffer
        ser.reset_input_buffer()
        
        print("\nLendo dados...\n")
        
        start = time.time()
        line_count = 0
        
        while time.time() - start < duration:
            if ser.in_waiting > 0:
                try:
                    line = ser.readline().decode('utf-8', errors='ignore').strip()
                    
                    if line:
                        line_count += 1
                        elapsed = time.time() - start
                        print(f"[{elapsed:.1f}s] {line}")
                        
                        # Analisa conteúdo
                        if '"source":"arduino1"' in line or '"temp"' in line:
                            print("  → 🎯 Parece ser Arduino 1 (Sensores)")
                        elif '"source":"arduino2"' in line or '"thresholds"' in line:
                            print("  → 🎯 Parece ser Arduino 2 (Teclado)")
                
                except Exception as e:
                    print(f"  ⚠️  Erro ao decodificar: {e}")
            
            time.sleep(0.1)
        
        ser.close()
        
        print(f"\n✓ Teste concluído: {line_count} linhas recebidas")
        
        if line_count == 0:
            print("\n⚠️  NENHUM DADO RECEBIDO!")
            print("\nPossíveis causas:")
            print("  1. Arduino não tem código carregado")
            print("  2. Baudrate incorreto (use 9600)")
            print("  3. Arduino travado/com problema")
            print("  4. Cabo USB com defeito")
            print("\nSoluções:")
            print("  - Re-upload do código Arduino")
            print("  - Reset manual (botão no Arduino)")
            print("  - Troque o cabo USB")
        
        return line_count > 0
        
    except serial.SerialException as e:
        print(f"\n❌ ERRO ao abrir porta: {e}")
        print("\nPossíveis causas:")
        print("  - Porta em uso por outro programa")
        print("  - Sem permissão (tente: sudo usermod -a -G dialout $USER)")
        print("  - Arduino desconectado")
        return False
    
    except Exception as e:
        print(f"\n❌ ERRO: {e}")
        return False

def test_all_arduinos():
    """Testa todos Arduinos encontrados"""
    ports = list_ports()
    
    if not ports:
        print("\n❌ Nenhum Arduino encontrado!")
        print("\nVerifique:")
        print("  1. Arduinos estão conectados via USB")
        print("  2. Cabos USB funcionando")
        print("  3. Drivers instalados (no Linux geralmente já vem)")
        return
    
    print(f"\n✓ {len(ports)} Arduino(s) encontrado(s)")
    print("\nTestando cada um...\n")
    
    input("Pressione ENTER para começar os testes...")
    
    results = {}
    
    for port in ports:
        success = test_port(port, duration=10)
        results[port] = success
        
        if len(ports) > 1:
            input(f"\nPressione ENTER para testar próxima porta...")
    
    # Resumo
    print("\n" + "=" * 60)
    print("RESUMO DOS TESTES")
    print("=" * 60)
    
    for port, success in results.items():
        status = "✓ OK" if success else "✗ FALHOU"
        print(f"{port}: {status}")
    
    working_ports = [p for p, s in results.items() if s]
    
    if len(working_ports) >= 2:
        print(f"\n✅ {len(working_ports)} Arduinos funcionando!")
        print("\nOrdem sugerida para app.py:")
        for i, port in enumerate(sorted(working_ports), 1):
            arduino_name = "Arduino 1 (Sensores)" if i == 1 else "Arduino 2 (Teclado)"
            print(f"  {port} → {arduino_name}")
    elif len(working_ports) == 1:
        print(f"\n⚠️  Apenas 1 Arduino funcionando: {working_ports[0]}")
        print("    Conecte o segundo Arduino")
    else:
        print("\n❌ Nenhum Arduino respondendo!")

def manual_test():
    """Modo interativo para testar porta específica"""
    print("\n" + "=" * 60)
    print("MODO MANUAL - TESTE DE PORTA ESPECÍFICA")
    print("=" * 60)
    
    port = input("\nDigite a porta (ex: /dev/ttyACM0): ").strip()
    
    if not port:
        print("❌ Porta inválida")
        return
    
    duration = input("Duração do teste em segundos (padrão: 10): ").strip()
    duration = int(duration) if duration.isdigit() else 10
    
    test_port(port, duration)

# ==================== MAIN ====================

def main():
    print("\n" + "=" * 60)
    print(" TESTE DE IDENTIFICAÇÃO DOS ARDUINOS")
    print("=" * 60)
    print("\nEste script ajuda a:")
    print("  1. Encontrar portas USB dos Arduinos")
    print("  2. Verificar se estão enviando dados")
    print("  3. Identificar qual é Arduino 1 e Arduino 2")
    
    while True:
        print("\n" + "-" * 60)
        print("OPÇÕES:")
        print("  1. Listar portas USB")
        print("  2. Testar todos Arduinos automaticamente")
        print("  3. Testar porta específica (manual)")
        print("  4. Sair")
        print("-" * 60)
        
        choice = input("\nEscolha: ").strip()
        
        if choice == '1':
            list_ports()
        
        elif choice == '2':
            test_all_arduinos()
        
        elif choice == '3':
            manual_test()
        
        elif choice == '4':
            print("\n👋 Até mais!")
            break
        
        else:
            print("❌ Opção inválida")

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n👋 Interrompido pelo usuário")