from .wet_recipe_context import *
from .process_manager import *
from pkg.configs.global_config import GlobalConfig
from .cooking_logger import cooking_logger
from datetime import datetime
global_config = GlobalConfig()
bb = GlobalBlackboard()

"""
Frying template Recipe FSM Implementation
"""

# class WaitPutinStrategy(Strategy):
#     def prepare(self, context: WetRecipeContext, **kwargs):
#         context.reset_cooking_state()
#         bb.set(f"recipe/basket{context.basket_index}/state", WetRecipeFsmState.WAIT_PUTIN)
#         ''' Reset recipe menu '''
#         context.assign_recipe(0)
#         # --- Putin Shake 프라이어별 상태 플래그 설정 ---
#         bb.set(f"wet_recipe/fryer{context.fryer_index}/putin_shake_active", True)

#         Logger.info(f"{get_time()}: [Basket {context.basket_index} FSM] Enter {self.__class__.__name__} State.")
#         Logger.info(f"{get_time()} Wet FSM {context.fsm_index} - basket {context.basket_index}, {context.fryer_index}")

#     def operate(self, context: WetRecipeContext) -> WetRecipeFsmEvent:
#         # TODO : assign basket (외부)
        
#         # if context.basket_index == 3 and bb.get("recipe/basket1/state") == WetRecipeFsmState.WAIT_PUTIN :
#         #     return None
                
#         # elif context.basket_index == 8 and bb.get("recipe/basket6/state") == WetRecipeFsmState.WAIT_PUTIN :
#         #     return None
        
#         putin_btn = int(bb.get(f"ui/command/putin_shake{context.fryer_index}"))

#         #Logger.info(f"putin_btn : {putin_btn} for test-------------")

#         # if bb.get("robot/state/worktarget") == 0 :  
#         if putin_btn == 1:
#             bb.set(f"ui/reset/putin_shake{context.fryer_index}",True)
#             bb.set(f"ui/state/putin_shake{context.fryer_index}",1)
#             Logger.info(f"putin_btn {context.fryer_index} {putin_btn}")
#             bb.set("int_var/shake_break/val", 0)
#             bb.set("int_var/putin_shake/val", 1)
                
#             Logger.info(f"[TEMP_FIX] putin_btn {context.fryer_index} {putin_btn} - set putin_shake=1, shake_break=0")
#             # bb.set("int_var/shake_break/val",0)
#             return WetRecipeFsmEvent.START_PUTIN
class WaitPutinStrategy(Strategy):
    def prepare(self, context: WetRecipeContext, **kwargs):
        context.reset_cooking_state()
        bb.set(f"recipe/basket{context.basket_index}/state", WetRecipeFsmState.WAIT_PUTIN)
        
        ''' Reset recipe menu '''
        context.assign_recipe(0)
        
        # 3번, 6번 바스켓만 특별 처리
        # if context.basket_index in [3, 8]:
        bb.set("int_var/putin_shake/val", 1)  # 초기화
        bb.set("int_var/shake_break/val", 0)   # 초기화
        bb.set("int_var/shake_done/val", 0)
        Logger.info(f"[SPECIAL] Basket {context.basket_index}: Reset putin_shake=0, shake_done=0")
        
        # Putin Shake 프라이어별 상태 플래그 설정
        bb.set(f"wet_recipe/fryer{context.fryer_index}/putin_shake_active", True)

        Logger.info(f"{get_time()}: [Basket {context.basket_index} FSM] Enter {self.__class__.__name__} State.")

    def operate(self, context: WetRecipeContext) -> WetRecipeFsmEvent:
        putin_btn = int(bb.get(f"ui/command/putin_shake{context.fryer_index}"))

        if putin_btn == 1:
            bb.set(f"ui/reset/putin_shake{context.fryer_index}",True)
            bb.set(f"ui/state/putin_shake{context.fryer_index}",1)
            Logger.info(f"putin_btn {context.fryer_index} {putin_btn}")

            # 흔들기 시작 설정
            bb.set("int_var/shake_break/val", 0)  # 흔들기 허용
            bb.set("int_var/putin_shake/val", 1)  # 흔들기 시작
            bb.set("int_var/shake_done/val", 0)   # 흔들기 미완료
                
            Logger.info(f"[PUTIN_START] Basket {context.basket_index}: Set putin_shake=1, shake_break=0, shake_done=0")
            return WetRecipeFsmEvent.START_PUTIN
        
    def exit(self, context: WetRecipeContext, event: WetRecipeFsmEvent) -> None:
        Logger.info(f"{get_time()}: [Basket {context.basket_index} FSM] Exit {self.__class__.__name__} State.")

