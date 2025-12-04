from .dry_recipe_context import *
from .process_manager import *
from pkg.configs.global_config import GlobalConfig
global_config = GlobalConfig()
bb = GlobalBlackboard()

"""
Frying template Recipe FSM Implementation
"""

class DryNoMenuStrategy(Strategy):
    def prepare(self, context: DryRecipeContext, **kwargs):
        ''' States to bb '''
        bb.set(f"recipe/basket{context.basket_index}/state", DryRecipeFsmState.NO_MENU)

        ''' Reset recipe menu '''
        # context.assign_recipe(0)
        # DryFinishStrategy에서 초기화 해주는 방향으로 변경. 중간에 배출할 시 초기화 안되는 문제 해결.

        Logger.info(f"{get_time()}: [Basket {context.basket_index} FSM] Enter {self.__class__.__name__} State.")

    def operate(self, context: DryRecipeContext) -> DryRecipeFsmEvent:
        ''' 고정된 바스켓 인덱스 기반 (1-8)
        - 바스켓 센서 미인식 시 메뉴 추가 안됨
        '''
        if context.cancel_basket():
            return DryRecipeFsmEvent.RESET_MENU
        if int(bb.get(f"ui/command/basket{context.basket_index}/select")):
            if context.cancel_basket():
                return DryRecipeFsmEvent.RESET_MENU
            
            new_menu = int(bb.get(f"ui/command/basket{context.basket_index}/state"))
            # Logger.info(f"Dry {context.basket_index} new_menu : {new_menu}")
            if new_menu > 0:
                if context.recipe_index == 0:
                    if context.assign_recipe(new_menu) :
                        bb.set(f"ui/reset/basket{context.basket_index}/select", True)
                        bb.set(f"ui/reset/basket{context.basket_index}/state", True)
                        Logger.info(f"{get_time()}: [Basket {context.basket_index} FSM] Assign new menu {new_menu}")
                        return DryRecipeFsmEvent.ASSIGN_MENU
                    
        return DryRecipeFsmEvent.NONE

    def exit(self, context: DryRecipeContext, event: DryRecipeFsmEvent) -> None:
        Logger.info(f"{get_time()}: [Basket {context.basket_index} FSM] Exit {self.__class__.__name__} State.")


class DryCookingReadyStrategy(Strategy):
    def prepare(self, context: DryRecipeContext, **kwargs):
        ''' States to bb '''
        bb.set(f"recipe/basket{context.basket_index}/state", DryRecipeFsmState.COOKING_READY)

        Logger.info(f"{get_time()}: [Basket {context.basket_index} FSM] Enter {self.__class__.__name__} State.")

    def operate(self, context: DryRecipeContext) -> DryRecipeFsmEvent:
        ''' Reset Menu: 바스켓 매뉴 취소 '''
        if context.cancel_basket():
            return DryRecipeFsmEvent.RESET_MENU

        '''
        - Recipe index가 0이 아닐 때
        - 바스켓 두 개 간 conflict가 없을 때 (예. 바스켓1, 바스켓3 -> 프라이어1)
        '''

        # conflict 미사용
        # 튀김기 사용 확인 recipe/enable/fryer1~4 : 1(사용중), 0(미사용)
        if bb.get(f"recipe/enable/fryer{context.fryer_index}") != 1:

            # 동시 실행 방지 부분
            if context.defer_execution :
                time.sleep(3)
                context.defer_execution = False        
                return DryRecipeFsmEvent.NONE 

            if context.recipe_index != 0:            
                bb.set(f"recipe/enable/fryer{context.fryer_index}",1)
                Logger.info(f"{get_time()}: [Basket {context.basket_index} FSM] Start cooking.")
                return DryRecipeFsmEvent.START_MENU
        else :
            return DryRecipeFsmEvent.NONE 
            

    def exit(self, context: DryRecipeContext, event: DryRecipeFsmEvent) -> None:
        Logger.info(f"{get_time()}: [Basket {context.basket_index} FSM] Exit {self.__class__.__name__} State.")


