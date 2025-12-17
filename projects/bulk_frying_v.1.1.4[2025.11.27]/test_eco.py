import socket
import struct
import time
import sys
import serial
import json
import queue

# Mocking the Logger since the original is not available in this standalone script
class Logger:
    @staticmethod
    def info(msg):
        print(f"[INFO] {msg}")
    
    @staticmethod
    def error(msg):
        print(f"[ERROR] {msg}")

    @staticmethod
    def warn(msg):
        print(f"[WARN] {msg}")

# Assuming IndyCare_Fnb_data is in the python path. 
# If not, you might need to add it to the PYTHONPATH
# export PYTHONPATH=$PYTHONPATH:/path/to/your/project
try:
    from IndyCare_Fnb_data.mqtt_client import MQTTSession
    from IndyCare_Fnb_data import config as mqtt_config
except ImportError as e:
    print(f"[ERROR] Failed to import IndyCare_Fnb_data modules: {e}")
    print("[ERROR] Make sure the project directory is in your PYTHONPATH.")
    sys.exit(1)


class EcoSensor:
    """
    Handles reading data from an AQM-200(LG) environmental sensor via Modbus RTU
    (either over Serial or TCP socket) and sending it via MQTT.
    The scheduling of reading/sending is handled externally.
    """
    # --- Constants -- -
    SLAVE_ID = 1
    REG_ADDR_CO2 = 0x0050
    NUM_REGISTERS = 5

    # Modbus RTU/Serial settings
    BAUDRATE = 9600
    BYTESIZE = 8
    PARITY = serial.PARITY_NONE
    STOPBITS = 1
    SERIAL_TIMEOUT = 25

    # TCP/Socket settings
    SOCKET_TIMEOUT = 25

    def __init__(self, mqtt_session=None):
        """Initializes the sensor, optionally sharing an MQTT session."""
        self.mqtt_session = mqtt_session
        self._mqtt_config = None

    def connect_mqtt(self):
        """Initializes and connects the MQTT client session if one isn't provided."""
        if self.mqtt_session and self.mqtt_session.is_connected():
            Logger.info("MQTT session already connected.")
            return True
        try:
            self._mqtt_config = mqtt_config.load_config()
            Logger.info(f"[EcoSensor] Using MQTT Device ID: {self._mqtt_config.get(mqtt_config.CONFIG_KEY_MQTT_DEVICE_ID)}")

            hostname = self._mqtt_config[mqtt_config.CONFIG_KEY_MQTT_BROKER_HOSTNAME]
            port = self._mqtt_config[mqtt_config.CONFIG_KEY_MQTT_BROKER_PORT]
            username = f"{self._mqtt_config[mqtt_config.CONFIG_KEY_MQTT_DEVICE_ID]}:{self._mqtt_config[mqtt_config.CONFIG_KEY_MQTT_USERNAME]}"
            password = self._mqtt_config[mqtt_config.CONFIG_KEY_MQTT_PASSWORD]

            message_queue = queue.Queue()
            self.mqtt_session = MQTTSession(
                _msg_queue=message_queue,
                hostname=hostname,
                port=port,
                username=username,
                password=password
            )
            self.mqtt_session.open()

            Logger.info("Waiting for MQTT connection...")
            conn_time = time.time()
            while not self.mqtt_session.is_connected() and time.time() - conn_time < 10:
                time.sleep(0.1)

            if self.mqtt_session.is_connected():
                Logger.info("[SUCCESS] EcoSensor: Connected to MQTT server.")
                return True
            else:
                Logger.error("[ERROR] EcoSensor: Could not connect to MQTT server.")
                self.mqtt_session = None
                return False

        except Exception as e:
            Logger.error(f"[CRITICAL ERROR] EcoSensor: Failed to initialize MQTT: {e}")
            self.mqtt_session = None
            return False

    @staticmethod
    def _calculate_crc16(data):
        crc = 0xFFFF
        for byte in data:
            crc ^= byte
            for _ in range(8):
                if crc & 0x0001:
                    crc >>= 1
                    crc ^= 0xA001
                else:
                    crc >>= 1
        return crc

    def _create_modbus_rtu_request(self):
        request_pdu = struct.pack('>BBHH', self.SLAVE_ID, 0x03, self.REG_ADDR_CO2, self.NUM_REGISTERS)
        crc = self._calculate_crc16(request_pdu)
        return request_pdu + struct.pack('<H', crc)

    def _parse_modbus_rtu_response(self, response_bytes):
        expected_num_bytes = self.NUM_REGISTERS * 2
        if len(response_bytes) < 5:
            Logger.error(f"Error: Response length too short. Got {len(response_bytes)} bytes.")
            return None

        response_slave_id = response_bytes[0]
        if response_slave_id != self.SLAVE_ID:
            Logger.error(f"Error: Slave ID mismatch. Expected {self.SLAVE_ID}, got {response_slave_id}")
            return None

        received_data_for_crc = response_bytes[:-2]
        received_crc = struct.unpack('<H', response_bytes[-2:])[0]
        calculated_crc = self._calculate_crc16(received_data_for_crc)
        if received_crc != calculated_crc:
            Logger.error(f"Error: CRC mismatch. Received=0x{received_crc:04X}, Calculated=0x{calculated_crc:04X}")
            return None

        registers = []
        for i in range(3, 3 + expected_num_bytes, 2):
            registers.append(struct.unpack('>H', response_bytes[i:i+2])[0])

        sensor_data = {
            "co2": registers[0],
            "co": registers[1]
            # "tvoc": registers[2],
            # "temperature": registers[3] / 10.0,
            # "humidity": registers[4]
        }
        Logger.info(f"EcoSensor: Parsed sensor data: {sensor_data}")
        return sensor_data

    def read_data(self, comm_config):
        comm_type = comm_config.get("communication_type", "socket")
        modbus_request = self._create_modbus_rtu_request()
        response = None

        Logger.info(f"EcoSensor: Reading data via {comm_type.upper()}...")

        if comm_type == 'serial':
            try:
                with serial.Serial(
                    port=comm_config.get('serial_port'),
                    baudrate=self.BAUDRATE,
                    bytesize=self.BYTESIZE,
                    parity=self.PARITY,
                    stopbits=self.STOPBITS,
                    timeout=self.SERIAL_TIMEOUT
                ) as ser:
                    Logger.info(f"Writing Modbus request to serial: {modbus_request.hex()}")
                    ser.write(modbus_request)
                    response = ser.read(15)
                    Logger.info(f"Received serial response: {response.hex() if response else 'None'}")
            except serial.SerialException as e:
                Logger.error(f"EcoSensor Serial Error: {e}")
                return None

        elif comm_type == 'socket':
            try:
                ip = comm_config.get('ip')
                port = comm_config.get('port')
                Logger.info(f"Connecting to sensor at {ip}:{port}...")
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                    sock.settimeout(self.SOCKET_TIMEOUT)
                    sock.connect((ip, port))
                    Logger.info(f"Socket connected. Sending Modbus request: {modbus_request.hex()}")
                    sock.sendall(modbus_request)
                    response = sock.recv(1024)
                    Logger.info(f"Received socket response: {response.hex() if response else 'None'}")
            except (socket.timeout, ConnectionRefusedError, OSError) as e:
                Logger.error(f"EcoSensor Socket Error: {e}")
                return None

        if response:
            return self._parse_modbus_rtu_response(response)
        else:
            Logger.warn("EcoSensor: No response from sensor.")
            return None

    def send_data_mqtt(self, data):
        if not self.mqtt_session or not self.mqtt_session.is_connected():
            Logger.error("[ERROR] EcoSensor: Cannot send MQTT message, session is not available or connected.")
            return

        try:
            topic = self._mqtt_config.get('mqtt_topic_telemetry', 'v1/devices/me/telemetry')
            payload = data # Send data directly
            self.mqtt_session.publish(topic, payload)
            Logger.info(f"EcoSensor: Successfully sent data to MQTT topic '{topic}'.")
        except Exception as e:
            Logger.error(f"[ERROR] EcoSensor: Failed to send MQTT message: {e}")

    def close(self):
        if self.mqtt_session and self.mqtt_session.is_opened():
            self.mqtt_session.close()
            Logger.info("EcoSensor: MQTT session closed.")

