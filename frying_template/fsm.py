from .strategy import *
from .constants import *


class FsmSequence(FiniteStateMachine):
    context: RobotActionsContext

    def __init__(self, context: RobotActionsContext, *args, **kwargs):
        FiniteStateMachine.__init__(self, FsmState.NOT_READY, context, *args, **kwargs)

    def _setup_rules(self):
        self._rule_table = {

            # New implementation
            FsmState.NOT_READY: {
                FsmEvent.DONE: FsmState.NOT_READY_IDLE,
                FsmEvent.ERROR_DETECT: FsmState.ERROR,
            },
            FsmState.ERROR: {
                FsmEvent.RECOVER: FsmState.RECOVERING,
                FsmEvent.DONE: FsmState.NOT_READY_IDLE,
            },
            FsmState.RECOVERING: {
                FsmEvent.DONE: FsmState.NOT_READY_IDLE,
                FsmEvent.ERROR_DETECT: FsmState.ERROR,
            },
            FsmState.NOT_READY_IDLE: {
                FsmEvent.START_PROGRAM: FsmState.MOVE_TO_READY,
                FsmEvent.START_WARMING: FsmState.WARMING_ROBOT,
                FsmEvent.ERROR_DETECT: FsmState.ERROR,
            },
            FsmState.WARMING_ROBOT: {
                FsmEvent.STOP: FsmState.NOT_READY_IDLE,
                FsmEvent.ERROR_DETECT: FsmState.ERROR,
            },
            FsmState.MOVE_TO_READY: {
                FsmEvent.DONE: FsmState.READY_IDLE,
                FsmEvent.STOP: FsmState.NOT_READY_IDLE,
                FsmEvent.ERROR_DETECT: FsmState.ERROR,
            },
            FsmState.READY_IDLE: {
                FsmEvent.RUN_BASKET_TO_FRYER: FsmState.MOVE_BASKET_TO_FRYER,
                FsmEvent.RUN_BASKET_FROM_FRYER: FsmState.MOVE_BASKET_FROM_FRYER,
                FsmEvent.RUN_SHAKE: FsmState.SHAKE_BASKET,
                FsmEvent.RUN_SHIFT: FsmState.SHIFT_BASKET,
                FsmEvent.RUN_CLEAN: FsmState.CLEAN_BASKET,
                FsmEvent.STOP: FsmState.NOT_READY_IDLE,
                FsmEvent.ERROR_DETECT: FsmState.ERROR,
            },
            FsmState.MOVE_BASKET_TO_FRYER: {
                FsmEvent.DONE: FsmState.MOVE_TO_READY,
                FsmEvent.RUN_BASKET_TO_FRYER: FsmState.BYPASS_TO_FRYER,
                FsmEvent.RUN_BASKET_FROM_FRYER: FsmState.MOVE_BASKET_FROM_FRYER,
                FsmEvent.RUN_SHAKE: FsmState.SHAKE_BASKET,
                FsmEvent.RUN_SHIFT: FsmState.SHIFT_BASKET,
                FsmEvent.RUN_CLEAN: FsmState.CLEAN_BASKET,
                FsmEvent.STOP: FsmState.NOT_READY_IDLE,
                FsmEvent.ERROR_DETECT: FsmState.ERROR,
            },
            FsmState.MOVE_BASKET_FROM_FRYER: {
                FsmEvent.DONE: FsmState.MOVE_TO_READY,
                FsmEvent.RUN_BASKET_TO_FRYER: FsmState.MOVE_BASKET_TO_FRYER,
                FsmEvent.RUN_BASKET_FROM_FRYER: FsmState.BYPASS_FROM_FRYER,
                FsmEvent.RUN_SHAKE: FsmState.SHAKE_BASKET,
                FsmEvent.RUN_SHIFT: FsmState.SHIFT_BASKET,
                FsmEvent.RUN_CLEAN: FsmState.CLEAN_BASKET,
                FsmEvent.STOP: FsmState.NOT_READY_IDLE,
                FsmEvent.ERROR_DETECT: FsmState.ERROR,
            },
            FsmState.SHAKE_BASKET: {
                FsmEvent.DONE: FsmState.MOVE_TO_READY,
                FsmEvent.RUN_BASKET_TO_FRYER: FsmState.MOVE_BASKET_TO_FRYER,
                FsmEvent.RUN_BASKET_FROM_FRYER: FsmState.MOVE_BASKET_FROM_FRYER,
                FsmEvent.RUN_SHAKE: FsmState.BYPASS_SHAKE,
                FsmEvent.RUN_SHIFT: FsmState.SHIFT_BASKET,
                FsmEvent.RUN_CLEAN: FsmState.CLEAN_BASKET,
                FsmEvent.STOP: FsmState.NOT_READY_IDLE,
                FsmEvent.ERROR_DETECT: FsmState.ERROR,
            },
            FsmState.SHIFT_BASKET: {
                FsmEvent.DONE: FsmState.MOVE_TO_READY,
                FsmEvent.RUN_BASKET_TO_FRYER: FsmState.MOVE_BASKET_TO_FRYER,
                FsmEvent.RUN_BASKET_FROM_FRYER: FsmState.MOVE_BASKET_FROM_FRYER,
                FsmEvent.RUN_SHAKE: FsmState.SHAKE_BASKET,
                FsmEvent.RUN_SHIFT: FsmState.BYPASS_SHIFT,
                FsmEvent.RUN_CLEAN: FsmState.CLEAN_BASKET,
                FsmEvent.STOP: FsmState.NOT_READY_IDLE,
                FsmEvent.ERROR_DETECT: FsmState.ERROR,
            },
            FsmState.CLEAN_BASKET: {
                FsmEvent.DONE: FsmState.MOVE_TO_READY,
                FsmEvent.RUN_BASKET_TO_FRYER: FsmState.MOVE_BASKET_TO_FRYER,
                FsmEvent.RUN_BASKET_FROM_FRYER: FsmState.MOVE_BASKET_FROM_FRYER,
                FsmEvent.RUN_SHAKE: FsmState.SHAKE_BASKET,
                FsmEvent.RUN_SHIFT: FsmState.SHIFT_BASKET,
                FsmEvent.RUN_CLEAN: FsmState.BYPASS_CLEAN,
                FsmEvent.STOP: FsmState.NOT_READY_IDLE,
                FsmEvent.ERROR_DETECT: FsmState.ERROR,
            },
            FsmState.BYPASS_TO_FRYER: {
                FsmEvent.DONE: FsmState.MOVE_BASKET_TO_FRYER
            },
            FsmState.BYPASS_FROM_FRYER: {
                FsmEvent.DONE: FsmState.MOVE_BASKET_FROM_FRYER
            },
            FsmState.BYPASS_SHAKE: {
                FsmEvent.DONE: FsmState.SHAKE_BASKET
            },
            FsmState.BYPASS_SHIFT: {
                FsmEvent.DONE: FsmState.SHIFT_BASKET
            },
            FsmState.BYPASS_CLEAN: {
                FsmEvent.DONE: FsmState.CLEAN_BASKET
            }
        }

    def _setup_strategies(self):
        self._strategy_table = {
            FsmState.ERROR: ErrorStrategy(),
            FsmState.RECOVERING: RecoveringStrategy(),

            FsmState.NOT_READY: NotReadyStrategy(),
            FsmState.NOT_READY_IDLE: NotReadyIdleStrategy(),
            FsmState.WARMING_ROBOT: WarmingRobotStrategy(),
            FsmState.MOVE_TO_READY: MoveToReadyStrategy(),

            FsmState.READY_IDLE: ReadyIdleStrategy(),

            FsmState.MOVE_BASKET_TO_FRYER: MoveBasketToFryerStrategy(),
            FsmState.MOVE_BASKET_FROM_FRYER: MoveBasketFromFryerStrategy(),
            FsmState.SHAKE_BASKET: ShakeBasketStrategy(),

            FsmState.BYPASS_TO_FRYER: BypassToFryerStrategy(),
            FsmState.BYPASS_FROM_FRYER: BypassFromFryerStrategy(),
            FsmState.BYPASS_SHAKE: BypassShakeStrategy(),

            FsmState.SHIFT_BASKET: ShiftBasketStrategy(),
            FsmState.CLEAN_BASKET: CleanBasketStrategy()
        }





