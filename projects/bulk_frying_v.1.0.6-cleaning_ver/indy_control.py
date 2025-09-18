# import threading
# import time
# import re
# from collections import deque
# from pkg.utils.blackboard import GlobalBlackboard

# from neuromeka import IndyDCP3
# from pkg.utils.file_io import load_json, save_json
# from .constants import *
# from .constants import RobotState
# from pkg.configs.global_config import GlobalConfig
# from pkg.utils.rotation_utils import diff_cmd

# global_config = GlobalConfig()
# bb = GlobalBlackboard()

# class GripperControl:
#     def __init__(self, alpha=0.9):
#         self.alpha = alpha  # EMA smoothing
#         self.filtered_signal = 0
#         self.target_state = "OPEN"
#         self.last_state = "OPEN"
#         self.close_failure_duration = 0
#         self.open_failure_duration = 0

#     def update_signal(self, new_signal, gripper_open):
#         # EMA 필터
#         if self.filtered_signal == 0:
#             self.filtered_signal = new_signal
#         else:
#             self.filtered_signal = self.alpha * new_signal + (1 - self.alpha) * self.filtered_signal

#         # 상태 판단
#         open_low, open_high = global_config.get("gripper.open_bound")
#         close_low, close_high = global_config.get("gripper.close_bound")
        
#         if open_low < self.filtered_signal < open_high:
#             # Logger.info(f"open {self.filtered_signal}")
#             current_state = "OPEN"
#         elif close_low < self.filtered_signal < close_high:
#             # Logger.info(f"close {self.filtered_signal}")
#             current_state = "CLOSED_BASKET"
#         else:
#             current_state = "TRANSITION"

#         # 실패 누적 시간 계산
#         if not gripper_open :
#             if current_state == "TRANSITION" :
#                 self.close_failure_duration = self.close_failure_duration + 1
#             elif current_state == "CLOSED_BASKET" :
#                 self.close_failure_duration = 0  
#             # self.close_failure_duration = self.close_failure_duration + 1 \
#             #     if not gripper_open and current_state != "CLOSED_BASKET" else 0
            
#             self.open_failure_duration = 0
            
#         else :
#             if current_state == "TRANSITION" :
#                 self.open_failure_duration = self.open_failure_duration + 1
#             elif current_state == "OPEN" :
#                 self.open_failure_duration = 0

#             self.close_failure_duration = 0     
#             # self.open_failure_duration = self.open_failure_duration + 1 \
#             #     if gripper_open and current_state != "OPEN" else 0
        

#         # 실패 여부 판단
#         # close_failure = self.close_failure_duration > 3 #global_config.get("gripper.close_failure_duration")
#         # open_failure = self.open_failure_duration > 3 #global_config.get("gripper.open_failure_duration")
#         # # Logger.info(f"update signal {gripper_open} {current_state} {close_failure} {open_failure} {self.close_failure_duration} {self.open_failure_duration}")
#         close_failure = self.close_failure_duration > global_config.get("gripper.close_failure_duration")
#         open_failure = self.open_failure_duration > global_config.get("gripper.open_failure_duration")
#         # Logger.info(f"[Gripper Control] update signal : new_signal={new_signal}, filtered_signal = {self.filtered_signal:.2f}, current_state = {current_state}, close_failure_duration = {self.close_failure_duration}, open_failure_duration={self.open_failure_duration}, close_failure ={close_failure}, open_failure = {open_failure}")

#         # 상태 업데이트
#         if current_state == "TRANSITION" and False:
#             Logger.info(f"gripper : {close_failure}, {open_failure}, {gripper_open}, {current_state}, {self.filtered_signal},"
#                         f"{self.close_failure_duration}, {self.open_failure_duration}")
#         self.last_state = current_state
#         return current_state, close_failure, open_failure


# class RobotCommunication:
#     def __init__(self, config_file="projects/bulk_frying/configs/indy_command.json", *args, **kwargs):
#         ''' Thread related '''
#         self.running = False
#         self.thread = None

#         ''' Config '''
#         self.config = load_json(config_file)
#         self.btn_direct_teaching_ch = int(global_config.get("switch_button.di_dt_channel"))
#         self.btn_stop_ch = int(global_config.get("switch_button.di_stop_channel"))
#         self.home_pos = self.config["home_pos"]
#         self.packaging_pos = self.config["packaging_pos"]

#         ''' Indy command '''
#         self.indy = IndyDCP3(global_config.get("robot_ip"), *args, **kwargs)
#         self.indy.set_speed_ratio(100)

#         self.gripper_product = global_config.get("gripper.product")
#         self.gripper_transistor = global_config.get("gripper.transistor")
#         self.endtool_port = global_config.get("gripper.endtool_port")
#         self.open_channel = global_config.get("gripper.open_channel")
#         self.endtool_ai_channel = global_config.get("gripper.ai_channel")

#         self.ex_int_cmd = 0

#         ''' Gripper setting '''
#         gripper_do_val = {"PNP": 2, "NPN": 1}.get(self.gripper_transistor, 1)

#         if self.gripper_product == "zimmer":
#             states = [
#                 [gripper_do_val, -gripper_do_val],
#                 [-gripper_do_val, gripper_do_val]
#             ]

#             if self.open_channel == 0:
#                 self.gripper_open_command = [{"port": self.endtool_port, "states": states[0]}]
#                 self.gripper_close_command = [{"port": self.endtool_port, "states": states[1]}]
#             elif self.open_channel == 1:
#                 self.gripper_open_command = [{"port": self.endtool_port, "states": states[1]}]
#                 self.gripper_close_command = [{"port": self.endtool_port, "states": states[0]}]
#         else:
#             pass

#         ''' Home and packaging pose '''
#         self.check_home_min = -10
#         self.check_home_max = 10
#         self.is_home_pos = False
#         self.is_packaging_pos = False
#         self.is_detect_pos = False

#         self.robot_state = 0
#         self.is_sim_mode = False
#         self.robot_running_hour = 0
#         self.robot_running_min = 0

#         self.gripper_control = GripperControl(alpha=global_config.get("gripper.filter_alpha"))

#         ''' Conty Int variable, first initialization '''
#         self.int_var_init = 0

