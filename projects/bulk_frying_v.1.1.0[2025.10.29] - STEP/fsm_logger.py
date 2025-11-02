import os
import csv
from datetime import datetime

class FSMCSVLogger:
    def __init__(self, recipe_fsm, robot_fsm):
        self.recipe_fsm = recipe_fsm
        self.robot_fsm = robot_fsm
        self.prev_states = [None] * 8
        self.prev_events = [None] * 8
        self.prev_robot_state = None
        self.prev_robot_event = None

        # ✅ logs 디렉토리 생성 (없으면)
        os.makedirs("LOG", exist_ok=True)

        # ✅ 시각 기반 고유 파일명 생성
        now_str = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        self.log_path = os.path.join("LOG", f"{now_str}-FSMStateLog.log")
        self.header_written = False
        print(f"[FSM LOG] Logging to file: {self.log_path}")

    def log_if_changed(self):
        cur_robot_state = self.robot_fsm.get_state()
        cur_robot_event = getattr(self.robot_fsm, "_last_event", None)

        changed_idx = -1
        changed_event = None

        for i, fsm in enumerate(self.recipe_fsm):
            if self.prev_states[i] != fsm.get_state() or getattr(fsm, "_last_event", None) != self.prev_events[i]:
                changed_idx = i
                changed_event = getattr(fsm, "_last_event", None)
                self.log_snapshot(f"B{i+1}", changed_event)
                return

        if cur_robot_state != self.prev_robot_state or cur_robot_event != self.prev_robot_event:
            self.log_snapshot("Robot", cur_robot_event)

    def log_snapshot(self, fsm_name, event):
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        robot_state = self.robot_fsm.get_state().name[:14]
        basket_states = [fsm.get_state().name[:7] for fsm in self.recipe_fsm]

        with open(self.log_path, "a", newline="") as f:
            writer = csv.writer(f)
            if not self.header_written:
                header = ["Time", "FSM", "Event"] + [f"B{i+1}" for i in range(8)] + ["Robot"]
                writer.writerow(header)
                self.header_written = True

            writer.writerow([
                now,
                fsm_name,
                event.name if event else "-",
                *basket_states,
                robot_state
            ])

        # 상태 갱신
        self.prev_robot_state = self.robot_fsm.get_state()
        self.prev_robot_event = getattr(self.robot_fsm, "_last_event", None)
        for i, fsm in enumerate(self.recipe_fsm):
            self.prev_states[i] = fsm.get_state()
            self.prev_events[i] = getattr(fsm, "_last_event", None)