# class PutinStrategy(Strategy):
#     def prepare(self, context: WetRecipeContext, **kwargs):
#         bb.set(f"recipe/basket{context.basket_index}/state", WetRecipeFsmState.PUTIN)
#         Logger.info(f"{get_time()}: [Basket {context.basket_index} FSM] Enter {self.__class__.__name__} State.")

#     def operate(self, context: WetRecipeContext) -> WetRecipeFsmEvent:
#         # TODO: trigger motion
#         if context.basket_index == bb.get(f"robot/state/worktarget") :
#             current_cmd = int(bb.get("int_var/cmd/val"))
#             putin_done = int(bb.get("int_var/putin_done/val"))
#             check_cmd = 310 + context.basket_index
#             if putin_done and current_cmd == check_cmd:
#                 if context.cooking_start_time == 0:
#                     context.cooking_start_time = time.time()
#                     context.initial_cooking_start_time = time.time()
#                 context.update_fryer_state()
#                 context.update_timer()
#                 bb.set(f"ui/state/putin_shake{context.fryer_index}",2)
#                 bb.set(f"ui/reset/putin_shake{context.fryer_index}",True)
                
#                 return WetRecipeFsmEvent.DONE
            
#         if bb.get("int_var/shake_break/val") :
#             current_cmd = int(bb.get("int_var/cmd/val"))
#             check_cmd = 310 + context.basket_index
#             if current_cmd == check_cmd:   
#                 bb.set(f"ui/state/putin_shake{context.fryer_index}",2)
#                 bb.set(f"ui/reset/putin_shake{context.fryer_index}",True)
#                 return WetRecipeFsmEvent.DONE

#     def exit(self, context: WetRecipeContext, event: WetRecipeFsmEvent) -> None:
#         Logger.info(f"{get_time()}: [Basket {context.basket_index} FSM] Exit {self.__class__.__name__} State.")
# class PutinStrategy(Strategy):
#     def prepare(self, context: WetRecipeContext, **kwargs):
#         bb.set(f"recipe/basket{context.basket_index}/state", WetRecipeFsmState.PUTIN)
#         Logger.info(f"{get_time()}: [Basket {context.basket_index} FSM] Enter {self.__class__.__name__} State.")

#     def operate(self, context: WetRecipeContext) -> WetRecipeFsmEvent:
#         # TODO: trigger motion
#         if context.basket_index == bb.get(f"robot/state/worktarget") :
#             current_cmd = int(bb.get("int_var/cmd/val"))
#             putin_done = int(bb.get("int_var/putin_done/val"))
#             check_cmd = 310 + context.basket_index
#             if putin_done and current_cmd == check_cmd:
#                 if context.cooking_start_time == 0:
#                     context.cooking_start_time = time.time()
#                     context.initial_cooking_start_time = time.time()
#                 context.update_fryer_state()
#                 context.update_timer()
#                 bb.set(f"ui/state/putin_shake{context.fryer_index}",2)
#                 bb.set(f"ui/reset/putin_shake{context.fryer_index}",True)
                
#                 return WetRecipeFsmEvent.DONE
            
