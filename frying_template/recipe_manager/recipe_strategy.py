from .recipe_context import *
from .recipe_manager import *
from configs.global_config import GlobalConfig
global_config = GlobalConfig()


bb = GlobalBlackboard()

"""
Frying template Recipe FSM Implementation
"""

class NoMenuStrategy(Strategy):
    def prepare(self, context: RecipeContext, **kwargs):
        ''' States to bb '''
        bb.set(f"recipe/basket{context.basket_index}/state", RecipeFsmState.NO_MENU)

        ''' Reset recipe menu '''
        context.assign_recipe(0, 0)
        if global_config.get("frying_coco_version") == "BType":
            context.fryer_index = 0
            bb.set(f"recipe/basket{context.basket_index}/fryer", 0)
            bb.set(f"ui/reset/basket{context.slot_index}/state", True)

        Logger.info(f"{get_time()}: [Basket {context.basket_index} FSM] Enter {self.__class__.__name__} State.")

    def operate(self, context: RecipeContext) -> RecipeFsmEvent:
        if global_config.get("frying_coco_version") == "AType":
            return self._operate_atype(context)
        elif global_config.get("frying_coco_version") == "BType":
            return self._operate_btype(context)

    def _operate_atype(self, context: RecipeContext) -> RecipeFsmEvent:
        ''' A타입: 고정된 바스켓 인덱스 기반
        - 바스켓 센서 미인식 시 매뉴 추가 안됨
        '''
        if int(bb.get(f"ui/command/basket{context.basket_index}/select")):
            if bb.get(f"indy_state/basket{context.basket_index}") == 0:
                bb.set(f"ui/reset/basket{context.basket_index}/select", True)
                bb.set(f"ui/reset/basket{context.basket_index}/state", True)
                return RecipeFsmEvent.NONE

            new_menu = int(bb.get(f"ui/command/basket{context.basket_index}/state"))
            if new_menu > 0:
                bb.set(f"ui/reset/basket{context.basket_index}/select", True)
                if context.recipe_index == 0:
                    Logger.info(f"{get_time()}: [Basket {context.basket_index} FSM] Assign new menu {new_menu}")
                    context.assign_recipe(new_menu, context.basket_index)
                    return RecipeFsmEvent.ASSIGN_MENU

        return RecipeFsmEvent.NONE

    def _operate_ctype(self, context: RecipeContext) -> RecipeFsmEvent:
        ''' C타입: 고정된 바스켓 인덱스 기반
        - 바스켓 센서 없음
        - 가루반죽, 물반죽 레시피 동일?
        '''
        if int(bb.get(f"ui/command/basket{context.basket_index}/select")):
            if bb.get(f"indy_state/basket{context.basket_index}") == 0:
                bb.set(f"ui/reset/basket{context.basket_index}/select", True)
                bb.set(f"ui/reset/basket{context.basket_index}/state", True)
                return RecipeFsmEvent.NONE

            new_menu = int(bb.get(f"ui/command/basket{context.basket_index}/state"))
            if new_menu > 0:
                bb.set(f"ui/reset/basket{context.basket_index}/select", True)
                if context.recipe_index == 0:
                    Logger.info(f"{get_time()}: [Basket {context.basket_index} FSM] Assign new menu {new_menu}")
                    context.assign_recipe(new_menu, context.basket_index)
                    return RecipeFsmEvent.ASSIGN_MENU

        return RecipeFsmEvent.NONE

    def _operate_btype(self, context: RecipeContext) -> RecipeFsmEvent:
        ''' B타입: 공통 메뉴 선택 플래그 + 내부 바스켓 인덱스 할당 '''
        # FSM 자체가 아직 할당 대상이 아닌 경우 → 할당 대상이 되어야 하는지 확인
        with fsm_assign_lock:
            if not context.is_assign_ready:
                for fsm_idx in range(1, 9):
                    if fsm_idx == context.basket_index:
                        continue  # 본인 제외
                    if bb.get(f"recipe/basket{fsm_idx}/state") == RecipeFsmState.NO_MENU:
                        other_ready = bb.get(f"recipe/basket{fsm_idx}/assign_ready")
                        if other_ready:
                            return RecipeFsmEvent.NONE  # 다른 FSM이 이미 assign 중

                # 자신이 첫 assign 후보가 됨
                context.is_assign_ready = True
                bb.set(f"recipe/basket{context.basket_index}/assign_ready", True)
                Logger.info(f"[Basket {context.basket_index} FSM] Set to assign_ready")


        if context.is_assign_ready:
            for slot_idx in range(1, 5):
                if int(bb.get(f"ui/command/basket{slot_idx}/select")):
                    if bb.get(f"indy_state/basket{slot_idx}") == 0:
                        bb.set(f"ui/reset/basket{slot_idx}/select", True)
                        bb.set(f"ui/reset/basket{slot_idx}/state", True)
                        continue

                    bb.set(f"ui/reset/basket{slot_idx}/select", True)
                    context.slot_index = slot_idx
                    while True:
                        # 다음 assign_ready가 되는 fsm이 곧바로 똑같은 slot에 할당해버림
                        time.sleep(0.1)
                        if bb.get(f"ui/command/basket{slot_idx}/select") == 0:
                            break

                    new_menu = int(bb.get(f"ui/command/basket{slot_idx}/state"))
                    if new_menu > 0 and context.recipe_index == 0:
                        context.is_assign_ready = False
                        bb.set(f"recipe/basket{context.basket_index}/assign_ready", False)
                        Logger.info(f"[Basket {context.basket_index} FSM] UI Slot {slot_idx} menu {new_menu} is assigned")
                        context.assign_recipe(new_menu, slot_idx)
                        return RecipeFsmEvent.ASSIGN_MENU

        return RecipeFsmEvent.NONE

    def exit(self, context: RecipeContext, event: RecipeFsmEvent) -> None:
        Logger.info(f"{get_time()}: [Basket {context.basket_index} FSM] Exit {self.__class__.__name__} State.")


