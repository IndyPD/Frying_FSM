from pkg.utils.blackboard import GlobalBlackboard
from pkg.utils.process_control import Flagger, reraise
from pkg.utils.file_io import load_json, save_json
from ..constants import *
from configs.global_config import GlobalConfig

import bisect

bb = GlobalBlackboard()
global_config = GlobalConfig()


class RecipeContext(ContextBase):
    violation_code: ViolationType

    def __init__(self, basket_idx):
        ContextBase.__init__(self)

        ''' Recipe config file '''
        self.config_file = CONFIG_FILE

        ''' Basket and fryer index '''
        self.basket_index = basket_idx
        if self.basket_index in {1, 3}:   # {BASKET1, BASKET3} in FRYER1
            self.fryer_index = 1
        elif self.basket_index in {2, 4}: # {BASKET2, BASKET4} in FRYER2
            self.fryer_index = 2
        elif self.basket_index in {5, 7}: # {BASKET5, BASKET7} in FRYER3
            self.fryer_index = 3
        elif self.basket_index in {6, 8}: # {BASKET6, BASKET8} in FRYER4
            self.fryer_index = 4

        ''' B Type '''
        self.is_assign_ready = False
        self.slot_index = 0

        self.sensor_missing_start = None


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
        self.prev_elapsed_time = 0
        self.overcooking_time = 0

        ''' Shake related '''
        self.shake_time = []
        self.shake_stage = 0
        self.shake_done_num = 0

        self.shake_option = 0
        self.shake_type = "auto"
        self.drain_num = 0

        self.next_state = RecipeFsmState.NO_MENU

        self.sensor_missing_time = 0
        self.finish_remaining_time = 1000

    def assign_recipe(self, recipe_idx, slot_idx):
        """
        지정된 recipe_idx에 해당하는 레시피 설정 로드
        - recipe_idx: 0~10, 0은 초기화
        - 작업 단계 리스트 초기화
        - recipe_idx: 레시피 인덱스, 저장된 10개 중 불러오기
        """

        ''' Assign slot '''
        self.slot_index = slot_idx

        ''' Assign menu '''
        self.config = load_json(CONFIG_FILE)
        self.recipe = self.config[f"recipe{recipe_idx}"]
        self.recipe_index = recipe_idx

        ''' Initialize menu '''
        self.cooking_start_time = time.time()
        self.fry_time = int(self.recipe["time_min"]) * 60 + int(self.recipe["time_sec"])
        self.cooking_min = 0
        self.cooking_sec = 0
        self.elapsed_time = 0
        self.prev_elapsed_time = 0
        self.overcooking_time = 0

        ''' Init motion '''
        if int(bb.get("recipe/command/move_to_fryer_done")) == self.basket_index:
            bb.set("recipe/command/move_to_fryer_done", 0)

        if int(bb.get("recipe/command/move_from_fryer_done")) == self.basket_index:
            bb.set("recipe/command/move_from_fryer_done", 0)

        if int(bb.get("recipe/command/shake_done")) == self.basket_index:
            bb.set("recipe/command/shake_done", 0)


        """
        if pos < len(self.shake_times): shake
        shake_times
        - 0개:       []              100
          * stage  0   
        - 1개:       [5]             100
          * stage  0   1 
        - 2개:       [5, 10]         100    
          * stage  0   1   2
        - 3개:       [5, 10, 15]     100
          * stage  0   1   2   3
        shake_stage: 다음 단계 shake{n}
        """
        self.shake_times = [int(self.recipe[f"shake{i}_min"]) * 60 + int(self.recipe[f"shake{i}_sec"])
                            for i in range(1, 4) if self.recipe.get(f"shake{i}", False)]

        self.shake_stage = 0
        self.shake_done_num = 0

        self.sensor_missing_start = None

        Logger.info(self.recipe)


    def cancel_basket(self):
        '''
        바스켓 매뉴 취소: COOKING_READY, MOVE_TO_FRY 상태에서만 동작
            1. 투입 모션 중에는 동작 안함
            2. 바스켓이 사라짐 (3초 간 센서 없어짐)
            3. App에서 바스켓 취소
            4. B 타입: fryer 할당 취소
        '''

        ''' 1. 투입 모션 중에는 동작 안함 '''
        if global_config.get("frying_coco_version") == "AType":
            condition = bb.get("int_var/cmd/val") == int(ContyCommand.MOVE_BASKET_TO_FRYER_A + self.basket_index)
        else:
            condition = int(ContyCommand.MOVE_BASKET_TO_FRYER_B + 10*self.slot_index + self.fryer_index)
        if condition:
            self.sensor_missing_start = None  # 리셋
            return False

        ''' 2. 바스켓 사라짐 (3초간 센서 Off) '''
        if bb.get(f"indy_state/basket{self.slot_index}") == 1:
            # 센서 ON
            self.sensor_missing_start = None
        else:
            # 센서 OFF 상태 지속 중
            if self.sensor_missing_start is None:
                self.sensor_missing_start = time.time()
            else:
                elapsed = time.time() - self.sensor_missing_start
                if elapsed > 3.0:
                    bb.set(f"ui/reset/basket{self.slot_index}/state", True)
                    Logger.info(
                        f"{get_time()}: [Basket {self.basket_index} FSM] Cancel basket by sensor missing (elapsed={elapsed:.2f}s)")
                    return True

        ''' 3. App을 통해 바스켓 취소 '''
        basket_cancel = int(bb.get("ui/command/cancel_recipe"))
        if self.slot_index == basket_cancel:
            bb.set("ui/reset/cancel_recipe", True)
            bb.set(f"ui/reset/basket{self.slot_index}/state", True)
            if self.recipe_index != 0:
                Logger.info(f"{get_time()}: [Basket {self.basket_index} FSM] Cancel basket by App.")
                return True
            else:
                return False
        else:
            return False


    def cancel_fryer(self):
        bb.set(f"ui/reset/fryer{self.fryer_index}/cancel", True)
        Logger.info(f"{get_time()}: [Basket {self.basket_index} FSM] "
                    f"Cancel fryer {self.fryer_index}.")
        return RecipeFsmEvent.CANCEL_MENU


    def update_fryer_state(self):
        ''' UI Fryer state '''
        bb.set(f"ui/state/fryer{self.fryer_index}/recipe", self.recipe_index)
        bb.set(f"ui/state/fryer{self.fryer_index}/min", self.cooking_min)
        bb.set(f"ui/state/fryer{self.fryer_index}/sec", self.cooking_sec)


    def peek_next_state(self):
        return self.next_state

    def get_shake_time(self):
        key_min = f"shake{self.shake_stage}_min"
        key_sec = f"shake{self.shake_stage}_sec"
        return self.cooking_start_time + int(self.recipe[key_min]) * 60 + int(self.recipe[key_sec])

    def update_timer(self):
        """ update timer
        - cooking elapsed time 계산
        - prev_elapsed time 계산
        - shake_pos -> shake_stage 계산
        - next_state 계산
        """

        ''' 기본 타이머 계산: elapsed time, cooking time, remaining time '''
        self.elapsed_time = time.time() - self.cooking_start_time
        self.cooking_min = int((self.elapsed_time % 3600) // 60)
        self.cooking_sec = int(self.elapsed_time % 60)
        self.finish_remaining_time = self.fry_time - self.elapsed_time
        # fry_time -now + start_time

        ''' shake stage 계산, next recipe state 계산 '''
        if not self.shake_times:
            self.shake_stage = 0
            self.next_state = RecipeFsmState.MOVE_FROM_FRYER
        else:
            self.shake_stage = bisect.bisect_left(self.shake_times, self.prev_elapsed_time)

            if self.shake_stage < len(self.shake_times):
                self.next_state = RecipeFsmState.SHAKE
            else:
                self.next_state = RecipeFsmState.MOVE_FROM_FRYER

        self.prev_elapsed_time = self.elapsed_time

    def check_timer(self):
        """
        FRY 일 때 타이머 업데이트, 조리 완료 시 다음단계 상태 전이
        1) 다음 상태가 SHAKE: Shake time 기반
            - shake_stage: 1, 2, 3 (shake1, shake2, shake3)
        2) 다음 상태가 MOVE_FROM_FRYER: 전체 Fry time 기반
        """

        if self.next_state == RecipeFsmState.SHAKE:
            if self.shake_done_num >= len(self.shake_times):
                return RecipeFsmEvent.NONE  # 아무 것도 할 shake 없음
            elif self.elapsed_time >= self.shake_times[self.shake_done_num]:
                self.shake_done_num += 1
                return RecipeFsmEvent.SHAKE_TIME_DONE
            else:
                return RecipeFsmEvent.NONE

        elif self.next_state == RecipeFsmState.MOVE_FROM_FRYER:
            if self.elapsed_time >= self.fry_time:
                return RecipeFsmEvent.COOKING_TIME_DONE
            else:
                return RecipeFsmEvent.NONE
        else:
            return RecipeFsmEvent.NONE


    def check_shake_timer(self):
        """
        SHAKE 중  타이머 업데이트:
        - Fry time 15초 남으면 SKIP
        - SHAKE 지난 시간 계산 (우선순위)
        """

        if self.elapsed_time >= self.fry_time - 15:
            return RecipeFsmEvent.DONE
        else:
            return RecipeFsmEvent.NONE


    def update_overcooking_timer(self):
        ''' Update until Pick-up motion done '''
        val = int(bb.get(f"int_var/pickup_done/fryer{self.fryer_index}/val"))

        if val > 0:
            return RecipeFsmEvent.NONE
        else:
            self.elapsed_time = time.time() - self.cooking_start_time
            self.cooking_min = int((self.elapsed_time % 3600) // 60)
            self.cooking_sec = int(self.elapsed_time % 60)
            self.overcooking_time = self.elapsed_time - self.fry_time

    def check_no_conflict(self):
        """
        To prevent two baskets in one fryer
        - target_index: 겹치는 바스켓 인덱스 (1-3, 2-4, 5-7, 6-8)
        - return True: target이 NO_MENU, COOKING_READY, FINISH 일 때 할당 가능
        - return False: 나머지 상태, my_index 잘못된 값
        * 일괄 매뉴 선택 시 Recipe FSM 동시 진입으로 conflict 발생 가능: MoveToFry strategy에서 이중 체크
        """
        target_idx = OPPOSITE_BASKET_MAP.get(self.basket_index)

        if target_idx is not None:
            target_state = bb.get(f"recipe/basket{target_idx}/state")
            if target_state in {RecipeFsmState.NO_MENU, RecipeFsmState.COOKING_READY, RecipeFsmState.FINISH}:
                return True
            else:
                return False
        else:
            return False

    def assign_empty_fryer(self) -> Optional[int]:
        """
        현재 slot_index에 따라 지정된 fryer 범위 내에서,
        가장 높은 번호의 빈 fryer를 반환 (내림차순)
        """
        # 슬롯 그룹에 따른 프라이어 후보군 정의
        if self.slot_index in (1, 2):
            fryer_candidates = [2, 1]
        elif self.slot_index in (3, 4):
            fryer_candidates = [4, 3]
        else:
            Logger.warn(f"[Basket {self.basket_index} FSM] Invalid slot_index: {self.slot_index}")
            return RecipeFsmEvent.NONE

        for fryer_id in fryer_candidates:
            fryer_in_use = False
            for b_idx in range(1, 9):
                if b_idx == self.basket_index:
                    continue
                other_fryer = int(bb.get(f"recipe/basket{b_idx}/fryer"))
                if other_fryer == fryer_id:
                    fryer_in_use = True
                    break

            if not fryer_in_use:
                self.fryer_index = fryer_id
                bb.set(f"recipe/basket{self.basket_index}/fryer", fryer_id)
                Logger.info(f"[Basket {self.basket_index} FSM] Assigned fryer {fryer_id}")
                Logger.info(f"{get_time()}: [Basket {self.basket_index} FSM] Start cooking to fryer {fryer_id}.")
                return RecipeFsmEvent.START_MENU

        Logger.warn(f"[Basket {self.basket_index} FSM] No fryer available for slot {self.slot_index}")
        return RecipeFsmEvent.NONE

    def find_empty_fryer(self) -> Optional[int]:
        """
        현재 비어 있는 fryer 중 가장 높은 번호의 fryer를 반환 (내림차순: 4 → 3 → 2 → 1)
        """

        for fryer_id in sorted(range(1, 5), reverse=True):
            fryer_in_use = False
            for b_idx in range(1, 9):
                if b_idx == self.basket_index:
                    continue
                other_fryer = int(bb.get(f"recipe/basket{b_idx}/fryer"))
                if other_fryer == fryer_id:
                    fryer_in_use = True
                    break
            if not fryer_in_use:
                self.fryer_index = fryer_id
                bb.set(f"recipe/basket{self.basket_index}/fryer", fryer_id)
                Logger.info(f"[Basket {self.basket_index} FSM] Assigned fryer {fryer_id}")
                break

        else:
            ''' 할당 실패 시 대기 '''
            print(f"[Basket {self.basket_index} FSM] No fryer available!")
            return RecipeFsmEvent.NONE

        Logger.info(f"{get_time()}: [Basket {self.basket_index} FSM] Start cooking to fryer {fryer_id}.")
        return RecipeFsmEvent.START_MENU


    def update_cooking_done_count(self):
        count = bb.get("recipe/finish_number") + 1
        bb.set("recipe/finish_number", count)
        bb.set("ui/state/finish_number", count)

    def release_finish(self):
        """
        RecipeState FINISH 상태에서 실행
            - 바스켓 거치대 센서 값 3초 이상 없으면 릴리즈 (0.5초 x 6time = 3초)
        """
        if bb.get(f"indy_state/basket{self.basket_index}") == 1:
            self.sensor_missing_start = None  # 센서 ON이면 타이머 리셋
        else:
            if self.sensor_missing_start is None:
                self.sensor_missing_start = time.time()
            else:
                elapsed = time.time() - self.sensor_missing_start
                if elapsed > 3.0:
                    Logger.info(
                        f"{get_time()}: [Basket {self.basket_index} FSM] Retrieve basket (elapsed={elapsed:.2f}s).")
                    bb.set(f"ui/reset/basket{self.basket_index}/state", True)

                    self.update_cooking_done_count()
                    return RecipeFsmEvent.DONE

        return RecipeFsmEvent.NONE

