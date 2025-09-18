from .context import *
from .recipe_manager import *

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

    def operate(self, context: RobotActionsContext) -> FsmEvent:
        if context.check_violation():
            if context.violation_code == MyViolation.NOT_READY:
                return FsmEvent.NONE
            elif context.robot_state() in (RobotState.OP_IDLE, RobotState.OP_SYSTEM_RESET):
                return FsmEvent.NONE
            else:
                return FsmEvent.ERROR_DETECT
        else:
            if context.robot_state() == RobotState.OP_IDLE:
                return FsmEvent.DONE
            else:
                return FsmEvent.NONE

    def exit(self, context: RobotActionsContext, event: OpEvent) -> None:
        Logger.info(f"{get_time()}: [Robot FSM] Exit {self.__class__.__name__} State.")

class ErrorStrategy(Strategy):
    def prepare(self, context: RobotActionsContext, **kwargs):
        bb.set("ui/state/work_status", WorkStatus.MANUAL)
        bb.set("indy_command/buzzer_on", True)

        ''' Define Error '''
        Logger.info(f"{get_time()}: [Robot FSM] Violation code {context.violation_code.name}")
        context.conty_command_reset()
        context.app_command_reset()
        context.motion_command_reset()
        Logger.info(f"{get_time()}: [Robot FSM] Enter {self.__class__.__name__} State.")

    def operate(self, context: RobotActionsContext) -> FsmEvent:
        ''' Program state '''
        if context.program_state() == ProgramState.PROG_RUNNING:
            context.stop_program()

        ''' Recover '''
        if context.robot_state() == RobotState.OP_IDLE:
            return FsmEvent.DONE
        else:
            if bb.get("ui/command/reset_robot") == 1:
                context.recover_robot()
                context.violation_code = MyViolation.RECOVERING
                bb.set("ui/reset/reset_robot", True)
                return FsmEvent.RECOVER

            return FsmEvent.NONE

    def exit(self, context: RobotActionsContext, event: FsmEvent) -> None:
        bb.set("indy_command/buzzer_off", True)
        Logger.info(f"{get_time()}: [Robot FSM] Exit {self.__class__.__name__} State.")


class RecoveringStrategy(Strategy):
    def prepare(self, context: RobotActionsContext, **kwargs):
        if context.check_program_running():
            context.stop_program()

        bb.set("ui/state/work_status", WorkStatus.MANUAL)

        Logger.info(f"{get_time()}: [Robot FSM] Enter {self.__class__.__name__} State.")

    def operate(self, context: RobotActionsContext) -> FsmEvent:
        ''' Check Error '''
        if context.check_violation():
            if context.violation_code == MyViolation.RECOVERING:
                return FsmEvent.NONE
            else:
                return FsmEvent.ERROR_DETECT
        else:
            if context.robot_state() == RobotState.OP_IDLE:
                return FsmEvent.DONE
            else:
                return FsmEvent.NONE

    def exit(self, context: RobotActionsContext, event: OpEvent) -> None:
        Logger.info(f"{get_time()}: [Robot FSM] Exit {self.__class__.__name__} State.")


