from .dry_recipe_context import *
from .process_manager import *
from pkg.configs.global_config import GlobalConfig
from .cooking_logger import cooking_logger
from datetime import datetime
global_config = GlobalConfig()
bb = GlobalBlackboard()

"""
Frying template Recipe FSM Implementation
"""

# class DryNoMenuStrategy(Strategy):
#     def prepare(self, context: DryRecipeContext, **kwargs):
#         ''' States to bb '''
#         bb.set(f"recipe/basket{context.basket_index}/state", DryRecipeFsmState.NO_MENU)

#         ''' Reset recipe menu '''
#         # context.assign_recipe(0)
#         # DryFinishStrategy에서 초기화 해주는 방향으로 변경. 중간에 배출할 시 초기화 안되는 문제 해결.

#         Logger.info(f"{get_time()}: [Basket {context.basket_index} FSM] Enter {self.__class__.__name__} State.")

#     def operate(self, context: DryRecipeContext) -> DryRecipeFsmEvent:
#         """ 고정된 바스켓 인덱스 기반 (1-8)
#         - 바스켓 센서 미인식 시 메뉴 추가 안됨
#         """
#         if context.cancel_basket():
#             return DryRecipeFsmEvent.RESET_MENU
#         if int(bb.get(f"ui/command/basket{context.basket_index}/select")):
#             if context.cancel_basket():
#                 return DryRecipeFsmEvent.RESET_MENU
            
#             # 레시피 번호 읽기 (0 = 대기, 1 ~ 10)
#             new_menu = int(bb.get(f"ui/command/basket{context.basket_index}/state"))
#             # Logger.info(f"Dry {context.basket_index} new_menu : {new_menu}")

#             """ 시나리오
#             1. 사용자가 1번 바스켓에 레시피 5번을 할당한다. (context.recipe_index는 5가 되고, 조리 시작이 됨)
#             2. 로봇이 한창 튀기고 있는데, 사용자가 실수로 UI에서 '레시피 7번' 버튼을 누름. (new_menu는 7이 됨.)
#             3. 만약 context.recipe_index == 0이 없다면, 시스템은 이미 조리 중인 바스켓에 새로운 레시피 7번을 덮어쓰려고 시도할 것.
#             4. 
#             """
#             if new_menu > 0:
#                 if context.recipe_index == 0:
#                     if context.assign_recipe(new_menu) :
#                         bb.set(f"ui/reset/basket{context.basket_index}/select", True)
#                         bb.set(f"ui/reset/basket{context.basket_index}/state", True)
#                         Logger.info(f"{get_time()}: [Basket {context.basket_index} FSM] Assign new menu {new_menu}")
#                         return DryRecipeFsmEvent.ASSIGN_MENU
                    
#         return DryRecipeFsmEvent.NONE

#     def exit(self, context: DryRecipeContext, event: DryRecipeFsmEvent) -> None:
#         Logger.info(f"{get_time()}: [Basket {context.basket_index} FSM] Exit {self.__class__.__name__} State.")

# class DryNoMenuStrategy(Strategy):
#     def prepare(self, context: DryRecipeContext, **kwargs):
#         ''' States to bb '''
#         bb.set(f"recipe/basket{context.basket_index}/state", DryRecipeFsmState.NO_MENU)

#         Logger.info(f"{get_time()}: [Basket {context.basket_index} FSM] Enter {self.__class__.__name__} State.")

#     def operate(self, context: DryRecipeContext) -> DryRecipeFsmEvent:
#         """ 고정된 바스켓 인덱스 기반 (1-8)
#         - 바스켓 센서 미인식 시 메뉴 추가 안됨
#         """
#         if context.cancel_basket():
#             return DryRecipeFsmEvent.RESET_MENU

#         # 앱에서 레시피 선택 명령이 왔을 때
#         if int(bb.get(f"ui/command/basket{context.basket_index}/select")):
#             if context.cancel_basket():
#                 return DryRecipeFsmEvent.RESET_MENU
            
