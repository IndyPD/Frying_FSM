import sys
from neuromeka import IndyDCP3
from time import sleep

def check_robot_state():
    """
    로봇에 연결하여 현재 상태(op_state)를 확인합니다.
    연결에 성공하고 op_state가 5일 경우 0을,
    그 외의 경우에는 1을 반환합니다.
    """
    try:
        indy = IndyDCP3(robot_ip='192.168.0.14', index=0)
        
        robot_data = indy.get_robot_data()
        state = robot_data.get('op_state')

        if state == 5:
            print("[INFO] 로봇 상태: 정상 (op_state=5)")
            return 0
        else:
            print(f"[WARN] 로봇 상태: 비정상 (op_state={state})")
            return 1
            
    except Exception as e:
        print(f"[ERROR] 로봇 연결 실패: {e}")
        return 1

if __name__ == "__main__":
    exit_code = check_robot_state()
    sys.exit(exit_code)