class DryMoveToFryStrategy(Strategy):
    def prepare(self, context: DryRecipeContext, **kwargs):
        ''' States to bb '''
        bb.set(f"recipe/basket{context.basket_index}/state", DryRecipeFsmState.MOVE_TO_FRYER)
        # Logger.info(f"recipe/basket{context.basket_index}/state {DryRecipeFsmState.MOVE_TO_FRYER}")

        Logger.info(f"{get_time()}: [Basket {context.basket_index} FSM] Enter {self.__class__.__name__} State.")

    def operate(self, context: DryRecipeContext) -> DryRecipeFsmEvent:
        ''' Reset Menu: 바스켓 매뉴 취소 '''
        if context.cancel_basket():
            return DryRecipeFsmEvent.RESET_MENU
        if bb.get("robot/state/worktarget") == context.basket_index :            
            putin_done = int(bb.get("int_var/putin_done/val"))            
            if putin_done :
                if context.cooking_start_time == 0 :
                    context.cooking_start_time = time.time()

                context.update_fryer_state()
                context.update_timer()
                Logger.info(f"[Debug] Basket {context.basket_index}: putin_shake={context.putin_shake}, type={type(context.putin_shake)}")
                # 투입 후 흔들기 한번 실행
                if context.putin_shake == 1 :
                    if context.fry_time > 10 :
                        bb.set("int_var/shake_break/val",1)

        ''' Motion done '''
        basket_idx = int(bb.get(f"recipe/command/move_to_fryer_done"))
        if context.basket_index == basket_idx:
            int_var_temp = int(bb.get("int_var/cmd/val"))
            Logger.info(f"{get_time()}: [Basket {context.basket_index} FSM] Motion move_to_fryer done ({int_var_temp})")

            bb.set(f"recipe/command/move_to_fryer_done", 0)
            # 투입 후 흔들기 관련 변수 초기화
            bb.set("int_var/shake_break/val",0)
            # context.cooking_start_time = time.time()
            
            return DryRecipeFsmEvent.MOTION_DONE

    def exit(self, context: DryRecipeContext, event: DryRecipeFsmEvent) -> None:
        Logger.info(f"{get_time()}: [Basket {context.basket_index} FSM] Exit {self.__class__.__name__} State.")


class DryFryStrategy(Strategy):
    def prepare(self, context: DryRecipeContext, **kwargs):
        ''' States to bb '''
        bb.set(f"recipe/basket{context.basket_index}/state", DryRecipeFsmState.FRY)

        Logger.info(f"{get_time()}: [Basket {context.basket_index} FSM] Enter {self.__class__.__name__} State.")

    def operate(self, context: DryRecipeContext) -> DryRecipeFsmEvent:
        ''' 튀김기 상태 업데이트 '''
        context.update_fryer_state()

        ''' Real-time cooking time update '''
        new_time = int(bb.get(f"ui/command/fryer{context.fryer_index}/update_time"))
        if new_time > 0:
            Logger.info(f"{get_time()}: [Basket {context.basket_index} FSM] Update fry_time from {context.fry_time} to {new_time}")
            context.fry_time = new_time
            bb.set(f"ui/command/fryer{context.fryer_index}/update_time", 0) # Reset command

        ''' Cancel menu: 튀김기 매뉴 취소 '''
        fryer_cancel = int(bb.get(f"ui/command/fryer{context.fryer_index}/cancel"))
        if fryer_cancel:
            return context.cancel_fryer()
        else:
            ''' Timer update  '''
            context.update_timer()
            if context.elapsed_time >= context.fry_time:
                return DryRecipeFsmEvent.COOKING_TIME_DONE
            else:
                return DryRecipeFsmEvent.NONE


    def exit(self, context: DryRecipeContext, event: DryRecipeFsmEvent) -> None:
        Logger.info(f"{get_time()}: [Basket {context.basket_index} FSM] Exit {self.__class__.__name__} State.")

