import time
import random

from eco import EcoSensor
from pkg.utils.logging import Logger

def run_test():
    """
    Initializes the EcoSensor, and sends simulated data every 5 seconds.
    """
    Logger.info("--- Starting EcoSensor MQTT Test ---")
    cnt = 0
    sensor = None
    try:
        # 1. Initialize and connect the sensor to MQTT
        sensor = EcoSensor()
        sensor.connect_mqtt()

        # Check if the connection was successful
        if not sensor.mqtt_session or not sensor.mqtt_session.is_connected():
            Logger.fatal("\n[FATAL] Could not connect to MQTT. Please check config and network. Aborting test.")
            return

        Logger.info("\nSuccessfully connected to MQTT. Starting to send simulated data...")
        Logger.info("Press Ctrl+C to stop the test.")

        # 2. Loop and send simulated data
        while cnt < 15:
            # Create a dictionary with simulated sensor data
            simulated_data = {
                "co2": random.randint(400, 1000),
                "co": random.randint(0, 10),
                "tvoc": random.randint(0, 500),
                "temperature": round(random.uniform(20.0, 28.0), 1),
                "humidity": random.randint(40, 60)
            }
            
            Logger.info(f"\n[{time.ctime()}] Sending simulated data:")
            Logger.info(simulated_data)
            
            # 3. Call the send method
            sensor.send_data_mqtt(simulated_data)
            
            # Wait for 5 seconds before sending the next data point
            time.sleep(5)
            cnt+=1

    except KeyboardInterrupt:
        Logger.info("\n\nKeyboardInterrupt detected. Shutting down the test script.")
    except Exception as e:
        Logger.error(f"\nAn unexpected error occurred: {e}")
    finally:
        # 4. Cleanly close the MQTT connection
        if sensor:
            sensor.close()
        Logger.info("--- EcoSensor MQTT Test Finished ---")

if __name__ == "__main__":
    run_test()
