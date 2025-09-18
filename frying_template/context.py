from pkg.utils.blackboard import GlobalBlackboard
from .constants import *
from pkg.utils.process_control import Flagger, reraise
from configs.global_config import GlobalConfig

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

        self.clean_basket_index = 0

        ''' Current working basket, slot, fryer index '''
        self.basket_index = 0
        self.fryer_index = 0
        self.slot_index = 0

        ''' Motion triggers '''
        self.trigger_move_from_fryer = False
        self.trigger_move_to_fryer = False
        self.trigger_shake = False
        self.trigger_shift = False
        self.trigger_clean = False
        ''' Motion options '''
        self.drain_num = 0
        self.shake_num = 0
        self.shake_option = 0

    """
    Robot FSM context API    
    """
    def check_violation_or_stop(self):
        ''' Check Error '''
        if self.check_violation():
            return FsmEvent.ERROR_DETECT
        ''' Check program running '''
        if not self.check_program_running():
            Logger.info(f"{get_time()}: Program stopped externally")
            return FsmEvent.STOP
        ''' Check program stop '''
        if self.check_program_stop():
            self.stop_program()
            return FsmEvent.STOP
        return None

    def conty_command_reset(self):
        bb.set("int_var/cmd/val", 0)

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
        self.trigger_clean = False
        self.fryer_index = 0

    def check_violation(self):
        """ Check violation at every tic
            - violation_code
            - indy_state
        """
        self.violation_code = MyViolation.NONE

        self.indy_state = RobotState(bb.get("indy")["robot_state"])

        if self.indy_state in (RobotState.OP_IDLE, RobotState.OP_MOVING,
                                    RobotState.OP_TEACHING, RobotState.OP_COMPLIANCE,
                                    RobotState.TELE_OP):

            self.violation_code = MyViolation.NONE
        else:
            if self.indy_state in (RobotState.OP_SYSTEM_OFF, RobotState.OP_SYSTEM_ON,
                                        RobotState.OP_STOP_AND_OFF):
                self.violation_code = MyViolation.NOT_READY

            if self.indy_state in (RobotState.OP_VIOLATE, RobotState.OP_VIOLATE_HARD,
                                        RobotState.OP_SYSTEM_RESET, RobotState.OP_SYSTEM_SWITCH):
                self.violation_code = MyViolation.VIOLATION

            if self.indy_state == RobotState.OP_COLLISION:
                self.violation_code = MyViolation.COLLISION

            if self.indy_state == RobotState.OP_BRAKE_CONTROL:
                self.violation_code = MyViolation.BRAKE_CONTROL

            if self.indy_state in (RobotState.OP_RECOVER_HARD, RobotState.OP_RECOVER_SOFT,
                                        RobotState.OP_MANUAL_RECOVER):
                self.violation_code = MyViolation.RECOVERING

            Logger.error(f"{get_time()}: [Robot FSM] Violation detected "
                         f"[indy_state={self.indy_state.name}, "
                         f"violation_code={self.violation_code.name}]")

            return True

    def check_program_running(self):
        prog_state = bb.get("indy")["program_state"]
        if prog_state == ProgramState.PROG_RUNNING:
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
        while time.time() - start < 3.0:
            time.sleep(0.1)
            Logger.info(f"{get_time()}: Wait for main program running")
            if self.check_program_running():
                break

    def play_warming_program(self):
        bb.set("indy_command/play_warming_program", True)

        start = time.time()
        while time.time() - start < 3.0:
            time.sleep(0.1)
            Logger.info(f"{get_time()}: Wait for warming  program running")
            if self.check_program_running():
                break


    def stop_program(self):
        bb.set("indy_command/stop_program", True)

    def recover_robot(self):
        bb.set("indy_command/recover", True)

    ''' 
    Recipe FSM related 
    '''
    def motion_done_logic(self, motion, basket_idx):
        ''' Motion done logic
        1. Conty CMD reset: to prevent Conty tree loop execute same motion twice
        2. Trigger Recipe FSM event, and wait Recipe FSM transition done
        3. Motion reset to trigger priority start next task computation
        '''
        ''' Conty CMD reset '''
        bb.set("int_var/cmd/val", 0)

        '''  Recipe FSM 모션 완료 트리거 → Recipe FSM 상태 천이 대기 (basket_idx = Recipe FSM index) '''
        prev_state = bb.get(f"recipe/basket{basket_idx}/state")
        bb.set(f"recipe/command/{motion}_done", basket_idx)
        self.wait_for_recipe_fsm_trainsition_done(basket_idx, prev_state)

        ''' Motion Reset: Priority schedule → Robot '''
        self.motion_command_reset()

    def home_pass_logic(self, current_motion):
        ''' Trigger to compute new priority task after 1.5 sec waiting '''
        time.sleep(1.5)
        if current_motion == "move_to_fryer":
            if self.trigger_move_to_fryer:
                bb.set("recipe/command/move_to_fryer_done", 0)
                return FsmEvent.RUN_BASKET_TO_FRYER
            elif self.trigger_move_from_fryer:
                return FsmEvent.RUN_BASKET_FROM_FRYER
            elif self.trigger_shake:
                return FsmEvent.RUN_SHAKE
            else:
                return FsmEvent.DONE
        elif current_motion == "move_from_fryer":
            if self.trigger_move_to_fryer:
                return FsmEvent.RUN_BASKET_TO_FRYER
            elif self.trigger_move_from_fryer:
                bb.set("recipe/command/move_from_fryer_done", 0)
                return FsmEvent.RUN_BASKET_FROM_FRYER
            elif self.trigger_shake:
                return FsmEvent.RUN_SHAKE
            else:
                # TODO: Why?
                bb.set("int_var/cmd/val", int(ContyCommand.NONE))
                return FsmEvent.DONE
        elif current_motion == "shake":
            if self.trigger_move_to_fryer:
                return FsmEvent.RUN_BASKET_TO_FRYER
            elif self.trigger_move_from_fryer:
                return FsmEvent.RUN_BASKET_FROM_FRYER
            elif self.trigger_shake:
                # TODO: Why?
                bb.set("indy_command/reset_init_var", True)
                bb.set("recipe/command/shake_done", 0)
                return FsmEvent.RUN_SHAKE
            else:
                return FsmEvent.DONE
        else:
            return FsmEvent.DONE


    def wait_for_recipe_fsm_trainsition_done(self, basket_idx, prev_state, timeout=2.0):
        key = f"recipe/basket{basket_idx}/state"
        start = time.time()
        while time.time() - start < timeout:
            new_state = bb.get(key)
            print(f"Wait Recipe FSM {basket_idx} change {new_state}/{prev_state}")
            if new_state != prev_state:
                return True
            time.sleep(0.05)
        Logger.warn(f"[Robot FSM] FSM state for basket {basket_idx} did not change in time.")
        return False

    def wait_for_popup_done(self):
        start = time.time()
        while time.time() - start < 3:
            time.sleep(0.2)
            if bb.get("ui/command/grip_fail_popup/done"):
                bb.set("ui/reset/grip_fail_popup/done", True)
                bb.set("ui/state/grip_fail_popup", 0)
                return

    def grip_close_fail_fool_proof(self):
        ''' 파지 실패 기능'''
        if bb.get("int_var/grip_state/val") == GripFailure.CLOSE_FAIL:
            bb.set("int_var/retry_grip/val", 0)
            bb.set("indy_command/buzzer_on", True)
            bb.set("ui/state/grip_fail_popup", 1)
            self.wait_for_popup_done()
            Logger.info(f"{get_time()}: [Robot FSM] Grip close fail, wait for retry")
            time.sleep(1.0)
            bb.set("indy_command/buzzer_off", True)

            start = time.time()
            while time.time() - start < 60:
                time.sleep(0.2)
                if bb.get("ui/command/grip_retry"):
                    Logger.info(f"{get_time()}: [Robot FSM] Start retry")
                    bb.set("ui/reset/grip_retry", True)
                    bb.set("int_var/retry_grip/val", 1)
                    return
            # TODO: Timeout --> STOP Event


    def grip_open_fail_fool_proof(self):
        ''' 오픈 실패 기능'''

        if bb.get("int_var/grip_state/val") == GripFailure.OPEN_FAIL:
            bb.set("int_var/retry_grip/val", 0)
            bb.set("indy_command/buzzer_on", True)
            bb.set("ui/state/grip_fail_popup", 2)
            self.wait_for_popup_done()
            Logger.info(f"{get_time()}: [Robot FSM] Grip open fail during MOVE_TO_FRYER motion")
            time.sleep(0.3)
            bb.set("indy_command/buzzer_off", True)

            start = time.time()
            while time.time() - start < 60:
                print("Wait for retry")
                time.sleep(0.2)
                if bb.get("ui/command/grip_retry"):
                    bb.set("ui/reset/grip_retry", True)
                    bb.set("int_var/retry_grip/val", 1)
                    return True
            return False

        return False

    def place_fail_fool_proof(self, basket_idx):
        ''' Place fool proof 기능:
        배출 모션 중 배출대에 바스켓 올릴 경우 (센서) 작업 중단
        Place approach
            1) 배출 모션 완료 이전: 무시
            2) 배출 ~ Place approach: 부저 울림, 모션 정지 (set_speed_ratio)
            3) Place approach 이후: 무시
        '''
        if (bb.get("int_var/init/val")
                == ContyCommand.MOVE_BASKET_FROM_FRYER_A + basket_idx + ContyCommand.INIT_ADD_APPROACH):
            if bb.get(f"indy_state/basket{basket_idx}") == 1:
                bb.set("indy_command/speed_ratio_zero", True)
                bb.set("indy_command/buzzer_on", True)
            else:
                bb.set("indy_command/speed_ratio_full", True)
                bb.set("indy_command/buzzer_off", True)


    ''' 
    Conty motion command (Int variables)
    - Frying COCO A type
    - Frying COCO B type 
    - Frying COCO C type: shift, clean added
    '''
    def move_ready_pos(self):
        motion = "move_to_ready"
        if bb.get("int_var/init/val") == ContyCommand.HOME + ContyCommand.INIT_ADD_VALUE:
            ''' Motion done '''
            Logger.info(f"{get_time()}: [Robot FSM] Finish motion {motion}")
            bb.set("int_var/cmd/val", int(ContyCommand.NONE))
            return FsmEvent.DONE
        elif bb.get("int_var/cmd/val") == 0:
            ''' Motion start '''
            Logger.info(f"{get_time()}: [Robot FSM] Start motion {motion} ")
            bb.set("int_var/cmd/val", int(ContyCommand.HOME))
            return FsmEvent.NONE
        else:
            ''' During motion '''
            return FsmEvent.NONE

    def basket_to_fryer(self, basket_idx, slot_idx, fryer_idx):
        '''
        A Type: Fixed
        B Type:
            Slot 1, 2, 3, 4 ---> Fryer 1, 2, 3, 4
            CMD value: 200 + basket_idx * 10 + fryer_idx
                ex) Basket 2 --> Fryer 4: 200 + 20 + 4 = 224
        C Type:

        '''
        motion = "move_to_fryer"

        if global_config.get("frying_coco_version") == "AType":
            start_cond = int(ContyCommand.MOVE_BASKET_TO_FRYER_A) + slot_idx
            finish_cond = start_cond + ContyCommand.INIT_ADD_VALUE
        elif global_config.get("frying_coco_version") == "CType":
            start_cond = int(ContyCommand.MOVE_BASKET_TO_FRYER_C) + 10*fryer_idx + basket_idx
            finish_cond = start_cond + ContyCommand.INIT_ADD_VALUE
        else:
            start_cond = int(ContyCommand.MOVE_BASKET_TO_FRYER_B) + 10 * slot_idx + fryer_idx
            finish_cond = start_cond + ContyCommand.INIT_ADD_VALUE

        if (self.motion_run_flag and bb.get("int_var/init/val") == finish_cond):
            ''' Motion Done logic '''
            self.motion_run_flag = False

            Logger.info(f"{get_time()}: [Robot FSM] Finish motion {motion} with "
                        f"[basket {basket_idx}, slot {slot_idx}, fryer {fryer_idx}]")

            self.motion_done_logic(motion, basket_idx)

            if global_config.get("home_pass_mode"):
                return self.home_pass_logic(motion)
            else:
                return FsmEvent.DONE

        elif bb.get("int_var/cmd/val") == 0:
            ''' Motion start '''
            Logger.info(f"{get_time()}: [Robot FSM] Start motion {motion} with "
                        f"[basket {basket_idx}, slot {slot_idx}, fryer {fryer_idx}]")
            bb.set("int_var/cmd/val", start_cond)
            self.motion_run_flag = True
            return FsmEvent.NONE
        else:
            ''' During motion: 투입 모션 중 파지/오픈 실패 '''
            if global_config.get("grip_close_fail_fool_proof"):
                self.grip_close_fail_fool_proof()

            if global_config.get("grip_open_fail_fool_proof"):
                self.grip_open_fail_fool_proof()


    def basket_from_fryer(self, basket_idx, fryer_idx):
        motion = "move_from_fryer"

        if global_config.get("frying_coco_version") == "AType":
            start_cond = int(ContyCommand.MOVE_BASKET_FROM_FRYER_A) + basket_idx
            finish_cond = start_cond + ContyCommand.INIT_ADD_VALUE
        elif global_config.get("frying_coco_version") == "CType":
            start_cond = int(ContyCommand.MOVE_BASKET_FROM_FRYER_C) + 10*fryer_idx + basket_idx
            finish_cond = start_cond + ContyCommand.INIT_ADD_VALUE
        else:
            start_cond = int(ContyCommand.MOVE_BASKET_FROM_FRYER_B) + fryer_idx
            finish_cond = start_cond + ContyCommand.INIT_ADD_VALUE

        if (self.motion_run_flag and bb.get("int_var/init/val") == finish_cond):
            ''' Motion Done logic '''
            bb.set("indy_command/buzzer_on", True)
            self.motion_run_flag = False

            Logger.info(f"{get_time()}: [Robot FSM] Finish motion {motion} with "
                        f"[basket {basket_idx}, fryer {fryer_idx}]")

            self.motion_done_logic(motion, basket_idx)

            if global_config.get("home_pass_mode"):
                return self.home_pass_logic(motion)
            else:
                time.sleep(0.3)
                return FsmEvent.DONE

        elif bb.get("int_var/cmd/val") == 0:
            ''' Motion start '''
            Logger.info(f"{get_time()}: [Robot FSM] Start motion {motion} with "
                        f"[basket {basket_idx}, fryer {fryer_idx}]")
            bb.set("int_var/cmd/val", start_cond)
            self.motion_run_flag = True
            return FsmEvent.NONE
        else:
            ''' During motion '''
            if global_config.get("frying_coco_version") == "AType" and global_config.get("place_fool_proof"):
                self.place_fail_fool_proof(basket_idx)

            if global_config.get("grip_close_fail_fool_proof"):
                self.grip_close_fail_fool_proof()

            if global_config.get("grip_open_fail_fool_proof"):
                self.grip_open_fail_fool_proof()


    def shake_basket(self, basket_idx, fryer_idx):
        motion = "shake"

        if global_config.get("frying_coco_version") == "AType":
            start_cond = int(ContyCommand.SHAKE_BASKET_A) + basket_idx
            finish_cond = start_cond + ContyCommand.INIT_ADD_VALUE
        elif global_config.get("frying_coco_version") == "CType":
            start_cond = int(ContyCommand.SHAKE_BASKET_C) + 10*fryer_idx + basket_idx
            finish_cond = start_cond + ContyCommand.INIT_ADD_VALUE
        else:
            start_cond = int(ContyCommand.SHAKE_BASKET_B) + fryer_idx
            finish_cond = start_cond + ContyCommand.INIT_ADD_VALUE

        if (self.motion_run_flag and bb.get("int_var/init/val") == finish_cond):
            ''' Motion Done logic '''
            self.motion_run_flag = False

            Logger.info(f"{get_time()}: [Robot FSM] Finish motion {motion} with "
                        f"[basket {basket_idx}, fryer {fryer_idx}]")

            self.motion_done_logic(motion, basket_idx)

            if global_config.get("home_pass_mode"):
                return self.home_pass_logic(motion)
            else:
                return FsmEvent.DONE

        elif bb.get("int_var/cmd/val") == 0:
            Logger.info(f"{get_time()}: [Robot FSM] Start motion {motion} with "
                        f"[basket {basket_idx}, fryer {fryer_idx}]")
            bb.set("int_var/cmd/val", start_cond)
            self.motion_run_flag = True
            return FsmEvent.NONE
        else:
            ''' During motion '''
            if global_config.get("grip_close_fail_fool_proof"):
                self.grip_close_fail_fool_proof()

            if global_config.get("grip_open_fail_fool_proof"):
                self.grip_open_fail_fool_proof()


    def shift_basket(self, basket_idx):
        motion = "shift"

        if global_config.get("frying_coco_version") == "CType":
            start_cond = int(ContyCommand.SHIFT_BASKET) + basket_idx
            finish_cond = start_cond + ContyCommand.INIT_ADD_VALUE
        else:
            return

        if (self.motion_run_flag and bb.get("int_var/init/val") == finish_cond):
            ''' Motion Done logic '''
            self.motion_run_flag = False

            Logger.info(f"{get_time()}: [Robot FSM] Finish motion {motion} with basket {basket_idx}")

            self.motion_done_logic(motion, basket_idx)

            if global_config.get("home_pass_mode"):
                return self.home_pass_logic(motion)
            else:
                return FsmEvent.DONE

        elif bb.get("int_var/cmd/val") == 0:
            Logger.info(f"{get_time()}: [Robot FSM] Start motion {motion} with basket {basket_idx}")
            bb.set("int_var/cmd/val", start_cond)
            self.motion_run_flag = True
            return FsmEvent.NONE
        else:
            ''' During motion '''
            if global_config.get("grip_close_fail_fool_proof"):
                self.grip_close_fail_fool_proof()

            if global_config.get("grip_open_fail_fool_proof"):
                self.grip_open_fail_fool_proof()

    def clean_basket(self, basket_idx, fryer_idx):
        motion = "clean"

        if global_config.get("frying_coco_version") == "CType":
            start_cond = int(ContyCommand.CLEAN_BASKET) + 10*fryer_idx + basket_idx
            finish_cond = start_cond + ContyCommand.INIT_ADD_VALUE
        else:
            return

        if (self.motion_run_flag and bb.get("int_var/init/val") == finish_cond):
            ''' Motion Done logic '''
            self.motion_run_flag = False

            Logger.info(f"{get_time()}: [Robot FSM] Finish motion {motion} with "
                        f"[basket {basket_idx}, fryer {fryer_idx}]")

            self.motion_done_logic(motion, basket_idx)

            if global_config.get("home_pass_mode"):
                return self.home_pass_logic(motion)
            else:
                return FsmEvent.DONE

        elif bb.get("int_var/cmd/val") == 0:
            Logger.info(f"{get_time()}: [Robot FSM] Start motion {motion} with "
                        f"[basket {basket_idx}, fryer {fryer_idx}]")
            bb.set("int_var/cmd/val", start_cond)
            self.motion_run_flag = True
            return FsmEvent.NONE
        else:
            ''' During motion '''
            if global_config.get("grip_close_fail_fool_proof"):
                self.grip_close_fail_fool_proof()

            if global_config.get("grip_open_fail_fool_proof"):
                self.grip_open_fail_fool_proof()

            # TODO: clean motion implementation


