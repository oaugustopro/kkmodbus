![kkmodbusbanner](banner.png)

# Modbus TCP Utilities - No External Libraries Required

This repository contains two Python scripts that allow for Modbus TCP communication. These scripts are designed to function **without any external libraries**, making them lightweight and easy to run on any system with Python installed. The focus of these scripts is to provide an easy-to-use interface for reading and writing Modbus registers, as well as enumerating Modbus devices.

## Features

- **No External Dependencies**: These scripts do not rely on any external libraries or packages. All functionality is implemented using only Python's standard libraries, ensuring compatibility and ease of use.
- **Flexible Modbus TCP Communication**: Both scripts support Modbus TCP communication, allowing you to interact with PLCs (Programmable Logic Controllers) and other Modbus-enabled devices.
- **Threaded Execution**: The scripts use Python's `ThreadPoolExecutor` to efficiently handle multiple Modbus requests in parallel, making them suitable for querying multiple registers or devices simultaneously.
- **Customizable via Command Line Arguments**: Each script provides a range of command-line arguments for specifying Modbus registers, IP addresses, ports, and more.

---

# Script 1: `kkmodbus-enum.py`

This script is used to enumerate Modbus TCP devices, specifically for reading Modbus registers like coils, input registers, holding registers, and discrete inputs.

### Usage

```bash
python3 kkmodbus-enum.py --ip <PLC_IP> --port <PORT> --slaveids <SLAVE_IDS> [--hr <HOLDING_REGISTER_RANGE>] [--coil <COIL_RANGE>] [--ir <INPUT_REGISTER_RANGE>] [--di <DISCRETE_INPUT_RANGE>]
```

## Command-line Arguments
```
    --ip: The IP address of the Modbus device (e.g., PLC).
    --port: The port of the Modbus TCP service (default is 502).
    --slaveids: A range or list of Modbus slave IDs to query (e.g., 1-5 or 1,3,5).
    --hr: Holding register address range to query (e.g., 40001-40010).
    --coil: Coil address range to query (e.g., 1-10).
    --ir: Input register address range to query (e.g., 30001-30010).
    --di: Discrete input address range to query (e.g., 10001-10010).
```
## What It Does

    - Enumerates and reads data from Modbus devices based on the provided register types (holding registers, coils, input registers, discrete inputs).
    - Uses threading to perform multiple queries simultaneously.

## Key Functions

    - build_modbus_request: Constructs the Modbus request payload.
    - parse_modbus_response: Parses the response from the Modbus device.
    - read_data: Handles the reading of data from the Modbus device.

---

# Script 2: kkmodbus-readwrite.py

This script allows for reading from and writing to Modbus registers. It supports both reading operations (coils, input registers, holding registers, discrete inputs) and writing operations (coils, holding registers).
## Usage

`python3 kkmodbus-readwrite.py --ip <PLC_IP> --port <PORT> --slaveids <SLAVE_IDS> --read|--write [--hr <HOLDING_REGISTER_RANGE>] [--coil <COIL_RANGE>] [--ir <INPUT_REGISTER_RANGE>] [--di <DISCRETE_INPUT_RANGE>] [--value <VALUES>]`

### Example (Reading)

`python3 kkmodbus-readwrite.py --ip 192.168.1.10 --port 502 --slaveids 1 --read --hr 40001-40005`

### Example (Writing)



`python3 kkmodbus-readwrite.py --ip 192.168.1.10 --port 502 --slaveids 1 --write --hr 40001-40002 --value 1234,5678`

## Command-line Arguments
```
    --ip: The IP address of the Modbus device (e.g., PLC).
    --port: The port of the Modbus TCP service (default is 502).
    --slaveids: A range or list of Modbus slave IDs to query (e.g., 1-5 or 1,3,5).
    --read: Specifies that this is a read operation.
    --write: Specifies that this is a write operation.
    --hr: Holding register address range to query (e.g., 40001-40010).
    --coil: Coil address range to query (e.g., 1-10).
    --ir: Input register address range to query (e.g., 30001-30010).
    --di: Discrete input address range to query (e.g., 10001-10010).
    --value: Comma-separated list of values to write (required if --write is specified).
```
## What It Does

    - Reads and/or writes data to/from Modbus devices.
    - Validates input ranges and values to ensure proper operation.
    - Utilizes threading to handle multiple read or write operations simultaneously.

## Key Functions

    - build_modbus_request: Constructs the Modbus request payload for both read and write operations.
    - parse_modbus_response: Parses the response from the Modbus device.
    - read_or_write_data: Handles both reading and writing data to/from the Modbus device.

## Why Choose These Scripts?

    - No External Libraries: These scripts do not require any external dependencies, making them simple and fast to run on any machine with Python 3 installed.
    - Modbus TCP Focused: Designed specifically for Modbus TCP, these scripts allow you to interact with PLCs and SCADA systems with minimal setup.
    - Versatile: The scripts support both reading and writing operations, with a focus on flexibility and speed through the use of threading.
    - Cross-Platform: Since they use only standard Python libraries, these scripts can be run on any platform that supports Python 3, including Linux, Windows, and macOS.

## Getting Started
### Requirements

    - Python 3.x installed on your machine.
    - Access to a Modbus TCP-enabled device (e.g., PLC or SCADA system).

### Running the Scripts

To run these scripts, simply download or clone this repository and execute the scripts using Python 3. No additional libraries or packages are needed!
```
git clone <repository_url>
cd <repository_directory>
```
## Example usage:
python3 kkmodbus-enum.py --ip 192.168.1.10 --port 502 --slaveids 1-5

## Contributing

Feel free to open issues or submit pull requests to improve these scripts. If you have any suggestions for new features or find any bugs, we'd love to hear from you!
## License

This project is licensed under the MIT License - see the LICENSE file for details.
