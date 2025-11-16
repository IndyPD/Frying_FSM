from pkg.utils.blackboard import GlobalBlackboard
from .constants import *
from pkg.utils.process_control import Flagger, reraise
from pkg.configs.global_config import GlobalConfig
from neuromeka import IndyDCP3

bb = GlobalBlackboard()
global_config = GlobalConfig()


class FSMStatus:
    def __init__(self):
        self.is_ready = Flagger()
        self.is_emg_pushed = Flagger()
        self.is_error_state = Flagger()
        self.is_moving = Flagger()

        self.reset()

    def reset(self):
        self.is_ready.up()
        self.is_emg_pushed.down()
        self.is_error_state.down()


class RobotActionsContext(ContextBase):
    violation_code: ViolationType
    status = FSMStatus()
    process_manager = None

    def __init__(self, *args, **kwargs):
        ContextBase.__init__(self)
        self.error = Flagger()
        self.is_ready = Flagger()
        self.is_emg_pushed = Flagger()
        self.is_error_state = Flagger()
        self.violation_code = 0
        self.workload_state = 0

        self.indy_state = 0
        self.motion_run_flag = False

        self.in_error_state = False

        bb.set("robot/state/handling_grip_failure", False)
        ''' Current working basket, slot, fryer index '''
        self.basket_index = 0
        self.fryer_index = 0
        self.fsm_index = 0

        ''' Motion triggers '''
        self.trigger_move_from_fryer = False
        self.trigger_move_to_fryer = False
        self.trigger_shake = False
        self.trigger_shift = False
        ''' Motion options '''
        self.putin_shake = 0
        self.shake_num = 0
        self.shake_done_num = 0

    """
    Robot FSM context API    
    """
    def check_violation_or_stop(self):
        ''' Check Error '''
        if self.check_violation():
            return RobotFsmEvent.ERROR_DETECT
        ''' Check program running '''
        if not self.check_program_running():
            Logger.info(f"{get_time()}: Program stopped externally")
            return RobotFsmEvent.STOP
        ''' Check program stop '''
        if self.check_program_stop():
            self.stop_program()
            return RobotFsmEvent.STOP
        return None

    def conty_command_reset(self):
        bb.set("int_var/cmd/val", 0)
        bb.set("robot/state/worktarget",0)

    def app_command_reset(self):
        bb.set("ui/reset/teaching", True)
        bb.set("ui/reset/gripper", True)
        bb.set("ui/reset/warming", True)
        bb.set("ui/reset/reset_robot", True)
        bb.set("ui/reset/program/start", True)

    def motion_command_reset(self):
        self.trigger_move_from_fryer = False
        self.trigger_move_to_fryer = False
        self.trigger_shake = False
        self.trigger_shift = False

    # def check_violation(self):
    #     """ Check violation at every tic
    #         - violation_code
    #         - indy_state
    #     """
    #     self.violation_code = MyViolation.NONE

    #     self.indy_state = RobotState(bb.get("indy")["robot_state"])

    #     if self.indy_state in (RobotState.OP_IDLE, RobotState.OP_MOVING,
    #                                 RobotState.OP_TEACHING, RobotState.OP_COMPLIANCE,
    #                                 RobotState.TELE_OP):

    #         self.violation_code = MyViolation.NONE
    #     else:
    #         if self.indy_state in (RobotState.OP_SYSTEM_OFF, RobotState.OP_SYSTEM_ON,
    #                                     RobotState.OP_STOP_AND_OFF):
    #             self.violation_code = MyViolation.NOT_READY

    #         if self.indy_state in (RobotState.OP_VIOLATE, RobotState.OP_VIOLATE_HARD,
    #                                     RobotState.OP_SYSTEM_RESET, RobotState.OP_SYSTEM_SWITCH):
    #             self.violation_code = MyViolation.VIOLATION

    #         if self.indy_state == RobotState.OP_COLLISION:
    #             self.violation_code = MyViolation.COLLISION

    #         if self.indy_state == RobotState.OP_BRAKE_CONTROL:
    #             self.violation_code = MyViolation.BRAKE_CONTROL

    #         if self.indy_state in (RobotState.OP_RECOVER_HARD, RobotState.OP_RECOVER_SOFT,
    #                                     RobotState.OP_MANUAL_RECOVER):
    #             self.violation_code = MyViolation.RECOVERING

    #         Logger.error(f"{get_time()}: [Robot FSM] Violation detected "
    #                      f"[indy_state={self.indy_state.name}, "
    #                      f"violation_code={self.violation_code.name}]")

    #         return True
    def check_violation(self):
        """ Check violation at every tic
            - violation_code
            - indy_state
        """
        self.violation_code = MyViolation.NONE

        self.indy_state = RobotState(bb.get("indy")["robot_state"])

        # 정상 상태들: OP_SYSTEM_ON과 OP_SYSTEM_RESET을 모두 포함
        if self.indy_state in (RobotState.OP_IDLE, RobotState.OP_MOVING,
                                    RobotState.OP_TEACHING, RobotState.OP_COMPLIANCE,
                                    RobotState.TELE_OP, RobotState.OP_SYSTEM_ON, 
                                    RobotState.OP_SYSTEM_RESET):  # 두 상태 모두 정상으로 처리

            self.violation_code = MyViolation.NONE
            return False  # violation 없음
        else:
            # NOT_READY 상태들: OP_SYSTEM_ON과 OP_SYSTEM_RESET 제거
            if self.indy_state in (RobotState.OP_SYSTEM_OFF, RobotState.OP_STOP_AND_OFF):
                self.violation_code = MyViolation.NOT_READY

            # VIOLATION 상태들: OP_SYSTEM_RESET 제거
            if self.indy_state in (RobotState.OP_VIOLATE, RobotState.OP_VIOLATE_HARD,
                                        RobotState.OP_SYSTEM_SWITCH):  # OP_SYSTEM_RESET 제거
                self.violation_code = MyViolation.VIOLATION

            # COLLISION 상태
            if self.indy_state == RobotState.OP_COLLISION:
                self.violation_code = MyViolation.COLLISION

            # BRAKE_CONTROL 상태
            if self.indy_state == RobotState.OP_BRAKE_CONTROL:
                self.violation_code = MyViolation.BRAKE_CONTROL

            # RECOVERING 상태들
            if self.indy_state in (RobotState.OP_RECOVER_HARD, RobotState.OP_RECOVER_SOFT,
                                        RobotState.OP_MANUAL_RECOVER):
                self.violation_code = MyViolation.RECOVERING

            # violation이 발생한 경우에만 로그 출력
            if self.violation_code != MyViolation.NONE:
                Logger.error(f"{get_time()}: [Robot FSM] Violation detected "
                            f"[indy_state={self.indy_state.name}, "
                            f"violation_code={self.violation_code.name}]")

            return True

    def check_program_running(self):
        indy_status = bb.get("indy")
        prog_state = indy_status["program_state"]
        robot_state = indy_status["robot_state"]

        # The robot is considered to be running not only when the program state is PROG_RUNNING,
        # but also when it is physically moving. This prevents the FSM from incorrectly
        # stopping the robot during motion commands where the 'running' flag might be transiently false.
        # if prog_state == ProgramState.PROG_RUNNING or robot_state == RobotState.OP_MOVING:
        # prog_state = bb.get("indy")["program_state"]
        # temp_log_data = bb.get("indy") 
        
        if prog_state == ProgramState.PROG_RUNNING :
            return True
        else:
            Logger.info(f"{get_time()}: Program is NOT running {ProgramState(prog_state).name}.")
            return False

    def check_program_stop(self):
        if bb.get("ui/command/program_control") == ProgramControl.PROG_STOP:
            bb.set("ui/reset/program_control", True)
            Logger.info(f"{get_time()}: Program stopped by App.")
            return True

        if bb.get("indy_state/button_stop") == DigitalState.ON_STATE:
            Logger.info(f"{get_time()}: Program stopped by Button.")
            return True

        return False

    def robot_state(self):
        return bb.get("indy")["robot_state"]

    def program_state(self):
        return bb.get("indy")["program_state"]

    def is_sim_mode(self):
        return bb.get("indy")["is_sim_mode"]

    def is_home_pos(self):
        return bb.get("indy")["is_home_pos"]

    def is_packaging_pos(self):
        return bb.get("indy")["is_packaging_pos"]

    def is_detect_pos(self):
        return bb.get("indy")["is_detect_pos"]

    def direct_teaching(self, onoff):
        if onoff:
            bb.set("indy_command/direct_teaching_on", True)
        else:
            bb.set("indy_command/direct_teaching_off", True)

    def gripper_control(self, open):
        if open:
            bb.set("indy_command/gripper_open", True)
        else:
            bb.set("indy_command/gripper_close", True)

    def stop_motion(self):
        bb.set("indy_command/stop_motion", True)

    def go_home_pos(self):
        bb.set("indy_command/go_home", True)

    def go_packaging_pos(self):
        bb.set("indy_command/go_packaging", True)

    def play_program(self):
        bb.set("indy_command/play_program", True)

        start = time.time()
        while time.time() - start < 10.0:
            time.sleep(0.1)
            Logger.info(f"{get_time()}: Wait for main program running")
            if self.check_program_running():
                break

    def play_warming_program(self):
        bb.set("indy_command/play_warming_program", True)

        start = time.time()
        while time.time() - start < 10.0:
            time.sleep(0.1)
            Logger.info(f"{get_time()}: Wait for warming  program running")
            if self.check_program_running():
                break

    def stop_program(self):
        Logger.info("[DEBUG] stop_program: Sending stop command to Conty.")
        bb.set("indy_command/stop_program", True)

        # Conty 프로그램이 PROG_IDLE 상태가 될 때까지 최대 5초간 대기
        start_time = time.time()
        wait_timeout = 10.0
        while time.time() - start_time < wait_timeout:
            current_state = self.program_state()
            if current_state == ProgramState.PROG_IDLE:
                Logger.info(f"[DEBUG] stop_program: Conty program confirmed to be in IDLE state.")
                break
            Logger.info(f"[DEBUG] stop_program: Waiting for Conty program to stop. Current state: {ProgramState(current_state).name}")
            time.sleep(0.2)
        else:
            Logger.warn(f"[DEBUG] stop_program: Timeout waiting for Conty program to stop. Proceeding with reset anyway.")

        # if self.process_manager:
        #     Logger.info("[DEBUG] stop_program: Resetting all FSMs and motion.")
        #     self.process_manager.reset_all_fsms()
        #     self.process_manager.reset_motion()
        #     Logger.info("[DEBUG] stop_program: Reset complete.")

    def recover_robot(self):
        bb.set("indy_command/recover", True)

    ''' 
    Recipe FSM related 
    '''
    def motion_done_logic(self, motion):
        ''' Motion done logic
        1. Conty CMD reset: to prevent Conty tree loop execute same motion twice
        2. Trigger Recipe FSM event, and wait Recipe FSM transition done
        3. Motion reset to trigger priority start next task computation
        '''
        ''' Conty CMD reset '''
        bb.set("int_var/cmd/val", 0)

        '''  Recipe FSM 모션 완료 트리거 → Recipe FSM 상태 천이 대기 (basket_idx = Recipe FSM index) '''
        prev_state = bb.get(f"recipe/basket{self.basket_index}/state")
        bb.set(f"recipe/command/{motion}_done", self.basket_index)
        self.wait_for_recipe_fsm_trainsition_done(prev_state)

        ''' Motion Reset: Priority schedule → Robot '''
        self.motion_command_reset()

    def home_pass_logic(self, current_motion):
        ''' Trigger to compute new priority task after 1.5 sec waiting '''
        time.sleep(1.5)
        if current_motion == "move_to_fryer":
            if self.trigger_move_to_fryer:
                bb.set("recipe/command/move_to_fryer_done", 0)
                return RobotFsmEvent.RUN_BASKET_TO_FRYER
            elif self.trigger_move_from_fryer:
                return RobotFsmEvent.RUN_BASKET_FROM_FRYER
            elif self.trigger_shake:
                return RobotFsmEvent.RUN_SHAKE
            elif self.trigger_shift:
                return RobotFsmEvent.RUN_SHIFT
            else:
                return RobotFsmEvent.DONE
        elif current_motion == "move_from_fryer":
            if self.trigger_move_to_fryer:
                return RobotFsmEvent.RUN_BASKET_TO_FRYER
            elif self.trigger_move_from_fryer:
                bb.set("recipe/command/move_from_fryer_done", 0)
                return RobotFsmEvent.RUN_BASKET_FROM_FRYER
            elif self.trigger_shake:
                return RobotFsmEvent.RUN_SHAKE
            elif self.trigger_shift:
                return RobotFsmEvent.RUN_SHIFT            
            else:
                # TODO: Why?
                bb.set("int_var/cmd/val", int(ContyCommand.NONE))
                return RobotFsmEvent.DONE
        elif current_motion == "shake":
            if self.trigger_move_to_fryer:
                return RobotFsmEvent.RUN_BASKET_TO_FRYER
            elif self.trigger_move_from_fryer:
                return RobotFsmEvent.RUN_BASKET_FROM_FRYER
            elif self.trigger_shake:
                # TODO: Why?
                bb.set("indy_command/reset_init_var", True)
                bb.set("recipe/command/shake_done", 0)
                return RobotFsmEvent.RUN_SHAKE
            elif self.trigger_shift:
                return RobotFsmEvent.RUN_SHIFT
            else:
                return RobotFsmEvent.DONE
        elif current_motion == "shift":
            if self.trigger_move_to_fryer:
                return RobotFsmEvent.RUN_BASKET_TO_FRYER
            elif self.trigger_move_from_fryer:
                return RobotFsmEvent.RUN_BASKET_FROM_FRYER
            elif self.trigger_shake:
                return RobotFsmEvent.RUN_SHAKE
            elif self.trigger_shift:
                return RobotFsmEvent.RUN_SHIFT
            else:
                return RobotFsmEvent.DONE
        else:
            return RobotFsmEvent.DONE

    def wait_for_recipe_fsm_trainsition_done(self, prev_state, timeout=2.0):
        key = f"recipe/basket{self.basket_index}/state"
        start = time.time()
        while time.time() - start < timeout:
            new_state = bb.get(key)
            # print(f"[Robot FSM] Wait Recipe FSM {self.basket_index} change {new_state}/{prev_state}")
            if new_state != prev_state:
                return True
            time.sleep(0.05)
        Logger.warn(f"[Robot FSM] FSM state for basket {self.basket_index} did not change in time.")
        return False

    def wait_for_popup_done(self):
        while True:
            time.sleep(0.2)
            if bb.get("ui/command/grip_fail_popup/done"):
                bb.set("ui/reset/grip_fail_popup/done", True)
                bb.set("ui/state/grip_fail_popup", 0)
                return
        # start = time.time()
        # while time.time() - start < 3:
        #     time.sleep(0.2)
        #     if bb.get("ui/command/grip_fail_popup/done"):
        #         bb.set("ui/reset/grip_fail_popup/done", True)
        #         bb.set("ui/state/grip_fail_popup", 0)
        #         return

    def grip_close_fail_fool_proof(self):
        ''' 파지 실패 기능
        Conty tree:

        SetTool('grip_close')
        SetVar(grip_fail_count = 0) --> grip_fail_count 변수 추가 및 0으로 초기화
        Loop (always)
            Sleep(0.1)    --> COCO는 0.5초 적용, 테스트 필요, 원래 교촌은 0.1초 였나?
            If (grip_state == 1)
                SetVar(grip_fail_count = 0)
                Break
            Elif (grip_state == 2)
                [SetVar(grip_fail_count += 1)] --> grip_fail_count +1
                SetSignal (buzzer on)
                SetTool('grip_open')
                MoveL (pick_back)
                If (grip_fail_count == 1) ---> 당기는 모션 1회만 시도, 당기고 파지 모션 수행
                    SetTool('grip_close')
                    MoveLRel(align) --> non-prehensile manipulation
                    SetTool('grip_open')
                    MoveL (pick)
                    SetTool('grip_close')
                    SetSignal(buzzer off)
                    Continue
                Else If (grip_fail_count > 1) ---> 당기고 나서도 실패하면 retry 수동 버튼 누르길 기다림
                    SetSignal(buzzer off)
            Loop (always)
                Sleep(1.0)
                If (retry_grip == 1)
                    SetVar(retry_grip = 0)
                    MoveL (pick)
                    SetTool('grip_close')
                    Break
        (Next command)
        '''
        ''' 파지 실패 기능'''

        # if True :
        #     if bb.get("int_var/grip_state/val") == GripFailure.CLOSE_FAIL:
        #         bb.set("int_var/retry_grip/val", 0)
        #         # bb.set("indy_command/buzzer_on", True)
        #         bb.set("ui/state/grip_fail_popup", 1)
        #         self.wait_for_popup_done()
        #         Logger.info(f"{get_time()}: [Robot FSM] Grip close fail, wait for retry")
        #         time.sleep(1.0)
        #         # bb.set("indy_command/buzzer_off", True)

        #         start = time.time()
        #         while time.time() - start < 10:
        #             time.sleep(0.2)
        #             if bb.get("ui/command/grip_retry"):
        #                 Logger.info(f"{get_time()}: [Robot FSM] Start retry")
        #                 bb.set("ui/reset/grip_retry", True)
        #                 bb.set("int_var/retry_grip/val", 1)
        #                 bb.set("int_var/grip_state/val", GripFailure.SUCCESS) #상태를 성공으로 초기화

        #                 #--- 2. 잠금해제 ----
        #                 bb.set("robot/state/handling_grip_failure", False)
        #                 return True
        #         # --- 3. 타임아웃 시에도 잠금 해제 ---
        #         # bb.set("ui/command/grip_fail_popup/done", True)
        #         bb.set("ui/state/grip_fail_popup", 0)
        #         bb.set("ui/reset/grip_fail_popup/done", True)
        #         # bb.set("ui/state/grip_fail_popup", 0)
        #         # self.wait_for_popup_done()
        #         bb.set("ui/reset/grip_retry", True)
        #         bb.set("int_var/retry_grip/val", 1)
        #         bb.set("int_var/grip_state/val", GripFailure.SUCCESS) #상태를 성공으로 초기화

        #         bb.set("robot/state/handling_grip_failure", False)
        #         return True
            
        # if True :
        #     if bb.get("int_var/grip_state/val") == GripFailure.CLOSE_FAIL:
        #         Logger.info(f"{get_time()}: [Robot FSM] Grip close fail detected. Waiting 60s for user retry or auto-retry.")

        #         # 1. 실패 처리 시작을 알리는 잠금 설정
        #         bb.set("robot/state/handling_grip_failure", True)
        #         bb.set("int_var/retry_grip/val", 0)
        #         # bb.set("indy_command/buzzer_on", True)
                
        #         # 2. UI에 파지 실패 팝업 표시
        #         bb.set("ui/state/grip_fail_popup", 1)

        #         self.wait_for_popup_done()
        #         user_pressed_retry = False
        #         Logger.info(f"{get_time()}: [Robot FSM] Grip close fail, wait for retry")
        #         # time.sleep(1.0)
        #         # bb.set("indy_command/buzzer_off", True)

        #         start = time.time()
        #         while time.time() - start < 10:
        #             time.sleep(0.2)
        #             if bb.get("ui/command/grip_retry"):
        #                 user_pressed_retry = True
        #                 bb.set("ui/reset/grip_retry", True)
        #                 Logger.info(f"{get_time()}: [Robot FSM] User requested retry.")
        #                 break
        #                 # bb.set("int_var/retry_grip/val", 1)
        #                 # bb.set("int_var/grip_state/val", GripFailure.SUCCESS) #상태를 성공으로 초기화

        #                 #--- 2. 잠금해제 ----
        #                 # bb.set("robot/state/handling_grip_failure", False)
        #         if not user_pressed_retry :
        #             Logger.info(f"{get_time()} : [Robot FSM] Timeout reached. Initiating auto-retry.")

        #         # bb.set("ui/state/grip_fail_popup", 0)
        #         bb.set("ui/command/grip_fail_popup/done", 0)
        #         bb.set("int_var/retry_grip/val", 1)
        #         bb.set("int_var/grip_state/val", GripFailure.SUCCESS)
        #         bb.set("robot/state/handling_grip_failure", False)
        #         return True # 재시도가 시작되었음을 알림.
        #     return False # 파지 실패가 아니면 False 반환
        
                # --- 3. 타임아웃 시에도 잠금 해제 ---
                # bb.set("robot/state/handling_grip_failure", False)
                # return False
        if True :
            if bb.get("int_var/grip_state/val") == GripFailure.CLOSE_FAIL:
                bb.set("int_var/retry_grip/val", 0)
                bb.set("ui/state/grip_fail_popup", 1)  # 1. 팝업을 띄웁니다.
                Logger.info(f"{get_time()}: [Robot FSM] Grip close fail, wait for retry")
            
                start_time = time.time()
                user_pressed_retry = False
            
                # 2. 사용자 입력을 10초 동안 기다립니다.
                while time.time() - start_time < 10:
                    if bb.get("ui/command/grip_retry"):
                        Logger.info(f"{get_time()}: [Robot FSM] User requested retry.")
                        user_pressed_retry = True
                        break
                    time.sleep(0.2)
            
                if not user_pressed_retry:
                    Logger.info(f"{get_time()}: [Robot FSM] Timeout reached. Initiating auto-retry.")
            
                # 3. (가장 중요) 팝업을 직접 닫습니다.
                bb.set("ui/state/grip_fail_popup", 0)
                # 만약을 위해 UI의 'done' 상태도 리셋해줍니다.
                bb.set("ui/reset/grip_fail_popup/done", True)
            
                # 4. 재시도를 시작합니다.
                bb.set("ui/reset/grip_retry", True)
                bb.set("int_var/retry_grip/val", 1)
                bb.set("int_var/grip_state/val", GripFailure.SUCCESS)
                bb.set("robot/state/handling_grip_failure", False)
                
                return True
            
            return False 
            # 1. 파지 실패 상태가 아니면, 아무것도 안 하고 즉시 함수를 종료합니다.
            # if bb.get("int_var/grip_state/val") != GripFailure.CLOSE_FAIL:
            #     return False

            # # 2. 파지 실패 상태라면, 성공할 때까지 계속 반복하는 루프를 시작합니다.
            # Logger.info(f"{get_time()}: [Robot FSM] Grip close fail detected. Starting continuous retry logic.")
            # bb.set("robot/state/handling_grip_failure", True) # 실패 처리 시작 (잠금)

            # while bb.get("int_var/grip_state/val") == GripFailure.CLOSE_FAIL:
            #     # --- 루프의 시작 ---
            #     bb.set("int_var/retry_grip/val", 0)
            #     bb.set("ui/state/grip_fail_popup", 1) # 팝업 표시

            #     Logger.info(f"{get_time()}: Waiting 10s for user intervention or auto-retry.")
            #     start_time = time.time()
            #     user_pressed_retry = False

            #     # 3. 10초 동안 사용자의 '재시도' 버튼 입력을 기다립니다.
            #     while time.time() - start_time < 10:
            #         if bb.get("ui/command/grip_retry"):
            #             Logger.info(f"{get_time()}: [Robot FSM] User requested retry.")
            #             user_pressed_retry = True
            #             break
            #         time.sleep(0.2)

            #     # 4. 팝업을 닫습니다.
            #     bb.set("ui/state/grip_fail_popup", 0)
            #     bb.set("ui/reset/grip_fail_popup/done", True) # UI의 done 상태도 리셋

            #     if not user_pressed_retry:
            #         Logger.info(f"{get_time()}: [Robot FSM] Timeout reached. Initiating auto-retry.")

            #     # 5. Conty Tree에 재시도를 하라는 신호를 보냅니다.
            #     bb.set("ui/reset/grip_retry", True)
            #     bb.set("int_var/retry_grip/val", 1)
                
            #     # 중요: 여기서 grip_state를 SUCCESS로 바꾸지 않습니다.
            #     # Conty Tree가 실제로 재파지를 시도한 후, 그 결과에 따라
            #     # grip_state 값을 SUCCESS 또는 FAIL로 다시 업데이트할 것입니다.

            #     # 6. Conty Tree가 재시도하고 상태를 업데이트할 시간을 줍니다.
            #     Logger.info(f"{get_time()}: Waiting for retry attempt result...")
            #     time.sleep(1.0) # 실제 재시도 동작에 필요한 시간 (조정 가능)
                
            #     # --- 루프의 끝으로 돌아가 grip_state를 다시 확인합니다 ---

            # # 7. 루프를 빠져나왔다는 것은 파지에 성공했다는 의미입니다.
            # Logger.info(f"{get_time()}: [Robot FSM] Grip success confirmed.")
            # bb.set("robot/state/handling_grip_failure", False) # 실패 처리 종료 (잠금 해제)
            # return True # 처리가 완료되었음을 알림

        else :
            if bb.get("int_var/grip_state/val") == GripFailure.CLOSE_FAIL:
                Logger.info(f"{get_time()}: [Robot FSM] Grip close fail, wait for retry")
                time.sleep(1.0)

                start = time.time()
                while time.time() - start < 10:
                    time.sleep(0.2)
                    if self.in_error_state:
                        self.in_error_state = False
                        break
                    if bb.get("int_var/retry_grip/val") > 0:
                        Logger.info(f"{get_time()}: [Robot FSM] Start retry (close fail)")
                        return True
                return False

    def grip_open_fail_fool_proof(self):
        ''' 오픈 실패 기능: Conty Tree
        SetTool('grip_open')
        SetVar(open_fail_count = 0) --> open_fail_count 변수 추가 및 0으로 초기화
        Loop (always)
            Sleep(0.1)
            If (grip_state == 1)                
                SetVar(open_fail_count = 0)
                Break            
            Else If (grip_state == 3)
                SetVar(open_fail_count += 1) --> open_fail_count +1                
                SetSignal (buzzer on)                            
                SetTool('grip_close')
                Sleep(0.2)
                SetTool('grip_open')
                SetSignal (buzzer off)
                If (open_fail_count > 4)
                    QuitProgram
        (Next command...)
        '''
        # if bb.get("int_var/grip_state/val") == GripFailure.OPEN_FAIL:
        #     bb.set("int_var/retry_grip/val", 0)
        #     bb.set("indy_command/buzzer_on", True)
        #     bb.set("ui/state/grip_fail_popup", 2)
        #     self.wait_for_popup_done()
        #     Logger.info(f"{get_time()}: [Robot FSM] Grip open fail during MOVE_TO_FRYER motion")
        #     time.sleep(0.3)
        #     bb.set("indy_command/buzzer_off", True)

        #     start = time.time()
        #     while time.time() - start < 60:
        #         print("Wait for retry")
        #         time.sleep(0.2)
        #         if bb.get("ui/command/grip_retry"):
        #             bb.set("ui/reset/grip_retry", True)
        #             bb.set("int_var/retry_grip/val", 1)
        #             return True
        #     return False

        # return False

        if bb.get("int_var/grip_state/val") == GripFailure.OPEN_FAIL:
            bb.set("int_var/retry_grip/val", 0)
            Logger.info(f"{get_time()}: [Robot FSM] Grip open fail during, wait for retry")
            time.sleep(1.0)

            start = time.time()
            while time.time() - start < 10:
                time.sleep(0.2)
                if self.in_error_state:
                    self.in_error_state = False
                    break

                if bb.get("int_var/retry_grip/val") > 0:
                    Logger.info(f"{get_time()}: [Robot FSM] Grip open sucess")
                    return True
            Logger.info(f"{get_time()}: [Robot FSM] Grip open fail")
            return False
        Logger.info(f"{get_time()}: [Robot FSM] Grip open fail")
        return False

    ''' 
    Conty motion command (Ies)
    '''
    def move_ready_pos(self):
        motion = "move_to_ready"
        if bb.get("int_var/init/val") == ContyCommand.HOME + ContyCommand.INIT_ADD_VALUE:
            ''' Motion done '''
            Logger.info(f"{get_time()}: [Robot FSM] Finish motion {motion}")
            bb.set("int_var/cmd/val", int(ContyCommand.NONE))
            return RobotFsmEvent.DONE
        elif bb.get("int_var/cmd/val") == 0:
            ''' Motion start '''
            isready = bb.get("recipe/state/ready")
            Logger.info(f"{get_time()}: [Robot FSM] Start motion {isready} {motion}  ")
            if isready :
                bb.set("int_var/cmd/val", int(ContyCommand.HOME))
                return RobotFsmEvent.NONE
            else :
                return RobotFsmEvent.DONE
                
        else:
            ''' During motion '''
            return RobotFsmEvent.NONE

    def basket_to_fryer(self):
        ''' Move basket to fryer '''
        motion = "move_to_fryer"

        bb.set("robot/state/worktarget",self.basket_index)

        start_cond = int(ContyCommand.MOVE_BASKET_TO_FRYER) + self.basket_index
        finish_cond = start_cond + ContyCommand.INIT_ADD_VALUE

        if (self.motion_run_flag and bb.get("int_var/init/val") == finish_cond):
            ''' Motion Done logic '''
            self.motion_run_flag = False

            Logger.info(f"{get_time()}: [Robot FSM] Finish motion {motion} with "
                        f"[basket {self.basket_index}, fryer {self.fryer_index}]")
            # TODO ERrro occur
            self.motion_done_logic(motion)

            if global_config.get("home_pass_mode"):
                # Logger.info(f"home pass : {self.home_pass_logic(motion)}")
                return self.home_pass_logic(motion)
            else:
                bb.set("robot/state/worktarget",0)
                return RobotFsmEvent.DONE

        elif bb.get("int_var/cmd/val") == 0:
            ''' Motion start '''
            Logger.info(f"{get_time()}: [Robot FSM] Start motion {motion} with "
                        f"[basket {self.basket_index}, fryer {self.fryer_index}]")
            bb.set("int_var/cmd/val", start_cond)
            Logger.info(f"basket_to_fryer {start_cond}")
            self.motion_run_flag = True
            return RobotFsmEvent.NONE
        else:
            ''' During motion: 투입 모션 중 파지/오픈 실패 '''
            if global_config.get("grip_close_fail_fool_proof"):
                self.grip_close_fail_fool_proof()

            if global_config.get("grip_open_fail_fool_proof"):
                self.grip_open_fail_fool_proof()

    def basket_from_fryer(self):
        motion = "move_from_fryer"

        bb.set("robot/state/worktarget",self.basket_index)
        start_cond = int(ContyCommand.MOVE_BASKET_FROM_FRYER) + self.fryer_index*10 + self.basket_index
        finish_cond = start_cond + ContyCommand.INIT_ADD_VALUE
        

        if (self.motion_run_flag and bb.get("int_var/init/val") == finish_cond):
            ''' Motion Done logic '''
            self.motion_run_flag = False

            Logger.info(f"{get_time()}: [Robot FSM] Finish motion {motion} with "
                        f"[basket {self.basket_index}, fryer {self.fryer_index}]")

            self.motion_done_logic(motion)

            if global_config.get("home_pass_mode"):
                return self.home_pass_logic(motion)
            else:
                time.sleep(0.3)
                bb.set("robot/state/worktarget",0)
                return RobotFsmEvent.DONE

        elif bb.get("int_var/cmd/val") == 0:
            ''' Motion start '''
            Logger.info(f"{get_time()}: [Robot FSM] Start motion {motion} with "
                        f"[basket {self.basket_index}, fryer {self.fryer_index}]")
            Logger.debug(f"{get_time()}: [Robot FSM] Current int_var/cmd/val: {bb.get('int_var/cmd/val')}, Setting to: {start_cond}")	
            bb.set("int_var/cmd/val", start_cond)
            Logger.info(f"basket_from_fryer {start_cond}")
            self.motion_run_flag = True
            return RobotFsmEvent.NONE
        else:
            ''' During motion '''
            if global_config.get("grip_close_fail_fool_proof"):
                self.grip_close_fail_fool_proof()

            if global_config.get("grip_open_fail_fool_proof"):
                self.grip_open_fail_fool_proof()

    def shake_basket(self):
        motion = "shake"
        bb.set("robot/state/worktarget",self.basket_index)
        start_cond = int(ContyCommand.SHAKE_BASKET) + self.fryer_index*10 + self.basket_index
        finish_cond = start_cond + ContyCommand.INIT_ADD_VALUE
        

        if (self.motion_run_flag and bb.get("int_var/init/val") == finish_cond):
            ''' Motion Done logic '''
            self.motion_run_flag = False

            Logger.info(f"{get_time()}: [Robot FSM] Finish motion {motion} with "
                        f"[basket {self.basket_index}, fryer {self.fryer_index}]")

            self.motion_done_logic(motion)

            if global_config.get("home_pass_mode"):
                return self.home_pass_logic(motion)
            else:
                bb.set("robot/state/worktarget",0)
                return RobotFsmEvent.DONE

        elif bb.get("int_var/cmd/val") == 0:
            Logger.info(f"{get_time()}: [Robot FSM] Start motion {motion} with "
                        f"[basket {self.basket_index}, fryer {self.fryer_index}]")
            bb.set("int_var/cmd/val", start_cond)
            Logger.info(f"shake_basket {start_cond}")
            self.motion_run_flag = True
            return RobotFsmEvent.NONE
        else:
            ''' During motion '''
            if global_config.get("grip_close_fail_fool_proof"):
                self.grip_close_fail_fool_proof()

            if global_config.get("grip_open_fail_fool_proof"):
                self.grip_open_fail_fool_proof()

            # TODO shake break 구현 (매뉴 추가 입력 받으면, break 던지기)


    def shift_basket(self):
        motion = "shift_basket"
        bb.set("robot/state/worktarget",self.basket_index)

        start_cond = int(ContyCommand.SHIFT_BASKET) + self.basket_index
        finish_cond = start_cond + ContyCommand.INIT_ADD_VALUE
        
        # Logger.info(f"shift_basket {start_cond}")

        if (self.motion_run_flag and bb.get("int_var/init/val") == finish_cond):
            ''' Motion Done logic '''
            self.motion_run_flag = False

            Logger.info(f"{get_time()}: [Robot FSM] Finish motion {motion} with "
                        f"[basket {self.basket_index}, fryer {self.fryer_index}]")

            self.motion_done_logic(motion)

            if global_config.get("home_pass_mode") and False:
                # Logger.info(f"global_config : {motion}")
                return self.home_pass_logic(motion)
            # else:
            Logger.info(f"Done : {motion}")
            bb.set("robot/state/worktarget",0)
            return RobotFsmEvent.DONE

        elif bb.get("int_var/cmd/val") == 0:
            Logger.info(f"{get_time()}: [Robot FSM] Start motion {motion} with "
                        f"[basket {self.basket_index}, fryer {self.fryer_index}]")
            bb.set("int_var/cmd/val", start_cond)
            Logger.info(f"shift_basket {start_cond}")
            self.motion_run_flag = True
            return RobotFsmEvent.NONE
        else:
            ''' During motion '''
            if global_config.get("grip_close_fail_fool_proof"):
                self.grip_close_fail_fool_proof()

            if global_config.get("grip_open_fail_fool_proof"):
                self.grip_open_fail_fool_proof()

            # TODO shake break 구현 (매뉴 추가 입력 받으면, break 던지기)
            
