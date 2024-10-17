#!/usr/bin/python3
# Author: Otávio Augusto Maciel Camargo
# Contact: contact@oaugusto.pro
# Date: 10/10/2024
# @oaugustopro

import socket
import struct
import argparse
import threading
from concurrent.futures import ThreadPoolExecutor

def build_modbus_request(trans_id, unit_id, function_code, address, value=None, count=1):
    protocol_id = 0
    if value is not None:
        if function_code in [5, 6]:  # Write single coil/register
            length = 6
            request = struct.pack('>HHHBBH', trans_id, protocol_id, length, unit_id, function_code, address)
            request += struct.pack('>H', value)
        else:
            raise Exception('Unsupported function code for writing')
    elif function_code in [1, 2, 3, 4]:  # Read functions
        length = 6
        request = struct.pack('>HHHBBH', trans_id, protocol_id, length, unit_id, function_code, address)
        request += struct.pack('>H', count)
    else:
        raise Exception('Unsupported function code')
    return request

def parse_modbus_response(response):
    if len(response) < 8:
        return None  # Invalid response
    trans_id, protocol_id, length, unit_id, function_code = struct.unpack('>HHHBB', response[:8])
    if function_code >= 0x80:
        return None  # Exception response
    if function_code in [1, 2, 3, 4]:  # Read responses
        byte_count = response[8]
        data = response[9:9 + byte_count]
        return data
    elif function_code in [5, 6]:  # Write single coil/register response
        return response[8:12]
    else:
        return None

def read_or_write_data(ip, port, unit_id, function_code, protocol_address, logical_address, data_type, operation, value=None, results=None):
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(2)  # Set a timeout for socket operations
        sock.connect((ip, port))
        trans_id = threading.get_ident() % 65535  # Use thread ID for transaction ID

        if operation == 'read':
            request = build_modbus_request(trans_id, unit_id, function_code, protocol_address)
        elif operation == 'write':
            request = build_modbus_request(trans_id, unit_id, function_code, protocol_address, value=value)
        else:
            return

        sock.sendall(request)
        response = sock.recv(1024)
        data = parse_modbus_response(response)
        sock.close()

        if data:
            if operation == 'read':
                if data_type in ['hr', 'ir']:
                    if len(data) >= 2:
                        reg = struct.unpack('>H', data[:2])[0]
                        results.append(f"Slave {unit_id} - {data_type.upper()}[{logical_address}]: {reg}")
                elif data_type in ['coil', 'di']:
                    bit = (data[0] & 0x01)
                    results.append(f"Slave {unit_id} - {data_type.upper()}[{logical_address}]: {bit}")
            elif operation == 'write':
                results.append(f"Slave {unit_id} - Wrote to {data_type.upper()}[{logical_address}]")
        else:
            if operation == 'read':
                results.append(f"Slave {unit_id} - Failed to read {data_type.upper()}[{logical_address}]")
            elif operation == 'write':
                results.append(f"Slave {unit_id} - Failed to write to {data_type.upper()}[{logical_address}]")
    except Exception:
        pass  # Suppress any output on error

def parse_address_range(arg_value):
    try:
        addresses = []
        for part in arg_value.split(','):
            part = part.strip()
            if '-' in part:
                start, end = map(int, part.split('-'))
                if start > end:
                    raise ValueError
                addresses.extend(range(start, end + 1))
            else:
                addresses.append(int(part))
        return addresses
    except ValueError:
        raise argparse.ArgumentTypeError(f"Invalid address range '{arg_value}'.")

