from pymodbus.server.asynchronous import StartTcpServer
from pymodbus.datastore import ModbusSequentialDataBlock
from pymodbus.datastore import ModbusSlaveContext, ModbusServerContext
import logging

# Set up logging
logging.basicConfig()
log = logging.getLogger()
log.setLevel(logging.DEBUG)

# Enable pymodbus logging
pymodbus_log = logging.getLogger('pymodbus')
pymodbus_log.setLevel(logging.DEBUG)

# Initialize the initial values
initial_values = [0]*6000

# Set other specific addresses
# state_cs (client will read 32-bit value at 1000)
#   0: CS_STATE_BOOTING
#   1: CS_STATE_NOT_READY
#   2: CS_STATE_READY
#   3: CS_STATE_CHARGING
#   4: CS_STATE_ERROR
#   5: CS_STATE_INTERRUPTED
initial_values[1001:1002] = [0x0000, 0x0001]

# state_cable (client will read 32-bit value at 1004)
#   0: CABLE_STATE_NONE
#   1: CABLE_STATE_CS
#   2: CABLE_STATE_LOCKED
#   4: CABLE_STATE_CAR
#   6: CABLE_STATE_CS_CAR
initial_values[1005:1006] = [0x0000, 0x0006]

# phase_mA (client will read 32-bit value at 1008)
initial_values[1009:1010] = [0x0110, 0x1000]

# phase_mA (client will read 32-bit value at 1010)
initial_values[1011:1012] = [0x0110, 0x1000]

# phase_mA (client will read 32-bit value at 1012)
initial_values[1013:1014] = [0x0110, 0x1000]

# serial (client will read 32-bit value at 1014)
initial_values[1015:1016] = [0x0110, 0x1000]

# product (client will read 32-bit value at 1016)
initial_values[1017:1018] = [0x0110, 0x1000]

# firmware (client will read 32-bit value at 1018)
initial_values[1019:1020] = [0x0110, 0x1000]

# power_mW (client will read 32-bit value at 1020)
initial_values[1021:1022] = [0x0110, 0x1000]

# energy_Wh (client will read 32-bit value at 1036)
initial_values[1037:1038] = [0x0110, 0x1000]

# phase_mV (client will read 32-bit value at 1040)
initial_values[1041:1042] = [0x0110, 0x1000]

# phase_mV (client will read 32-bit value at 1042)
initial_values[1043:1044] = [0x0110, 0x1000]

# phase_mV (client will read 32-bit value at 1044)
initial_values[1045:1046] = [0x0110, 0x1000]

# current_max_mA (client will read 32-bit value at 1110)
initial_values[1111:1112] = [0x0110, 0x1000]

# rfid (client will read 32-bit value at 1500)
initial_values[1501:1502] = [0xA1B2, 0xC3D4]

# charged_Wh (client will read 32-bit value at 1502)
initial_values[1503:1504] = [0x0110, 0x1000]

# Initialize a datastore to support addresses up to 6000
store = ModbusSlaveContext(
    di=ModbusSequentialDataBlock(0, initial_values),  # Discrete inputs
    co=ModbusSequentialDataBlock(0, initial_values),  # Coils
    hr=ModbusSequentialDataBlock(0, initial_values),  # Holding registers
    ir=ModbusSequentialDataBlock(0, initial_values))  # Input registers

context = ModbusServerContext(slaves=store, single=True)

log.debug("Starting Modbus TCP server")

# Start the Modbus TCP server
StartTcpServer(context, address=("192.168.1.89", 8444))