class NotReadyIdleStrategy(Strategy):
    def __init__(self):
        self.stop_flag = False
        self.prev_dt_btn = DigitalState.UNUSED_STATE

    def prepare(self, context: RobotActionsContext, **kwargs):

        bb.set("ui/state/work_status", WorkStatus.MANUAL)

        if context.check_program_running():
            context.stop_program()

        context.conty_command_reset()
        context.app_command_reset()

        Logger.info(f"{get_time()}: [Robot FSM] Enter {self.__class__.__name__} State.")

    def operate(self, context: RobotActionsContext) -> FsmEvent:
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

        ''' Check Error '''
        if context.check_violation():
            if context.robot_state() in (RobotState.OP_IDLE, RobotState.OP_SYSTEM_RESET):
                return FsmEvent.NONE
            else:
                return FsmEvent.ERROR_DETECT

        ''' Gripper control request from UI '''
        if bb.get("ui/command/gripper") == 1: # 닫기
            context.gripper_control(False)
            bb.set("ui/reset/gripper", True)
        elif bb.get("ui/command/gripper") == 2: # 열기
            context.gripper_control(True)
            bb.set("ui/reset/gripper", True)


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
                    context.direct_teaching(True)
            elif global_config.get("switch_button.button_type") == "toggle":
                if dt_btn_on == DigitalState.ON_STATE:
                    context.direct_teaching(True)
            self.prev_dt_btn = dt_btn_on

            # DT on (UI)
            if bb.get("ui/command/teaching") == 1:
                context.direct_teaching(True)
                bb.set("ui/reset/teaching", True)

            ''' Start Program request from UI '''
            if bb.get("ui/command/program_control") == ProgramControl.PROG_START:
                bb.set("ui/reset/program_control", True)
                if context.is_home_pos():
                    context.play_program()
                    return FsmEvent.START_PROGRAM

            ''' Warming motion '''
            if bb.get("ui/command/warming") == 1:
                bb.set("ui/reset/warming", True)
                if context.is_home_pos():
                    context.play_warming_program()
                    return FsmEvent.START_WARMING

            ''' Go home and packaging request from UI '''
            if bb.get("ui/command/go_home") or bb.get("ui/command/go_packing"):
                if bb.get("ui/command/go_home"):
                    context.go_home_pos()
                if bb.get("ui/command/go_packing"):
                    context.go_packaging_pos()
                self.stop_flag = True
                return FsmEvent.NONE
            else:
                if self.stop_flag:
                    context.stop_motion()
                    self.stop_flag = False

        return FsmEvent.NONE

    def exit(self, context: RobotActionsContext, event: OpEvent) -> None:
        Logger.info(f"{get_time()}: [Robot FSM] Exit {self.__class__.__name__} State.")


class WarmingRobotStrategy(Strategy):
    def prepare(self, context: RobotActionsContext, **kwargs):
        bb.set("ui/state/work_status", WorkStatus.WARMING)

        Logger.info(f"{get_time()}: [Robot FSM] Enter {self.__class__.__name__} State.")

    def operate(self, context: RobotActionsContext) -> FsmEvent:
        event = context.check_violation_or_stop()
        if event:
            return event

        ''' Stop by App '''
        if bb.get("ui/command/warming") == 2:
            context.stop_program()
            return FsmEvent.STOP

    def exit(self, context: RobotActionsContext, event: OpEvent) -> None:
        Logger.info(f"{get_time()}: [Robot FSM] Exiting {self.__class__.__name__} State.")


class MoveToReadyStrategy(Strategy):
    def prepare(self, context: RobotActionsContext, **kwargs):
        bb.set("ui/state/work_status", WorkStatus.IDLE)
        context.conty_command_reset()
        context.app_command_reset()

        Logger.info(f"{get_time()}: [Robot FSM] Enter {self.__class__.__name__} State.")

    def operate(self, context: RobotActionsContext) -> FsmEvent:
        event = context.check_violation_or_stop()
        if event: return event

        return context.move_ready_pos()

    def exit(self, context: RobotActionsContext, event: FsmEvent):
        Logger.info(f"{get_time()}: [Robot FSM] Exiting {self.__class__.__name__} State.")