#         self.indy.set_int_variable([
#             {'addr': int(self.config["int_var/cmd/addr"]), 'value': 0},
#             {'addr': int(self.config["int_var/init/addr"]), 'value': 0},
#             {'addr': int(self.config["int_var/grip_state/addr"]), 'value': 0},
#             {'addr': int(self.config["int_var/retry_grip/addr"]), 'value': 0},
#             {'addr': int(self.config["int_var/pickup_done/addr"]), 'value': 0},
#             {'addr': int(self.config["int_var/putin_shake/addr"]), 'value': 0},
#             {'addr': int(self.config["int_var/shake_num/addr"]), 'value': 0},
#             {'addr': int(self.config["int_var/shake_break/addr"]), 'value': 0}
#         ])

#         ''' Indy ioboard '''
#         self.btn_direct_teaching = 0
#         self.btn_stop = 0

#         ''' Indy endtool gripper '''
#         self.endtool_ai = False
#         self.is_gripper_open = False

#         ###아날로그 변수값####
#         self.analog_min = 0
#         self.analog_max = 100
#         self.analog_min_avg = 100
#         self.analog_max_avg = 800
#         self.data_queue = deque(maxlen=10)


#     def start(self):
#         """ Start the robot communication thread """

#         if not self.running:
#             self.running = True
#             self.thread = threading.Thread(target=self.run, daemon=True)
#             self.thread.start()

#     def stop(self):
#         """ Stop the app communication thread """
#         if self.running:
#             self.running = False

#             if self.program_state in (ProgramState.PROG_RUNNING, ProgramState.PROG_PAUSING):
#                 try:
#                     Logger.info("Stop program!!")
#                     self.indy.stop_program()
#                     self.indy.set_speed_ratio(100)
#                 except:
#                     Logger.error("Stop program fail")

#             self.indy.stop_motion(stop_category=2)
#             self.indy.set_int_variable([{'addr': int(self.config["int_var/cmd/addr"]), 'value': 0}])

#             if self.thread:
#                 self.thread.join()

#     def run(self):
#         """ Thread's target function """
#         while self.running:
#             time.sleep(0.001)
#             self.receive_data_from_bb()  # Get bb data, process bb data
#             self.handle_int_variable()  # Get bb data, process bb data

#             self.indy_communication()  # Get indy data
#             self.send_data_to_bb()  # Send indy data to bb

#     def get_dio_channel(self, di, ch):
#         return next((int(item['state']) for item in di if item['address'] == ch), None)

#     def get_intvar_address(self, int_var, addr):
#         return next((int(item['value']) for item in int_var if item['addr'] == addr), None)

#     def get_tposvar_address(self, tpos_var, addr):
#         return next((item['tpos'] for item in tpos_var if item['addr'] == addr), None)


#     def receive_data_from_bb(self):
#         """
#         Command request from FSM by blackbaord
#         - only work in NotReadyIdle mode (Program is NOT running)
#         """

#         ''' Gripper control '''
#         if bb.get("indy_command/gripper_open"):
#             self.indy.set_endtool_do(self.gripper_open_command)
#             bb.set("indy_command/gripper_open", False)

#         if bb.get("indy_command/gripper_close"):
#             self.indy.set_endtool_do(self.gripper_close_command)
#             bb.set("indy_command/gripper_close", False)

#         ''' Direct teaching '''
#         if bb.get("indy_command/direct_teaching_on"):
#             bb.set("indy_command/direct_teaching_on", False)
#             self.indy.set_direct_teaching(True)

#         if bb.get("indy_command/direct_teaching_off"):
#             bb.set("indy_command/direct_teaching_off", False)
#             self.indy.set_direct_teaching(False)

#         ''' Buzzer '''
#         if bb.get("indy_command/buzzer_on"):
#             bb.set("indy_command/buzzer_on", False)
#             self.indy.set_do([{'address': self.buzzer_ch, 'state': DigitalState.ON_STATE}])


#         if bb.get("indy_command/buzzer_off"):
#             bb.set("indy_command/buzzer_off", False)
#             self.indy.set_do([{'address': self.buzzer_ch, 'state': DigitalState.OFF_STATE}])

#         ''' Speed ratio control '''
#         if bb.get("indy_command/speed_ratio_full"):
#             bb.set("indy_command/speed_ratio_full", False)
#             self.indy.set_speed_ratio(100)

#         if bb.get("indy_command/speed_ratio_zero"):
#             bb.set("indy_command/speed_ratio_zero", False)
#             self.indy.set_speed_ratio(0)

#         ''' Stop motion '''
#         if bb.get("indy_command/stop_motion"):
#             bb.set("indy_command/stop_motion", False)
#             self.indy.stop_motion(stop_category=2)

#         ''' Move to home position '''
#         if bb.get("indy_command/go_home"):
#             bb.set("indy_command/go_home", False)
#             try:
#                 self.indy.movej(self.home_pos, teaching_mode=True, vel_ratio=30)
#             except:
#                 Logger.error("Fail to execute move command")

#         ''' Move to packaging position '''
#         if bb.get("indy_command/go_packaging"):
#             bb.set("indy_command/go_packaging", False)
#             try:
#                 self.indy.movej(self.packaging_pos, teaching_mode=True, vel_ratio=30)
#             except:
#                 Logger.error("Fail to execute move command")



#         ''' Start program (Main program, index=1) '''
#         if bb.get("indy_command/play_program"):
#             bb.set("indy_command/play_program", False)
#             if self.program_state != ProgramState.PROG_RUNNING:
#                 try:
#                     Logger.error("Start main program")
#                     self.indy.play_program(prog_idx=int(self.config["conty_main_program_index"]))
#                 except:
#                     Logger.error("Start main program fail")

#         ''' Start program (Warming motion, index=2) '''
#         if bb.get("indy_command/play_warming_program"):
#             bb.set("indy_command/play_warming_program", False)
#             if self.program_state != ProgramState.PROG_RUNNING:
#                 try:
#                     self.indy.play_program(prog_idx=int(self.config["conty_warming_program_index"]))
#                 except:
#                     Logger.error("Start warming program fail")

#         ''' Stop program '''
#         if bb.get("indy_command/stop_program"):
#             bb.set("indy_command/stop_program", False)
#             if self.program_state in (ProgramState.PROG_RUNNING, ProgramState.PROG_PAUSING):
#                 try:
#                     Logger.info("Stop program!!")
#                     self.indy.stop_program()
#                     self.indy.set_speed_ratio(100)
#                 except:
#                     Logger.error("Stop program fail")


#         ''' Reset '''
#         if bb.get("indy_command/recover"):
#             bb.set("indy_command/recover", False)
#             self.indy.recover()


