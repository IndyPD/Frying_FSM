from .wet_recipe_context import WetRecipeContext
from .wet_recipe_strategy import *
from .constants import *


class WetRecipeFsmSequence(FiniteStateMachine):
    context: WetRecipeContext

    def __init__(self, context: WetRecipeContext, *args, **kwargs):
        FiniteStateMachine.__init__(self, WetRecipeFsmState.WAIT_PUTIN, context, *args, **kwargs)

    def _setup_rules(self):
        self._rule_table = {
            WetRecipeFsmState.WAIT_PUTIN: {
                WetRecipeFsmEvent.START_PUTIN: WetRecipeFsmState.PUTIN
            },
            WetRecipeFsmState.PUTIN: {
                WetRecipeFsmEvent.DONE: WetRecipeFsmState.WAIT_MENU,
                WetRecipeFsmEvent.RESET_MENU: WetRecipeFsmState.WAIT_PUTIN,
                WetRecipeFsmEvent.ERROR_DETECT: WetRecipeFsmState.WAIT_PUTIN
            },
            WetRecipeFsmState.WAIT_MENU: {
                WetRecipeFsmEvent.ASSIGN_MENU: WetRecipeFsmState.PRE_FRY,
                WetRecipeFsmEvent.ERROR_DETECT: WetRecipeFsmState.WAIT_PUTIN,
                WetRecipeFsmEvent.RESET_MENU: WetRecipeFsmState.WAIT_PUTIN
            },
            WetRecipeFsmState.PRE_FRY: {
                WetRecipeFsmEvent.COOKING_TIME_DONE: WetRecipeFsmState.SHIFT_BASKET,  
                WetRecipeFsmEvent.DONE_SHIFT: WetRecipeFsmState.SHIFT_BASKET,                
                WetRecipeFsmEvent.MANUAL_SERVE: WetRecipeFsmState.MOVE_FROM_FRYER,
                WetRecipeFsmEvent.DONE: WetRecipeFsmState.FRY,
                WetRecipeFsmEvent.RESET_MENU: WetRecipeFsmState.WAIT_PUTIN
            },
            WetRecipeFsmState.SHIFT_BASKET: {
                WetRecipeFsmEvent.MOTION_DONE: WetRecipeFsmState.FRY,
                WetRecipeFsmEvent.ERROR_DETECT: WetRecipeFsmState.WAIT_PUTIN,
                WetRecipeFsmEvent.RESET_MENU: WetRecipeFsmState.WAIT_PUTIN
            },
            WetRecipeFsmState.FRY: {
                WetRecipeFsmEvent.MANUAL_SERVE: WetRecipeFsmState.MOVE_FROM_FRYER,
                WetRecipeFsmEvent.COOKING_TIME_DONE: WetRecipeFsmState.MOVE_FROM_FRYER,
                WetRecipeFsmEvent.RESET_MENU: WetRecipeFsmState.WAIT_PUTIN
            },
            WetRecipeFsmState.MOVE_FROM_FRYER: {
                WetRecipeFsmEvent.MOTION_DONE: WetRecipeFsmState.FINISH,
                WetRecipeFsmEvent.ERROR_DETECT: WetRecipeFsmState.FINISH,
                WetRecipeFsmEvent.RESET_MENU: WetRecipeFsmState.WAIT_PUTIN
            },
            WetRecipeFsmState.FINISH: {
                WetRecipeFsmEvent.DONE: WetRecipeFsmState.WAIT_PUTIN
            }
        }

    def _setup_strategies(self):
        self._strategy_table = {
            WetRecipeFsmState.WAIT_PUTIN: WaitPutinStrategy(),
            WetRecipeFsmState.PUTIN: PutinStrategy(),
            WetRecipeFsmState.WAIT_MENU: WaitMenuStrategy(),
            WetRecipeFsmState.PRE_FRY: WetPreFryStrategy(),
            WetRecipeFsmState.SHIFT_BASKET: ShiftBasketStrategy(),
            WetRecipeFsmState.FRY: WetFryStrategy(),
            WetRecipeFsmState.MOVE_FROM_FRYER: WetMoveFromFryStrategy(),
            WetRecipeFsmState.FINISH: WetFinishStrategy()
        }





