from .dry_recipe_context import DryRecipeContext
from .dry_recipe_strategy import *
from .constants import *


class DryRecipeFsmSequence(FiniteStateMachine):
    context: DryRecipeContext

    def __init__(self, context: DryRecipeContext, *args, **kwargs):
        FiniteStateMachine.__init__(self, DryRecipeFsmState.NO_MENU, context, *args, **kwargs)

    def _setup_rules(self):
        self._rule_table = {
            DryRecipeFsmState.NO_MENU: {
                DryRecipeFsmEvent.ASSIGN_MENU: DryRecipeFsmState.COOKING_READY
            },
            DryRecipeFsmState.COOKING_READY: {
                DryRecipeFsmEvent.START_MENU: DryRecipeFsmState.MOVE_TO_FRYER,
                DryRecipeFsmEvent.RESET_MENU: DryRecipeFsmState.NO_MENU
            },
            DryRecipeFsmState.MOVE_TO_FRYER: {
                DryRecipeFsmEvent.MOTION_DONE: DryRecipeFsmState.FRY,
                DryRecipeFsmEvent.RETURN_READY: DryRecipeFsmState.COOKING_READY,
                DryRecipeFsmEvent.ERROR_DETECT: DryRecipeFsmState.COOKING_READY,
                DryRecipeFsmEvent.RESET_MENU: DryRecipeFsmState.NO_MENU
            },
            DryRecipeFsmState.FRY: {
                DryRecipeFsmEvent.CANCEL_MENU: DryRecipeFsmState.MOVE_FROM_FRYER,
                DryRecipeFsmEvent.SHAKE_TIME_DONE: DryRecipeFsmState.SHAKE,
                DryRecipeFsmEvent.COOKING_TIME_DONE: DryRecipeFsmState.MOVE_FROM_FRYER,
                DryRecipeFsmEvent.ERROR_DETECT: DryRecipeFsmState.NO_MENU,
                DryRecipeFsmEvent.RESET_MENU: DryRecipeFsmState.NO_MENU
            },
            DryRecipeFsmState.SHAKE: {
                DryRecipeFsmEvent.MOTION_DONE: DryRecipeFsmState.FRY,
                DryRecipeFsmEvent.CANCEL_MENU: DryRecipeFsmState.MOVE_FROM_FRYER,
                DryRecipeFsmEvent.DONE: DryRecipeFsmState.FRY,
                DryRecipeFsmEvent.COOKING_TIME_DONE: DryRecipeFsmState.MOVE_FROM_FRYER,
                DryRecipeFsmEvent.ERROR_DETECT: DryRecipeFsmState.FRY,
                DryRecipeFsmEvent.RESET_MENU: DryRecipeFsmState.NO_MENU
            },
            DryRecipeFsmState.MOVE_FROM_FRYER: {
                DryRecipeFsmEvent.MOTION_DONE: DryRecipeFsmState.FINISH,
                DryRecipeFsmEvent.ERROR_DETECT: DryRecipeFsmState.FINISH,
                DryRecipeFsmEvent.RESET_MENU: DryRecipeFsmState.NO_MENU
            },
            DryRecipeFsmState.FINISH: {
                DryRecipeFsmEvent.DONE: DryRecipeFsmState.NO_MENU,
                DryRecipeFsmEvent.RESET_MENU: DryRecipeFsmState.NO_MENU
            }
        }

    def _setup_strategies(self):
        self._strategy_table = {
            DryRecipeFsmState.NO_MENU: DryNoMenuStrategy(),
            DryRecipeFsmState.COOKING_READY: DryCookingReadyStrategy(),
            DryRecipeFsmState.MOVE_TO_FRYER: DryMoveToFryStrategy(),
            DryRecipeFsmState.FRY: DryFryStrategy(),
            DryRecipeFsmState.SHAKE: DryShakeStrategy(),
            DryRecipeFsmState.MOVE_FROM_FRYER: DryMoveFromFryStrategy(),
            DryRecipeFsmState.FINISH: DryFinishStrategy()
        }





