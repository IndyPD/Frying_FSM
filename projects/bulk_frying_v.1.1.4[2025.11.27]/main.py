import sys
import signal
import time
import threading

from pkg.configs.global_config import GlobalConfig
from pkg.utils.blackboard import GlobalBlackboard
from pkg.app import modbus_app
from pkg.app import grpc_app
from pkg.utils.logging import Logger, LogLevel

from projects.bulk_frying.process_manager import ProcessManager
from projects.bulk_frying import indy_control
# from projects.bulk_frying.auto_inspection import auto_inspection


project_name = "bulk_frying"
bb = GlobalBlackboard()

global_config = GlobalConfig()
global_config.initialize(project_name)
Logger.set_log_level(LogLevel.DEBUG)
terminate_flag = threading.Event()


def sig_handler(signum, frame):
    Logger.warn(f"[SIGNAL] Received signal {signum}. Gracefully shutting down...")
    terminate_flag.set()

def main():
    ''' Signal handler '''
    signal.signal(signal.SIGINT, sig_handler)
    signal.signal(signal.SIGTERM, sig_handler)

    Logger.info(f"[SYSTEM] Starting {project_name} System...")

    app_server = None
    process = None
    robot = None
    try:
        app_config_file = f"projects/{project_name}/configs/app_config.json"
        app_server = grpc_app.GRPCAppCommunication(config_path=app_config_file, run_server=True)
        app_server.start()
        time.sleep(0.1)
        print("Debug1")

        robot = indy_control.RobotCommunication()
        robot.start()
        time.sleep(0.1)

        process = ProcessManager()
        process.robot_fsm.context.process_manager = process
        process.start()
        time.sleep(0.1)

        # if global_config.get("auto_inspection"):
        #     auto_inspection(process.robot_fsm, terminate_flag)

        Logger.info(f"[SYSTEM] {project_name} system initialized. Running...")

        while not terminate_flag.is_set():
            time.sleep(0.5)

    except Exception as e:
        Logger.error(f"[SYSTEM ERROR] Unexpected exception: {e}")
    finally:
        Logger.info("[SYSTEM] Shutdown started...")

        if app_server:
            app_server.stop()
        if robot:
            robot.stop()
        if process:
            process.stop()

        Logger.info("[SYSTEM] Shutdown complete.")
        sys.exit(0)


if __name__ == '__main__':
    main()

