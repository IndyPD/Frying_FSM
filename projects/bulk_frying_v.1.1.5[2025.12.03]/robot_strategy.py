from .robot_context import *
from .process_manager import *

bb = GlobalBlackboard()

"""
Frying template FSM Implementation
"""

class NotReadyStrategy(Strategy):
    def prepare(self, context: RobotActionsContext, **kwargs):
        bb.set("ui/state/work_status", WorkStatus.MANUAL)
        context.conty_command_reset()
        context.app_command_reset()

        if context.check_program_running():
            Logger.info(f"{get_time()}: [Robot FSM] Program is Running, Stop the program (NotReadyStrategy)")
            context.stop_program()

        Logger.info(f"{get_time()}: [Robot FSM] Enter {self.__class__.__name__} State.")

    def operate(self, context: RobotActionsContext) -> RobotFsmEvent:
        if context.check_violation():
            if context.violation_code == MyViolation.NOT_READY:
                return RobotFsmEvent.NONE
            elif context.robot_state() in (RobotState.OP_IDLE, RobotState.OP_SYSTEM_RESET):
                return RobotFsmEvent.NONE
            else:
                return RobotFsmEvent.ERROR_DETECT
        else:
            if context.robot_state() == RobotState.OP_IDLE:
                return RobotFsmEvent.DONE
            else:
                return RobotFsmEvent.NONE

    def exit(self, context: RobotActionsContext, event: OpEvent) -> None:
        Logger.info(f"{get_time()}: [Robot FSM] Exit {self.__class__.__name__} State.")

class ErrorStrategy(Strategy):
    def prepare(self, context: RobotActionsContext, **kwargs):
        bb.set("ui/state/work_status", WorkStatus.MANUAL)

        ''' Define Error '''
        Logger.info(f"{get_time()}: [Robot FSM] Violation code {context.violation_code.name}")
        context.conty_command_reset()
        context.app_command_reset()
        context.motion_command_reset()
        Logger.info(f"{get_time()}: [Robot FSM] Enter {self.__class__.__name__} State.")

    def operate(self, context: RobotActionsContext) -> RobotFsmEvent:
        ''' Program state '''
        if context.program_state() == ProgramState.PROG_RUNNING:
            context.stop_program()

        ''' Recover '''
        if context.robot_state() == RobotState.OP_IDLE:
            return RobotFsmEvent.DONE
        else:
            if bb.get("ui/command/reset_robot") == 1:
                context.recover_robot()
                context.violation_code = MyViolation.RECOVERING
                bb.set("ui/reset/reset_robot", True)
                return RobotFsmEvent.RECOVER

            return RobotFsmEvent.NONE

    def exit(self, context: RobotActionsContext, event: RobotFsmEvent) -> None:
        Logger.info(f"{get_time()}: [Robot FSM] Exit {self.__class__.__name__} State.")

class RecoveringStrategy(Strategy):
    def prepare(self, context: RobotActionsContext, **kwargs):
        if context.check_program_running():
            context.stop_program()

        bb.set("ui/state/work_status", WorkStatus.MANUAL)

        Logger.info(f"{get_time()}: [Robot FSM] Enter {self.__class__.__name__} State.")

    def operate(self, context: RobotActionsContext) -> RobotFsmEvent:
        ''' Check Error '''
        if context.check_violation():
            if context.violation_code == MyViolation.RECOVERING:
                return RobotFsmEvent.NONE
            else:
                return RobotFsmEvent.ERROR_DETECT
        else:
            if context.robot_state() == RobotState.OP_IDLE:
                return RobotFsmEvent.DONE
            else:
                return RobotFsmEvent.NONE

    def exit(self, context: RobotActionsContext, event: OpEvent) -> None:
        Logger.info(f"{get_time()}: [Robot FSM] Exit {self.__class__.__name__} State.")