#         if bb.get("int_var/shake_break/val") :
#             current_cmd = int(bb.get("int_var/cmd/val"))
#             check_cmd = 310 + context.basket_index
#             if current_cmd == check_cmd:   
#                 bb.set(f"ui/state/putin_shake{context.fryer_index}",2)
#                 bb.set(f"ui/reset/putin_shake{context.fryer_index}",True)
#                 return WetRecipeFsmEvent.DONE

#     def exit(self, context: WetRecipeContext, event: WetRecipeFsmEvent) -> None:
        # Logger.info(f"{get_time()}: [Basket {context.basket_index} FSM] Exit {self.__class__.__name__} State.")
class PutinStrategy(Strategy):
    def prepare(self, context: WetRecipeContext, **kwargs):
        bb.set(f"recipe/basket{context.basket_index}/state", WetRecipeFsmState.PUTIN)
        Logger.info(f"{get_time()}: [Basket {context.basket_index} FSM] Enter {self.__class__.__name__} State.")
        bb.set("int_var/putin_shake/val", 1)  # 흔들기 시작
        bb.set("int_var/shake_done/val", 0)   # 흔들기 미완료
        bb.set("int_var/shake_break/val", 0)  # 흔들기 허용
        Logger.info(f"{get_time()}: [Basket {context.basket_index} FSM] Enter PUTIN State. Set putin_shake=1")
    def operate(self, context: WetRecipeContext) -> WetRecipeFsmEvent:
        # 세트별 순차 처리 로직
        should_wait = False
        
        if context.basket_index == 3:  # 3번은 1번 완료 후
            basket1_state = bb.get("recipe/basket1/state")
            if basket1_state == WetRecipeFsmState.PUTIN:
                should_wait = True
                Logger.info(f"[Basket 3] Waiting for Basket 1 to complete putin_shake")
                
        elif context.basket_index == 8:  # 8번은 6번 완료 후
            basket6_state = bb.get("recipe/basket6/state")
            if basket6_state == WetRecipeFsmState.PUTIN:
                should_wait = True
                Logger.info(f"[Basket 8] Waiting for Basket 6 to complete putin_shake")
        
        # 대기 중이면 아무것도 하지 않음
        if should_wait:
            return WetRecipeFsmEvent.NONE
        
        # 기존 로직 (수정 없음)
        if context.basket_index == bb.get(f"robot/state/worktarget"):
            current_cmd = int(bb.get("int_var/cmd/val"))
            putin_done = int(bb.get("int_var/putin_done/val"))
            check_cmd = 310 + context.basket_index
            if putin_done and current_cmd == check_cmd:
                if context.cooking_start_time == 0:
                    context.cooking_start_time = time.time()
                    context.initial_cooking_start_time = time.time()
                context.update_fryer_state()
                context.update_timer()
                bb.set(f"ui/state/putin_shake{context.fryer_index}",2)
                bb.set(f"ui/reset/putin_shake{context.fryer_index}",True)
                
                return WetRecipeFsmEvent.DONE
            
        if bb.get("int_var/shake_break/val"):
            current_cmd = int(bb.get("int_var/cmd/val"))
            check_cmd = 310 + context.basket_index
            if current_cmd == check_cmd:   
                bb.set(f"ui/state/putin_shake{context.fryer_index}",2)
                bb.set(f"ui/reset/putin_shake{context.fryer_index}",True)
                return WetRecipeFsmEvent.DONE

        return WetRecipeFsmEvent.NONE
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

                    # ProcessManager에서 관리하므로 제거
                    bb.set("int_var/shake_done/val",1)
                    bb.set("int_var/shake_break/val",1)

                    # 타이머 시작
                    if context.cooking_start_time == 0 :
                        context.cooking_start_time = time.time()
                    
                    context.update_fryer_state()
                    context.update_timer()

                    return WetRecipeFsmEvent.ASSIGN_MENU

    def exit(self, context: WetRecipeContext, event: WetRecipeFsmEvent) -> None:
        # --- Putin Shake 프라이어별 상태 플래그 해제 ---
        bb.set(f"wet_recipe/fryer{context.fryer_index}/putin_shake_active", False)

        Logger.info(f"{get_time()}: [Basket {context.basket_index} FSM] Exit {self.__class__.__name__} State. Fryer {context.fryer_index}")