#             # 레시피 번호 읽기 (0 = 대기, 1 ~ 10)
#             new_menu = int(bb.get(f"ui/command/basket{context.basket_index}/state"))
            
#             if new_menu > 0:
#                 # 조건 1: 현재 바스켓이 대기 상태 (recipe_index == 0)
#                 # 조건 2: 바스켓 상태가 NO_MENU (완전한 idle 상태)
#                 current_basket_state = int(bb.get(f"recipe/basket{context.basket_index}/state"))
                
#                 if (context.recipe_index == 0 and 
#                     current_basket_state == DryRecipeFsmState.NO_MENU):
                    
#                     if context.assign_recipe(new_menu):
#                         bb.set(f"ui/reset/basket{context.basket_index}/select", True)
#                         bb.set(f"ui/reset/basket{context.basket_index}/state", True)
#                         Logger.info(f"{get_time()}: [Basket {context.basket_index} FSM] Assign new menu {new_menu}")
#                         return DryRecipeFsmEvent.ASSIGN_MENU
#                 else:
#                     # 조리 중이거나 다른 상태일 때는 명령을 무시하고 리셋
#                     Logger.info(f"{get_time()}: [Basket {context.basket_index} FSM] Recipe assignment rejected - basket not idle (current_state: {current_basket_state}, recipe_index: {context.recipe_index})")
#                     bb.set(f"ui/reset/basket{context.basket_index}/select", True)
#                     bb.set(f"ui/reset/basket{context.basket_index}/state", True)
                    
#         return DryRecipeFsmEvent.NONE

#     def exit(self, context: DryRecipeContext, event: DryRecipeFsmEvent) -> None:
#         Logger.info(f"{get_time()}: [Basket {context.basket_index} FSM] Exit {self.__class__.__name__} State.")
# class DryNoMenuStrategy(Strategy):
#     def prepare(self, context: DryRecipeContext, **kwargs):
#         ''' States to bb '''
#         bb.set(f"recipe/basket{context.basket_index}/state", DryRecipeFsmState.NO_MENU)

#         ''' Reset recipe menu '''
#         # context.assign_recipe(0)
#         # DryFinishStrategy에서 초기화 해주는 방향으로 변경. 중간에 배출할 시 초기화 안되는 문제 해결.

