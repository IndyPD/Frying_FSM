from .wet_recipe_context import *
from .process_manager import *
from pkg.configs.global_config import GlobalConfig
global_config = GlobalConfig()
bb = GlobalBlackboard()

"""
Frying template Recipe FSM Implementation
"""

class WaitPutinStrategy(Strategy):
    def prepare(self, context: WetRecipeContext, **kwargs):
        bb.set(f"recipe/basket{context.basket_index}/state", WetRecipeFsmState.WAIT_PUTIN)
        ''' Reset recipe menu '''
        context.assign_recipe(0)

        Logger.info(f"{get_time()}: [Basket {context.basket_index} FSM] Enter {self.__class__.__name__} State.")
        Logger.info(f"{get_time()} Wet FSM {context.fsm_index} - basket {context.basket_index}, {context.fryer_index}")

    def operate(self, context: WetRecipeContext) -> WetRecipeFsmEvent:
        # TODO : assign basket (외부)
        
        if context.basket_index == 3 and bb.get("recipe/basket1/state") == WetRecipeFsmState.WAIT_PUTIN :
            return None
                
        elif context.basket_index == 8 and bb.get("recipe/basket6/state") == WetRecipeFsmState.WAIT_PUTIN :
            return None
        
        putin_btn = int(bb.get(f"ui/command/putin_shake{context.fryer_index}"))

        #Logger.info(f"putin_btn : {putin_btn} for test-------------")

        if bb.get("robot/state/worktarget") == 0 :  
            if putin_btn == 1:
                bb.set(f"ui/reset/putin_shake{context.fryer_index}",True)
                bb.set(f"ui/state/putin_shake{context.fryer_index}",1)
                Logger.info(f"putin_btn {context.fryer_index} {putin_btn}")
                bb.set("int_var/shake_break/val",0)
                return WetRecipeFsmEvent.START_PUTIN

    def exit(self, context: WetRecipeContext, event: WetRecipeFsmEvent) -> None:
        Logger.info(f"{get_time()}: [Basket {context.basket_index} FSM] Exit {self.__class__.__name__} State.")

class PutinStrategy(Strategy):
    def prepare(self, context: WetRecipeContext, **kwargs):
        bb.set(f"recipe/basket{context.basket_index}/state", WetRecipeFsmState.PUTIN)
        Logger.info(f"{get_time()}: [Basket {context.basket_index} FSM] Enter {self.__class__.__name__} State.")

    def operate(self, context: WetRecipeContext) -> WetRecipeFsmEvent:

        if context.basket_index == 3:
            if bb.get("robot/state/worktarget") == 1 :
                return WetRecipeFsmEvent.RESET_MENU
        elif context.basket_index == 8:
            if bb.get("robot/state/worktarget") == 6 :
                return WetRecipeFsmEvent.RESET_MENU
            
        if bb.get(f"robot/state/worktarget") != context.basket_index and bb.get(f"robot/state/worktarget") != 0:
            return WetRecipeFsmEvent.RESET_MENU
            
        # TODO: trigger motion
        if context.basket_index == bb.get(f"robot/state/worktarget") :
            current_cmd = int(bb.get("int_var/cmd/val"))
            putin_done = int(bb.get("int_var/putin_done/val"))
            check_cmd = 310 + context.basket_index
            if putin_done and current_cmd == check_cmd:                
                if context.cooking_start_time == 0 :
                    context.cooking_start_time = time.time()
                context.update_fryer_state()
                context.update_timer()
                bb.set(f"ui/state/putin_shake{context.fryer_index}",2)
                bb.set(f"ui/reset/putin_shake{context.fryer_index}",True)
                return WetRecipeFsmEvent.DONE
            
        if bb.get("int_var/shake_break/val") :
            current_cmd = int(bb.get("int_var/cmd/val"))
            check_cmd = 310 + context.basket_index
            if current_cmd == check_cmd:   
                bb.set(f"ui/state/putin_shake{context.fryer_index}",2)
                bb.set(f"ui/reset/putin_shake{context.fryer_index}",True)
                return WetRecipeFsmEvent.DONE

    def exit(self, context: WetRecipeContext, event: WetRecipeFsmEvent) -> None:
        Logger.info(f"{get_time()}: [Basket {context.basket_index} FSM] Exit {self.__class__.__name__} State.")