class ReadyIdleStrategy(Strategy):
    def prepare(self, context: RobotActionsContext, **kwargs):
        bb.set("ui/state/work_status", WorkStatus.IDLE)

        context.conty_command_reset()
        context.app_command_reset()

        Logger.info(f"{get_time()}: [Robot FSM] Enter {self.__class__.__name__} State.")

    def operate(self, context: RobotActionsContext) -> FsmEvent:
        event = context.check_violation_or_stop()
        if event:
            return event

        ''' Motion process  '''
        if bb.get("int_var/cmd/val") == 0:
            ''' 
            Request from recipe (three trigger):                    
                - MoveBasketToFryer, MoveBasketFromFryer, ShakeBasket
                - (C Type) ShiftBasket, CleanBasket
            '''
            if context.trigger_move_to_fryer:
                return FsmEvent.RUN_BASKET_TO_FRYER
            if context.trigger_move_from_fryer:
                return FsmEvent.RUN_BASKET_FROM_FRYER
            if context.trigger_shake:
                return FsmEvent.RUN_SHAKE
            if context.trigger_shift:
                return FsmEvent.RUN_SHIFT
            if context.trigger_clean:
                return FsmEvent.RUN_CLEAN

    def exit(self, context: RobotActionsContext, event: OpEvent) -> None:
        context.conty_command_reset()
        context.app_command_reset()
        Logger.info(f"{get_time()}: [Robot FSM] Exiting {self.__class__.__name__} State.")


class MoveBasketToFryerStrategy(Strategy):
    def __init__(self):
        self.basket_index = 0
        self.slot_index = 0
        self.fryer_index = 0

    def prepare(self, context: RobotActionsContext, **kwargs):
        bb.set("ui/state/work_status", WorkStatus.TO_FRYER)

        self.basket_index = context.basket_index
        self.slot_index = context.slot_index
        self.fryer_index = context.fryer_index

        Logger.info(f"{get_time()}: [Robot FSM] Enter {self.__class__.__name__} State.")

    def operate(self, context: RobotActionsContext) -> FsmEvent:
        event = context.check_violation_or_stop()
        if event:
            return event

        return context.basket_to_fryer(self.basket_index, self.slot_index, self.fryer_index)

    def exit(self, context: RobotActionsContext, event: FsmEvent):
        Logger.info(f"{get_time()}: Exit {self.__class__.__name__} State.")


class MoveBasketFromFryerStrategy(Strategy):
    def __init__(self):
        self.basket_index = 0
        self.fryer_index = 0

    def prepare(self, context: RobotActionsContext, **kwargs):
        bb.set("ui/state/work_status", WorkStatus.TO_STATION)

        bb.set("int_var/drain_num/val", context.drain_num)
        self.basket_index = context.basket_index
        self.fryer_index = context.fryer_index


        Logger.info(f"{get_time()}: [Robot FSM] Enter {self.__class__.__name__} State.")

    def operate(self, context: RobotActionsContext) -> FsmEvent:

        event = context.check_violation_or_stop()
        if event: return event

        return context.basket_from_fryer(self.basket_index, self.fryer_index)

    def exit(self, context: RobotActionsContext, event: FsmEvent):
        bb.set("indy_command/buzzer_off", True)
        Logger.info(f"{get_time()}: Exit {self.__class__.__name__} State.")

class ShakeBasketStrategy(Strategy):
    def __init__(self):
        self.basket_index = 0
        self.slot_index = 0
        self.fryer_index = 0

    def prepare(self, context: RobotActionsContext, **kwargs):
        bb.set("ui/state/work_status", WorkStatus.SHAKE)

        bb.set("int_var/shake_num/val", context.shake_num)
        bb.set("int_var/shake_option/val", context.shake_option)
        self.basket_index = context.basket_index
        self.fryer_index = context.fryer_index

        Logger.info(f"{get_time()}: [Robot FSM] Enter {self.__class__.__name__} State.")

    def operate(self, context: RobotActionsContext) -> FsmEvent:

        event = context.check_violation_or_stop()
        if event: return event

        return context.shake_basket(self.basket_index, self.fryer_index)

    def exit(self, context: RobotActionsContext, event: OpEvent) -> None:
        Logger.info(f"{get_time()}: Exit {self.__class__.__name__} State.")