#         Logger.info(f"{get_time()}: [Basket {context.basket_index} FSM] Enter {self.__class__.__name__} State.")
class DryNoMenuStrategy(Strategy):
    def prepare(self, context: DryRecipeContext, **kwargs):
        bb.set(f"recipe/basket{context.basket_index}/state", DryRecipeFsmState.NO_MENU)
        
        if context.recipe_index != 0:
            # 같은 프라이어를 사용하는 다른 바스켓이 활성 상태인지 확인
            other_basket_active = self._check_other_basket_using_fryer(context)
            
            if not other_basket_active:
                # 다른 바스켓이 사용하지 않을 때만 프라이어 해제
                bb.set(f"recipe/enable/fryer{context.fryer_index}", 0)
                bb.set(f"ui/state/fryer{context.fryer_index}/recipe", 0)
                bb.set(f"ui/state/fryer{context.fryer_index}/min", 0)
                bb.set(f"ui/state/fryer{context.fryer_index}/sec", 0)
                bb.set(f"ui/state/fryer{context.fryer_index}/elapsed_time", 0)
                Logger.info(f"{get_time()}: [Basket {context.basket_index} FSM] Released fryer{context.fryer_index}")
            else:
                Logger.info(f"{get_time()}: [Basket {context.basket_index} FSM] Fryer{context.fryer_index} still in use by other basket")
            
            # 개별 바스켓 상태는 항상 초기화
            bb.set(f"recipe/basket{context.basket_index}/fryer", 0)
            bb.set(f"ui/command/basket{context.basket_index}/select", 0)
            bb.set(f"ui/command/basket{context.basket_index}/state", 0)
            
            # Context 초기화
            context.recipe_index = 0
            context.cooking_start_time = 0
            context.fry_time = 0
            context.putin_shake = False
            context.cooking_min = 0
            context.cooking_sec = 0
            context.elapsed_time = 0
            context.overcooking_time = 0
            context.total_elapsed_at_pickup = 0
            context.finish_remaining_time = 1000
            context.shake_num = 0
        
        Logger.info(f"{get_time()}: [Basket {context.basket_index} FSM] Enter {self.__class__.__name__} State.")

    def _check_other_basket_using_fryer(self, context):
        """같은 프라이어를 사용하는 다른 바스켓이 활성 상태인지 확인"""
        from .constants import OPPOSITE_BASKET_MAP
        
        other_basket_idx = OPPOSITE_BASKET_MAP[context.basket_index]
        other_basket_state = bb.get(f"recipe/basket{other_basket_idx}/state")
        
        # 다른 바스켓이 활성 상태인지 확인
        active_states = [
            DryRecipeFsmState.COOKING_READY,
            DryRecipeFsmState.MOVE_TO_FRYER, 
            DryRecipeFsmState.FRY,
            DryRecipeFsmState.SHAKE,
            DryRecipeFsmState.MOVE_FROM_FRYER
        ]
        
        return other_basket_state in active_states

    def operate(self, context: DryRecipeContext) -> DryRecipeFsmEvent:
        """ 고정된 바스켓 인덱스 기반 (1-8)
        - 바스켓 센서 미인식 시 메뉴 추가 안됨
        """
        if context.cancel_basket():
            return DryRecipeFsmEvent.RESET_MENU
        if int(bb.get(f"ui/command/basket{context.basket_index}/select")):
            if context.cancel_basket():
                return DryRecipeFsmEvent.RESET_MENU
            
            # 레시피 번호 읽기 (0 = 대기, 1 ~ 10)
            new_menu = int(bb.get(f"ui/command/basket{context.basket_index}/state"))
            # Logger.info(f"Dry {context.basket_index} new_menu : {new_menu}")

            """ 시나리오
            1. 사용자가 1번 바스켓에 레시피 5번을 할당한다. (context.recipe_index는 5가 되고, 조리 시작이 됨)
            2. 로봇이 한창 튀기고 있는데, 사용자가 실수로 UI에서 '레시피 7번' 버튼을 누름. (new_menu는 7이 됨.)
            3. 만약 context.recipe_index == 0이 없다면, 시스템은 이미 조리 중인 바스켓에 새로운 레시피 7번을 덮어쓰려고 시도할 것.
            4. 
            """
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

    # def operate(self, context: DryRecipeContext) -> DryRecipeFsmEvent:
    #     ''' Reset Menu: 바스켓 매뉴 취소 '''
    #     if context.cancel_basket():
    #         return DryRecipeFsmEvent.RESET_MENU

    #     '''
    #     - Recipe index가 0이 아닐 때
    #     - 바스켓 두 개 간 conflict가 없을 때 (예. 바스켓1, 바스켓3 -> 프라이어1)
    #     '''

    #     # conflict 미사용
    #     # 튀김기 사용 확인 recipe/enable/fryer1~4 : 1(사용중), 0(미사용)
    #     if bb.get(f"recipe/enable/fryer{context.fryer_index}") != 1:

    #         # 동시 실행 방지 부분
    #         if context.defer_execution :
    #             time.sleep(3)
    #             context.defer_execution = False        
    #             return DryRecipeFsmEvent.NONE 

    #         if context.recipe_index != 0:            
    #             bb.set(f"recipe/enable/fryer{context.fryer_index}",1)
    #             Logger.info(f"{get_time()}: [Basket {context.basket_index} FSM] Start cooking.")
    #             return DryRecipeFsmEvent.START_MENU
    #     else :
    #         return DryRecipeFsmEvent.NONE 
    def operate(self, context: DryRecipeContext) -> DryRecipeFsmEvent:
        ''' Reset Menu: 바스켓 메뉴 취소 '''
        if context.cancel_basket():
            return DryRecipeFsmEvent.RESET_MENU

        # 프라이어 사용 중인지 확인
        fryer_in_use = bb.get(f"recipe/enable/fryer{context.fryer_index}") == 1
        
        if fryer_in_use:
            # 같은 프라이어를 사용하는 다른 바스켓이 작업 중이면 대기
            return DryRecipeFsmEvent.NONE
        
        # 동시 실행 방지 부분
        if context.defer_execution:
            time.sleep(3)
            context.defer_execution = False        
            return DryRecipeFsmEvent.NONE 

        if context.recipe_index != 0:            
            bb.set(f"recipe/enable/fryer{context.fryer_index}",1)
            Logger.info(f"{get_time()}: [Basket {context.basket_index} FSM] Start cooking.")
            return DryRecipeFsmEvent.START_MENU
        
        return DryRecipeFsmEvent.NONE
            

    def exit(self, context: DryRecipeContext, event: DryRecipeFsmEvent) -> None:
        Logger.info(f"{get_time()}: [Basket {context.basket_index} FSM] Exit {self.__class__.__name__} State.")


