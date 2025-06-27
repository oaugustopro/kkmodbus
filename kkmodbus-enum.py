#!/usr/bin/python3
# Author: Otávio Augusto Maciel Camargo
# Contact: contact@oaugusto.pro
# 10/10/2024
# @oaugustopro

import socket
import struct
import argparse
import threading
from concurrent.futures import ThreadPoolExecutor
import time
import sys

MODBUS_TCP_PORT = 502
# Ajustes para maior estabilidade e performance equilibrada
DEFAULT_SOCKET_TIMEOUT = 4 # Timeout para as tentativas com threading
RETRY_DELAY_THREADING = 0.3 # Atraso entre as tentativas na fase de threading
RETRY_DELAY_SEQUENTIAL = 0.1 # Atraso pequeno para as tentativas sequenciais

# Número de tentativas
MAX_RETRIES_THREADING = 3 # Tentativas na fase paralela
MAX_RETRIES_SEQUENTIAL = 2 # Tentativas adicionais na fase sequencial

def build_modbus_request(trans_id, unit_id, function_code, address, count=1):
    """Constrói um pacote de requisição Modbus TCP."""
    protocol_id = 0
    length = 6 # Comprimento padrão para o cabeçalho Modbus PDU
    request = struct.pack('>HHHBBH', trans_id, protocol_id, length, unit_id, function_code, address)
    if function_code in [1, 2, 3, 4]:  # Funções de leitura
        request += struct.pack('>H', count) # Adiciona o count para leituras
    return request

def parse_modbus_response(response):
    """Analisa um pacote de resposta Modbus TCP."""
    if len(response) < 9:
        return None  # Resposta inválida (muito curta)

    try:
        trans_id, protocol_id, length, unit_id, function_code = struct.unpack('>HHHBB', response[:8])
    except struct.error:
        return None # Cabeçalho malformado

    if function_code >= 0x80: # Resposta de exceção Modbus
        # Se for uma exceção, não há dados válidos para retorno
        return None
    
    if function_code in [1, 2, 3, 4]:  # Respostas de leitura
        if len(response) < 9: # Precisa de pelo menos cabeçalho MBAP + ID Unidade + Código Função + Byte Count
            return None
        byte_count = struct.unpack('>B', response[8:9])[0] # O nono byte é o byte count
        # Garante que temos bytes de dados suficientes conforme indicado pelo byte_count
        if len(response) >= 9 + byte_count:
            data = response[9:9 + byte_count]
            return data
    
    return None # Para códigos de função não suportados ou respostas malformadas

def read_data_single_attempt(ip, port, unit_id, function_code, protocol_address, logical_address, data_type, timeout):
    """
    Realiza uma única tentativa de leitura Modbus.
    Retorna a string formatada em caso de sucesso, ou None em caso de falha.
    """
    sock = None
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        sock.connect((ip, port))
        trans_id = threading.get_ident() % 65535 # Usa o ID da thread para o Transaction ID
        request = build_modbus_request(trans_id, unit_id, function_code, protocol_address)
        sock.sendall(request)
        response = sock.recv(1024) # Recebe um buffer de tamanho razoável
        
        data = parse_modbus_response(response)
        if data:
            if data_type in ['hr', 'ir']: # Holding Registers / Input Registers (16-bit)
                if len(data) >= 2: # Esperamos pelo menos 2 bytes para um registro
                    reg = struct.unpack('>H', data[:2])[0]
                    return f"Slave {unit_id} - {data_type.upper()}[{logical_address}]: {reg} (16-bit integer)"
            elif data_type in ['coil', 'di']: # Coils / Discrete Inputs (1-bit)
                if len(data) >= 1: # Esperamos pelo menos 1 byte para coils/di
                    bit = (data[0] >> 0) & 1 # Pega o bit menos significativo do primeiro byte
                    return f"Slave {unit_id} - {data_type.upper()}[{logical_address}]: {bit}"
    except (socket.timeout, ConnectionRefusedError, OSError, Exception):
        # Captura e silencia erros de rede/conexão ou outras exceções gerais
        pass
    finally:
        if sock:
            sock.close() # Garante que o socket seja fechado
    return None # Retorna None em caso de qualquer falha

def read_data_with_retries(ip, port, unit_id, function_code, protocol_address, logical_address, data_type, num_retries, retry_delay, timeout):
    """
    Tenta ler dados com um número específico de retries e delay entre as tentativas.
    """
    for attempt in range(num_retries):
        result = read_data_single_attempt(ip, port, unit_id, function_code, protocol_address, logical_address, data_type, timeout)
        if result:
            return result # Retorna o resultado assim que uma tentativa for bem-sucedida
        if attempt < num_retries - 1: # Se não for a última tentativa, aguarda
            time.sleep(retry_delay)
    return None # Retorna None se todas as tentativas falharem

