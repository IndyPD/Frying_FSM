from pkg.utils.blackboard import GlobalBlackboard
from pkg.utils.process_control import Flagger, reraise
from pkg.utils.file_io import load_json, save_json
from pkg.configs.global_config import GlobalConfig
from .constants import *


import bisect

bb = GlobalBlackboard()
global_config = GlobalConfig()


class WetRecipeContext(ContextBase):
    violation_code: ViolationType

    def __init__(self, basket_idx):
        ContextBase.__init__(self)

        ''' Recipe config file '''
        self.config_file = CONFIG_FILE
        self.fryer_index = 0

        ''' Basket and fryer index '''
        self.basket_index = basket_idx
        self.fsm_index = basket_idx
        if self.basket_index in {1, 3}:   # {BASKET1, BASKET3} in FRYER1
            self.fryer_index = 1
        elif self.basket_index in {6, 8}: # {BASKET5, BASKET7} in FRYER3
            self.fryer_index = 4
        Logger.info(f"{self.basket_index} fryer Index : {self.fryer_index}")

        ''' Load default recipe (recipe0) '''
        self.config = load_json(self.config_file)
        self.recipe = self.config["recipe0"]
        self.recipe_index = 0

        ''' Cooking time related '''
        self.cooking_state = CookingState.NONE
        self.cooking_start_time = 0
        self.cooking_min = 0
        self.cooking_sec = 0
        self.elapsed_time = 0
        self.fry_time = 0
        self.overcooking_time = 0

        self.total_elapsed_at_pickup = 0
        self.main_fry_target_duration = 0
        ''' Flag '''
        self.putin_done = False

        ''' Shake related '''
        self.putin_shake = False
        self.shake_num = 1
        self.shake_break = False

        self.fry_type = "wet"
        self.shake_type = "auto"
        

        self.next_state = WetRecipeFsmState.WAIT_PUTIN

        self.finish_remaining_time = 1000

    def reset_cooking_state(self) :
        
        self.recipe_index = 0
        self.cooking_start_time = 0
        self.fry_time = 0
        self.putin_shake = False  # <--- 이 부분이 경쟁 상태를 일으킵니다.
        
        self.cooking_min = 0
        self.cooking_sec = 0
        self.elapsed_time = 0
        self.overcooking_time = 0
        self.total_elapsed_at_pickup = 0
        self.main_fry_target_duration = 0        
    def assign_recipe(self, recipe_idx):
        """
        지정된 recipe_idx에 해당하는 레시피 설정 로드
        - recipe_idx: 0~10, 0은 초기화
        - 작업 단계 리스트 초기화
        - recipe_idx: 레시피 인덱스, 저장된 10개 중 불러오기
        """
        ''' Assign menu '''
        self.config = load_json(CONFIG_FILE)
        self.recipe = self.config[f"recipe{recipe_idx}"]
        self.recipe_index = recipe_idx

        ''' Initialize fryer index '''
        if self.basket_index in {1, 3}:  # {BASKET1, BASKET3} in FRYER1
            self.fryer_index = 1
        elif self.basket_index in {6, 8}:  # {BASKET5, BASKET7} in FRYER3
            self.fryer_index = 4

        self.cooking_start_time = time.time()
        
        try :
            self.frying_type = int(self.recipe["frying_type"])  # 1 for dry, 2 for wet        
        except :
            self.frying_type = int(self.recipe["type"])

        try :
            self.pre_fry_time = int(self.recipe["pre_fry_time"])
        except :
            self.pre_fry_time = int(self.recipe["first_fry_time"])

        self.fry_time = int(self.recipe["fry_time"])
        # self.fry_time = 30
        # try :
        #     self.putin_shake = bool(self.recipe["putin_shake"])
        # except :
        #     self.putin_shake = bool(self.recipe["input_shake"])
        self.putin_shake = 1
         # 흔들기 모션 값 bb추가
        bb.set("int_var/putin_shake/val",self.putin_shake)

        self.cooking_min = 0
        self.cooking_sec = 0
        self.elapsed_time = 0
        self.overcooking_time = 0

        self.total_elapsed_at_pickup = 0
        self.main_fry_target_duration = 0
        ''' Init motion '''
        if self.frying_type == 2:
            if int(bb.get("recipe/command/move_to_fryer_done")) == self.basket_index:
                bb.set("recipe/command/move_to_fryer_done", 0)

            if int(bb.get("recipe/command/move_from_fryer_done")) == self.basket_index:
                bb.set("recipe/command/move_from_fryer_done", 0)

            if int(bb.get("recipe/command/shake_done")) == self.basket_index:
                bb.set("recipe/command/shake_done", 0)
            
            if int(bb.get("recipe/command/shift_basket_done")) == self.basket_index:
                bb.set("recipe/command/shift_basket_done", 0)
            
            return True
        else :
            return False

    def cancel_basket(self):
        '''
        바스켓 매뉴 취소: COOKING_READY, MOVE_TO_FRY 상태에서만 동작
            3. App에서 바스켓 취소
        '''
        basket_cancel = int(bb.get("ui/command/cancel_recipe"))
        if self.basket_index == basket_cancel:
            bb.set("ui/reset/cancel_recipe", True)
            bb.set(f"ui/reset/basket{self.basket_index}/state", True)
            if self.recipe_index != 0:
                Logger.info(f"{get_time()}: [Basket {self.basket_index} FSM] Cancel basket by App.")
                return True
            else:
                return False
        else:
            return False

    def cancel_fryer(self):
        bb.set(f"ui/reset/fryer{self.fryer_index}/cancel", True)
        bb.set(f"ui/reset/manual_btn{self.fryer_index}",True)
        Logger.info(f"{get_time()}: [Basket {self.basket_index} FSM] "
                    f"Cancel fryer {self.fryer_index}.")
        return WetRecipeFsmEvent.CANCEL_MENU

    def update_fryer_state(self):
        ''' UI Fryer state '''
        bb.set(f"ui/state/fryer{self.fryer_index}/recipe", self.recipe_index)
        bb.set(f"ui/state/fryer{self.fryer_index}/min", self.cooking_min)
        bb.set(f"ui/state/fryer{self.fryer_index}/sec", self.cooking_sec)

    def peek_next_state(self):
        return self.next_state

    def update_timer(self):
        """ update timer
        - cooking elapsed time 계산
        """
        ''' 기본 타이머 계산: elapsed time, cooking time, remaining time '''
        self.elapsed_time = time.time() - self.cooking_start_time
        self.cooking_min = int((self.elapsed_time % 3600) // 60)
        self.cooking_sec = int(self.elapsed_time % 60)
        self.finish_remaining_time = self.fry_time - self.elapsed_time

    def update_overcooking_timer(self):
        ''' Update until Pick-up motion done '''
        val = int(bb.get(f"int_var/pickup_done/fryer{self.fryer_index}/val"))

        if val > 0:
            return WetRecipeFsmEvent.NONE
        else:
            self.elapsed_time = time.time() - self.cooking_start_time
            self.cooking_min = int((self.elapsed_time % 3600) // 60)
            self.cooking_sec = int(self.elapsed_time % 60)
            self.overcooking_time = self.elapsed_time - self.fry_time

    def check_no_conflict(self, from_state, to_state):
        """
        Conflict check during PRE_FRY -> FRY 
        - 1,4번에 이미 바스켓이 있다면 넣지 않도록
        - 1,3번 바스켓은 2번 fryer 5,7번 바스켓은 3번 fryer 로 이동
        - 2번과,3번 fryer 에 이미 있다면 옮기지 않도록 판단
        """

        if not (from_state == WetRecipeFsmState.PRE_FRY and to_state == WetRecipeFsmState.FRY):
            return True  # Only enforce checks during PRE_FRY -> FRY

        # Same fryer conflict
        target_idx = OPPOSITE_BASKET_MAP.get(self.basket_index)
        if target_idx is not None:
            target_state = bb.get(f"recipe/basket{target_idx}/state")
            if target_state not in {WetRecipeFsmState.NO_MENU, WetRecipeFsmState.PRE_FRY, WetRecipeFsmState.FINISH}:
                return False

        # Prevent new assignment if fryer1 (baskets 1,3) or fryer4 (baskets 5,7) is occupied
        if self.basket_index in {1, 3}:
            for idx in [1, 3]:
                if idx != self.basket_index:
                    if bb.get(f"recipe/basket{idx}/state") not in {WetRecipeFsmState.NO_MENU, WetRecipeFsmState.FINISH}:
                        return False
        elif self.basket_index in {5, 7}:
            for idx in [5, 7]:
                if idx != self.basket_index:
                    if bb.get(f"recipe/basket{idx}/state") not in {WetRecipeFsmState.NO_MENU, WetRecipeFsmState.FINISH}:
                        return False

        # Cross-fryer target conflict
        if self.basket_index in {1, 3}:  # fryer1 -> fryer2
            for idx in [1, 3]:
                if bb.get(f"recipe/fryer2/basket{idx}/active") == True:
                    return False
        elif self.basket_index in {5, 7}:  # fryer4 -> fryer3
            for idx in [5, 7]:
                if bb.get(f"recipe/fryer3/basket{idx}/active") == True:
                    return False

        return True

    def update_cooking_done_count(self):
        count = bb.get("recipe/finish_number") + 1
        bb.set("recipe/finish_number", count)
        bb.set("ui/state/finish_number", count)

    def release_finish(self):
        return WetRecipeFsmEvent.DONE

    def check_shake_timer(self):
        """
        SHAKE 중  타이머 업데이트:
        - Fry time 15초 남으면 SKIP
        - SHAKE 지난 시간 계산 (우선순위)
        """

        if self.elapsed_time >= self.fry_time - 15:
            return WetRecipeFsmEvent.DONE
        else:
            return WetRecipeFsmEvent.NONE
        
    def transition_to_pre_fry(self):
        """
        PRE_FRY 상태로 전이될 때 fryer_index를 할당한다.
        초기에는 미할당(0) 상태이며, 바스켓 인덱스에 따라 2 또는 3으로 설정한다.
        """
        if self.fryer_index == 0:
            if self.basket_index in {1, 3}:
                self.fryer_index = 2
            elif self.basket_index in {5, 7}:
                self.fryer_index = 3
            else:
                raise ValueError(f"Invalid basket_index for fryer assignment: {self.basket_index}")