class WetPreFryStrategy(Strategy):
    def prepare(self, context: WetRecipeContext, **kwargs):
        bb.set(f"recipe/basket{context.basket_index}/state", WetRecipeFsmState.PRE_FRY)

        Logger.info(f"{get_time()}: [Basket {context.basket_index} FSM] Enter {self.__class__.__name__} State.")
    

    def operate(self, context: WetRecipeContext) -> WetRecipeFsmEvent:
        ''' 튀김기 상태 업데이트 '''
        context.update_fryer_state()

        if context.cooking_start_time == 0 :
            context.cooking_start_time = time.time()

        # --- 타이머 업데이트 (항상 실행) ---
        context.update_timer()
        # --- 타이머 업데이트 끝 ---

        # --- 수동 버튼 처리 로직 (최우선) ---
        if int(bb.get(f"ui/command/manual_btn{context.fryer_index}")) == 2:
            bb.set(f"ui/reset/manual_btn{context.fryer_index}",True)
            # TODO: check fryer 2 is available
            return WetRecipeFsmEvent.DONE_SHIFT
        
        elif int(bb.get(f"ui/command/manual_btn{context.fryer_index}")) == 1:
            bb.set(f"ui/reset/manual_btn{context.fryer_index}",True)
            return WetRecipeFsmEvent.MANUAL_SERVE
        # --- 수동 버튼 처리 로직 끝 ---

        # --- 튀김기 취소 로직 ---
        fryer_cancel = int(bb.get(f"ui/command/fryer{context.fryer_index}/cancel"))
        if fryer_cancel:
            return context.cancel_fryer()
        # --- 튀김기 취소 로직 끝 ---


        # --- 초벌 튀김 완료 판단 로직 ---
        # pickup_done 신호가 Conty에서 단일 소스로 오므로, 타겟팅 메커니즘 사용
        # pickup_signal = int(bb.get("int_var/pickup_done/val"))
        # pickup_target = int(bb.get("int_var/pickup_target_fryer/val"))

        # 1. 신호 기반 처리 (1번, 4번 프라이기 대상)
        # if pickup_signal != 0 and pickup_target == context.fryer_index:
        #     context.total_elapsed_at_pickup = context.elapsed_time
        #     Logger.info(f"{get_time()}: [Basket {context.basket_index} FSM] Targeted pickup signal received. "
        #                 f"total_elapsed_at_pickup set to {context.total_elapsed_at_pickup:.2f}")
            
        #     # 신호와 타겟을 모두 리셋하여 중복 처리 방지
        #     bb.set("int_var/pickup_done/val", 0)
        #     bb.set("pickup_target_fryer", 0)
            
        #     return WetRecipeFsmEvent.COOKING_TIME_DONE
        
        # 2. 타이머 기반 처리 (신호가 없거나, 1번/4번 프라이기에서 신호가 누락된 경우의 폴백)
        # 초벌 시간이 경과했는지 확인
        if context.elapsed_time >= context.pre_fry_time:
            # ProcessManager에서 관리하므로 제거
            # bb.set("int_var/shake_break/val",1)  
            
            if bb.get("int_var/pickup_done/val") == 0 :
                context.total_elapsed_at_pickup = context.elapsed_time
                Logger.info(f"{get_time()} : [Basket {context.basket_index} FSM] Pre-fry time elapsed. total_elapsed_at_pickup set to {context.total_elapsed_at_pickup:.2f}")

            return WetRecipeFsmEvent.COOKING_TIME_DONE
        
        # elif context.elapsed_time >= context.pre_fry_time - 20:
        #     # 이 부분은 유지 - 특별한 조건에서만 설정
        #     if context.fryer_index == 1 :
        #         if bb.get(f"ui/state/fryer2/recipe") :
        #             pass
        #         else :
        #             # ProcessManager에서 관리하므로 제거 고려
        #             # bb.set("int_var/shake_break/val",1)  
        #             pass

        #     elif context.fryer_index == 4 :
        #         if bb.get(f"ui/state/fryer3/recipe") :
        #             pass
        #         else :
        #             # ProcessManager에서 관리하므로 제거 고려
        #             # bb.set("int_var/shake_break/val",1)  
        #             pass

    def exit(self, context: WetRecipeContext, event: WetRecipeFsmEvent) -> None:
        Logger.info(f"{get_time()}: [Basket {context.basket_index} FSM] Exit {self.__class__.__name__} State.")