if __name__ == "__main__":
    print("--- Running EcoSensor Test Script ---")
    
    # Load configuration
    config = None
    try:
        with open("configs/app_config.json", "r") as f:
            config = json.load(f)
        eco_sensor_config = config.get("eco_sensor")
        if not eco_sensor_config or not eco_sensor_config.get("enabled"):
            print("[ERROR] EcoSensor is not enabled in configs/app_config.json. Exiting.")
            sys.exit(1)
        print("Successfully loaded eco_sensor config:", eco_sensor_config)
    except FileNotFoundError:
        print("[ERROR] Configuration file 'configs/app_config.json' not found. Exiting.")
        sys.exit(1)
    except (json.JSONDecodeError, KeyError) as e:
        print(f"[ERROR] Failed to parse config file or find 'eco_sensor' key: {e}. Exiting.")
        sys.exit(1)

    # Initialize sensor
    eco_sensor = EcoSensor()
    
    # 1. Connect to MQTT
    print("\n--- Step 1: Connecting to MQTT ---")
    if not eco_sensor.connect_mqtt():
        print("[RESULT] MQTT Connection Failed. The script will still attempt to read sensor data, but will not be able to send it.")
    else:
        print("[RESULT] MQTT Connection Successful.")

    # 2. Read data from sensor
    print("\n--- Step 2: Reading Sensor Data ---")
    sensor_data = eco_sensor.read_data(eco_sensor_config)
    
    if sensor_data:
        print(f"[RESULT] Successfully read and parsed sensor data: {sensor_data}")
        
        # 3. Send data via MQTT
        print("\n--- Step 3: Sending Data via MQTT ---")
        eco_sensor.send_data_mqtt(sensor_data)
    else:
        print("[RESULT] Failed to read sensor data. See error messages above for details.")

    # 4. Clean up
    print("\n--- Step 4: Closing Connections ---")
    eco_sensor.close()
    
    print("\n--- Test Script Finished ---")
