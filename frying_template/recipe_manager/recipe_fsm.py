from .recipe_strategy import *
from ..constants import *


class RecipeFsmSequence(FiniteStateMachine):
    context: RecipeContext

    def __init__(self, context: RecipeContext, *args, **kwargs):
        FiniteStateMachine.__init__(self, RecipeFsmState.NO_MENU, context, *args, **kwargs)

    def _setup_rules(self):
        self._rule_table = {
            RecipeFsmState.NO_MENU: {
                RecipeFsmEvent.ASSIGN_MENU: RecipeFsmState.COOKING_READY
            },
            RecipeFsmState.COOKING_READY: {
                RecipeFsmEvent.START_MENU: RecipeFsmState.MOVE_TO_FRYER,
                RecipeFsmEvent.RESET_MENU: RecipeFsmState.NO_MENU
            },
            RecipeFsmState.MOVE_TO_FRYER: {
                RecipeFsmEvent.MOTION_DONE: RecipeFsmState.FRY,
                RecipeFsmEvent.RETURN_READY: RecipeFsmState.COOKING_READY,
                RecipeFsmEvent.ERROR_DETECT: RecipeFsmState.FRY,
                RecipeFsmEvent.RESET_MENU: RecipeFsmState.NO_MENU
            },
            RecipeFsmState.FRY: {
                RecipeFsmEvent.CANCEL_MENU: RecipeFsmState.MOVE_FROM_FRYER,
                RecipeFsmEvent.SHAKE_TIME_DONE: RecipeFsmState.SHAKE,
                RecipeFsmEvent.COOKING_TIME_DONE: RecipeFsmState.MOVE_FROM_FRYER,
                RecipeFsmEvent.RESET_MENU: RecipeFsmState.NO_MENU
            },
            RecipeFsmState.SHAKE: {
                RecipeFsmEvent.MOTION_DONE: RecipeFsmState.FRY,
                RecipeFsmEvent.CANCEL_MENU: RecipeFsmState.MOVE_FROM_FRYER,
                RecipeFsmEvent.DONE: RecipeFsmState.FRY,
                RecipeFsmEvent.ERROR_DETECT: RecipeFsmState.FRY,
                RecipeFsmEvent.RESET_MENU: RecipeFsmState.NO_MENU
            },
            RecipeFsmState.MOVE_FROM_FRYER: {
                RecipeFsmEvent.MOTION_DONE: RecipeFsmState.FINISH,
                RecipeFsmEvent.ERROR_DETECT: RecipeFsmState.FINISH,
                RecipeFsmEvent.RESET_MENU: RecipeFsmState.NO_MENU
            },
            RecipeFsmState.FINISH: {
                RecipeFsmEvent.DONE: RecipeFsmState.NO_MENU,
                RecipeFsmEvent.RESET_MENU: RecipeFsmState.NO_MENU
            }
        }

    def _setup_strategies(self):
        self._strategy_table = {
            RecipeFsmState.NO_MENU: NoMenuStrategy(),
            RecipeFsmState.COOKING_READY: CookingReadyStrategy(),
            RecipeFsmState.MOVE_TO_FRYER: MoveToFryStrategy(),
            RecipeFsmState.FRY: FryStrategy(),
            RecipeFsmState.SHAKE: ShakeStrategy(),
            RecipeFsmState.MOVE_FROM_FRYER: MoveFromFryStrategy(),
            RecipeFsmState.FINISH: FinishStrategy()
        }