def parse_address_range(arg_value):
    """Analisa e valida um argumento de intervalo de endereço."""
    try:
        if '-' in arg_value:
            start, end = map(int, arg_value.split('-'))
        else:
            start = end = int(arg_value)
        if start > end:
            raise ValueError
        return start, end
    except ValueError:
        raise argparse.ArgumentTypeError(f"Intervalo de endereço inválido '{arg_value}'. Esperado formato inicio-fim com inicio <= fim, ou um único número.")


def main():
    parser = argparse.ArgumentParser(description='Leitor Modbus TCP')
    parser.add_argument('--ip', type=str, default='172.21.2.250', help='Endereço IP do CLP')
    parser.add_argument('--port', type=int, default=MODBUS_TCP_PORT, help='Número da porta do CLP')
    parser.add_argument('--slaveids', type=str, default='1-5', help='IDs de escravos para consultar (ex: 1-5 ou 1,3,5)')
    parser.add_argument('--hr', type=str, help='Intervalo de endereços de Holding Registers (ex: --hr 40001-40010)')
    parser.add_argument('--coil', type=str, help='Intervalo de endereços de Coils (ex: --coil 1-10)')
    parser.add_argument('--ir', type=str, help='Intervalo de endereços de Input Registers (ex: --ir 30001-30010)')
    parser.add_argument('--di', type=str, help='Intervalo de endereços de Discrete Inputs (ex: --di 10001-10010)')
    args = parser.parse_args()

    # Processa os IDs dos escravos
    slave_ids = []
    if '-' in args.slaveids:
        start_id, end_id = map(int, args.slaveids.split('-'))
        slave_ids = list(range(start_id, end_id + 1))
    else:
        slave_ids = list(map(int, args.slaveids.split(',')))

    # Processa os tipos de dados e seus intervalos de endereço
    data_types_to_query = {}
    if args.hr:
        start, end = parse_address_range(args.hr)
        data_types_to_query['hr'] = (start, end)
    if args.coil:
        start, end = parse_address_range(args.coil)
        data_types_to_query['coil'] = (start, end)
    if args.ir:
        start, end = parse_address_range(args.ir)
        data_types_to_query['ir'] = (start, end)
    if args.di:
        start, end = parse_address_range(args.di)
        data_types_to_query['di'] = (start, end)

    # Define intervalos padrão se nenhum for especificado
    if not data_types_to_query:
        print("Nenhum tipo de dado específico fornecido. Usando intervalos padrão.")
        data_types_to_query = {
            'hr': (40001, 40010),
            'coil': (1, 10),
            'ir': (30001, 30010),
            'di': (10001, 10010)
        }

    # Estruturas para coletar resultados durante as fases
    all_successful_results = {} # Armazena resultados formatados (string)
    all_failed_results = {}     # Armazena detalhes das leituras que falharam totalmente
    failed_initial_pass_details = [] # Armazena detalhes das leituras que falharam na primeira fase (para re-tentativa)

    # Ordem arbitrária para impressão consistente dos tipos de dados
    data_type_order = {'coil': 0, 'di': 1, 'hr': 2, 'ir': 3} 

    # --- FASE 1: Leitura Paralela com Threading ---
    max_workers = 30 # Número razoável de workers para a fase inicial
    print(f"Iniciando fase 1 (paralela) para {args.ip}:{args.port} (Max. {max_workers} conexões concorrentes)...")

    tasks_to_submit = [] # Lista de tarefas a serem submetidas ao ThreadPool
    for unit_id in slave_ids:
        for data_type, (start_address, end_address) in data_types_to_query.items():
            function_code = None
            base_address = None

            # Define o código de função Modbus e o endereço base para cada tipo
            if data_type == 'hr':
                function_code = 3
                base_address = 40001
            elif data_type == 'ir':
                function_code = 4
                base_address = 30001
            elif data_type == 'coil':
                function_code = 1
                base_address = 1
            elif data_type == 'di':
                function_code = 2
                base_address = 10001
            else:
                continue # Pula tipos de dados desconhecidos

            for logical_address in range(start_address, end_address + 1):
                protocol_address = logical_address - base_address
                if protocol_address < 0:
                    continue # Ignora endereços que resultariam em um protocolo_address negativo
                
                # Armazena os detalhes da tarefa para submissão e ordenação futura
                tasks_to_submit.append({
                    'unit_id': unit_id,
                    'data_type_order': data_type_order[data_type],
                    'logical_address': logical_address,
                    'data_type': data_type,
                    'function_code': function_code,
                    'protocol_address': protocol_address
                })
    
    # Ordena as tarefas antes de submeter para manter a previsibilidade na ordem dos futures
    tasks_to_submit.sort(key=lambda x: (x['unit_id'], x['data_type_order'], x['logical_address']))

    futures_with_metadata = [] # Para guardar os futuros e seus detalhes para processamento posterior

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        for task in tasks_to_submit:
            future = executor.submit(
                read_data_with_retries,
                args.ip,
                args.port,
                task['unit_id'],
                task['function_code'],
                task['protocol_address'],
                task['logical_address'],
                task['data_type'],
                MAX_RETRIES_THREADING, # Número de retries para esta fase
                RETRY_DELAY_THREADING, # Delay para esta fase
                DEFAULT_SOCKET_TIMEOUT # Timeout para esta fase
            )
            futures_with_metadata.append((task, future))

    # Coleta os resultados da Fase 1 e identifica as leituras que falharam
    for task_details, future in futures_with_metadata:
        result_string = future.result()
        if result_string:
            if task_details['unit_id'] not in all_successful_results:
                all_successful_results[task_details['unit_id']] = []
            all_successful_results[task_details['unit_id']].append(result_string)
        else:
            # Se falhou na primeira fase, adiciona aos detalhes para a segunda fase
            failed_initial_pass_details.append(task_details)

    print(f"\nFase 1 concluída. {len(failed_initial_pass_details)} leituras falharam e serão re-tentadas em série.")
    
    # --- FASE 2: Re-tentativas Sequenciais para Leituras Falhas ---
    if failed_initial_pass_details:
        print(f"Iniciando fase 2 (sequencial) para {len(failed_initial_pass_details)} leituras falhas...")
        
        # Ordena novamente as falhas para garantir um processamento sequencial ordenado
        failed_initial_pass_details.sort(key=lambda x: (x['unit_id'], x['data_type_order'], x['logical_address']))

        for task in failed_initial_pass_details:
            # Tenta novamente em série
            result_string = read_data_with_retries(
                args.ip,
                args.port,
                task['unit_id'],
                task['function_code'],
                task['protocol_address'],
                task['logical_address'],
                task['data_type'],
                MAX_RETRIES_SEQUENTIAL, # Número de retries para esta fase
                RETRY_DELAY_SEQUENTIAL, # Delay para esta fase (pequeno)
                DEFAULT_SOCKET_TIMEOUT # Usa o mesmo timeout
            )
            if result_string:
                if task['unit_id'] not in all_successful_results:
                    all_successful_results[task['unit_id']] = []
                all_successful_results[task['unit_id']].append(result_string)
            else:
                # Se falhou mesmo na segunda fase, registra como falha final
                if task['unit_id'] not in all_failed_results:
                    all_failed_results[task['unit_id']] = []
                all_failed_results[task['unit_id']].append(f"{task['data_type'].upper()}[{task['logical_address']}]")

    # --- Impressão dos Resultados Finais ---
    print("\n--- Resultados de Leitura ---")
    
    # Prepara a lista de resultados bem-sucedidos para impressão ordenada
    final_results_for_print = []
    for unit_id, results in all_successful_results.items():
        for res_str in results:
            # Extrai os detalhes para re-ordenar tudo junto para uma impressão final coesa
            try:
                parts = res_str.split(' - ')[1].split(': ')[0] # Ex: "HR[40001]"
                data_type_str = parts.split('[')[0].lower() # Ex: "hr"
                logical_address = int(parts.split('[')[1][:-1]) # Ex: 40001
                final_results_for_print.append((unit_id, data_type_order[data_type_str], logical_address, res_str))
            except (IndexError, ValueError):
                # Caso a string formatada seja inesperada, apenas adicione-a ao final
                final_results_for_print.append((unit_id, 999, 999999, res_str)) # Coloca no final com alta prioridade

    final_results_for_print.sort() # Ordena todos os resultados de sucesso coletados

    current_unit_id = None
    for unit_id, _, _, result_string in final_results_for_print:
        if unit_id != current_unit_id:
            print(f"\n--- Resultados para Slave ID {unit_id} em {args.ip}:{args.port} ---")
            current_unit_id = unit_id
        print(result_string)

    # Imprime resumo das falhas (para stderr para separação clara)
    print("\n--- Resumo das Leituras Falhas ---", file=sys.stderr)
    if not any(all_failed_results.values()):
        print("Todas as leituras solicitadas foram concluídas com sucesso ou não retornaram dados válidos.", file=sys.stderr)
    else:
        for unit_id in sorted(all_failed_results.keys()):
            print(f"Para Slave ID {unit_id}:", file=sys.stderr)
            for failed_entry in all_failed_results[unit_id]:
                print(f"  - Falha ao ler {failed_entry} (Após múltiplas tentativas)", file=sys.stderr)

    print("\nConcluído.")

if __name__ == '__main__':
    main()
