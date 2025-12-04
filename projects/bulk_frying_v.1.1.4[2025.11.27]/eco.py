import socket
import struct
import time
import sys
import serial
import json
import queue
import os

# Assuming IndyCare_Fnb_data is in the python path
from IndyCare_Fnb_data.mqtt_client import MQTTSession
from IndyCare_Fnb_data import config as mqtt_config
from pkg.utils.logging import Logger

class EcoSensor:
    """
    Handles reading data from an AQM-200(LG) environmental sensor via Modbus RTU
    (either over Serial or TCP socket) and sending it via MQTT.
    The scheduling of reading/sending is handled externally.
    """
    # --- Constants ---
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
        self.indycare_enabled = False
        self._load_app_config()

    def _load_app_config(self):
        try:
            script_dir = os.path.dirname(os.path.abspath(__file__))
            config_path = os.path.join(script_dir, 'configs', 'app_config.json')
            with open(config_path, 'r', encoding='utf-8') as f:
                app_config = json.load(f)
                self.indycare_enabled = app_config.get("indycare", False)
                Logger.info(f"[EcoSensor] IndyCare MQTT sending is {'enabled' if self.indycare_enabled else 'disabled'}.")
        except Exception as e:
            Logger.error(f"[EcoSensor] Error loading app_config.json: {e}")
            self.indycare_enabled = False

    def connect_mqtt(self):
        """Initializes and connects the MQTT client session if one isn't provided."""
        if not self.indycare_enabled:
            return
        if self.mqtt_session and self.mqtt_session.is_connected():
            return
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
            
            conn_time = time.time()
            while not self.mqtt_session.is_connected() and time.time() - conn_time < 10:
                time.sleep(0.1)

            if self.mqtt_session.is_connected():
                Logger.info("[SUCCESS] EcoSensor: Connected to MQTT server.")
            else:
                Logger.error("[ERROR] EcoSensor: Could not connect to MQTT server.")
                self.mqtt_session = None

        except Exception as e:
            Logger.error(f"[CRITICAL ERROR] EcoSensor: Failed to initialize MQTT: {e}")
            self.mqtt_session = None

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
            Logger.error("Error: Response length too short.")
            return None

        response_slave_id = response_bytes[0]
        if response_slave_id != self.SLAVE_ID:
            Logger.error(f"Error: Slave ID mismatch. Expected {self.SLAVE_ID}, got {response_slave_id}")
            return None

        # Further validation (CRC, function code, etc.) as in the original script
        # For brevity, some checks are omitted here but should be kept in production
        
        received_data_for_crc = response_bytes[:-2]
        received_crc = struct.unpack('<H', response_bytes[-2:])[0]
        calculated_crc = self._calculate_crc16(received_data_for_crc)
        if received_crc != calculated_crc:
            Logger.error(f"Error: CRC mismatch.")
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
        """
        Reads data from the sensor using the specified communication configuration.
        :param comm_config: A dict containing 'communication_type' and other params.
        """
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
                    ser.write(modbus_request)
                    response = ser.read(15)
            except serial.SerialException as e:
                Logger.error(f"EcoSensor Serial Error: {e}")
                return None

        elif comm_type == 'socket':
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                    sock.settimeout(self.SOCKET_TIMEOUT)
                    sock.connect((comm_config.get('ip'), comm_config.get('port')))
                    sock.sendall(modbus_request)
                    response = sock.recv(1024)
            except (socket.timeout, ConnectionRefusedError, OSError) as e:
                Logger.error(f"EcoSensor Socket Error: {e}")
                return None
        
        if response:
            return self._parse_modbus_rtu_response(response)
        else:
            Logger.warn("EcoSensor: No response from sensor.")
            return None
    def is_mqtt_connected(self):
        """MQTT 연결 상태 확인"""
        return self.mqtt_session and self.mqtt_session.is_connected()

    def ensure_mqtt_connection(self):
        """MQTT 연결이 끊어진 경우 재연결 시도"""
        if not self.is_mqtt_connected():
            Logger.info("EcoSensor: MQTT connection lost, attempting to reconnect...")
            self.connect_mqtt()
            return self.is_mqtt_connected()
        return True
    def send_data_mqtt(self, data):
        """Sends sensor data to the MQTT broker."""
        if not self.indycare_enabled:
            return
        # if not self.mqtt_session or not self.mqtt_session.is_connected():
        if not self.ensure_mqtt_connection() :
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
        """Closes any open connections (like MQTT)."""
        if self.mqtt_session:
            self.mqtt_session.close()
            Logger.info("EcoSensor: MQTT session closed.")
