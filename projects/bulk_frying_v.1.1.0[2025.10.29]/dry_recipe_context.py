from pkg.utils.blackboard import GlobalBlackboard
from pkg.utils.process_control import Flagger, reraise
from pkg.utils.file_io import load_json, save_json
from pkg.configs.global_config import GlobalConfig
from .constants import *
import threading


import bisect

file_access_lock = threading.Lock()
bb = GlobalBlackboard()
global_config = GlobalConfig()


class DryRecipeContext(ContextBase):
    violation_code: ViolationType

    def __init__(self, basket_idx):
        ContextBase.__init__(self)

        ''' Recipe config file '''
        self.config_file = CONFIG_FILE

        ''' Basket and fryer index '''
        Logger.info(f"dryfsm {basket_idx}")
        self.basket_index = basket_idx
        self.fsm_index = basket_idx
        if self.basket_index in {1, 3}:   # {BASKET1, BASKET3} in FRYER1
            self.fryer_index = 1
        elif self.basket_index in {2, 4}: # {BASKET2, BASKET4} in FRYER2
            self.fryer_index = 2
        elif self.basket_index in {5, 7}: # {BASKET5, BASKET7} in FRYER3
            self.fryer_index = 3
        elif self.basket_index in {6, 8}: # {BASKET6, BASKET8} in FRYER4
            self.fryer_index = 4

        ''' Load default recipe (recipe0) '''
        self.config = load_json(self.config_file)
        self.recipe = self.config["recipe0"]
        self.recipe_index = 0

        # 우선 실행 방지 변수 ex) 1번 3번 동시 등록 시 3번 먼저 실행 방지
        
        if self.basket_index in {3,4,7,8} :
            self.defer_execution = True
        else :
            self.defer_execution = False


        ''' Cooking time related '''
        self.cooking_state = CookingState.NONE
        self.cooking_start_time = 0
        self.cooking_min = 0
        self.cooking_sec = 0
        self.elapsed_time = 0
        self.elapsed_shake_done_time = 0
        self.fry_time = 0
        self.overcooking_time = 0
        self.total_elapsed_at_pickup = 0

        ''' Shake related '''
        self.putin_shake = False
        self.shake_num = 0
        self.last_shake_done_time = time.time()
        self.shake_break = False

        self.fry_type = "dry"

        self.shake_type = "auto"

        self.next_state = DryRecipeFsmState.NO_MENU

        self.finish_remaining_time = 1000
        self.cancellation_in_progress = False

    def assign_recipe(self, recipe_idx):
        """
        지정된 recipe_idx에 해당하는 레시피 설정 로드
        - recipe_idx: 0~10, 0은 초기화
        - 작업 단계 리스트 초기화
        - recipe_idx: 레시피 인덱스, 저장된 10개 중 불러오기
        """
        Logger.info(f"[Basket {self.basket_index}] Waiting for recipe assignment lock.")
        with file_access_lock:
            Logger.info(f"[Basket {self.basket_index}] Acquired recipe assignment lock.")
            ''' Assign menu '''
            self.config = load_json(CONFIG_FILE)
            self.recipe = self.config[f"recipe{recipe_idx}"]
            self.recipe_index = recipe_idx
            # Logger.info(f'recipe : {self.recipe}')

            ''' Initialize menu '''
            # self.cooking_start_time = time.time()
            self.cooking_start_time = 0
            bb.set(f"ui/reset/fryer{self.fryer_index}/cancel",True)
            
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
            try :
                self.putin_shake = bool(self.recipe["putin_shake"])
            except :
                self.putin_shake = bool(self.recipe["input_shake"])

            # 흔들기 모션 값 bb추가
            bb.set("int_var/putin_shake/val",self.putin_shake)

            # Logger.info(f"add recipe {self.frying_type} {self.pre_fry_time} {self.fry_time} {self.putin_shake}")

            self.cooking_min = 0
            self.cooking_sec = 0
            self.elapsed_time = 0
            self.overcooking_time = 0
            # self.finish_remaining_time = self.fry_time

            if self.frying_type == 1:

                ''' Init motion '''
                if int(bb.get("recipe/command/move_to_fryer_done")) == self.basket_index:
                    bb.set("recipe/command/move_to_fryer_done", 0)

                if int(bb.get("recipe/command/move_from_fryer_done")) == self.basket_index:
                    bb.set("recipe/command/move_from_fryer_done", 0)

                if int(bb.get("recipe/command/shake_done")) == self.basket_index:
                    bb.set("recipe/command/shake_done", 0)
                
                Logger.info(f"[Basket {self.basket_index}] Releasing recipe assignment lock.")
                return True
            
            else :
                Logger.info(f"[Basket {self.basket_index}] Releasing recipe assignment lock (recipe type not dry)." )
                return False


        # Logger.info("assign recipe : ",self.recipe)


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
        bb.set(f"ui/state/fryer{self.fryer_index}/elapsed_time", 0)
        self.cancellation_in_progress = True
        bb.set(f"ui/reset/fryer{self.fryer_index}/cancel", True)
        Logger.info(f"{get_time()}: [Basket {self.basket_index} FSM] "
                    f"Cancel fryer {self.fryer_index}.")
        return DryRecipeFsmEvent.CANCEL_MENU


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
        # Logger.info(f"{self.cooking_start_time} {time.time()}")
        self.elapsed_time = time.time() - self.cooking_start_time

        self.elapsed_shake_done_time = time.time() - self.last_shake_done_time
        self.cooking_min = int((self.elapsed_time % 3600) // 60)
        self.cooking_sec = int(self.elapsed_time % 60)
        self.finish_remaining_time = self.fry_time - self.elapsed_time
        bb.set(f"ui/state/fryer{self.fryer_index}/elapsed_time",self.elapsed_time)
        bb.set(f"ui/state/basket{self.basket_index}/fry_time",self.elapsed_time)
        bb.set(f"ui/state/basket{self.basket_index}/fry_remain_time",self.finish_remaining_time)
        bb.set(f"ui/state/fryer{self.fryer_index}/remain_time",self.finish_remaining_time)
        # Logger.info(f"{self.cooking_start_time}, {self.elapsed_time}, {self.cooking_min}, {self.cooking_sec}, {self.finish_remaining_time}")

        # self.last_shake_done_time

        if 70< self.finish_remaining_time < self.fry_time:
            self.next_state = DryRecipeFsmState.SHAKE

        elif self.finish_remaining_time <= 70 :
            self.next_state = DryRecipeFsmState.MOVE_FROM_FRYER
        
    def update_overcooking_timer(self):
        ''' Update until Pick-up motion done '''
        val = int(bb.get(f"int_var/pickup_done/fryer{self.fryer_index}/val"))

        if val > 0:
            return DryRecipeFsmEvent.NONE
        else:
            self.elapsed_time = time.time() - self.cooking_start_time
            self.cooking_min = int((self.elapsed_time % 3600) // 60)
            self.cooking_sec = int(self.elapsed_time % 60)
            self.overcooking_time = self.elapsed_time - self.fry_time

    def update_cooking_done_count(self):
        count = bb.get("recipe/finish_number") + 1
        bb.set("recipe/finish_number", count)
        bb.set("ui/state/finish_number", count)

    def release_finish(self):
        self.shake_num = 0
        if self.basket_index in {3,4,7,8} :
            self.defer_execution = True
        self.next_state = DryRecipeFsmState.NO_MENU
        return DryRecipeFsmEvent.DONE
    # 같은 튀김기에 두 개의 메뉴가 동시에 등록되었을 때, 두 번째 바스켓(3,4,7,8)이 먼저 튀김기에 들어가는 동작을 막기 위한 것. 
    # 즉 로봇의 동선이 꼬이거나 충돌하는 것을 방지하기 위한 안전장치 

    def check_shake_timer(self):
        """
        SHAKE 중  타이머 업데이트:
        - Fry time 15초 남으면 SKIP
        - SHAKE 지난 시간 계산 (우선순위)
        """

        if self.elapsed_time >= self.fry_time - 15:
            return DryRecipeFsmEvent.DONE
        else:
            return DryRecipeFsmEvent.NONE