#     def handle_int_variable(self):
#         """
#         Command request from FSM by blackbaord
#         - only work in ReadyIdle mode (Program is Running)
#         """
#         '''
#         Variables
#             Write variables (FSM -> Conty)
#                 - cmd (600)
#                 - grip_state (100)
#                 - retry_grip (101): conty에서 0으로 초기화
#                 - putin_shake (130)
#                 - shake_num (131)
#                 - shake_break (132)
#             Read variables (Conty -> FSM)
#                 - init (700): 동일 동작을 위해 Python에서 초기화
#                 - putit_done (109)
#                 - pickup_done (110)                
#         '''

#         ''' Reset variables '''
#         if bb.get("indy_command/reset_init_var"):
#             bb.set("indy_command/reset_init_var", False)
#             self.indy.set_int_variable([{'addr': int(self.config["int_var/init/addr"]), 'value': 0}])

#         ''' Read Variables: Send int variable from Conty to bb '''
#         int_var = self.indy.get_int_variable()['variables']

#         self.int_var_init = self.get_intvar_address(int_var, int(self.config["int_var/init/addr"]))
#         bb.set("int_var/init/val", self.int_var_init)
#         bb.set(f"int_var/putin_done/val", self.get_intvar_address(int_var, int(self.config[f"int_var/putin_done/addr"])))
#         bb.set(f"int_var/pickup_done/val", self.get_intvar_address(int_var, int(self.config[f"int_var/pickup_done/addr"])))

#         ''' Write Variables: Set Int variable from bb to Conty '''
#         deb_value = bb.get("int_var/cmd/val")
#         if self.ex_int_cmd != deb_value :
#             Logger.info(f"Command I600 : {deb_value}")
#             self.ex_int_cmd = deb_value
            
#         self.indy.set_int_variable([
#             {'addr': int(self.config["int_var/cmd/addr"]), 'value': int(bb.get("int_var/cmd/val"))},
#             {'addr': int(self.config["int_var/grip_state/addr"]), 'value': int(bb.get("int_var/grip_state/val"))},
#             {'addr': int(self.config["int_var/retry_grip/addr"]), 'value': int(bb.get("int_var/retry_grip/val"))},
#             {'addr': int(self.config["int_var/putin_shake/addr"]), 'value': int(bb.get("int_var/putin_shake/val"))},
#             {'addr': int(self.config["int_var/shake_num/addr"]), 'value': int(bb.get("int_var/shake_num/val"))},
#             {'addr': int(self.config["int_var/shake_break/addr"]), 'value': int(bb.get("int_var/shake_break/val"))}
#          ])


#     def indy_communication(self):

#         ''' Get Indy status '''
#         control_data = self.indy.get_control_data()
#         program_data = self.indy.get_program_data()
#         self.robot_state = control_data["op_state"]
#         self.is_sim_mode = control_data["sim_mode"]
#         self.robot_running_hour = control_data["running_hours"]
#         self.robot_running_min = control_data["running_mins"]
#         self.program_state = program_data["program_state"]
#         self.program_name = program_data["program_name"]

#         # if self.robot_state == RobotState.OP_IDLE:
#         #     self.indy.set_do([
#         #         {'address': 10, 'state': DigitalState.OFF_STATE},
#         #         {'address': 11, 'state': DigitalState.ON_STATE},
#         #         {'address': 12, 'state': DigitalState.OFF_STATE},
#         #         {'address': 13, 'state': DigitalState.OFF_STATE}
#         #     ])
#         # elif self.robot_state == RobotState.OP_MOVING:
#         #     self.indy.set_do([
#         #         {'address': 10, 'state': DigitalState.OFF_STATE},
#         #         {'address': 11, 'state': DigitalState.OFF_STATE},
#         #         {'address': 12, 'state': DigitalState.ON_STATE},
#         #         {'address': 13, 'state': DigitalState.OFF_STATE}
#         #     ])
#         # elif self.robot_state == RobotState.OP_VIOLATE:
#         #     self.indy.set_do([
#         #         {'address': 10, 'state': DigitalState.ON_STATE},
#         #         {'address': 11, 'state': DigitalState.OFF_STATE},
#         #         {'address': 12, 'state': DigitalState.OFF_STATE},
#         #         {'address': 13, 'state': DigitalState.ON_STATE}
#         #     ])
#         # else:
#         #     self.indy.set_do([
#         #         {'address': 10, 'state': DigitalState.OFF_STATE},
#         #         {'address': 11, 'state': DigitalState.OFF_STATE},
#         #         {'address': 12, 'state': DigitalState.OFF_STATE},
#         #         {'address': 13, 'state': DigitalState.OFF_STATE}
#         #     ])

#         q = self.indy.get_control_data()["q"]
#         self.is_home_pos = all(self.check_home_min <= a - b <= self.check_home_max for a, b in zip(q, self.home_pos))
#         self.is_packaging_pos = all(
#             self.check_home_min <= a - b <= self.check_home_max for a, b in zip(q, self.packaging_pos))

#         ''' Get Indy ioboard data '''
#         do = self.indy.get_do()['signals']  # type: ignore
#         di = self.indy.get_di()['signals']  # type: ignore

#         # Buttons, Tray sensors
#         if self.is_sim_mode:
#             self.btn_direct_teaching = self.get_dio_channel(do, self.btn_direct_teaching_ch)
#             self.btn_stop = self.get_dio_channel(do, self.btn_stop_ch)
            
#         else:
#             self.btn_direct_teaching = self.get_dio_channel(di, self.btn_direct_teaching_ch)
#             self.btn_stop = self.get_dio_channel(di, self.btn_stop_ch)
#             # if self.get_dio_channel(di,0) == 1 or self.get_dio_channel(di, 5) == 1 :
#             #     self.indy.set_speed_ratio(100)
#             #     Logger.info("Lidar detected far object, setting speed to 100")
#             # elif self.get_dio_channel(di, 8) == 1 or self.get_dio_channel(di, 9) == 1 :
#             #     self.indy.set_speed_ratio(0)
#             #     Logger.info("Lidar detected close object, setting speed to 0")


#         ''' Get Indy endtool data '''
#         endtool_do = self.indy.get_endtool_do()['signals']  # type: ignore
#         endtool_ai = self.indy.get_endtool_ai()['signals']  # type: ignore
#         endtool_do_state = next((item['states'] for item in endtool_do if item['port'] == self.endtool_port), None)


#         if endtool_do_state == self.gripper_open_command[0]['states']:
#             self.is_gripper_open = True     # Open
#         else:
#             self.is_gripper_open = False    # Close
        