class NotReadyIdleStrategy(Strategy):
    def __init__(self):
        self.stop_flag = False
        self.prev_dt_btn = DigitalState.UNUSED_STATE
        self.prev_stop_btn = DigitalState.UNUSED_STATE
        self.gripper_state = False

    def prepare(self, context: RobotActionsContext, **kwargs):
        bb.set("ui/state/work_status", WorkStatus.MANUAL)

        if context.check_program_running():
            context.stop_program()

        context.conty_command_reset()
        context.app_command_reset()

        Logger.info(f"{get_time()}: [Robot FSM] Enter {self.__class__.__name__} State.")

    def operate(self, context: RobotActionsContext) -> RobotFsmEvent:
        '''
        State manage:
            - Direct teaching
            - Go to home pose
            - Go to package pose
            - Gripper control
        Event:
            - StartProgram
        '''

        dt_btn_on = bb.get("indy_state/button_dt")
        stop_btn_on = bb.get("indy_state/button_stop")

        ''' Check Error '''
        if context.check_violation():
            if context.robot_state() in (RobotState.OP_IDLE, RobotState.OP_SYSTEM_RESET):
                return RobotFsmEvent.NONE
            else:
                return RobotFsmEvent.ERROR_DETECT

        ''' Gripper control request from UI '''
        if bb.get("ui/command/gripper") == 1: # 닫기
            Logger.info(f"UI Command : close - False")
            context.gripper_control(False)
            bb.set("ui/reset/gripper", True)
        elif bb.get("ui/command/gripper") == 2: # 열기
            Logger.info(f"UI Command : open - True")
            context.gripper_control(True)
            bb.set("ui/reset/gripper", True)

        # if global_config.get("switch_button.button_type") == "momentary":
        #     if (stop_btn_on == DigitalState.OFF_STATE and
        #         self.prev_stop_btn == DigitalState.ON_STATE):
        #         self.gripper_state = 1 - self.gripper_state
        #         context.gripper_control(self.gripper_state)
        #         Logger.info(f"momentary : {self.gripper_state}")
        #     self.prev_stop_btn = stop_btn_on

        if global_config.get("switch_button.button_type") == "toggle":
            #TODO 일시정지 추가
            if stop_btn_on == DigitalState.ON_STATE: # 열기
                # Logger.info(f"toggle : {stop_btn_on}")
                pass
                # pause() 함수 추가 ratio 0

                # context.gripper_control(False)

            elif stop_btn_on == DigitalState.OFF_STATE:  # 닫기
                # Logger.info(f"toggle : {stop_btn_on}")
                pass
                # resume() 함수 추가 ratio 100

                # context.gripper_control(True)


        if context.robot_state() == RobotState.OP_TEACHING:
            ''' During direct teaching mode '''
            # DT off (UI)
            if bb.get("ui/command/teaching") == 2:
                Logger.info(f"{get_time()}: [Robot FSM] Direct Teaching OFF by App.")
                context.direct_teaching(False)
                bb.set("ui/reset/teaching", True)

            # DT off (Button)
            if (dt_btn_on == DigitalState.OFF_STATE and
                self.prev_dt_btn == DigitalState.ON_STATE):
                Logger.info(f"{get_time()}: [Robot FSM] Direct Teaching OFF by Button.")
                context.direct_teaching(False)
            self.prev_dt_btn = dt_btn_on
        else:
            ''' During Idle mode '''
            # DT on (Button)
            if global_config.get("switch_button.button_type") == "momentary":
                if (dt_btn_on == DigitalState.OFF_STATE and
                        self.prev_dt_btn == DigitalState.ON_STATE):
                    Logger.info(f"{get_time()}: [Robot FSM] momentary Direct Teaching ON.")
                    context.direct_teaching(True)
            elif global_config.get("switch_button.button_type") == "toggle":
                if dt_btn_on == DigitalState.ON_STATE:
                    Logger.info(f"{get_time()}: [Robot FSM] toggle Direct Teaching ON.")
                    context.direct_teaching(True)
            self.prev_dt_btn = dt_btn_on

            # DT on (UI)
            if bb.get("ui/command/teaching") == 1:
                Logger.info(f"{get_time()}: [Robot FSM] UI Direct Teaching ON.")
                context.direct_teaching(True)
                bb.set("ui/reset/teaching", True)

            ''' Start Program request from UI '''
            if bb.get("ui/command/program_control") == ProgramControl.PROG_START:
                Logger.info(f"{get_time()}: [Robot FSM] Program Start.")
                bb.set("ui/reset/program_control", True)
                if context.is_home_pos():
                    context.play_program()
                    return RobotFsmEvent.START_PROGRAM

            ''' Warming motion '''
            if bb.get("ui/command/warming") == 1:
                bb.set("ui/reset/warming", True)
                if context.is_home_pos():
                    context.play_warming_program()
                    return RobotFsmEvent.START_WARMING

            ''' Go home and packaging request from UI '''
            if bb.get("ui/command/go_home") or bb.get("ui/command/go_packing"):
                if bb.get("ui/command/go_home"):
                    context.go_home_pos()
                if bb.get("ui/command/go_packing"):
                    context.go_packaging_pos()
                self.stop_flag = True
                return RobotFsmEvent.NONE
            else:
                if self.stop_flag:
                    context.stop_motion()
                    self.stop_flag = False

        return RobotFsmEvent.NONE

    def exit(self, context: RobotActionsContext, event: OpEvent) -> None:
        Logger.info(f"{get_time()}: [Robot FSM] Exit {self.__class__.__name__} State.")