class WaitMenuStrategy(Strategy):
    def prepare(self, context: WetRecipeContext, **kwargs):
        bb.set(f"recipe/basket{context.basket_index}/state", WetRecipeFsmState.WAIT_MENU)
        Logger.info(f"{get_time()}: [Basket {context.basket_index} FSM] Enter {self.__class__.__name__} State.")
        

    def operate(self, context: WetRecipeContext) -> WetRecipeFsmEvent:
        if context.basket_index in [1,3] :
            select_index = 1
        
        elif context.basket_index in [6,8] :
            select_index = 4
        else :
            select_index = context.basket_index

        if int(bb.get(f"ui/command/basket{select_index}/select")):
            new_menu = int(bb.get(f"ui/command/basket{select_index}/state"))
            if new_menu > 0:
                bb.set(f"ui/reset/basket{select_index}/select", True)
                bb.set(f"ui/reset/basket{select_index}/state", True)
                if context.recipe_index == 0:
                    Logger.info(f"{get_time()}: [Basket {select_index} FSM] Assign new menu {new_menu}")
                    context.assign_recipe(new_menu)

                    # 매뉴 추가시 쉐이크 종료
                    bb.set("int_var/shake_break/val",1)

                    # 타이머 시작
                    if context.cooking_start_time == 0 :
                        context.cooking_start_time = time.time()
                    
                    context.update_fryer_state()
                    context.update_timer()

                    return WetRecipeFsmEvent.ASSIGN_MENU
                
    def exit(self, context: WetRecipeContext, event: WetRecipeFsmEvent) -> None:
        Logger.info(f"{get_time()}: [Basket {context.basket_index} FSM] Exit {self.__class__.__name__} State.")


class WetPreFryStrategy(Strategy):
    def prepare(self, context: WetRecipeContext, **kwargs):
        bb.set(f"recipe/basket{context.basket_index}/state", WetRecipeFsmState.PRE_FRY)
        Logger.info(f"{get_time()}: [Basket {context.basket_index} FSM] Enter {self.__class__.__name__} State.")

        

    def operate(self, context: WetRecipeContext) -> WetRecipeFsmEvent:
        ''' 튀김기 상태 업데이트 '''
        context.update_fryer_state()

        if context.cooking_start_time == 0 :
            context.cooking_start_time = time.time()

        # context.update_fryer_state()
        # context.update_timer()

        if int(bb.get(f"ui/command/manual_btn{context.fryer_index}")) == 2:
            bb.set(f"ui/reset/manual_btn{context.fryer_index}",True)
            # TODO: check fryer 2 is available
            return WetRecipeFsmEvent.DONE_SHIFT
        
        elif int(bb.get(f"ui/command/manual_btn{context.fryer_index}")) == 1:
            bb.set(f"ui/reset/manual_btn{context.fryer_index}",True)
            return WetRecipeFsmEvent.MANUAL_SERVE
        
        ''' Cancel menu: 튀김기 매뉴 취소 '''
        fryer_cancel = int(bb.get(f"ui/command/fryer{context.fryer_index}/cancel"))
        if fryer_cancel:
            return context.cancel_fryer()

        # TODO: timer update
        ''' Timer update  '''
        context.update_overcooking_timer()        
        if context.elapsed_time >= context.pre_fry_time:
            # Logger.info(f"{get_time()} WetPreFryStrategy {context.elapsed_time} {context.pre_fry_time} ")
            bb.set("int_var/shake_break/val",1)  
            if (bb.get(f"int_var/pickup_done/fryer{context.fryer_index}/val") != 0) :
                context.total_elapsed_at_pickup = context.elapsed_time

            return WetRecipeFsmEvent.COOKING_TIME_DONE
        
        elif context.elapsed_time >= context.pre_fry_time - 20:
            if context.fryer_index == 1 :
                if bb.get(f"ui/state/fryer2/recipe") :
                    pass
                else :
                    bb.set("int_var/shake_break/val",1)  

            elif context.fryer_index == 4 :
                if bb.get(f"ui/state/fryer3/recipe") :
                    pass
                else :
                    bb.set("int_var/shake_break/val",1)  

        else:
            return WetRecipeFsmEvent.NONE

    def exit(self, context: WetRecipeContext, event: WetRecipeFsmEvent) -> None:
        Logger.info(f"{get_time()}: [Basket {context.basket_index} FSM] Exit {self.__class__.__name__} State.")