#         # Logger.info(f"endtool gripper : {self.is_gripper_open}")

#         self.endtool_ai = next(
#             (int(item['voltage']) for item in endtool_ai if item['address'] == self.endtool_ai_channel), None)

#         state, close_fail, open_fail = self.gripper_control.update_signal(self.endtool_ai, self.is_gripper_open)
        
#         if self.is_sim_mode:
#             if self.get_dio_channel(do, 13):
#                 bb.set("int_var/grip_state/val", GripFailure.SUCCESS)
#             elif self.get_dio_channel(do, 14):
#                 bb.set("int_var/grip_state/val", GripFailure.OPEN_FAIL)
#             elif self.get_dio_channel(do, 15):
#                 bb.set("int_var/grip_state/val", GripFailure.CLOSE_FAIL)
#         else:
#             # Logger.info(f"close_fail {close_fail} {global_config.get('grip_close_fail_fool_proof')}")
#             # Logger.info(f"open_fail {open_fail} {global_config.get('grip_open_fail_fool_proof')}")

#             # if close_fail and global_config.get("grip_close_fail_fool_proof"):
#             # if close_fail:
#             #     bb.set("int_var/grip_state/val", GripFailure.CLOSE_FAIL)
#             #     Logger.info(f"grip close fail---------------------------------")
#             # # elif open_fail and global_config.get("grip_open_fail_fool_proof"):
#             # elif open_fail:
#             #     bb.set("int_var/grip_state/val", GripFailure.OPEN_FAIL)
#             # else:
#             #     bb.set("int_var/grip_state/val", GripFailure.SUCCESS)

#             # state == 'TRANSITION' -> OPEN도 CLOSED_BACKET도 아닌 상태 / TRANSITION 상태일 때는 close_fail이나 open_fail이 잠시 True가 되더라도, state != "TRANSITION" 조건 때문에 실패로
#             # 처리되지 않고 else 문으로 빠져 GripFailure.SUCCESS가 블랙보드에 기록됨.

#             # if close_fail and state != "TRANSITION" :
#             #     bb.set("int_var/grip_state/val", GripFailure.CLOSE_FAIL)
#             #     Logger.info(f"grip close fail---------------------------------")
#             # # elif open_fail and global_config.get("grip_open_fail_fool_proof"):
#             # elif open_fail and state != "TRANSITION" :
#             #     bb.set("int_var/grip_state/val", GripFailure.OPEN_FAIL)
#             # else:
#             #     bb.set("int_var/grip_state/val", GripFailure.SUCCESS)
#             if not bb.get("robot/state/handling_grip_failure") :
#                 if close_fail :
#                     bb.set("int_var/grip_state/val", GripFailure.CLOSE_FAIL)
#                     Logger.info(f"grip close fail---------------------------------")
#                 # elif open_fail and global_config.get("grip_open_fail_fool_proof"):
#                 elif open_fail :
#                     bb.set("int_var/grip_state/val", GripFailure.OPEN_FAIL)
#                 else:
#                     bb.set("int_var/grip_state/val", GripFailure.SUCCESS)
                    

#     def send_data_to_bb(self):
#         """
#         Set data to bb
#             - bb send to App
#             - bb sent to FSM
#         """
#         ''' DI Button '''
#         bb.set("indy_state/button_dt", self.btn_direct_teaching)
#         bb.set("indy_state/button_stop", self.btn_stop)

#         ''' Indy status '''
#         indy_data = {
#             "robot_state": self.robot_state,
#             "is_sim_mode": self.is_sim_mode,
#             "program_state": self.program_state,
#             "endtool_ai": self.endtool_ai,
#             "is_home_pos": self.is_home_pos,
#             "is_packaging_pos": self.is_packaging_pos,
#             "is_detect_pos": self.is_detect_pos
#         }
#         bb.set("indy", indy_data)

#         ''' App '''
#         robot_state_ui = 0
#         if self.robot_state in (RobotState.OP_SYSTEM_OFF, RobotState.OP_SYSTEM_ON):
#             robot_state_ui = 1  # Off
#         elif self.robot_state in (RobotState.OP_VIOLATE, RobotState.OP_VIOLATE_HARD):
#             robot_state_ui = 2  # Emergency
#         elif self.robot_state in (RobotState.OP_RECOVER_SOFT, RobotState.OP_RECOVER_HARD,
#                                   RobotState.OP_BRAKE_CONTROL, RobotState.OP_SYSTEM_RESET,
#                                   RobotState.OP_SYSTEM_SWITCH, RobotState.OP_MANUAL_RECOVER):
#             robot_state_ui = 3  # Error
#         elif self.robot_state in (RobotState.OP_IDLE, RobotState.OP_MOVING,
#                                   RobotState.OP_TEACHING, RobotState.OP_COMPLIANCE,
#                                   RobotState.TELE_OP):
#             robot_state_ui = 4  # Ready
#         elif self.robot_state == RobotState.OP_COLLISION:
#             robot_state_ui = 5  # Collision

#         # Robot state, working time
#         bb.set("ui/state/robot_state", robot_state_ui)
#         bb.set("ui/state/working_time", self.robot_running_hour)
#         bb.set("ui/state/working_minute", self.robot_running_min)

#         ''' Direct teaching (On, Off) '''
#         if self.robot_state == RobotState.OP_TEACHING:
#             bb.set("ui/state/direct_state", 1)  # On
#         else:
#             bb.set("ui/state/direct_state", 2)  # Off

#         ''' Gripper (닫기, 열기) '''
#         if self.is_gripper_open:
#             bb.set("ui/state/gripper_state", 2)  # 닫기
#         else:
#             bb.set("ui/state/gripper_state", 1)  # 열기

#         if bb.get("ui/command/program_control") == ProgramControl.PROG_START:
#             bb.set("ui/reset/program_control", True)
#             if self.program_state == ProgramState.PROG_RUNNING:
#                 self.indy.set_speed_ratio(100)


#         match = re.search(r'/index/(\d+)', self.program_name)
#         if match:
#             program_index = match.group(1)
#             if program_index == "1":
#                 ''' 프로그램 시작/일시정지/정지/다시시작 버튼  '''
#                 if self.program_state == ProgramState.PROG_IDLE:
#                     bb.set("ui/state/program_state", 0)  # Init
#                 elif self.program_state == ProgramState.PROG_RUNNING:
#                     if self.indy.get_motion_data().get("speed_ratio", 100) == 0:
#                         bb.set("ui/state/program_state", 3)  # Pause
#                     elif self.indy.get_motion_data().get("speed_ratio", 100) == 100:
#                         bb.set("ui/state/program_state", 1)  # Start
#                 elif self.program_state == ProgramState.PROG_STOPPING:
#                     bb.set("ui/state/program_state", 4)  # Stop
#                     if self.indy.get_motion_data().get("speed_ratio", 100) == 0:
#                         bb.set("ui/state/program_state", 3)  # Pause
#                     elif self.indy.get_motion_data().get("speed_ratio", 100) == 100:
#                         bb.set("ui/state/program_state", 2)  # Resume