class WetFryStrategy(Strategy):
    def prepare(self, context: WetRecipeContext, **kwargs):
        bb.set(f"recipe/basket{context.basket_index}/state", WetRecipeFsmState.FRY)
        Logger.info(f"{get_time()}: [Basket {context.basket_index} FSM] Enter {self.__class__.__name__} State.")

        context.main_fry_target_duration = context.fry_time - context.total_elapsed_at_pickup
        Logger.info(f"{get_time()}: [Basket {context.basket_index} FSM] main_fry_target_duration calculated: {context.main_fry_target_duration:.2f} (fry_time: {context.fry_time:.2f}, total_elapsed_at_pickup: {context.total_elapsed_at_pickup:.2f})")
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
                #bb.set("int_var/shake_break/val",1)  
                Logger.info(f"{get_time()}: [Basket {context.basket_index} FSM] COOKING TIME DONE event triggered in Fry state.")
                return WetRecipeFsmEvent.COOKING_TIME_DONE
            # elif context.elapsed_time >= context.main_fry_target_duration - 20:
                #bb.set("int_var/shake_break/val",1)  
                # Logger.info(f"{get_time()} : [Basket {context.basket_index} FSM] duration - 20.")
            else:
                return WetRecipeFsmEvent.NONE
        
    def exit(self, context: WetRecipeContext, event: WetRecipeFsmEvent) -> None:
        Logger.info(f"{get_time()}: [Basket {context.basket_index} FSM] Exit {self.__class__.__name__} State.")