# class WarmingRobotStrategy(Strategy):
#     def prepare(self, context: RobotActionsContext, **kwargs):
#         bb.set("ui/state/work_status", WorkStatus.WARMING)

#         Logger.info(f"{get_time()}: [Robot FSM] Enter {self.__class__.__name__} State.")

#     def operate(self, context: RobotActionsContext) -> RobotFsmEvent:
#         event = context.check_violation_or_stop()
#         if event:
#             return event

#         ''' Stop by App '''
#         if bb.get("ui/command/warming") == 2:
#             context.stop_program()
#             return RobotFsmEvent.STOP

#     def exit(self, context: RobotActionsContext, event: OpEvent) -> None:
#         Logger.info(f"{get_time()}: [Robot FSM] Exiting {self.__class__.__name__} State.")

class WarmingRobotStrategy(Strategy):
    def prepare(self, context: RobotActionsContext, **kwargs):
        bb.set("ui/state/work_status", WorkStatus.WARMING)
        Logger.info(f"{get_time()}: [Robot FSM] Enter {self.__class__.__name__} State.")

    def operate(self, context: RobotActionsContext) -> RobotFsmEvent:
        # 프로그램이 실행 중인지 확인
        if context.check_program_running():
            # 프로그램이 실행 중이면 정상적으로 violation과 stop 체크
            event = context.check_violation_or_stop()
            if event:
                return event
                
            # Stop by App 체크
            if bb.get("ui/command/warming") == 2:
                context.stop_program()
                return RobotFsmEvent.STOP
        else:
            # 프로그램이 실행되지 않는 경우 - Conty warming program이 없거나 실행 불가
            Logger.warn(f"{get_time()}: [Robot FSM] Warming program is not running. Conty may not have warming program (index=2).")
            
            # violation 체크는 여전히 필요
            if context.check_violation():
                return RobotFsmEvent.ERROR_DETECT
                
            # Stop by App 체크
            if bb.get("ui/command/warming") == 2:
                Logger.info(f"{get_time()}: [Robot FSM] Warming stopped by App.")
                return RobotFsmEvent.STOP

        return RobotFsmEvent.NONE

    def exit(self, context: RobotActionsContext, event: OpEvent) -> None:
        Logger.info(f"{get_time()}: [Robot FSM] Exiting {self.__class__.__name__} State.")
        
# class MoveToReadyStrategy(Strategy):
#     def prepare(self, context: RobotActionsContext, **kwargs):
#         bb.set("ui/state/work_status", WorkStatus.IDLE)
#         context.conty_command_reset()
#         context.app_command_reset()

#         Logger.info(f"{get_time()}: [Robot FSM] Enter {self.__class__.__name__} State.")

#     def operate(self, context: RobotActionsContext) -> RobotFsmEvent:
#         if context.robot_state() == RobotState.OP_SYSTEM_RESET:
#             Logger.info(f"{get_time()}: [Robot FSM] Robot is in SYSTEM_RESET state. Attempting to recover.")
#             context.recover_robot()
#             context.violation_code = MyViolation.RECOVERING
#             return RobotFsmEvent.RECOVER
        
#         if context.violation_code == MyViolation.RECOVERING:
#             return RobotFsmEvent.NONE

#         event = context.check_violation_or_stop()
#         if event: return event

#         return context.move_ready_pos()