class DryShakeStrategy(Strategy):
    def prepare(self, context: DryRecipeContext, **kwargs):
        ''' States to bb '''
        bb.set(f"recipe/basket{context.basket_index}/state", DryRecipeFsmState.SHAKE)
        context.last_shake_done_time = time.time()

        Logger.info(f"{get_time()}: [Basket {context.basket_index} FSM] Enter {self.__class__.__name__} State.")

    def operate(self, context: DryRecipeContext) -> DryRecipeFsmEvent:
        ''' 튀김기 상태 업데이트 '''
        context.update_fryer_state()

        ''' Timer update '''
        context.update_timer()

        ''' Cancel menu: 튀김기 매뉴 취소 '''
        fryer_cancel = int(bb.get(f"ui/command/fryer{context.fryer_index}/cancel"))
        if fryer_cancel:
            return context.cancel_fryer()
        
        ''' Cooking Time : 70 초 이하로 남았을 때, MoveFromFryer'''
        if context.finish_remaining_time < 70 :
            return DryRecipeFsmEvent.DONE

        ''' Shake Motion done '''
        basket_idx = int(bb.get("recipe/command/shake_done"))
        if context.basket_index == basket_idx:
            int_var_temp = int(bb.get("int_var/cmd/val"))
            Logger.info(f"{get_time()}: [Basket {context.basket_index} FSM] Motion shake done ({int_var_temp})")

            bb.set(f"recipe/command/shake_done", 0)
            context.shake_num += 1
            context.last_shake_done_time = time.time()
            return DryRecipeFsmEvent.MOTION_DONE
        elif bb.get("int_var/cmd/val") == int(ContyCommand.SHAKE_BASKET + context.basket_index):
            ''' Shake 모션 실행 중 '''
            return DryRecipeFsmEvent.NONE
        else:
            ''' Skip shake '''
            return context.check_shake_timer()

    def exit(self, context: DryRecipeContext, event: DryRecipeFsmEvent) -> None:
        Logger.info(f"{get_time()}: [Basket {context.basket_index} FSM] Exit {self.__class__.__name__} State.")

class DryMoveFromFryStrategy(Strategy):
    def prepare(self, context: DryRecipeContext, **kwargs):
        ''' States to bb '''
        bb.set(f"recipe/basket{context.basket_index}/state", DryRecipeFsmState.MOVE_FROM_FRYER)

        Logger.info(f"{get_time()}: [Basket {context.basket_index} FSM] Enter {self.__class__.__name__} State.")

    def operate(self, context: DryRecipeContext) -> DryRecipeFsmEvent:
        ''' 튀김기 상태 업데이트 '''
        context.update_fryer_state()

        ''' Motion done '''
        basket_idx = int(bb.get(f"recipe/command/move_from_fryer_done"))
        if context.basket_index == basket_idx:
            int_var_temp = int(bb.get("int_var/cmd/val"))
            Logger.info(f"{get_time()}: [Basket {context.basket_index} FSM] Motion move_from_fryer done ({int_var_temp})")

            bb.set(f"recipe/command/move_from_fryer_done", 0)
            # 작업량 추가
            context.update_cooking_done_count()

            return DryRecipeFsmEvent.MOTION_DONE

        ''' Timer update  '''
        if bb.get("int_var/pickup_done/val") == 0:
            context.update_overcooking_timer()

    def exit(self, context: DryRecipeContext, event: DryRecipeFsmEvent) -> None:
        Logger.info(f"{get_time()}: [Basket {context.basket_index} FSM] Exit {self.__class__.__name__} State.")



class DryFinishStrategy(Strategy):
    def prepare(self, context: DryRecipeContext, **kwargs):
        ''' States to bb '''
        bb.set(f"recipe/basket{context.basket_index}/state", DryRecipeFsmState.FINISH)
        bb.set(f"ui/state/fryer{context.fryer_index}/recipe", 0)
        bb.set(f"ui/state/fryer{context.fryer_index}/min", 0)
        bb.set(f"ui/state/fryer{context.fryer_index}/sec", 0)
        bb.set(f"recipe/basket{context.basket_index}/fryer", 0)
        bb.set(f"recipe/enable/fryer{context.fryer_index}",0)
        bb.set(f"ui/state/fryer{context.fryer_index}/elapsed_time", 0)
        
        # Init the recipe
        context.assign_recipe(0)

        Logger.info(f"{get_time()}: [Basket {context.basket_index} FSM] Enter {self.__class__.__name__} State.")

    def operate(self, context: DryRecipeContext) -> DryRecipeFsmEvent:
        ''' 바스켓 회수 '''
        return context.release_finish()

    def exit(self, context: DryRecipeContext, event: DryRecipeFsmEvent) -> None:
        Logger.info(f"{get_time()}: [Basket {context.basket_index} FSM] Exit {self.__class__.__name__} State.")