class ShiftBasketStrategy(Strategy):    
    def prepare(self, context: WetRecipeContext, **kwargs):
        bb.set(f"recipe/basket{context.basket_index}/state", WetRecipeFsmState.SHIFT_BASKET)
        Logger.info(f"{get_time()}: [Basket {context.basket_index} FSM] Enter {self.__class__.__name__} State.")
        if context.basket_index == 3:
            Logger.info(f"[DEBUG_B3] Entering SHIFT_BASKET. total_elapsed_at_pickup = {context.total_elapsed_at_pickup:.2f}")

    def operate(self, context: WetRecipeContext) -> WetRecipeFsmEvent:
        ''' 튀김기 상태 업데이트 '''
        
        context.update_fryer_state()
        context.update_timer()
         # pickup_done 신호가 Conty에서 단일 소스로 오므로, 타겟팅 메커니즘 사용
        pickup_signal = int(bb.get("int_var/pickup_done/val"))
        pickup_target = int(bb.get("int_var/pickup_target_fryer/val"))

        if pickup_signal > 0 and pickup_target > 0 :
            Logger.info(f"{get_time()} : [Fryer {pickup_target} has received pickup singal {pickup_signal}.")
        # 1. 신호 기반 처리 (1번, 4번 프라이기 대상)
        if pickup_signal != 0 and pickup_target == context.fryer_index:
            context.total_elapsed_at_pickup = context.elapsed_time
            Logger.info(f"{get_time()}: [Basket {context.basket_index} FSM] Targeted pickup signal received. "
                        f"total_elapsed_at_pickup set to {context.total_elapsed_at_pickup:.2f}")
            
            # 신호와 타겟을 모두 리셋하여 중복 처리 방지
            bb.set("int_var/pickup_done/val", 0)
            bb.set("pickup_target_fryer", 0)
            # shift 완료 후 새로운 바스켓이 들어올 수 있도록 shake_break 리셋
            bb.set("int_var/shake_break/val", 0)
            # return WetRecipeFsmEvent.COOKING_TIME_DONE
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
        # context.update_overcooking_timer()

    def exit(self, context: WetRecipeContext, event: WetRecipeFsmEvent) -> None:
        if context.basket_index == 3:
            Logger.info(f"[DEBUG_B3] Exiting SHIFT_BASKET. total_elapsed_at_pickup = {context.total_elapsed_at_pickup:.2f}")
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
        context.update_timer()
         # pickup_done 신호가 Conty에서 단일 소스로 오므로, 타겟팅 메커니즘 사용
        pickup_signal = int(bb.get("int_var/pickup_done/val"))
        pickup_target = int(bb.get("int_var/pickup_target_fryer/val"))

        if pickup_signal > 0 and pickup_target > 0 :
            Logger.info(f"{get_time()} : [Fryer {pickup_target} has received pickup singal {pickup_signal}.")
        # 1. 신호 기반 처리 (1번, 4번 프라이기 대상)
        if pickup_signal != 0 and pickup_target == context.fryer_index:
            if context.pickup_done_cnt == 0 :
                context.pickup_signal_time = time.time()
                context.total_elapsed_at_pickup += context.elapsed_time
                Logger.info(f"{get_time()}: [Basket {context.basket_index} FSM] Targeted pickup signal received. "
                        f"total_elapsed_at_pickup updated to {context.total_elapsed_at_pickup:.2f}")
            context.pickup_done_cnt+=1
            # 신호와 타겟을 모두 리셋하여 중복 처리 방지
            bb.set("int_var/pickup_done/val", 0)
            bb.set("int_var/pickup_target_fryer/val", 0)

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
        context.pickup_done_cnt = 0
        
        # Derive start_time and end_time from the pickup signal and total duration
        if context.pickup_signal_time > 0 and context.total_elapsed_at_pickup > 0:
            end_time_ts = context.pickup_signal_time
            start_time_ts = end_time_ts - context.total_elapsed_at_pickup
            
            start_time = datetime.fromtimestamp(start_time_ts)
            end_time = datetime.fromtimestamp(end_time_ts)
        else:
            # Fallback if the necessary values aren't available
            end_time = datetime.now()
            start_time = end_time

        cooking_tact_time = (end_time - start_time).total_seconds()
        Logger.info(f"cooking tact time : {cooking_tact_time:.2f}")
        
        cooking_logger.log(
            basket_name=f"Basket {context.basket_index}",
            recipe_index=context.recipe_index,
            start_time=start_time,
            end_time=end_time,
            process_type='wet'
        )

        bb.set(f"recipe/basket{context.basket_index}/state", WetRecipeFsmState.FINISH)
        Logger.info(f"{get_time()}: [Basket {context.basket_index} FSM] Enter {self.__class__.__name__} State.")
        
    def operate(self, context: WetRecipeContext) -> WetRecipeFsmEvent:
        return context.release_finish()

    def exit(self, context: WetRecipeContext, event: WetRecipeFsmEvent) -> None:
        bb.set(f"ui/state/fryer{context.fryer_index}/recipe", 0)
        bb.set(f"ui/state/fryer{context.fryer_index}/min", 0)
        bb.set(f"ui/state/fryer{context.fryer_index}/sec", 0)
        bb.set(f"recipe/basket{context.basket_index}/fryer", 0)
        bb.set(f"ui/state/putin_shake{context.fryer_index}", 0)

        bb.set("int_var/shake_break/val", 0)
        Logger.info(f"[FINISH] Set shake_break=0 for basket {context.basket_index}")

        context.reset_cooking_state()

        Logger.info(f"{get_time()}: [Basket {context.basket_index} FSM] Exit {self.__class__.__name__} State.")
