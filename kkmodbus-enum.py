#!/usr/bin/python3
# Author: Otávio Augusto Maciel Camargo
# Contact: contact@oaugusto.pro
# 10/10/2024
# @oaugustopro

import socket
import struct
import argparse
from concurrent.futures import ThreadPoolExecutor

MODBUS_TCP_PORT = 502  # Default Modbus TCP port

def build_modbus_request(trans_id, unit_id, function_code, address, count=1):
    protocol_id = 0
    length = 6
    request = struct.pack('>HHHBBH', trans_id, protocol_id, length, unit_id, function_code, address)
    if function_code in [1, 2, 3, 4]:  # Read functions
        request += struct.pack('>H', count)
    return request

def parse_modbus_response(response):
    if len(response) < 9:
        return None  # Invalid response
    trans_id, protocol_id, length, unit_id, function_code = struct.unpack('>HHHBB', response[:8])
    if function_code >= 0x80:
        return None  # Exception response
    if function_code in [1, 2, 3, 4]:  # Read responses
        byte_count = struct.unpack('>B', response[8:9])[0]
        data = response[9:9 + byte_count]
        return data
    else:
        return None

def read_data(ip, port, unit_id, function_code, protocol_address, logical_address, data_type, results):
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(2)  # Set a timeout for socket operations
        sock.connect((ip, port))
        trans_id = threading.get_ident() % 65535  # Use thread ID for transaction ID
        request = build_modbus_request(trans_id, unit_id, function_code, protocol_address)
        sock.sendall(request)
        response = sock.recv(1024)
        data = parse_modbus_response(response)
        sock.close()
        if data:
            if data_type in ['hr', 'ir']:
                if len(data) >= 2:
                    reg = struct.unpack('>H', data[:2])[0]
                    results.append(f"Slave {unit_id} - {data_type.upper()}[{logical_address}]: {reg} (16-bit integer)")
            elif data_type in ['coil', 'di']:
                bits = []
                for byte in data:
                    for i in range(8):
                        bits.append((byte >> i) & 1)
                if bits:
                    bit = bits[0]
                    results.append(f"Slave {unit_id} - {data_type.upper()}[{logical_address}]: {bit}")
    except Exception:
        pass  # Suppress any output on error

def parse_address_range(arg_value):
    try:
        if '-' in arg_value:
            start, end = map(int, arg_value.split('-'))
        else:
            start = end = int(arg_value)
        if start > end:
            raise ValueError
        return start, end
    except ValueError:
        raise argparse.ArgumentTypeError(f"Invalid address range '{arg_value}'. Expected format start-end with start <= end, or a single number.")

def main():
    parser = argparse.ArgumentParser(description='Modbus TCP Reader')
    parser.add_argument('--ip', type=str, default='172.21.2.250', help='IP address of the PLC')
    parser.add_argument('--port', type=int, default=502, help='Port number of the PLC')
    parser.add_argument('--slaveids', type=str, default='1-5', help='Slave IDs to query (e.g., 1-5 or 1,3,5)')
    parser.add_argument('--hr', type=str, help='Holding Registers address range (e.g., --hr 40001-40010)')
    parser.add_argument('--coil', type=str, help='Coils address range (e.g., --coil 1-10)')
    parser.add_argument('--ir', type=str, help='Input Registers address range (e.g., --ir 30001-30010)')
    parser.add_argument('--di', type=str, help='Discrete Inputs address range (e.g., --di 10001-10010)')
    args = parser.parse_args()

    # Parse slave IDs
    slave_ids = []
    if '-' in args.slaveids:
        start_id, end_id = map(int, args.slaveids.split('-'))
        slave_ids = list(range(start_id, end_id + 1))
    else:
        slave_ids = list(map(int, args.slaveids.split(',')))

    data_types = {}

    # Parse address ranges for each data type
    if args.hr:
        start, end = parse_address_range(args.hr)
        data_types['hr'] = (start, end)
    if args.coil:
        start, end = parse_address_range(args.coil)
        data_types['coil'] = (start, end)
    if args.ir:
        start, end = parse_address_range(args.ir)
        data_types['ir'] = (start, end)
    if args.di:
        start, end = parse_address_range(args.di)
        data_types['di'] = (start, end)

    # If no data types specified, default to reading addresses 1-10 for all types
    if not data_types:
        data_types = {
            'hr': (40001, 40010),
            'coil': (1, 10),
            'ir': (30001, 30010),
            'di': (10001, 10010)
        }

    # Use ThreadPoolExecutor to limit the number of concurrent threads
    max_workers = 100  # Adjust as needed
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        for unit_id in slave_ids:
            print(f"\nConnecting to Slave ID {unit_id} at {args.ip}:{args.port}")
            slave_results = []

            futures = []

            for data_type, (start_address, end_address) in data_types.items():
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
                    continue  # Invalid data type

                # Prepare list of addresses
                for logical_address in range(start_address, end_address + 1):
                    protocol_address = logical_address - base_address
                    if protocol_address < 0:
                        continue  # Skip invalid addresses

                    # Submit read task to the executor
                    future = executor.submit(
                        read_data,
                        args.ip,
                        args.port,
                        unit_id,
                        function_code,
                        protocol_address,
                        logical_address,
                        data_type,
                        slave_results
                    )
                    futures.append(future)

            # Wait for all futures to complete for this slave
            for future in futures:
                future.result()  # Ensure all tasks have completed

            # Print results for this slave
            for result in slave_results:
                print(result)

    print("\nDone.")

if __name__ == '__main__':
    import threading
    main()