def main():
    parser = argparse.ArgumentParser(description='Modbus TCP Read/Write Utility')
    parser.add_argument('--ip', type=str, required=True, help='IP address of the PLC')
    parser.add_argument('--port', type=int, default=502, help='Port number of the PLC (default: 502)')
    parser.add_argument('--slaveids', type=str, default='1', help='Slave IDs to query (e.g., 1-5 or 1,3,5)')
    parser.add_argument('--read', action='store_true', help='Read operation')
    parser.add_argument('--write', action='store_true', help='Write operation')
    parser.add_argument('--hr', type=str, help='Holding Registers address(es) (e.g., --hr 40001-40010)')
    parser.add_argument('--coil', type=str, help='Coils address(es) (e.g., --coil 1-10)')
    parser.add_argument('--ir', type=str, help='Input Registers address(es) (e.g., --ir 30001-30010)')
    parser.add_argument('--di', type=str, help='Discrete Inputs address(es) (e.g., --di 10001-10010)')
    parser.add_argument('--value', type=str, help='Value(s) to write (comma-separated)')
    args = parser.parse_args()

    if not args.read and not args.write:
        parser.error('Must specify either --read or --write')

    if args.read and args.write:
        parser.error('Cannot specify both --read and --write')

    # Parse slave IDs
    slave_ids = []
    if '-' in args.slaveids:
        start_id, end_id = map(int, args.slaveids.split('-'))
        slave_ids = list(range(start_id, end_id + 1))
    else:
        slave_ids = list(map(int, args.slaveids.split(',')))

    # Determine data type and addresses
    data_types = {}
    if args.hr:
        data_types['hr'] = parse_address_range(args.hr)
    if args.coil:
        data_types['coil'] = parse_address_range(args.coil)
    if args.ir:
        data_types['ir'] = parse_address_range(args.ir)
    if args.di:
        data_types['di'] = parse_address_range(args.di)

    if not data_types:
        parser.error('Must specify at least one data type (--hr, --coil, --ir, --di)')

    # Validate and parse values if writing
    values = {}
    if args.write:
        if args.value is None:
            parser.error('--value is required when --write is specified')

        # Split and validate values
        value_list = args.value.split(',')
        total_addresses = sum(len(addresses) for addresses in data_types.values())
        if len(value_list) != total_addresses:
            parser.error('Number of values does not match number of addresses')

        # Map values to addresses
        value_index = 0
        for data_type, addresses in data_types.items():
            values[data_type] = []
            for _ in addresses:
                val = int(value_list[value_index])
                if data_type == 'coil' and val not in [0, 1]:
                    parser.error('Coil values must be 0 or 1')
                elif data_type in ['hr'] and not (0 <= val <= 65535):
                    parser.error('Register values must be between 0 and 65535')
                values[data_type].append(val)
                value_index += 1

    # Use ThreadPoolExecutor to limit the number of concurrent threads
    max_workers = 100  # Adjust as needed
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        for unit_id in slave_ids:
            print(f"\nProcessing Slave ID {unit_id} at {args.ip}:{args.port}")
            slave_results = []

            futures = []

            for data_type, addresses in data_types.items():
                if data_type == 'hr':
                    base_address = 40001
                    function_code_read = 3
                    function_code_write = 6
                elif data_type == 'ir':
                    base_address = 30001
                    function_code_read = 4
                    function_code_write = None  # Cannot write to input registers
                elif data_type == 'coil':
                    base_address = 1
                    function_code_read = 1
                    function_code_write = 5
                elif data_type == 'di':
                    base_address = 10001
                    function_code_read = 2
                    function_code_write = None  # Cannot write to discrete inputs
                else:
                    continue  # Invalid data type

                if args.write and function_code_write is None:
                    print(f"Cannot write to {data_type.upper()}")
                    continue

                for idx, logical_address in enumerate(addresses):
                    protocol_address = logical_address - base_address
                    if protocol_address < 0:
                        continue  # Skip invalid addresses

                    value = None
                    if args.write:
                        value = values[data_type][idx]
                        if data_type == 'coil':
                            value = 0xFF00 if value == 1 else 0x0000

                    future = executor.submit(
                        read_or_write_data,
                        args.ip,
                        args.port,
                        unit_id,
                        function_code_write if args.write else function_code_read,
                        protocol_address,
                        logical_address,
                        data_type,
                        'write' if args.write else 'read',
                        value=value,
                        results=slave_results
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
    main()
