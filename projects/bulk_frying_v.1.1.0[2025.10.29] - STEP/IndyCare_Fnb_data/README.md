# How to use MQTT Class

This is an example of how to use the MQTT class. 
The usage depends on your specific requirements.

The parameter in <> can be found in the config file.
Some of parameters are depends on setting from server (Daliworks).
Please modify the config file to suit your application.

Import the mqtt class

```python
import queue
import yaml
from mqtt_client import MQTTSession
```

Fill the class by using data in config file
```python
message_queue = queue.Queue()

mqtt_session = MQTTSession(
            message_queue,
            hostname=<hostname>,
            port=<port>,
            username=f"{<device id>}:{<user name>}",
            password=<password>
        )
```

Open the connection
```python
mqtt_session.open()
```

Subscribe to server topic
```python
mqtt_session.request_subscribe(<topic attributes>)
```

To send data
```python
data = {
    "co2": co2_var,
    "co": co_var
}
mqtt_session.publish(
    topic=<topic telemetry>
    data=data
)
```
