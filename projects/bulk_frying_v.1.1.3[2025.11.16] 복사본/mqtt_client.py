import json
import threading
import paho.mqtt.client as mqtt


class MQTTSession:
    def __init__(self, _msg_queue, hostname: str, port: int, username: str, password: str):
        self._msg_queue = _msg_queue
        self._client = None
        self._hostname = hostname
        self._port = port
        self._username = username
        self._password = password
        self._thread_lock = threading.Lock()
        self._opened = False
        self._connected = False
        self._on_message_callback = None

    def __on_connect(self, client, userdata, flags, rc):
        # self._connected = rc == 0
        self._connected = True
        print("Connected OK Returned code=", rc)

    def __on_disconnect(self, client, userdata, rc):
        # self._connected = not (rc == 0)
        self._connected = False
        print("Bad connection Returned code=", rc)

    # 0: Connection successful
    # 1: Connection refused – incorrect protocol version
    # 2: Connection refused – invalid client identifier
    # 3: Connection refused – server unavailable
    # 4: Connection refused – bad username or password
    # 5: Connection refused – not authorised
    # 6 - 255: Currently unused.

    # @staticmethod
    # def connect_status(self, client, userdata, flags, rc):
    #     if rc == 0:
    #         print("connected OK Returned code=", rc)
    #     else:
    #         print("Bad connection Returned code=", rc)

    def __on_message(self, client, userdata, msg):
        # self._thread_lock.acquire()
        # print("Message received-> " + msg.topic + " " + str(msg.payload.decode("utf-8")))  # Print a received msg
        self._msg_queue.put(str(msg.payload.decode("utf-8")))
        # self._thread_lock.release()

    def open(self):
        try:
            if self._client is not None:
                self.close()
            self._thread_lock.acquire()
            self._client = mqtt.Client()
            self._client.connect(host=self._hostname, port=self._port)
            self._client.username_pw_set(username=self._username, password=self._password)
            self._client.on_connect = self.__on_connect
            self._client.on_disconnect = self.__on_disconnect
            self._client.on_message = self.__on_message
            self._client.loop_start()
            self._opened = True
            self._thread_lock.release()
        except:
            self._thread_lock.release()
            self.close()

    def close(self):
        self._thread_lock.acquire()
        self._client.loop_stop()
        self._client.disconnect()
        del self._client
        self._client = None
        self._opened = False
        self._thread_lock.release()

    def publish(self, topic: str, data: dict):
        if self._client is None:
            raise RuntimeError("MQTT Session is not opened.")
        self._thread_lock.acquire()
        self._client.publish(topic=topic, payload=json.dumps(data))
        self._thread_lock.release()

    def request_subscribe(self, topic: str):
        if self._client is None:
            raise RuntimeError("MQTT Session is not opened.")
        self._thread_lock.acquire()
        self._client.subscribe(topic)
        self._thread_lock.release()

    def is_opened(self) -> bool:
        return self._opened

    def is_connected(self) -> bool:
        return self._connected