class DryMoveToFryStrategy(Strategy):
    def prepare(self, context: DryRecipeContext, **kwargs):
        ''' States to bb '''
        bb.set(f"recipe/basket{context.basket_index}/state", DryRecipeFsmState.MOVE_TO_FRYER)
        # Logger.info(f"recipe/basket{context.basket_index}/state {DryRecipeFsmState.MOVE_TO_FRYER}")

        Logger.info(f"{get_time()}: [Basket {context.basket_index} FSM] Enter {self.__class__.__name__} State.")
        Logger.info(f"[Debug] Basket {context.basket_index}: putin_shake={context.putin_shake}, type={type(context.putin_shake)}")

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
                # 3,4,7,8번 바스켓이 MOVE_TO_FRYER 상태에 진입했을 때, putin_shake 변수의 실제값과 그 타입을 확인하기 위한 로그. 
                # Logger.info(f"[Debug] Basket {context.basket_index}: putin_shake={context.putin_shake}, type={type(context.putin_shake)}")
                
                # 투입 후 흔들기 한번 실행
                # --- Debugging Start ---
                print(f"--- DEBUG [Basket {context.basket_index}]: Checking shake conditions ---")
                print(f"    context.putin_shake: {context.putin_shake} (type: {type(context.putin_shake)})")
                if context.putin_shake:
                    print(f"    context.fry_time: {context.fry_time} (type: {type(context.fry_time)})")
                    print(f"    Is context.fry_time > 30? {context.fry_time > 30}")
                    if context.fry_time > 30:
                        bb.set("int_var/shake_break/val", 1)
                        print(f"    --- DEBUG: Set 'shake_break' to 1 for basket {context.basket_index} ---")
                print(f"--- DEBUG [Basket {context.basket_index}]: End of shake conditions ---")
                # --- Debugging End ---

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
        # if event == DryRecipeFsmEvent.RESET_MENU:
        #     bb.set(f"recipe/enable/fryer{context.fryer_index}", 0)
        #     Logger.warn(f"[Basket {context.basket_index}] Released fryer {context.fryer_index} lock due to cancellation in {self.__class__.__name__}.")
        Logger.info(f"{get_time()}: [Basket {context.basket_index} FSM] Exit {self.__class__.__name__} State.")


