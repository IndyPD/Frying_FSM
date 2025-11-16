from os import path as op
import os
import yaml

INDY_CARE_CONFIG_FILE = op.join(op.abspath(op.dirname(__file__)), "config.yml")

CONFIG_KEY_MQTT_DEVICE_ID = "mqtt_device_id"
CONFIG_KEY_MQTT_BROKER_HOSTNAME = "mqtt_broker_hostname"
CONFIG_KEY_MQTT_BROKER_PORT = "mqtt_broker_port"
CONFIG_KEY_MQTT_USERNAME = "mqtt_username"
CONFIG_KEY_MQTT_PASSWORD = "mqtt_password"
CONFIG_KEY_MQTT_TOPIC_TELEMETRY = "mqtt_topic_telemetry"
CONFIG_KEY_MQTT_TOPIC_ATTRIBUTES = "mqtt_topic_attrubutes"
CONFIG_KEY_MQTT_TRANSMIT_PERIOD = "mqtt_transmit_period"
CONFIG_KEY_AWS_HOSTNAME = "aws_hostname"
CONFIG_KEY_ROBOT_SN = "robot_sn"
CONFIG_KEY_ROBOT_DOF = "robot_dof"
CONFIG_KEY_INDYCARE_VERSION = "indycare_version"
CONFIG_KEY_INDYCARE_TACTTIME_ADDR = "tact_time_address"

RTSP = "rtsp"
RTSP_URL = "rtsp_url"

# STREAMER_KEY_COMPRESS_SIZE = "compress_size"
# STREAMER_KEY_FRAME_WIDTH = "frame_width"
# STREAMER_KEY_FRAME_HEIGHT = "frame_height"
# STREAMER_KEY_RECORD_TIME = "record_time"
# STREAMER_KEY_VIDEO_FPS = "video_fps"
# STREAMER_KEY_NUMBERS_OF_VIDEO = "numbers_of_video"
# STREAMER_KEY_RETENTION_PERIOD = "retention_period"
# STREAMER_KEY_LIMIT_CAPACITY = "limit_capacity"

NGROK_REGION = "ngrok_region"

MANUAL_ERROR_ADDR = "manual_error_addr"


def load_config() -> dict:
    try:
        with open(INDY_CARE_CONFIG_FILE, "r") as f:
            data = yaml.load(f, Loader=yaml.FullLoader)
            if RTSP in data and data[RTSP]:
                data[RTSP] = f"{data[RTSP_URL]}"
            else:
                pass
    except:
        print("cannot load yaml config")
        data = {
            CONFIG_KEY_MQTT_DEVICE_ID: "indyHomyeongFrying",
            CONFIG_KEY_MQTT_BROKER_HOSTNAME: "device.thingplus.net",
            CONFIG_KEY_MQTT_BROKER_PORT: 1883,
            CONFIG_KEY_MQTT_USERNAME: "neuromeka",
            CONFIG_KEY_MQTT_PASSWORD: "dali3254",
            CONFIG_KEY_MQTT_TOPIC_TELEMETRY: "v1/devices/me/telemetry",
            CONFIG_KEY_MQTT_TOPIC_ATTRIBUTES: "v1/devices/me/attributes",
            CONFIG_KEY_MQTT_TRANSMIT_PERIOD: 60,
            CONFIG_KEY_AWS_HOSTNAME: "https://neuromeka.thingplus.net/",
            CONFIG_KEY_ROBOT_SN: "DB51I7E0C001",
            CONFIG_KEY_ROBOT_DOF: 6,
            CONFIG_KEY_INDYCARE_VERSION: "unknown",
            RTSP: 0,
            NGROK_REGION: "ap",
            MANUAL_ERROR_ADDR: 0
        }
        # save_config(data)
    return data


def save_config(data, no_retry=False):
    try:
        with open(INDY_CARE_CONFIG_FILE, "w") as f:
            yaml.dump(data, f)
    except Exception as err:
        print(err)
        if no_retry:
            return
        os.remove(INDY_CARE_CONFIG_FILE)
        save_config(data, True)