class WetFryStrategy(Strategy):
    def prepare(self, context: WetRecipeContext, **kwargs):
        bb.set(f"recipe/basket{context.basket_index}/state", WetRecipeFsmState.FRY)
        Logger.info(f"{get_time()}: [Basket {context.basket_index} FSM] Enter {self.__class__.__name__} State.")

        context.main_fry_target_duration = context.fry_time - context.total_elapsed_at_pickup
        context.cooking_start_time = time.time()
    def operate(self, context: WetRecipeContext) -> WetRecipeFsmEvent:
        ''' 튀김기 상태 업데이트 '''
        context.update_fryer_state()       
        if int(bb.get(f"ui/command/manual_btn{context.fryer_index}")) == 1:
            bb.set(f"ui/reset/manual_btn{context.fryer_index}",True)
            return WetRecipeFsmEvent.MANUAL_SERVE

        ''' Cancel menu: 튀김기 매뉴 취소 '''
        fryer_cancel = int(bb.get(f"ui/command/fryer{context.fryer_index}/cancel"))
        if fryer_cancel:
            return context.cancel_fryer()
        else:
            ''' Timer update  '''
            context.update_timer()
            if context.elapsed_time >= context.main_fry_target_duration:
                bb.set("int_var/shake_break/val",1)  
                return WetRecipeFsmEvent.COOKING_TIME_DONE
            elif context.elapsed_time >= context.main_fry_target_duration - 20:
                bb.set("int_var/shake_break/val",1)  
            else:
                return WetRecipeFsmEvent.NONE
        
    def exit(self, context: WetRecipeContext, event: WetRecipeFsmEvent) -> None:
        Logger.info(f"{get_time()}: [Basket {context.basket_index} FSM] Exit {self.__class__.__name__} State.")


class ShiftBasketStrategy(Strategy):    
    def prepare(self, context: WetRecipeContext, **kwargs):
        bb.set(f"recipe/basket{context.basket_index}/state", WetRecipeFsmState.SHIFT_BASKET)
        Logger.info(f"{get_time()}: [Basket {context.basket_index} FSM] Enter {self.__class__.__name__} State.")

    def operate(self, context: WetRecipeContext) -> WetRecipeFsmEvent:
        ''' 튀김기 상태 업데이트 '''
        
        context.update_fryer_state()

        ''' Motion done '''
        basket_idx = int(bb.get(f"recipe/command/shift_basket_done"))
        # Logger.info(f"ShiftBasketStrategy : {basket_idx}")
        if context.basket_index == basket_idx:
            int_var_temp = int(bb.get("int_var/cmd/val"))
            Logger.info(f"{get_time()}: [Basket {context.basket_index} FSM] Motion shift_basket done ({int_var_temp})")

            bb.set(f"recipe/command/shift_basket_done", 0)

            # 타이머 시작
            if context.cooking_start_time == 0 :
                context.cooking_start_time = time.time()
            
            # context.assign_recipe(0)
            bb.set(f"ui/state/fryer{context.fryer_index}/recipe", 0)
            bb.set(f"ui/state/fryer{context.fryer_index}/min", 0)
            bb.set(f"ui/state/fryer{context.fryer_index}/sec", 0)
            if context.basket_index in [1,3] :
                bb.set(f"recipe/basket{context.basket_index}/fryer", 2)
                context.fryer_index = 2
            elif context.basket_index in [6,8] : 
                bb.set(f"recipe/basket{context.basket_index}/fryer", 3)
                context.fryer_index = 3
            
            return WetRecipeFsmEvent.MOTION_DONE

        ''' Timer update  '''
        context.update_overcooking_timer()

    def exit(self, context: WetRecipeContext, event: WetRecipeFsmEvent) -> None:
        Logger.info(f"{get_time()}: [Basket {context.basket_index} FSM] Exit {self.__class__.__name__} State.")