class DryFryStrategy(Strategy):
    def prepare(self, context: DryRecipeContext, **kwargs):
        ''' States to bb '''
        bb.set(f"recipe/basket{context.basket_index}/state", DryRecipeFsmState.FRY)

        Logger.info(f"{get_time()}: [Basket {context.basket_index} FSM] Enter {self.__class__.__name__} State.")

    def operate(self, context: DryRecipeContext) -> DryRecipeFsmEvent:
        ''' 튀김기 상태 업데이트 '''
        context.update_fryer_state()

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
        # if event == DryRecipeFsmEvent.RESET_MENU:
        #     bb.set(f"recipe/enable/fryer{context.fryer_index}", 0)
        #     Logger.warn(f"[Basket {context.basket_index}] Released fryer {context.fryer_index} lock due to cancellation in {self.__class__.__name__}.")
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
            bb.set("int_var/pickup_target_fryer/val", 0)
            # shift 완료 후 새로운 바스켓이 들어올 수 있도록 shake_break 리셋
            # bb.set("int_var/shake_break/val", 0)
        ''' Motion done '''
        basket_idx = int(bb.get(f"recipe/command/move_from_fryer_done"))
        if context.basket_index == basket_idx:
            int_var_temp = int(bb.get("int_var/cmd/val"))
            Logger.info(f"{get_time()}: [Basket {context.basket_index} FSM] Motion move_from_fryer done ({int_var_temp})")

            bb.set(f"recipe/command/move_from_fryer_done", 0)
            # 작업량 추가
            context.update_cooking_done_count()

            if context.cancellation_in_progress:
                bb.set(f"ui/reset/fryer{context.fryer_index}/cancel", True)
                context.cancellation_in_progress = False

            return DryRecipeFsmEvent.MOTION_DONE

        ''' Timer update  '''
        if bb.get("int_var/pickup_done/val") == 0:
            context.update_overcooking_timer()

    def exit(self, context: DryRecipeContext, event: DryRecipeFsmEvent) -> None:
        Logger.info(f"{get_time()}: [Basket {context.basket_index} FSM] Exit {self.__class__.__name__} State.")



class DryFinishStrategy(Strategy):
    def prepare(self, context: DryRecipeContext, **kwargs):
        if context.total_elapsed_at_pickup > 0:
            end_time = datetime.fromtimestamp(context.cooking_start_time + context.total_elapsed_at_pickup)
        else:
            end_time = datetime.now()
        
        start_time = datetime.fromtimestamp(context.cooking_start_time)
        cooking_logger.log(
            basket_name=f"Basket {context.basket_index}",
            recipe_index=context.recipe_index,
            start_time=start_time,
            end_time=end_time,
            process_type='dry'
        )
        bb.set(f"ui/command/fryer{context.fryer_index}/cancel", 0)
        bb.set(f"recipe/basket{context.basket_index}/state", DryRecipeFsmState.FINISH)
        Logger.info(f"{get_time()}: [Basket {context.basket_index} FSM] Enter {self.__class__.__name__} State.")

    def operate(self, context: DryRecipeContext) -> DryRecipeFsmEvent:
        return context.release_finish()

    def exit(self, context: DryRecipeContext, event: DryRecipeFsmEvent) -> None:
        bb.set(f"ui/state/fryer{context.fryer_index}/recipe", 0)
        bb.set(f"ui/state/fryer{context.fryer_index}/min", 0)
        bb.set(f"ui/state/fryer{context.fryer_index}/sec", 0)
        bb.set(f"recipe/basket{context.basket_index}/fryer", 0)
        bb.set(f"recipe/enable/fryer{context.fryer_index}",0)
        bb.set(f"ui/state/fryer{context.fryer_index}/elapsed_time", 0)

        # 다음 사이클에 영향을 주지 않도록 명령 관련 플래그 모두 초기화
        bb.set(f"ui/command/basket{context.basket_index}/select", 0)
        bb.set(f"ui/command/basket{context.basket_index}/state", 0)
        
        context.recipe_index = 0
        context.cooking_start_time = 0
        context.fry_time = 0
        context.putin_shake = False
        context.cooking_min = 0
        context.cooking_sec = 0
        context.elapsed_time = 0
        context.overcooking_time = 0
        context.total_elapsed_at_pickup = 0
        context.cancellation_in_progress = False

        Logger.info(f"{get_time()}: [Basket {context.basket_index} FSM] Exit {self.__class__.__name__} State.")
