import time
from typing import List, Dict
import requests
import config
from context import Context
import queue

from mqtt_client import MQTTSession  # 실제로 사용할 클래스 임포트

TIMER_WAIT_FOR_SERVER = 10  # (second) not smaller than 7s

class MQTT_TEST:
    IDLE = None

    def __init__(self) -> None:
        super().__init__()
        self.context: Context or None = None
        self._config = config.load_config()
        self._msg_queue_MQTT = queue.Queue()  # threading
        # self.MQTT_session: MQTTSession = None  # 잘못된 서브스크립트
        self.MQTT_session = None  # 서브스크립트 제거

    def __connect_to_broker_process(self):
        """MQTT 브로커 재연결 처리"""
        print("🔄 MQTT 재연결 시도 중...")
        try:
            if self.MQTT_session:
                self.MQTT_session.close()  # 기존 연결 정리
            
            # 새로운 세션 생성
            self.MQTT_session = MQTTSession(
                self._msg_queue_MQTT,
                hostname=self._config[config.CONFIG_KEY_MQTT_BROKER_HOSTNAME],
                port=self._config[config.CONFIG_KEY_MQTT_BROKER_PORT],
                username=f"{self._config[config.CONFIG_KEY_MQTT_DEVICE_ID]}:{self._config[config.CONFIG_KEY_MQTT_USERNAME]}",
                password=self._config[config.CONFIG_KEY_MQTT_PASSWORD]
            )
            
            # 연결 시도
            self.MQTT_session.open()
            
            # 연결 대기
            conn_time = time.time()
            while time.time() - conn_time < TIMER_WAIT_FOR_SERVER:
                if self.MQTT_session.is_connected():
                    print("✅ MQTT 재연결 성공!")
                    return True
                time.sleep(0.1)
            
            print("❌ MQTT 재연결 실패")
            return False
            
        except Exception as e:
            print(f"❌ MQTT 재연결 중 오류: {e}")
            return False
    
    def on_create(self, context: Context) -> None:
        self.context = context

        if self.context is None:
            raise ValueError("Context cannot be None")

        logger = self.context.logger()
        if logger is None:
            raise ValueError("Logger cannot be None")

        print(f" - OnCreate")

        # self._config = config.load_config()
        self.MQTT_session = MQTTSession(  # 실제로 사용할 클래스 인스턴스화
            self._msg_queue_MQTT,
            hostname=self._config[config.CONFIG_KEY_MQTT_BROKER_HOSTNAME],
            port=self._config[config.CONFIG_KEY_MQTT_BROKER_PORT],
            # username=self._config[config.CONFIG_KEY_MQTT_USERNAME],
            username=f"{self._config[config.CONFIG_KEY_MQTT_DEVICE_ID]}:{self._config[config.CONFIG_KEY_MQTT_USERNAME]}",
            password=self._config[config.CONFIG_KEY_MQTT_PASSWORD]
        )
        print(config.CONFIG_KEY_MQTT_BROKER_HOSTNAME)
        print("Trying to connect to mqtt broker...")
        try:
            while not self.MQTT_session.is_connected():
                self.MQTT_session.open()
                conn_time = time.time()
                while time.time() - conn_time < TIMER_WAIT_FOR_SERVER:
                    if self.MQTT_session.is_connected():
                        break
                    time.sleep(0.1)
                if not self.MQTT_session.is_connected():
                    print("CANNOT connect to server, try again later...")
                    time.sleep(5)
            print("CONNECT MQTT server success...")
            # 20241113 수정, 구독은 밑 실행단계에서 진행해도 될 거같음 .
            # self.MQTT_session.request_subscribe(self._config['mqtt_topic_telemetry'])
            # print("Successfully connected to Broker.")
        except Exception as e:
            print("Failed to connect to Broker. Exception: %s", str(e))
            # self.context.acquire_logger().exception("[Error Log]")
            # self.context.release_logger()
        
        print("OnCreate Done.")

    def send_msg_to_MQTT(self, context: Context, data=None):
        self.context = context

        if self.context is None:
            raise ValueError("Context cannot be None")

        logger = self.context.logger()
        if logger is None:
            raise ValueError("Logger cannot be None")

        print(f" Sending MQTT Message")

        try:
            if self.MQTT_session.is_connected():
                self.MQTT_session.publish(
                    topic=self._config['mqtt_topic_telemetry'],
                    data=data
                )
                print("DONE send data to server...") 
                print("data:",data)
            else:
                print("SERVER is not connected, try to reconnect...")
                self.__connect_to_broker_process()
        except Exception as e:
            print("CANNOT send data to server. Exception: %s", str(e))


#임시 데이터 작성 
sensor_data = {
    "co2": 999,
    "co": 9999
}


recipe_data = {
  "recipeName" : "HotCoffee",
  "cookingState" : 2
}

coffeeBeans_data = {
"coffeeBeans": 1
}




# 클래스 인스턴스 생성 및 메서드 호출
mqtt_test_instance = MQTT_TEST()
context_instance = Context()  # Context 인스턴스 생성 필요
mqtt_test_instance.on_create(context_instance)
mqtt_test_instance.send_msg_to_MQTT(context=context_instance, data=coffeeBeans_data)