#     def exit(self, context: RobotActionsContext, event: RobotFsmEvent):
#         Logger.info(f"{get_time()}: [Robot FSM] Exiting {self.__class__.__name__} State.")
class MoveToReadyStrategy(Strategy):
    def prepare(self, context: RobotActionsContext, **kwargs):
        bb.set("ui/state/work_status", WorkStatus.IDLE)
        context.conty_command_reset()
        context.app_command_reset()

        Logger.info(f"{get_time()}: [Robot FSM] Enter {self.__class__.__name__} State.")

    def operate(self, context: RobotActionsContext) -> RobotFsmEvent:
        # violation과 stop 체크
        event = context.check_violation_or_stop()
        if event: 
            return event

        # ready position으로 이동
        return context.move_ready_pos()

    def exit(self, context: RobotActionsContext, event: RobotFsmEvent):
        Logger.info(f"{get_time()}: [Robot FSM] Exiting {self.__class__.__name__} State.")

class ReadyIdleStrategy(Strategy):
    def prepare(self, context: RobotActionsContext, **kwargs):
        bb.set("ui/state/work_status", WorkStatus.IDLE)

        context.conty_command_reset()
        context.app_command_reset()

        Logger.info(f"{get_time()}: [Robot FSM] Enter {self.__class__.__name__} State.")

    def operate(self, context: RobotActionsContext) -> RobotFsmEvent:
        event = context.check_violation_or_stop()
        if event:
            return event

        ''' Motion process  '''
        if bb.get("int_var/cmd/val") == 0:
            ''' 
            Request from recipe (three trigger):                    
                - MoveBasketToFryer, MoveBasketFromFryer, ShakeBasket
                - ShiftBasket
            '''
            if context.trigger_move_to_fryer:
                return RobotFsmEvent.RUN_BASKET_TO_FRYER
            elif context.trigger_move_from_fryer:
                return RobotFsmEvent.RUN_BASKET_FROM_FRYER
            elif context.trigger_shake:
                return RobotFsmEvent.RUN_SHAKE
            elif context.trigger_shift:
                return RobotFsmEvent.RUN_SHIFT


    def exit(self, context: RobotActionsContext, event: OpEvent) -> None:
        context.conty_command_reset()
        context.app_command_reset()
        Logger.info(f"{get_time()}: [Robot FSM] Exiting {self.__class__.__name__} State.")

class MoveBasketToFryerStrategy(Strategy):
    def prepare(self, context: RobotActionsContext, **kwargs):
        bb.set("ui/state/work_status", WorkStatus.TO_FRYER)
        # TODO: 투입 흔들기 변수 (Python->FSM) 구현 
        Logger.info(f"{get_time()}: [Robot FSM] Enter {self.__class__.__name__} State.")
        bb.set("int_var/shake_break/val",0)  

    def operate(self, context: RobotActionsContext) -> RobotFsmEvent:
        event = context.check_violation_or_stop()
        if event:
            return event
        return context.basket_to_fryer()
        

    def exit(self, context: RobotActionsContext, event: RobotFsmEvent):
        Logger.info(f"{get_time()}: Exit {self.__class__.__name__} State.")

class MoveBasketFromFryerStrategy(Strategy):
    def prepare(self, context: RobotActionsContext, **kwargs):
        bb.set("ui/state/work_status", WorkStatus.TO_STATION)
        Logger.info(f"{get_time()}: [Robot FSM] Enter {self.__class__.__name__} State.")

    def operate(self, context: RobotActionsContext) -> RobotFsmEvent:
        event = context.check_violation_or_stop()
        if event: return event

        return context.basket_from_fryer()

    def exit(self, context: RobotActionsContext, event: RobotFsmEvent):
        Logger.info(f"{get_time()}: Exit {self.__class__.__name__} State.")

class ShakeBasketStrategy(Strategy):
    def prepare(self, context: RobotActionsContext, **kwargs):
        bb.set("ui/state/work_status", WorkStatus.SHAKE)
        #TODO: Python -> Conty shake_num 구현
        Logger.info(f"{get_time()}: [Robot FSM] Enter {self.__class__.__name__} State.")

    def operate(self, context: RobotActionsContext) -> RobotFsmEvent:
        event = context.check_violation_or_stop()
        if event: return event

        return context.shake_basket()

    def exit(self, context: RobotActionsContext, event: OpEvent) -> None:
        Logger.info(f"{get_time()}: Exit {self.__class__.__name__} State.")

