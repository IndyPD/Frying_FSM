from .robot_strategy import *
from .constants import *


class RobotFsmSequence(FiniteStateMachine):
    context: RobotActionsContext

    def __init__(self, context: RobotActionsContext, *args, **kwargs):
        FiniteStateMachine.__init__(self, RobotFsmState.NOT_READY, context, *args, **kwargs)

    def _setup_rules(self):
        self._rule_table = {

            # New implementation
            RobotFsmState.NOT_READY: {
                RobotFsmEvent.DONE: RobotFsmState.NOT_READY_IDLE,
                RobotFsmEvent.ERROR_DETECT: RobotFsmState.ERROR,
            },
            RobotFsmState.ERROR: {
                RobotFsmEvent.RECOVER: RobotFsmState.RECOVERING,
                RobotFsmEvent.DONE: RobotFsmState.NOT_READY_IDLE,
            },
            RobotFsmState.RECOVERING: {
                RobotFsmEvent.DONE: RobotFsmState.NOT_READY_IDLE,
                RobotFsmEvent.ERROR_DETECT: RobotFsmState.ERROR,
            },
            RobotFsmState.NOT_READY_IDLE: {
                RobotFsmEvent.START_PROGRAM: RobotFsmState.MOVE_TO_READY,
                RobotFsmEvent.START_WARMING: RobotFsmState.WARMING_ROBOT,
                RobotFsmEvent.ERROR_DETECT: RobotFsmState.ERROR,
            },
            RobotFsmState.WARMING_ROBOT: {
                RobotFsmEvent.STOP: RobotFsmState.NOT_READY_IDLE,
                RobotFsmEvent.ERROR_DETECT: RobotFsmState.ERROR,
            },
            RobotFsmState.MOVE_TO_READY: {
                RobotFsmEvent.DONE: RobotFsmState.READY_IDLE,
                RobotFsmEvent.STOP: RobotFsmState.FINISHING_MOTION, # STOP event handling changed
                RobotFsmEvent.ERROR_DETECT: RobotFsmState.ERROR,
            },
            RobotFsmState.READY_IDLE: {
                RobotFsmEvent.RUN_BASKET_TO_FRYER: RobotFsmState.MOVE_BASKET_TO_FRYER,
                RobotFsmEvent.RUN_BASKET_FROM_FRYER: RobotFsmState.MOVE_BASKET_FROM_FRYER,
                RobotFsmEvent.RUN_SHAKE: RobotFsmState.SHAKE_BASKET,
                RobotFsmEvent.RUN_SHIFT: RobotFsmState.SHIFT_BASKET,
                RobotFsmEvent.STOP: RobotFsmState.NOT_READY_IDLE,
                RobotFsmEvent.ERROR_DETECT: RobotFsmState.ERROR,
            },
            RobotFsmState.MOVE_BASKET_TO_FRYER: {
                RobotFsmEvent.DONE: RobotFsmState.MOVE_TO_READY,
                RobotFsmEvent.RUN_BASKET_TO_FRYER: RobotFsmState.BYPASS_TO_FRYER,
                RobotFsmEvent.RUN_BASKET_FROM_FRYER: RobotFsmState.MOVE_BASKET_FROM_FRYER,
                RobotFsmEvent.RUN_SHAKE: RobotFsmState.SHAKE_BASKET,
                RobotFsmEvent.RUN_SHIFT: RobotFsmState.SHIFT_BASKET,
                RobotFsmEvent.STOP: RobotFsmState.FINISHING_MOTION, # STOP event handling changed
                RobotFsmEvent.ERROR_DETECT: RobotFsmState.ERROR,
            },
            RobotFsmState.MOVE_BASKET_FROM_FRYER: {
                RobotFsmEvent.DONE: RobotFsmState.MOVE_TO_READY,
                RobotFsmEvent.RUN_BASKET_TO_FRYER: RobotFsmState.MOVE_BASKET_TO_FRYER,
                RobotFsmEvent.RUN_BASKET_FROM_FRYER: RobotFsmState.BYPASS_FROM_FRYER,
                RobotFsmEvent.RUN_SHAKE: RobotFsmState.SHAKE_BASKET,
                RobotFsmEvent.RUN_SHIFT: RobotFsmState.SHIFT_BASKET,
                RobotFsmEvent.STOP: RobotFsmState.FINISHING_MOTION, # STOP event handling changed
                RobotFsmEvent.ERROR_DETECT: RobotFsmState.ERROR,
            },
            RobotFsmState.SHAKE_BASKET: {
                RobotFsmEvent.DONE: RobotFsmState.MOVE_TO_READY,
                RobotFsmEvent.RUN_BASKET_TO_FRYER: RobotFsmState.MOVE_BASKET_TO_FRYER,
                RobotFsmEvent.RUN_BASKET_FROM_FRYER: RobotFsmState.MOVE_BASKET_FROM_FRYER,
                RobotFsmEvent.RUN_SHAKE: RobotFsmState.BYPASS_SHAKE,
                RobotFsmEvent.RUN_SHIFT: RobotFsmState.SHIFT_BASKET,
                RobotFsmEvent.STOP: RobotFsmState.FINISHING_MOTION, # STOP event handling changed
                RobotFsmEvent.ERROR_DETECT: RobotFsmState.ERROR,
            },
            RobotFsmState.SHIFT_BASKET: {
                RobotFsmEvent.DONE: RobotFsmState.MOVE_TO_READY,
                RobotFsmEvent.RUN_BASKET_TO_FRYER: RobotFsmState.MOVE_BASKET_TO_FRYER,
                RobotFsmEvent.RUN_BASKET_FROM_FRYER: RobotFsmState.MOVE_BASKET_FROM_FRYER,
                RobotFsmEvent.RUN_SHAKE: RobotFsmState.SHAKE_BASKET,
                # RobotFsmEvent.RUN_SHIFT: RobotFsmState.BYPASS_SHIFT,
                RobotFsmEvent.STOP: RobotFsmState.FINISHING_MOTION, # STOP event handling changed
                RobotFsmEvent.ERROR_DETECT: RobotFsmState.ERROR,
            },
            RobotFsmState.FINISHING_MOTION: { # New state for graceful stop
                RobotFsmEvent.DONE: RobotFsmState.NOT_READY_IDLE,
                RobotFsmEvent.ERROR_DETECT: RobotFsmState.ERROR,
            },
            RobotFsmState.BYPASS_TO_FRYER: {
                RobotFsmEvent.DONE: RobotFsmState.MOVE_BASKET_TO_FRYER
            },
            RobotFsmState.BYPASS_FROM_FRYER: {
                RobotFsmEvent.DONE: RobotFsmState.MOVE_BASKET_FROM_FRYER
            },
            RobotFsmState.BYPASS_SHAKE: {
                RobotFsmEvent.DONE: RobotFsmState.SHAKE_BASKET
            },
            RobotFsmState.BYPASS_SHIFT: {
                RobotFsmEvent.DONE: RobotFsmState.SHIFT_BASKET
            }
        }

    def _setup_strategies(self):
        self._strategy_table = {
            RobotFsmState.ERROR: ErrorStrategy(),
            RobotFsmState.RECOVERING: RecoveringStrategy(),

            RobotFsmState.NOT_READY: NotReadyStrategy(),
            RobotFsmState.NOT_READY_IDLE: NotReadyIdleStrategy(),
            RobotFsmState.WARMING_ROBOT: WarmingRobotStrategy(),
            RobotFsmState.MOVE_TO_READY: MoveToReadyStrategy(),

            RobotFsmState.READY_IDLE: ReadyIdleStrategy(),

            RobotFsmState.MOVE_BASKET_TO_FRYER: MoveBasketToFryerStrategy(),
            RobotFsmState.MOVE_BASKET_FROM_FRYER: MoveBasketFromFryerStrategy(),
            RobotFsmState.SHAKE_BASKET: ShakeBasketStrategy(),

            RobotFsmState.BYPASS_TO_FRYER: BypassToFryerStrategy(),
            RobotFsmState.BYPASS_FROM_FRYER: BypassFromFryerStrategy(),
            RobotFsmState.BYPASS_SHAKE: BypassShakeStrategy(),

            RobotFsmState.SHIFT_BASKET: ShiftBasketStrategy(),

            RobotFsmState.FINISHING_MOTION: FinishingMotionStrategy()
        }