#             if program_index == "2":
#                 ''' 예열 On, Off 버튼 '''
#                 if self.program_state == ProgramState.PROG_IDLE:
#                     bb.set("ui/state/warming_state", 0)
#                 elif self.program_state == ProgramState.PROG_RUNNING:
#                     bb.set("ui/state/warming_state", 1)
#                 elif self.program_state == ProgramState.PROG_STOPPING:
#                     bb.set("ui/state/warming_state", 2)
#             else:
#                 bb.set("ui/state/warming_state", 0)

import threading
import time
import re
from collections import deque
from pkg.utils.blackboard import GlobalBlackboard

from neuromeka import IndyDCP3
from pkg.utils.file_io import load_json, save_json
from .constants import *
from .constants import RobotState
from pkg.configs.global_config import GlobalConfig
from pkg.utils.rotation_utils import diff_cmd

global_config = GlobalConfig()
bb = GlobalBlackboard()

class GripperControl:
    def __init__(self, alpha=0.9):
        self.alpha = alpha  # EMA smoothing
        self.filtered_signal = 0
        self.target_state = "OPEN"
        self.last_state = "OPEN"
        self.close_failure_duration = 0
        self.open_failure_duration = 0

    def update_signal(self, new_signal, gripper_open):
        # EMA 필터
        if self.filtered_signal == 0:
            self.filtered_signal = new_signal
        else:
            self.filtered_signal = self.alpha * new_signal + (1 - self.alpha) * self.filtered_signal

        # 상태 판단
        open_low, open_high = global_config.get("gripper.open_bound")
        close_low, close_high = global_config.get("gripper.close_bound")
        
        if open_low < self.filtered_signal < open_high:
            current_state = "OPEN"
        elif close_low < self.filtered_signal < close_high:
            current_state = "CLOSED_BASKET"
        else:
            current_state = "TRANSITION"

        # 실패 누적 시간 계산
        if not gripper_open:
            if current_state == "TRANSITION":
                self.close_failure_duration = self.close_failure_duration + 1
            elif current_state == "CLOSED_BASKET":
                self.close_failure_duration = 0  
            self.open_failure_duration = 0
        else:
            if current_state == "TRANSITION":
                self.open_failure_duration = self.open_failure_duration + 1
            elif current_state == "OPEN":
                self.open_failure_duration = 0
            self.close_failure_duration = 0     

        # 실패 여부 판단
        close_failure = self.close_failure_duration > global_config.get("gripper.close_failure_duration")
        open_failure = self.open_failure_duration > global_config.get("gripper.open_failure_duration")

        self.last_state = current_state
        return current_state, close_failure, open_failure