class CookingReadyStrategy(Strategy):
    def prepare(self, context: RecipeContext, **kwargs):
        ''' States to bb '''
        bb.set(f"recipe/basket{context.basket_index}/state", RecipeFsmState.COOKING_READY)

        Logger.info(f"{get_time()}: [Basket {context.basket_index} FSM] Enter {self.__class__.__name__} State.")

    def operate(self, context: RecipeContext) -> RecipeFsmEvent:
        ''' Reset Menu: 바스켓 매뉴 취소 '''
        if context.cancel_basket():
            return RecipeFsmEvent.RESET_MENU

        ''' Start Menu: COOKING_READY -> MOVE_TO_FRYER '''
        if global_config.get("frying_coco_version") == "AType":
            return self._operate_atype(context)
        elif global_config.get("frying_coco_version") == "BType":
            return self._operate_btype(context)

    def _operate_atype(self, context: RecipeContext) -> RecipeFsmEvent:
        ''' A타입
        - Recipe index가 0이 아닐 때
        - 바스켓 센서 신호 있을 때
        - 바스켓 두 개 간 conflict가 없을 때 (예. 바스켓1, 바스켓3 -> 프라이어1)
        '''
        if (context.recipe_index != 0 and
            bb.get(f"indy_state/basket{context.basket_index}") and
            context.check_no_conflict()):

            Logger.info(f"{get_time()}: [Basket {context.basket_index} FSM] Start cooking.")
            return RecipeFsmEvent.START_MENU

    def _operate_btype(self, context: RecipeContext) -> RecipeFsmEvent:
        ''' B타입
        - Recipe index가 0이 아닐 때
        - 바스켓 센서 신호 있을 때
        - 빈 프라이어 찾아서 할당
        '''
        if (context.recipe_index != 0 and
                bb.get(f"indy_state/basket{context.slot_index}")):
            return context.assign_empty_fryer()

    def exit(self, context: RecipeContext, event: RecipeFsmEvent) -> None:
        Logger.info(f"{get_time()}: [Basket {context.basket_index} FSM] Exit {self.__class__.__name__} State.")


class MoveToFryStrategy(Strategy):
    def prepare(self, context: RecipeContext, **kwargs):
        ''' States to bb '''
        bb.set(f"recipe/basket{context.basket_index}/state", RecipeFsmState.MOVE_TO_FRYER)

        Logger.info(f"{get_time()}: [Basket {context.basket_index} FSM] Enter {self.__class__.__name__} State.")

    def operate(self, context: RecipeContext) -> RecipeFsmEvent:
        ''' Reset Menu: 바스켓 매뉴 취소 '''
        if context.cancel_basket():
            return RecipeFsmEvent.RESET_MENU

        ''' Motion done '''
        basket_idx = int(bb.get(f"recipe/command/move_to_fryer_done"))
        if context.basket_index == basket_idx:
            int_var_temp = int(bb.get("int_var/cmd/val"))
            Logger.info(f"{get_time()}: [Basket {context.basket_index} FSM] Motion move_to_fryer done ({int_var_temp})")

            bb.set(f"recipe/command/move_to_fryer_done", 0)
            context.cooking_start_time = time.time()
            if global_config.get("frying_coco_version") == "BType":
                bb.set(f"ui/reset/basket{context.slot_index}/state", True)
            return RecipeFsmEvent.MOTION_DONE

    def exit(self, context: RecipeContext, event: RecipeFsmEvent) -> None:
        Logger.info(f"{get_time()}: [Basket {context.basket_index} FSM] Exit {self.__class__.__name__} State.")


