import json
import paho.mqtt.client as mqtt
import random
import time

# MQTT 브로커 정보
BROKER = "device.thingplus.net"
PORT = 1883
PASSWORD = "dali3254"
TOPIC = "v1/devices/me/telemetry"

# 로봇 시리얼 아이디 (고정)
robot_id = "indyPohangSoup"     #포항고 국탕 시리얼 아이디
#robot_id = "indyX600WO0067"    #가흥초 국탕 시리얼 아이디

def send_mqtt_message(payload):
    """
    MQTT 메시지를 전송하는 함수.
    :param payload: 전송할 데이터 (dict 형식)
    """
    username = f"{robot_id}:neuromeka"
    client = mqtt.Client()
    client.username_pw_set(username=username, password=PASSWORD)
    client.connect(BROKER, PORT, keepalive=60)
    message = json.dumps(payload)
    result = client.publish(TOPIC, message)
    status = result[0]
    if status == 0:
        print(f"메시지가 {robot_id}를 통해 성공적으로 전송되었습니다: {message}")
    else:
        print(f"메시지 전송 실패 (robot_id: {robot_id})")
    client.disconnect()

# 1. CORE 상태정보
def send_core_status():
    payload = {
        "voltage_48V_inlet": ",".join(map(str, [random.uniform(45.0, 50.0) for _ in range(6)])),
        "voltage_48V_protcV": ",".join(map(str, [random.uniform(45.0, 50.0) for _ in range(6)])),
        "temperature_driver_1": ",".join(map(str, [random.uniform(30.0, 80.0) for _ in range(6)])),
        "temperature_driver_2": ",".join(map(str, [random.uniform(30.0, 80.0) for _ in range(6)])),
        "temperature_driver_3": ",".join(map(str, [random.uniform(30.0, 80.0) for _ in range(6)])),
        "temperature_encoder_motor": ",".join(map(str, [random.uniform(30.0, 80.0) for _ in range(6)])),
        "temperature_encoder_output": ",".join(map(str, [random.uniform(30.0, 80.0) for _ in range(6)])),
        "temperature_motor": ",".join(map(str, [random.uniform(30.0, 80.0) for _ in range(6)]))
    }
    send_mqtt_message(payload)

# 2. COBOT 상태정보
def send_cobot_status():
    payload = {
        "time": random.uniform(0, 10000),
        "opState": random.choice(["SERVO_OFF", "VIOLATE", "RECOVER", "IDLE", "MOVING", "TEACHING", "COLLISION"]),
        "violationType": random.randint(0, 10),
        "q": ",".join(map(str, [random.uniform(-180, 180) for _ in range(6)])),
        "e": ",".join(map(str, [random.uniform(-10, 10) for _ in range(6)])),
        "epos": ",".join(map(str, [random.uniform(-10, 10) for _ in range(6)])),
        "extau": ",".join(map(str, [random.uniform(-50, 50) for _ in range(6)]))
    }
    send_mqtt_message(payload)

# 3. 조업 정보
def send_operation_status():
    payload = {
        "firmware_version": "1.2.3",
        "software_version": "2.3.4",
        "workload": ",".join(map(str, [random.uniform(0, 100) for _ in range(6)])),
        "tactTime": random.uniform(30, 1200),
        "play_time": ",".join(map(str, [random.uniform(0, 10000) for _ in range(6)]))
    }
    send_mqtt_message(payload)


# 4. 조리로봇 정보
def send_cooking_robot_status():
    payload = {
        "cookingType": random.choice(["COFFEE", "FRYING", "DEEP_FRYING", "BOILING_NOODLES"]),
        "cookingTactTime": random.randint(0, 2000),
        "recipeName": f"레시피{random.randint(1, 10)}"
    }
    send_mqtt_message(payload)

# 5. 조리로봇 레시피 정보
def send_recipe_list():
    recipe_list = [
        {"label": f"레시피{i}", "time": random.uniform(10, 2000)}
        for i in range(1, 10)
    ]
    payload = {"recipeList": recipe_list}
    send_mqtt_message(payload)

# 6. 환경 센서 데이터
def send_environmental_data():
    payload = {
        "co2": random.randint(400, 2000),
        "co": random.randint(1, 1000)
    }
    send_mqtt_message(payload)


  
if __name__ == "__main__":
    runCount=0
    while runCount<10:

        send_core_status()  # CORE 상태정보 전송
        send_cobot_status()  # COBOT 상태정보 전송
        send_operation_status()  # 조업 정보 전송
        send_cooking_robot_status()  # 조리로봇 정보 전송
        send_recipe_list()  # 레시피 리스트 전송
        send_environmental_data()  # 환경 센서 데이터 전송
        
        runCount+=1
        print(runCount)
        time.sleep(5)
