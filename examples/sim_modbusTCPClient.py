from pymodbus.client.sync import ModbusTcpClient
import logging

# Set up logging
logging.basicConfig()
log = logging.getLogger()
log.setLevel(logging.DEBUG)

# Enable pymodbus logging
pymodbus_log = logging.getLogger('pymodbus')
pymodbus_log.setLevel(logging.DEBUG)

# Create a Modbus TCP client
client = ModbusTcpClient('192.168.1.89', port=8444)

# Connect to the server
connection = client.connect()
if connection:
    log.debug("Connected to Modbus server")
else:
    log.error("Failed to connect to Modbus server")

# Define the addresses to read
addresses = [1000, 1004, 1008, 1014, 1012, 1016, 1018, 1020, 1036, 1040, 1042, 1044, 1010, 1110, 1500, 1502]

# Read from each address
for address in addresses:
    response = client.read_holding_registers(address, 1)
    if response.isError():
        log.error("Failed to read register at address %s: %s", address, response)
    else:
        log.debug("Read register at address %s: %s", address, response.registers[0])

# Close the connection
client.close()