class FryStrategy(Strategy):
    def prepare(self, context: RecipeContext, **kwargs):
        ''' States to bb '''
        bb.set(f"recipe/basket{context.basket_index}/state", RecipeFsmState.FRY)

        Logger.info(f"{get_time()}: [Basket {context.basket_index} FSM] Enter {self.__class__.__name__} State.")

    def operate(self, context: RecipeContext) -> RecipeFsmEvent:
        ''' 튀김기 상태 업데이트 '''
        context.update_fryer_state()

        ''' Cancel menu: 튀김기 매뉴 취소 '''
        fryer_cancel = int(bb.get(f"ui/command/fryer{context.fryer_index}/cancel"))
        if fryer_cancel:
            return context.cancel_fryer()
        else:
            ''' Timer update  '''
            context.update_timer()
            return context.check_timer()


    def exit(self, context: RecipeContext, event: RecipeFsmEvent) -> None:
        Logger.info(f"{get_time()}: [Basket {context.basket_index} FSM] Exit {self.__class__.__name__} State.")

class ShakeStrategy(Strategy):
    def prepare(self, context: RecipeContext, **kwargs):
        ''' States to bb '''
        bb.set(f"recipe/basket{context.basket_index}/state", RecipeFsmState.SHAKE)


        Logger.info(f"{get_time()}: [Basket {context.basket_index} FSM] Enter {self.__class__.__name__} State.")

    def operate(self, context: RecipeContext) -> RecipeFsmEvent:
        ''' 튀김기 상태 업데이트 '''
        context.update_fryer_state()

        ''' Timer update '''
        context.update_timer()

        ''' Cancel menu: 튀김기 매뉴 취소 '''
        fryer_cancel = int(bb.get(f"ui/command/fryer{context.fryer_index}/cancel"))
        if fryer_cancel:
            return context.cancel_fryer()

        ''' Shake Motion done '''
        basket_idx = int(bb.get("recipe/command/shake_done"))
        if context.basket_index == basket_idx:
            int_var_temp = int(bb.get("int_var/cmd/val"))
            Logger.info(f"{get_time()}: [Basket {context.basket_index} FSM] Motion shake done ({int_var_temp})")

            bb.set(f"recipe/command/shake_done", 0)

            return RecipeFsmEvent.MOTION_DONE
        elif bb.get("int_var/cmd/val") == int(ContyCommand.SHAKE_BASKET_A + context.basket_index):
            ''' Shake 모션 실행 중 '''
            return RecipeFsmEvent.NONE
        else:
            ''' Skip shake '''
            return context.check_shake_timer()

    def exit(self, context: RecipeContext, event: RecipeFsmEvent) -> None:
        Logger.info(f"{get_time()}: [Basket {context.basket_index} FSM] Exit {self.__class__.__name__} State.")

class MoveFromFryStrategy(Strategy):
    def prepare(self, context: RecipeContext, **kwargs):
        ''' States to bb '''
        bb.set(f"recipe/basket{context.basket_index}/state", RecipeFsmState.MOVE_FROM_FRYER)

        Logger.info(f"{get_time()}: [Basket {context.basket_index} FSM] Enter {self.__class__.__name__} State.")

    def operate(self, context: RecipeContext) -> RecipeFsmEvent:
        ''' 튀김기 상태 업데이트 '''
        context.update_fryer_state()

        ''' Motion done '''
        basket_idx = int(bb.get(f"recipe/command/move_from_fryer_done"))
        if context.basket_index == basket_idx:
            int_var_temp = int(bb.get("int_var/cmd/val"))
            Logger.info(f"{get_time()}: [Basket {context.basket_index} FSM] Motion move_from_fryer done ({int_var_temp})")

            bb.set(f"recipe/command/move_from_fryer_done", 0)

            return RecipeFsmEvent.MOTION_DONE

        ''' Timer update  '''
        context.update_overcooking_timer()

    def exit(self, context: RecipeContext, event: RecipeFsmEvent) -> None:
        Logger.info(f"{get_time()}: [Basket {context.basket_index} FSM] Exit {self.__class__.__name__} State.")



class FinishStrategy(Strategy):
    def prepare(self, context: RecipeContext, **kwargs):
        ''' States to bb '''
        bb.set(f"recipe/basket{context.basket_index}/state", RecipeFsmState.FINISH)

        bb.set(f"ui/state/fryer{context.fryer_index}/recipe", 0)
        bb.set(f"ui/state/fryer{context.fryer_index}/min", 0)
        bb.set(f"ui/state/fryer{context.fryer_index}/sec", 0)
        bb.set(f"recipe/basket{context.basket_index}/fryer", 0)

        Logger.info(f"{get_time()}: [Basket {context.basket_index} FSM] Enter {self.__class__.__name__} State.")

    def operate(self, context: RecipeContext) -> RecipeFsmEvent:
        ''' 바스켓 회수 '''
        if global_config.get("frying_coco_version") == "AType":
            return context.release_finish()
        else:
            context.update_cooking_done_count()
            return RecipeFsmEvent.DONE

    def exit(self, context: RecipeContext, event: RecipeFsmEvent) -> None:
        Logger.info(f"{get_time()}: [Basket {context.basket_index} FSM] Exit {self.__class__.__name__} State.")