class ShiftBasketStrategy(Strategy):
    def __init__(self):
        self.basket_index = 0
        self.slot_index = 0
        self.fryer_index = 0

    def prepare(self, context: RobotActionsContext, **kwargs):
        bb.set("ui/state/work_status", WorkStatus.SHAKE)

        self.basket_index = context.basket_index
        self.fryer_index = context.fryer_index

        Logger.info(f"{get_time()}: [Robot FSM] Enter {self.__class__.__name__} State.")

    def operate(self, context: RobotActionsContext) -> FsmEvent:

        event = context.check_violation_or_stop()
        if event: return event

        return context.shake_basket(self.basket_index, self.fryer_index)

    def exit(self, context: RobotActionsContext, event: OpEvent) -> None:
        Logger.info(f"{get_time()}: Exit {self.__class__.__name__} State.")

class CleanBasketStrategy(Strategy):
    def __init__(self):
        self.basket_index = 0
        self.slot_index = 0
        self.fryer_index = 0

    def prepare(self, context: RobotActionsContext, **kwargs):
        bb.set("ui/state/work_status", WorkStatus.SHAKE)

        self.basket_index = context.basket_index
        self.fryer_index = context.fryer_index

        Logger.info(f"{get_time()}: [Robot FSM] Enter {self.__class__.__name__} State.")

    def operate(self, context: RobotActionsContext) -> FsmEvent:

        event = context.check_violation_or_stop()
        if event: return event

        return context.shake_basket(self.basket_index, self.fryer_index)

    def exit(self, context: RobotActionsContext, event: OpEvent) -> None:
        Logger.info(f"{get_time()}: Exit {self.__class__.__name__} State.")


class BypassToFryerStrategy(Strategy):
    def prepare(self, context: RobotActionsContext, **kwargs):
        Logger.info(f"{get_time()}: Enter {self.__class__.__name__} State.")

    def operate(self, context: RobotActionsContext) -> FsmEvent:
        return FsmEvent.DONE

    def exit(self, context: RobotActionsContext, event: OpEvent) -> None:
        Logger.info(f"{get_time()}: Exit {self.__class__.__name__} State.")

class BypassFromFryerStrategy(Strategy):
    def prepare(self, context: RobotActionsContext, **kwargs):
        Logger.info(f"{get_time()}: Enter {self.__class__.__name__} State.")

    def operate(self, context: RobotActionsContext) -> FsmEvent:
        return FsmEvent.DONE

    def exit(self, context: RobotActionsContext, event: OpEvent) -> None:
        Logger.info(f"{get_time()}: Exit {self.__class__.__name__} State.")

class BypassShakeStrategy(Strategy):
    def prepare(self, context: RobotActionsContext, **kwargs):
        Logger.info(f"{get_time()}: Enter {self.__class__.__name__} State.")

    def operate(self, context: RobotActionsContext) -> FsmEvent:
        return FsmEvent.DONE

    def exit(self, context: RobotActionsContext, event: OpEvent) -> None:
        Logger.info(f"{get_time()}: Exit {self.__class__.__name__} State.")

class BypassShiftStrategy(Strategy):
    def prepare(self, context: RobotActionsContext, **kwargs):
        Logger.info(f"{get_time()}: Enter {self.__class__.__name__} State.")

    def operate(self, context: RobotActionsContext) -> FsmEvent:
        return FsmEvent.DONE

    def exit(self, context: RobotActionsContext, event: OpEvent) -> None:
        Logger.info(f"{get_time()}: Exit {self.__class__.__name__} State.")

class BypassCleanStrategy(Strategy):
    def prepare(self, context: RobotActionsContext, **kwargs):
        Logger.info(f"{get_time()}: Enter {self.__class__.__name__} State.")

    def operate(self, context: RobotActionsContext) -> FsmEvent:
        return FsmEvent.DONE

    def exit(self, context: RobotActionsContext, event: OpEvent) -> None:
        Logger.info(f"{get_time()}: Exit {self.__class__.__name__} State.")