# class WetShakeStrategy(Strategy):
#     def prepare(self, context: WetRecipeContext, **kwargs):#
#         Logger.info(f"{get_time()}: [Basket {context.basket_index} FSM] Enter {self.__class__.__name__} State.")
#
#     def operate(self, context: WetRecipeContext) -> WetRecipeFsmEvent:
#         ''' 튀김기 상태 업데이트 '''
#         context.update_fryer_state()
#
#         ''' Timer update '''
#         context.update_timer()
#
#         ''' Cancel menu: 튀김기 매뉴 취소 '''
#         fryer_cancel = int(bb.get(f"ui/command/fryer{context.fryer_index}/cancel"))
#         if fryer_cancel:
#             return context.cancel_fryer()
#
#         ''' Shake Motion done '''
#         basket_idx = int(bb.get("recipe/command/shake_done"))
#         if context.basket_index == basket_idx:
#             int_var_temp = int(bb.get("int_var/cmd/val"))
#             Logger.info(f"{get_time()}: [Basket {context.basket_index} FSM] Motion shake done ({int_var_temp})")
#
#             bb.set(f"recipe/command/shake_done", 0)
#
#             return WetRecipeFsmEvent.MOTION_DONE
#         elif bb.get("int_var/cmd/val") == int(ContyCommand.SHAKE_BASKET + context.basket_index):
#             ''' Shake 모션 실행 중 '''
#             return WetRecipeFsmEvent.NONE
#         else:
#             ''' Skip shake '''
#             return context.check_shake_timer()
#
#     def exit(self, context: WetRecipeContext, event: WetRecipeFsmEvent) -> None:
#         Logger.info(f"{get_time()}: [Basket {context.basket_index} FSM] Exit {self.__class__.__name__} State.")

class WetMoveFromFryStrategy(Strategy):
    def prepare(self, context: WetRecipeContext, **kwargs):
        bb.set(f"recipe/basket{context.basket_index}/state", WetRecipeFsmState.MOVE_FROM_FRYER)        
        Logger.info(f"{get_time()}: [Basket {context.basket_index} FSM] Enter {self.__class__.__name__} State.")

    def operate(self, context: WetRecipeContext) -> WetRecipeFsmEvent:
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

            return WetRecipeFsmEvent.MOTION_DONE

        ''' Timer update  '''
        if bb.get("int_var/pickup_done/val") == 0:
            context.update_overcooking_timer()

    def exit(self, context: WetRecipeContext, event: WetRecipeFsmEvent) -> None:
        Logger.info(f"{get_time()}: [Basket {context.basket_index} FSM] Exit {self.__class__.__name__} State.")



class WetFinishStrategy(Strategy):
    def prepare(self, context: WetRecipeContext, **kwargs):
        bb.set(f"recipe/basket{context.basket_index}/state", WetRecipeFsmState.FINISH)
        bb.set(f"ui/state/fryer{context.fryer_index}/recipe", 0)
        bb.set(f"ui/state/fryer{context.fryer_index}/min", 0)
        bb.set(f"ui/state/fryer{context.fryer_index}/sec", 0)
        bb.set(f"recipe/basket{context.basket_index}/fryer", 0)
        bb.set(f"ui/state/putin_shake{context.fryer_index}", 0)

        Logger.info(f"{get_time()}: [Basket {context.basket_index} FSM] Enter {self.__class__.__name__} State.")

        context.reset_cooking_state()

    def operate(self, context: WetRecipeContext) -> WetRecipeFsmEvent:
        ''' 바스켓 회수 '''
        return context.release_finish()

    def exit(self, context: WetRecipeContext, event: WetRecipeFsmEvent) -> None:
        Logger.info(f"{get_time()}: [Basket {context.basket_index} FSM] Exit {self.__class__.__name__} State.")