class ShiftBasketStrategy(Strategy):
    def prepare(self, context: RobotActionsContext, **kwargs):
        bb.set("ui/state/work_status", WorkStatus.SHIFT)

        Logger.info(f"{get_time()}: [Robot FSM] Enter {self.__class__.__name__} State.")

    def operate(self, context: RobotActionsContext) -> RobotFsmEvent:
        event = context.check_violation_or_stop()
        if event: return event

        return context.shift_basket()

    def exit(self, context: RobotActionsContext, event: OpEvent) -> None:
        Logger.info(f"{get_time()}: Exit {self.__class__.__name__} State.")

class BypassToFryerStrategy(Strategy):
    def prepare(self, context: RobotActionsContext, **kwargs):
        Logger.info(f"{get_time()}: Enter {self.__class__.__name__} State.")

    def operate(self, context: RobotActionsContext) -> RobotFsmEvent:
        return RobotFsmEvent.DONE

    def exit(self, context: RobotActionsContext, event: OpEvent) -> None:
        Logger.info(f"{get_time()}: Exit {self.__class__.__name__} State.")

class BypassFromFryerStrategy(Strategy):
    def prepare(self, context: RobotActionsContext, **kwargs):
        Logger.info(f"{get_time()}: Enter {self.__class__.__name__} State.")

    def operate(self, context: RobotActionsContext) -> RobotFsmEvent:
        return RobotFsmEvent.DONE

    def exit(self, context: RobotActionsContext, event: OpEvent) -> None:
        Logger.info(f"{get_time()}: Exit {self.__class__.__name__} State.")

class BypassShakeStrategy(Strategy):
    def prepare(self, context: RobotActionsContext, **kwargs):
        Logger.info(f"{get_time()}: Enter {self.__class__.__name__} State.")

    def operate(self, context: RobotActionsContext) -> RobotFsmEvent:
        return RobotFsmEvent.DONE

    def exit(self, context: RobotActionsContext, event: OpEvent) -> None:
        Logger.info(f"{get_time()}: Exit {self.__class__.__name__} State.")

class BypassShiftStrategy(Strategy):
    def prepare(self, context: RobotActionsContext, **kwargs):
        Logger.info(f"{get_time()}: Enter {self.__class__.__name__} State.")

    def operate(self, context: RobotActionsContext) -> RobotFsmEvent:
        return RobotFsmEvent.DONE

    def exit(self, context: RobotActionsContext, event: OpEvent) -> None:
        Logger.info(f"{get_time()}: Exit {self.__class__.__name__} State.")


class FinishingMotionStrategy(Strategy):
    def prepare(self, context: RobotActionsContext, **kwargs):
        Logger.info(f"{get_time()}: [Robot FSM] Enter {self.__class__.__name__} State. Waiting for motion to finish or program to stop.")
        bb.set("ui/state/work_status", WorkStatus.IDLE)

    def operate(self, context: RobotActionsContext) -> RobotFsmEvent:
        is_program_stopped = not context.check_program_running()

        # [FIX] 프로그램이 멈춘 직후에는 Violation을 체크하지 않고 바로 DONE으로 처리한다.
        if is_program_stopped:
            Logger.warn(f"{get_time()}: [Robot FSM] Program has stopped. Forcing FINISH_MOTION to DONE.")
            return RobotFsmEvent.DONE

        # 프로그램이 아직 실행 중일 때만 Violation과 동작 완료를 체크한다.
        if context.check_violation():
            Logger.error(f"{get_time()}: [Robot FSM] Violation detected while finishing motion. Transitioning to ERROR.")
            return RobotFsmEvent.ERROR_DETECT
        
        is_motion_cmd_finished = (int(bb.get("int_var/cmd/val")) == 0)
        if is_motion_cmd_finished:
            Logger.info(f"{get_time()}: [Robot FSM] Motion finished gracefully. Proceeding to stop.")
            return RobotFsmEvent.DONE
        
        return RobotFsmEvent.NONE

    def exit(self, context: RobotActionsContext, event: OpEvent) -> None:
        Logger.info(f"{get_time()}: [Robot FSM] Exit {self.__class__.__name__} State.")

