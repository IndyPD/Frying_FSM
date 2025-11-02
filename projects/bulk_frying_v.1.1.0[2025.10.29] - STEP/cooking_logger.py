
import os
import csv
import threading
from datetime import datetime
import json
import time
import queue

# Assuming IndyCare_Fnb_data is in the python path
# You might need to adjust the path if it's not found
import sys
# Add the parent directory to the python path to find IndyCare_Fnb_data
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from IndyCare_Fnb_data.mqtt_client import MQTTSession
from IndyCare_Fnb_data import config as mqtt_config
from pkg.utils.logging import Logger

Logger.info("DEBUG: cooking_logger.py module is being loaded.")

class CookingLogger:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            with cls._lock:
                if not cls._instance:
                    cls._instance = super(CookingLogger, cls).__new__(cls)
        return cls._instance

    def __init__(self, filename="cooking_log.csv"):
        if not hasattr(self, 'initialized'):
            self.script_dir = os.path.dirname(os.path.abspath(__file__))
            self.filename = os.path.join(self.script_dir, filename)
            
            self.file_exists = os.path.isfile(self.filename)
            self.initialized = True
            self._write_header()

            # Load app config
            self.indycare_enabled = False
            self._load_app_config()

            # Load recipes
            self.recipes = {}
            self._load_recipes()

            # MQTT Initialization
            self.mqtt_session = None
            if self.indycare_enabled:
                self._init_mqtt()

    def _load_app_config(self):
        try:
            config_path = os.path.join(self.script_dir, 'configs', 'app_config.json')
            with open(config_path, 'r', encoding='utf-8') as f:
                app_config = json.load(f)
                self.indycare_enabled = app_config.get("indycare", False)
                Logger.info(f"IndyCare MQTT logging is {'enabled' if self.indycare_enabled else 'disabled'}.")
        except Exception as e:
            Logger.error(f"Error loading app_config.json: {e}")
            self.indycare_enabled = False

    def _load_recipes(self):
        try:
            recipe_path = os.path.join(self.script_dir, 'configs', 'frying_recipe.json')
            with open(recipe_path, 'r', encoding='utf-8') as f:
                self.recipes = json.load(f)
        except Exception as e:
            Logger.error(f"Error loading recipe file: {e}")

    def _init_mqtt(self):
        Logger.debug("cooking_logger.py: _init_mqtt() called.")
        try:
            self._mqtt_config = mqtt_config.load_config()
            Logger.info(f"[CookingLogger] Using MQTT Device ID: {self._mqtt_config.get(mqtt_config.CONFIG_KEY_MQTT_DEVICE_ID)}")
            
            hostname = self._mqtt_config[mqtt_config.CONFIG_KEY_MQTT_BROKER_HOSTNAME]
            port = self._mqtt_config[mqtt_config.CONFIG_KEY_MQTT_BROKER_PORT]
            username = f"{self._mqtt_config[mqtt_config.CONFIG_KEY_MQTT_DEVICE_ID]}:{self._mqtt_config[mqtt_config.CONFIG_KEY_MQTT_USERNAME]}"
            password = self._mqtt_config[mqtt_config.CONFIG_KEY_MQTT_PASSWORD]

            Logger.debug(f"cooking_logger.py: MQTT session params: hostname={hostname}, port={port}, username={username}")
            message_queue = queue.Queue()
            self.mqtt_session = MQTTSession(
                _msg_queue=message_queue, 
                hostname=hostname,
                port=port,
                username=username,
                password=password
            )
            Logger.debug("cooking_logger.py: MQTTSession instance created.")
            Logger.debug("cooking_logger.py: Calling mqtt_session.open()...")
            self.mqtt_session.open()
            Logger.debug("cooking_logger.py: mqtt_session.open() called. Checking connection status...")
            
            conn_time = time.time()
            while not self.mqtt_session.is_connected() and time.time() - conn_time < 10:
                Logger.debug(f"cooking_logger.py: Waiting for MQTT connection... (elapsed: {time.time() - conn_time:.2f}s)")
                time.sleep(0.1)

            if self.mqtt_session.is_connected():
                Logger.info("cooking_logger.py: CONNECT MQTT server success...")
            else:
                Logger.error("cooking_logger.py: CANNOT connect to MQTT server after 10s timeout.")
                self.mqtt_session = None

        except Exception as e:
            Logger.error(f"cooking_logger.py: Failed to initialize MQTT: {e}")
            self.mqtt_session = None

    def _write_header(self):
        with self._lock:
            if not self.file_exists:
                with open(self.filename, mode='w', newline='', encoding='utf-8') as csvfile:
                    writer = csv.writer(csvfile)
                    writer.writerow(['basket_name', 'recipe_index', 'start_time', 'end_time', 'process_type'])

    # def log(self, basket_name, recipe_index, start_time, end_time, process_type):
    #     Logger.debug(f"cooking_logger.py: log() called for basket {basket_name}, recipe {recipe_index}.")
    #     # 1. Log to CSV
    #     with self._lock:
    #         try:
    #             with open(self.filename, mode='a', newline='', encoding='utf-8') as csvfile:
    #                 writer = csv.writer(csvfile)
    #                 writer.writerow([
    #                     basket_name,
    #                     recipe_index,
    #                     start_time.strftime('%Y-%m-%d %H:%M:%S'),
    #                     end_time.strftime('%Y-%m-%d %H:%M:%S'),
    #                     process_type
    #                 ])
    #         except Exception as e:
    #             Logger.error(f"Error writing to CSV: {e}")

    #     # 2. Prepare and Send log via MQTT
    #     try:
    #         cooking_tact_time = (end_time - start_time).total_seconds()
            
    #         recipe_key = f"recipe{recipe_index}"
    #         recipe_info = self.recipes.get(recipe_key, {})
    #         # recipe_name = recipe_info.get("recipe_name")

    #         # If recipe_name is missing or empty, use the key (e.g., "recipe1")
    #         if not recipe_name:
    #             recipe_name = recipe_key

    #         mqtt_data = {
    #             "cookingTactTime": cooking_tact_time,
    #             "recipeName": recipe_name
    #         }
    #         Logger.debug(f"cooking_logger.py: Prepared MQTT data for cooking log: {mqtt_data}")
    #         self.send_mqtt_log(mqtt_data)
    #     except Exception as e:
    #         Logger.error(f"Error preparing MQTT data: {e}")
    def log(self, basket_name, recipe_index, start_time, end_time, process_type):
        Logger.debug(f"cooking_logger.py: log() called for basket {basket_name}, recipe {recipe_index}.")
        
        # 1. Log to CSV
        with self._lock:
            try:
                recipe_name = self._get_recipe_name_from_file(recipe_index)
                with open(self.filename, mode='a', newline='', encoding='utf-8') as csvfile:
                    writer = csv.writer(csvfile)
                    writer.writerow([
                        basket_name,
                        recipe_name,
                        start_time.strftime('%Y-%m-%d %H:%M:%S'),
                        end_time.strftime('%Y-%m-%d %H:%M:%S'),
                        process_type
                    ])
            except Exception as e:
                Logger.error(f"Error writing to CSV: {e}")

        # 2. Prepare and Send log via MQTT
        try:
            cooking_tact_time = (end_time - start_time).total_seconds()
            
            # 실시간으로 frying_recipe.json에서 recipe_name 가져오기
            recipe_name = self._get_recipe_name_from_file(recipe_index)

            mqtt_data = {
                "cookingTactTime": cooking_tact_time,
                "recipeName": recipe_name
            }
            Logger.debug(f"cooking_logger.py: Prepared MQTT data for cooking log: {mqtt_data}")
            Logger.info(f"cooking_logger.py: Sending recipe_name '{recipe_name}' from frying_recipe.json for recipe{recipe_index}")
            self.send_mqtt_log(mqtt_data)
        except Exception as e:
            Logger.error(f"Error preparing MQTT data: {e}")

    def _get_recipe_name_from_file(self, recipe_index):
        """실시간으로 frying_recipe.json에서 recipe_name을 읽어옴"""
        try:
            recipe_path = os.path.join(self.script_dir, 'configs', 'frying_recipe.json')
            with open(recipe_path, 'r', encoding='utf-8') as f:
                recipes = json.load(f)
            
            recipe_key = f"recipe{recipe_index}"
            recipe_info = recipes.get(recipe_key, {})
            recipe_name = recipe_info.get("recipe_name", "")
            
            # If recipe_name is missing or empty, use the key (e.g., "recipe1")
            if not recipe_name:
                recipe_name = recipe_key
                
            Logger.debug(f"cooking_logger.py: Read recipe_name '{recipe_name}' for {recipe_key} from file")
            return recipe_name
            
        except Exception as e:
            Logger.error(f"Error reading recipe name from file for recipe{recipe_index}: {e}")
            return f"recipe{recipe_index}"  # fallback
        
    def send_recipe_list_mqtt(self, recipe_list):
        Logger.debug(f"cooking_logger.py: send_recipe_list_mqtt() called with data: {recipe_list}")
        if not recipe_list:
            Logger.debug("cooking_logger.py: Recipe list is empty, nothing to send.")
            return

        mqtt_payload = {"recipeList": recipe_list}
        self.send_mqtt_log(mqtt_payload)

    def send_mqtt_log(self, data):
        if not self.indycare_enabled:
            return
        Logger.debug(f"cooking_logger.py: send_mqtt_log() called with data: {data}")
        if self.mqtt_session and self.mqtt_session.is_connected():
            try:
                topic = self._mqtt_config.get('mqtt_topic_telemetry', 'v1/devices/me/telemetry')
                # payload = json.dumps(data)
                Logger.debug(f"cooking_logger.py: Publishing to topic '{topic}' with payload: {data}")
                self.mqtt_session.publish(topic, data)
                Logger.info(f"cooking_logger.py: Successfully sent log to MQTT.")
            except Exception as e:
                Logger.error(f"cooking_logger.py: Failed to send MQTT message: {e}")
        else:
            if not self.mqtt_session:
                Logger.error("cooking_logger.py: Cannot send MQTT message, session is None. Attempting to re-initialize MQTT session.")
            elif not self.mqtt_session.is_connected():
                Logger.error("cooking_logger.py: Cannot send MQTT message, session is not connected. Attempting to re-initialize MQTT session.")
            
            self._init_mqtt() # Attempt to re-initialize the MQTT session
            if self.mqtt_session and self.mqtt_session.is_connected():
                Logger.debug("cooking_logger.py: Re-initialization successful, retrying send.")
                self.send_mqtt_log(data) # Retry sending the message
            else:
                Logger.error("cooking_logger.py: Re-initialization failed. Message not sent.")

# Singleton instance
cooking_logger = CookingLogger()