class RobotCommunication:
    def __init__(self, config_file="projects/bulk_frying/configs/indy_command.json", *args, **kwargs):
        ''' Thread related '''
        self.running = False
        self.thread = None

        ''' Config '''
        self.config = load_json(config_file)
        self.btn_direct_teaching_ch = int(global_config.get("switch_button.di_dt_channel"))
        self.btn_stop_ch = int(global_config.get("switch_button.di_stop_channel"))
        self.home_pos = self.config["home_pos"]
        self.packaging_pos = self.config["packaging_pos"]

        ''' Indy command '''
        self.indy = IndyDCP3(global_config.get("robot_ip"), *args, **kwargs)
        self.indy.set_speed_ratio(100)

        self.gripper_product = global_config.get("gripper.product")
        self.gripper_transistor = global_config.get("gripper.transistor")
        self.endtool_port = global_config.get("gripper.endtool_port")
        self.open_channel = global_config.get("gripper.open_channel")
        self.endtool_ai_channel = global_config.get("gripper.ai_channel")

        self.ex_int_cmd = 0

        ''' Gripper setting '''
        gripper_do_val = {"PNP": 2, "NPN": 1}.get(self.gripper_transistor, 1)

        if self.gripper_product == "zimmer":
            states = [
                [gripper_do_val, -gripper_do_val],
                [-gripper_do_val, gripper_do_val]
            ]

            if self.open_channel == 0:
                self.gripper_open_command = [{"port": self.endtool_port, "states": states[0]}]
                self.gripper_close_command = [{"port": self.endtool_port, "states": states[1]}]
            elif self.open_channel == 1:
                self.gripper_open_command = [{"port": self.endtool_port, "states": states[1]}]
                self.gripper_close_command = [{"port": self.endtool_port, "states": states[0]}]
        else:
            pass

        ''' Home and packaging pose '''
        self.check_home_min = -10
        self.check_home_max = 10
        self.is_home_pos = False
        self.is_packaging_pos = False
        self.is_detect_pos = False

        self.robot_state = 0
        self.is_sim_mode = False
        self.robot_running_hour = 0
        self.robot_running_min = 0

        self.gripper_control = GripperControl(alpha=global_config.get("gripper.filter_alpha"))

        ''' Conty Int variable, first initialization '''
        self.int_var_init = 0

        self.indy.set_int_variable([
            {'addr': int(self.config["int_var/cmd/addr"]), 'value': 0},
            {'addr': int(self.config["int_var/init/addr"]), 'value': 0},
            {'addr': int(self.config["int_var/grip_state/addr"]), 'value': 0},
            {'addr': int(self.config["int_var/retry_grip/addr"]), 'value': 0},
            {'addr': int(self.config["int_var/pickup_done/addr"]), 'value': 0},
            {'addr': int(self.config["int_var/putin_shake/addr"]), 'value': 0},
            {'addr': int(self.config["int_var/shake_num/addr"]), 'value': 0},
            {'addr': int(self.config["int_var/shake_break/addr"]), 'value': 0}
        ])

        ''' Indy ioboard '''
        self.btn_direct_teaching = 0
        self.btn_stop = 0

        ''' Indy endtool gripper '''
        self.endtool_ai = False
        self.is_gripper_open = False

        ''' Analog variables '''
        self.analog_min = 0
        self.analog_max = 100
        self.analog_min_avg = 100
        self.analog_max_avg = 800
        self.data_queue = deque(maxlen=10)

        ''' 청소 모드 관련 변수 추가 '''
        self.prev_cleaning_mode_ui = None  # 이전 청소 모드 상태 저장
        self.cleaning_mode_do_channel = 8  # 청소 모드 DO 채널
        self.lidar_warning_channel = 0     # 라이다 경고 신호 DI 채널
        self.lidar_protective_channel = 1  # 라이다 보호 신호 DI 채널

    def start(self):
        """ Start the robot communication thread """
        if not self.running:
            self.running = True
            self.thread = threading.Thread(target=self.run, daemon=True)
            self.thread.start()

    def stop(self):
        """ Stop the app communication thread """
        if self.running:
            self.running = False

            if self.program_state in (ProgramState.PROG_RUNNING, ProgramState.PROG_PAUSING):
                try:
                    Logger.info("Stop program!!")
                    self.indy.stop_program()
                    self.indy.set_speed_ratio(100)
                except:
                    Logger.error("Stop program fail")

            self.indy.stop_motion(stop_category=2)
            self.indy.set_int_variable([{'addr': int(self.config["int_var/cmd/addr"]), 'value': 0}])

            if self.thread:
                self.thread.join()

    def run(self):
        """ Thread's target function """
        while self.running:
            time.sleep(0.001)
            self.receive_data_from_bb()  # Get bb data, process bb data
            self.handle_int_variable()   # Get bb data, process bb data
            self.indy_communication()    # Get indy data
            self.handle_cleaning_mode()  # 청소 모드 처리 추가
            self.send_data_to_bb()       # Send indy data to bb

    def get_dio_channel(self, di, ch):
        return next((int(item['state']) for item in di if item['address'] == ch), None)

    def get_intvar_address(self, int_var, addr):
        return next((int(item['value']) for item in int_var if item['addr'] == addr), None)

    def get_tposvar_address(self, tpos_var, addr):
        return next((item['tpos'] for item in tpos_var if item['addr'] == addr), None)

    def handle_cleaning_mode(self):
        """
        청소 모드 처리 함수
        - UI에서 청소 모드 명령을 받아 DO 신호 제어
        - 라이다 센서 신호에 따른 안전 제어 (일반 모드에서만)
        
        cleaning_mode 값:
        - 0: 대기 상태 (아무 동작 없음)
        - 1: 일반 모드 (라이다 센서 활성화)  
        - 2: 청소 모드 (라이다 센서 무시)
        """
        try:
            # 현재 DO/DI 상태 가져오기
            do = self.indy.get_do()['signals']
            di = self.indy.get_di()['signals']
            
            # UI에서 청소 모드 명령 확인
            cleaning_mode_command = bb.get('ui/command/cleaning_mode')
            
            # 명령이 들어왔을 때만 처리
            if cleaning_mode_command != 0:
                # 상태 업데이트
                bb.set('ui/state/cleaning_mode', cleaning_mode_command)
                
                # DO 신호 설정
                if cleaning_mode_command == 2:  # 청소 모드
                    self.indy.set_do([{'address': self.cleaning_mode_do_channel, 'state': 1}])
                    Logger.info("[Cleaning Mode] Activated - Lidar sensors disabled, DO channel 8 = ON")
                elif cleaning_mode_command == 1:  # 일반 모드
                    self.indy.set_do([{'address': self.cleaning_mode_do_channel, 'state': 0}])
                    Logger.info("[Cleaning Mode] Normal mode activated - Lidar sensors enabled, DO channel 8 = OFF")
                elif cleaning_mode_command == 0:  # 대기 상태
                    self.indy.set_do([{'address': self.cleaning_mode_do_channel, 'state': 0}])
                    Logger.info("[Cleaning Mode] Standby mode activated, DO channel 8 = OFF")
                
                # 명령 처리 완료 후 리셋 (다음 명령을 위해)
                bb.set('ui/command/cleaning_mode', 0)
                Logger.info(f"[Cleaning Mode] Command processed and reset. Current state: {bb.get('ui/state/cleaning_mode')}")
            
            # 현재 상태 가져오기
            current_cleaning_mode = bb.get('ui/state/cleaning_mode')
            
            # 대기 상태(0)일 때는 라이다 센서 처리하지 않음
            if current_cleaning_mode == 0:
                return

            # 실제 청소 모드 상태 확인 (UI 상태와 DO 신호가 모두 참일 때)
            is_cleaning_mode = (current_cleaning_mode == 2) and (self.get_dio_channel(do, self.cleaning_mode_do_channel) == 1)
            
            # 라이다 센서 신호 확인
            # is_di0_on = self.get_dio_channel(di, self.lidar_warning_channel) == 1     # 경고 신호
            # is_di1_on = self.get_dio_channel(di, self.lidar_protective_channel) == 1  # 보호 신호
            is_di0_on = self.get_dio_channel(do, self.lidar_warning_channel) == 1     # 경고 신호
            is_di1_on = self.get_dio_channel(do, self.lidar_protective_channel) == 1  # 보호 신호

            if is_cleaning_mode:
                # 청소 모드일 경우, 라이다 신호에 관계없이 동작 제한 없음
                if is_di0_on or is_di1_on:
                    Logger.debug("Lidar detected object in cleaning mode, but no action will be taken.")
            elif current_cleaning_mode == 1:
                # 일반 모드(1)일 경우 라이다 신호에 따른 안전 제어
                if is_di1_on:
                    # 보호 신호 우선: 프로그램 일시 정지
                    if self.program_state == ProgramState.PROG_RUNNING:
                        self.indy.pause_program()
                        Logger.info("Lidar detected object in protective zone, pausing program.")
                elif is_di0_on:
                    # 경고 신호: 속도 감속
                    current_speed = self.indy.get_motion_data().get("speed_ratio", 100)
                    if current_speed > 30:
                        self.indy.set_speed_ratio(30)
                        Logger.info("Lidar detected object in warning zone, setting speed to 30.")
                else:
                    # 신호 없음: 정상 동작 복구
                    if self.program_state == ProgramState.PROG_PAUSING:
                        self.indy.resume_program()
                        Logger.info("Lidar signal cleared, resuming program.")
                    
                    current_speed = self.indy.get_motion_data().get("speed_ratio", 100)
                    if current_speed < 100:
                        self.indy.set_speed_ratio(100)
                        Logger.info("Lidar signal cleared, setting speed to 100.")

        except Exception as e:
            Logger.error(f"Error in handle_cleaning_mode: {e}")

    def receive_data_from_bb(self):
        """
        Command request from FSM by blackboard
        - only work in NotReadyIdle mode (Program is NOT running)
        """
        ''' Gripper control '''
        if bb.get("indy_command/gripper_open"):
            self.indy.set_endtool_do(self.gripper_open_command)
            bb.set("indy_command/gripper_open", False)

        if bb.get("indy_command/gripper_close"):
            self.indy.set_endtool_do(self.gripper_close_command)
            bb.set("indy_command/gripper_close", False)

        ''' Direct teaching '''
        if bb.get("indy_command/direct_teaching_on"):
            bb.set("indy_command/direct_teaching_on", False)
            self.indy.set_direct_teaching(True)

        if bb.get("indy_command/direct_teaching_off"):
            bb.set("indy_command/direct_teaching_off", False)
            self.indy.set_direct_teaching(False)

        ''' Buzzer '''
        if bb.get("indy_command/buzzer_on"):
            bb.set("indy_command/buzzer_on", False)
            self.indy.set_do([{'address': self.buzzer_ch, 'state': DigitalState.ON_STATE}])

        if bb.get("indy_command/buzzer_off"):
            bb.set("indy_command/buzzer_off", False)
            self.indy.set_do([{'address': self.buzzer_ch, 'state': DigitalState.OFF_STATE}])

        ''' Speed ratio control '''
        if bb.get("indy_command/speed_ratio_full"):
            bb.set("indy_command/speed_ratio_full", False)
            self.indy.set_speed_ratio(100)

        if bb.get("indy_command/speed_ratio_zero"):
            bb.set("indy_command/speed_ratio_zero", False)
            self.indy.set_speed_ratio(0)

        ''' Stop motion '''
        if bb.get("indy_command/stop_motion"):
            bb.set("indy_command/stop_motion", False)
            self.indy.stop_motion(stop_category=2)

        ''' Move to home position '''
        if bb.get("indy_command/go_home"):
            bb.set("indy_command/go_home", False)
            try:
                self.indy.movej(self.home_pos, teaching_mode=True, vel_ratio=30)
            except:
                Logger.error("Fail to execute move command")

        ''' Move to packaging position '''
        if bb.get("indy_command/go_packaging"):
            bb.set("indy_command/go_packaging", False)
            try:
                self.indy.movej(self.packaging_pos, teaching_mode=True, vel_ratio=30)
            except:
                Logger.error("Fail to execute move command")

        ''' Start program (Main program, index=1) '''
        if bb.get("indy_command/play_program"):
            bb.set("indy_command/play_program", False)
            if self.program_state != ProgramState.PROG_RUNNING:
                try:
                    Logger.error("Start main program")
                    self.indy.play_program(prog_idx=int(self.config["conty_main_program_index"]))
                except:
                    Logger.error("Start main program fail")

        ''' Start program (Warming motion, index=2) '''
        if bb.get("indy_command/play_warming_program"):
            bb.set("indy_command/play_warming_program", False)
            if self.program_state != ProgramState.PROG_RUNNING:
                try:
                    self.indy.play_program(prog_idx=int(self.config["conty_warming_program_index"]))
                except:
                    Logger.error("Start warming program fail")

        ''' Stop program '''
        if bb.get("indy_command/stop_program"):
            bb.set("indy_command/stop_program", False)
            if self.program_state in (ProgramState.PROG_RUNNING, ProgramState.PROG_PAUSING):
                try:
                    Logger.info("Stop program!!")
                    self.indy.stop_program()
                    self.indy.set_speed_ratio(100)
                except:
                    Logger.error("Stop program fail")

        ''' Reset '''
        if bb.get("indy_command/recover"):
            bb.set("indy_command/recover", False)
            self.indy.recover()

    def handle_int_variable(self):
        """
        Command request from FSM by blackboard
        - only work in ReadyIdle mode (Program is Running)
        """
        ''' Reset variables '''
        if bb.get("indy_command/reset_init_var"):
            bb.set("indy_command/reset_init_var", False)
            self.indy.set_int_variable([{'addr': int(self.config["int_var/init/addr"]), 'value': 0}])

        ''' Read Variables: Send int variable from Conty to bb '''
        int_var = self.indy.get_int_variable()['variables']

        self.int_var_init = self.get_intvar_address(int_var, int(self.config["int_var/init/addr"]))
        bb.set("int_var/init/val", self.int_var_init)
        bb.set(f"int_var/putin_done/val", self.get_intvar_address(int_var, int(self.config[f"int_var/putin_done/addr"])))
        bb.set(f"int_var/pickup_done/val", self.get_intvar_address(int_var, int(self.config[f"int_var/pickup_done/addr"])))

        ''' Write Variables: Set Int variable from bb to Conty '''
        deb_value = bb.get("int_var/cmd/val")
        if self.ex_int_cmd != deb_value:
            Logger.info(f"Command I600 : {deb_value}")
            self.ex_int_cmd = deb_value
            
        self.indy.set_int_variable([
            {'addr': int(self.config["int_var/cmd/addr"]), 'value': int(bb.get("int_var/cmd/val"))},
            {'addr': int(self.config["int_var/grip_state/addr"]), 'value': int(bb.get("int_var/grip_state/val"))},
            {'addr': int(self.config["int_var/retry_grip/addr"]), 'value': int(bb.get("int_var/retry_grip/val"))},
            {'addr': int(self.config["int_var/putin_shake/addr"]), 'value': int(bb.get("int_var/putin_shake/val"))},
            {'addr': int(self.config["int_var/shake_num/addr"]), 'value': int(bb.get("int_var/shake_num/val"))},
            {'addr': int(self.config["int_var/shake_break/addr"]), 'value': int(bb.get("int_var/shake_break/val"))}
        ])

    def indy_communication(self):
        ''' Get Indy status '''
        control_data = self.indy.get_control_data()
        program_data = self.indy.get_program_data()
        self.robot_state = control_data["op_state"]
        self.is_sim_mode = control_data["sim_mode"]
        self.robot_running_hour = control_data["running_hours"]
        self.robot_running_min = control_data["running_mins"]
        self.program_state = program_data["program_state"]
        self.program_name = program_data["program_name"]

        q = self.indy.get_control_data()["q"]
        self.is_home_pos = all(self.check_home_min <= a - b <= self.check_home_max for a, b in zip(q, self.home_pos))
        self.is_packaging_pos = all(
            self.check_home_min <= a - b <= self.check_home_max for a, b in zip(q, self.packaging_pos))

        ''' Get Indy ioboard data '''
        do = self.indy.get_do()['signals']
        di = self.indy.get_di()['signals']

        # Buttons
        if self.is_sim_mode:
            self.btn_direct_teaching = self.get_dio_channel(do, self.btn_direct_teaching_ch)
            self.btn_stop = self.get_dio_channel(do, self.btn_stop_ch)
        else:
            self.btn_direct_teaching = self.get_dio_channel(di, self.btn_direct_teaching_ch)
            self.btn_stop = self.get_dio_channel(di, self.btn_stop_ch)

        ''' Get Indy endtool data '''
        endtool_do = self.indy.get_endtool_do()['signals']
        endtool_ai = self.indy.get_endtool_ai()['signals']
        endtool_do_state = next((item['states'] for item in endtool_do if item['port'] == self.endtool_port), None)

        if endtool_do_state == self.gripper_open_command[0]['states']:
            self.is_gripper_open = True     # Open
        else:
            self.is_gripper_open = False    # Close

        self.endtool_ai = next(
            (int(item['voltage']) for item in endtool_ai if item['address'] == self.endtool_ai_channel), None)

        state, close_fail, open_fail = self.gripper_control.update_signal(self.endtool_ai, self.is_gripper_open)
        
        if self.is_sim_mode:
            if self.get_dio_channel(do, 13):
                bb.set("int_var/grip_state/val", GripFailure.SUCCESS)
            elif self.get_dio_channel(do, 14):
                bb.set("int_var/grip_state/val", GripFailure.OPEN_FAIL)
            elif self.get_dio_channel(do, 15):
                bb.set("int_var/grip_state/val", GripFailure.CLOSE_FAIL)
        else:
            if not bb.get("robot/state/handling_grip_failure"):
                if close_fail:
                    bb.set("int_var/grip_state/val", GripFailure.CLOSE_FAIL)
                    Logger.info(f"grip close fail---------------------------------")
                elif open_fail:
                    bb.set("int_var/grip_state/val", GripFailure.OPEN_FAIL)
                else:
                    bb.set("int_var/grip_state/val", GripFailure.SUCCESS)

    def send_data_to_bb(self):
        """
        Set data to bb
            - bb send to App
            - bb sent to FSM
        """
        ''' DI Button '''
        bb.set("indy_state/button_dt", self.btn_direct_teaching)
        bb.set("indy_state/button_stop", self.btn_stop)

        ''' Indy status '''
        indy_data = {
            "robot_state": self.robot_state,
            "is_sim_mode": self.is_sim_mode,
            "program_state": self.program_state,
            "endtool_ai": self.endtool_ai,
            "is_home_pos": self.is_home_pos,
            "is_packaging_pos": self.is_packaging_pos,
            "is_detect_pos": self.is_detect_pos
        }
        bb.set("indy", indy_data)

        ''' App '''
        robot_state_ui = 0
        if self.robot_state in (RobotState.OP_SYSTEM_OFF, RobotState.OP_SYSTEM_ON):
            robot_state_ui = 1  # Off
        elif self.robot_state in (RobotState.OP_VIOLATE, RobotState.OP_VIOLATE_HARD):
            robot_state_ui = 2  # Emergency
        elif self.robot_state in (RobotState.OP_RECOVER_SOFT, RobotState.OP_RECOVER_HARD,
                                  RobotState.OP_BRAKE_CONTROL, RobotState.OP_SYSTEM_RESET,
                                  RobotState.OP_SYSTEM_SWITCH, RobotState.OP_MANUAL_RECOVER):
            robot_state_ui = 3  # Error
        elif self.robot_state in (RobotState.OP_IDLE, RobotState.OP_MOVING,
                                  RobotState.OP_TEACHING, RobotState.OP_COMPLIANCE,
                                  RobotState.TELE_OP):
            robot_state_ui = 4  # Ready
        elif self.robot_state == RobotState.OP_COLLISION:
            robot_state_ui = 5  # Collision

        # Robot state, working time
        bb.set("ui/state/robot_state", robot_state_ui)
        bb.set("ui/state/working_time", self.robot_running_hour)
        bb.set("ui/state/working_minute", self.robot_running_min)

        ''' Direct teaching (On, Off) '''
        if self.robot_state == RobotState.OP_TEACHING:
            bb.set("ui/state/direct_state", 1)  # On
        else:
            bb.set("ui/state/direct_state", 2)  # Off

        ''' Gripper (닫기, 열기) '''
        if self.is_gripper_open:
            bb.set("ui/state/gripper_state", 2)  # 닫기
        else:
            bb.set("ui/state/gripper_state", 1)  # 열기

        if bb.get("ui/command/program_control") == ProgramControl.PROG_START:
            bb.set("ui/reset/program_control", True)
            if self.program_state == ProgramState.PROG_RUNNING:
                self.indy.set_speed_ratio(100)

        match = re.search(r'/index/(\d+)', self.program_name)
        if match:
            program_index = match.group(1)
            if program_index == "1":
                ''' 프로그램 시작/일시정지/정지/다시시작 버튼  '''
                if self.program_state == ProgramState.PROG_IDLE:
                    bb.set("ui/state/program_state", 0)  # Init
                elif self.program_state == ProgramState.PROG_RUNNING:
                    if self.indy.get_motion_data().get("speed_ratio", 100) == 0:
                        bb.set("ui/state/program_state", 3)  # Pause
                    elif self.indy.get_motion_data().get("speed_ratio", 100) == 100:
                        bb.set("ui/state/program_state", 1)  # Start
                elif self.program_state == ProgramState.PROG_STOPPING:
                    bb.set("ui/state/program_state", 4)  # Stop
                    if self.indy.get_motion_data().get("speed_ratio", 100) == 0:
                        bb.set("ui/state/program_state", 3)  # Pause
                    elif self.indy.get_motion_data().get("speed_ratio", 100) == 100:
                        bb.set("ui/state/program_state", 2)  # Resume

            if program_index == "2":
                ''' 예열 On, Off 버튼 '''
                if self.program_state == ProgramState.PROG_IDLE:
                    bb.set("ui/state/warming_state", 0)
                elif self.program_state == ProgramState.PROG_RUNNING:
                    bb.set("ui/state/warming_state", 1)
                elif self.program_state == ProgramState.PROG_STOPPING:
                    bb.set("ui/state/warming_state", 2)
            else:
                bb.set("ui/state/warming_state", 0)