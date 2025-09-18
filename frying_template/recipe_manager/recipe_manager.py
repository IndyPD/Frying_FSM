# recipe_manager.py
import threading
import time
from ..constants import *
from ..fsm import FsmSequence
from .recipe_fsm import RecipeFsmSequence
from .recipe_context import RecipeContext
from pkg.utils.file_io import load_json, save_json
from pkg.utils.blackboard import GlobalBlackboard
from configs.global_config import GlobalConfig

from ..fsm_logger import FSMCSVLogger


bb = GlobalBlackboard()
global_config = GlobalConfig()


class RecipeManager:
    def __init__(self, robot_fsm: FsmSequence):
        self.running = False
        self.thread = None

        self.config_file = CONFIG_FILE
        self.config = load_json(self.config_file)

        ''' Robot FSM '''
        self.robot_fsm = robot_fsm

        if bool(global_config.get("maximum_shake")):
            bb.set("ui/state/priority/max_shake", 1)
        else:
            bb.set("ui/state/priority/max_shake", 2)

        self.robot_error = None
        self.prog_stopped = None


        ''' Priority '''
        self.prev_program_state = ProgramState.PROG_IDLE
        self.priority_recipe = None
        self.working_recipe_index = None

        ''' Shake command buffer '''
        self.shake_buffer = [[], [], [], []]

        ''' Initialize Recipe FSMs '''
        self.recipe_fsm = [
            RecipeFsmSequence(RecipeContext(i)) for i in range(1, 9)
        ]
        for fsm in self.recipe_fsm:
            fsm.start_service_background()

        ''' For FSM logging '''
        self.fsm_logger = FSMCSVLogger(self.recipe_fsm, self.robot_fsm)


    def reset_app(self):
        """
            1. 최초 실행 시,
            2. 로봇 상태 초기화 버튼 입력 시
        """
        bb.set("recipe/finish_number", 0)
        bb.set("ui/state/finish_number", 0)

        for fryer_idx in range(1, 5):
            bb.set(f"ui/state/fryer{fryer_idx}/recipe", 0)
            bb.set(f"ui/state/fryer{fryer_idx}/min", 0)
            bb.set(f"ui/state/fryer{fryer_idx}/sec", 0)
        
        for basket_idx in range(1, 9):
            bb.set(f"ui/reset/basket{basket_idx}/state", True)


    def reset_motion(self):
        self.robot_fsm.context.trigger_move_from_fryer = False
        self.robot_fsm.context.trigger_move_to_fryer = False
        self.robot_fsm.context.trigger_shake = False

        bb.set("recipe/command/move_to_fryer_done", 0)
        bb.set("recipe/command/move_from_fryer_done", 0)
        bb.set("recipe/command/shake_done", 0)

        # TODO: 추가, 검증 필요
        self.robot_fsm.context.basket_index = 0
        self.robot_fsm.context.slot_index = 0
        self.robot_fsm.context.fryer_index = 0
        self.robot_fsm.context.drain_num = 0
        self.robot_fsm.context.shake_num = 0
        self.robot_fsm.context.shake_option = 0

    def trigger_to_fryer_motion(self, context):
        '''
        Move to fryer motion command
        A타입: Recipe FSM (basket) 인덱스
        B타입: Slot 인덱스
        '''

        self.robot_fsm.context.basket_index = context.basket_index
        self.robot_fsm.context.slot_index = context.slot_index
        self.robot_fsm.context.fryer_index = context.fryer_index
        self.robot_fsm.context.trigger_move_to_fryer = True

        Logger.info(f"{get_time()}: [RecipeManager] Trigger move_to_fryer motion "
                    f"[basket {context.basket_index}, slot {context.slot_index}, fryer {context.fryer_index}]")

    def trigger_from_fryer_motion(self, context):
        '''
        Move from fryer motion command
        A타입: Slot 인덱스 = Recipe FSM의 인덱스
        B타입: Recipe FSM 인덱스
        '''
        self.robot_fsm.context.drain_num = int(context.recipe.get("drain_num", 0))
        self.robot_fsm.context.basket_index = context.basket_index
        self.robot_fsm.context.fryer_index = context.fryer_index
        self.robot_fsm.context.trigger_move_from_fryer = True

        Logger.info(f"{get_time()}: [RecipeManager] Trigger move_from_fryer motion "
         f"[basket {context.basket_index}, slot {context.slot_index}, fryer {context.fryer_index}], "
                    f"drain num {self.robot_fsm.context.drain_num}.")

    def trigger_shake_motion(self, context):
        '''
        Recipe FSM -> Robot FSM command
        Shake motion command
        A타입: Recipe FSM (Basket) 인덱스
        B타입: Fryer index
        '''
        if context.shake_type == "auto":
            self.robot_fsm.context.shake_num = int(context.recipe.get(f"shake{context.shake_stage}_num", 1))
        elif context.shake_type == "manual":
            self.robot_fsm.context.shake_num = 4

        self.robot_fsm.context.shake_option = context.shake_option
        self.robot_fsm.context.basket_index = context.basket_index
        self.robot_fsm.context.fryer_index = context.fryer_index
        self.robot_fsm.context.trigger_shake = True

        Logger.info(
            f"{get_time()}: [RecipeManager] Trigger shake motion "
            f"[basket {context.basket_index}, fryer {context.fryer_index}], shake num {self.robot_fsm.context.shake_num}")

    def add_new_recipe(self):
        is_save_event = False
        keys = ["time_min", "time_sec", "shake1", "shake1_num", "shake1_min", "shake1_sec",
                "shake2", "shake2_num", "shake2_min", "shake2_sec", "shake3", "shake3_num",
                "shake3_min", "shake3_sec", "drain_num"]

        for recipe_idx in range(1, 11):
            new_recipe = [int(bb.get(f"ui/recipe{recipe_idx}/{key}")) for key in keys]

            if any(new_recipe):
                is_save_event = True
                self.config[f"recipe{recipe_idx}"] = {"recipe_index": recipe_idx, **dict(zip(keys, new_recipe))}

                for key in keys:
                    bb.set(f"ui/recipe{recipe_idx}/reset/{key}", True)

        if is_save_event:
            save_json(self.config_file, self.config)

    def priority_schedule(self):

        if (int(bb.get("int_var/cmd/val")) != 0 or
            self.robot_fsm.context.trigger_move_to_fryer or
            self.robot_fsm.context.trigger_move_from_fryer or
            self.robot_fsm.context.trigger_shake):
            return

        if self.robot_error or self.prog_stopped:
            return

        now = time.time()
        fryer_finish_time = {i: 0 for i in range(1, 5)}  # fryer1~4
        priority_list = []

        ''' STEP 1: 조리 종료 예정 시간 기록 '''
        for fsm in self.recipe_fsm:
            context = fsm.context
            state = fsm.get_state()

            if state in {RecipeFsmState.FRY, RecipeFsmState.SHAKE, RecipeFsmState.MOVE_FROM_FRYER}:
                # 아직 조리 중 → 종료 예정 시간 계산
                finish_time = (context.cooking_start_time + context.fry_time)
                fryer_finish_time[context.fryer_index] = max(fryer_finish_time[context.fryer_index], finish_time)


        ''' STEP 2: 우선순위 작업 수집 '''
        for fsm in self.recipe_fsm:
            context = fsm.context
            state = fsm.get_state()

            if state == RecipeFsmState.MOVE_FROM_FRYER:
                ''' Priority 1: 배출 (오버쿠킹 방지 절대 조건) '''
                priority_list.append((1, context))

            elif state == RecipeFsmState.FRY:
                ''' Priority 2: FRY → 배출까지 5초 남으면 다른 작업 미할당 '''
                if (context.peek_next_state() == RecipeFsmState.MOVE_FROM_FRYER
                        and context.finish_remaining_time < 5):
                    priority_list.append((2, context))

                ''' Priority 5: 모션 없을 때 SHAKE 앞당기기 '''
                if global_config.get("maximum_shake"):
                    if context.peek_next_state() == RecipeFsmState.SHAKE:
                        context.shake_done_num += 1
                        context.shake_option = 0
                        fsm.trigger(RecipeFsmEvent.SHAKE_TIME_DONE)
                        priority_list.append((5, context))
                        context.shake_type = "auto"

                ''' Priority 6: App 수동 쉐이크 버튼 '''
                if self.shake_buffer[context.fryer_index - 1]:
                    context.shake_option = self.shake_buffer[context.fryer_index - 1][0]
                    self.shake_buffer[context.fryer_index - 1].pop(0)
                    fsm.trigger(RecipeFsmEvent.SHAKE_TIME_DONE)
                    priority_list.append((6, context))
                    context.shake_type = "manual"

            elif state == RecipeFsmState.MOVE_TO_FRYER:
                ''' Priority 3: 투입, 추후 배출 시 오버쿠킹 안되도록 이 레시피 종료와 다른 레시피 종료 10초 차이 유지 '''
                # 예상 종료 시간 + 투입 모션 시간: 실제 시작
                estimated_end_time = now + context.fry_time + MOVE_TO_FRY_MOTION_TIME

                # 배출 모션 시간 - 오버쿠킹 허용 시간
                buffer = MOVE_FROM_FRY_MOTION_TIME  - 1
                is_conflict = False

                for fryer_idx, scheduled_finish in fryer_finish_time.items():
                    if scheduled_finish == 0:
                        continue  # 조리 중인 바스켓 없음 → 비교 안 함

                    time_diff = abs(estimated_end_time - scheduled_finish)
                    if time_diff < buffer:
                        is_conflict = True
                        Logger.info(
                            f"[RecipeManager] MOVE_TO_FRYER delayed for Basket {context.basket_index} | "
                            f"Conflict with fryer{fryer_idx} | Δt={time_diff:.1f}s")
                        break
                if not is_conflict:
                    priority_list.append((3, context))

            elif state == RecipeFsmState.SHAKE:
                ''' Priority 4: SHAKE '''
                priority_list.append((4, context))


        """ Trigger priority motion """
        if not priority_list:
            self.working_recipe_index = None
            return

        '''  
        - 우선순위 오름차순, 오버쿠킹 시간 내림차순, 쉐이크 횟수 오름차순
        - (B타입) Fryer 번호 높은 순  
        '''
        if global_config.get("frying_coco_version") == "BType":
            if global_config.get("maximum_shake"):
                priority_list.sort(key=lambda x: (
                    x[0],                    # priority
                    -x[1].overcooking_time,  # overcooking_time desc
                    x[1].shake_done_num,     # shake_done_num asc
                    -x[1].fryer_index        # fryer_index desc
                ))
            else:
                priority_list.sort(key=lambda x: (
                    x[0],
                    -x[1].overcooking_time,
                    -x[1].fryer_index
                ))
        else:
            if global_config.get("maximum_shake"):
                priority_list.sort(key=lambda x: (
                    x[0],  -x[1].overcooking_time, x[1].shake_done_num))
            else:
                priority_list.sort(key=lambda x: (x[0], -x[1].overcooking_time))


        Logger.info("[PriorityScheduler] Current priority list:")
        for priority, context in priority_list:
            Logger.info(
                f"  - Basket {context.basket_index} | "
                f"Slot: {context.slot_index} | "
                f"Fryer: {context.fryer_index} | "
                f"State: {context.state.name} | "
                f"Elapsed: {context.elapsed_time:.1f}s | "
                f"FinishRemain: {context.finish_remaining_time:.1f}s | "
                f"ShakeStage: {context.shake_stage} | "
                f"Priority: {priority}"
            )

        _, context = priority_list[0]
        self.priority_recipe = context
        self.working_recipe_index = context.basket_index - 1

        state = context.state

        if state == RecipeFsmState.MOVE_FROM_FRYER:
            self.trigger_from_fryer_motion(context)

        elif state == RecipeFsmState.SHAKE:
            self.trigger_shake_motion(context)

        elif state == RecipeFsmState.MOVE_TO_FRYER:
            self.trigger_to_fryer_motion(context)

    def update_cooking_state(self):
        ''' Update all baskets (FSMs) cooking state, and send it to app
        A Type:
            - 바스켓 없음, 조리 준비: NO_MENU, COOKING_READY
            - 조리 중: MOVE_TO_FRY, SHAKE, MOVE_FROM_FRY
            - 조리 완료: FINISH
        B Type:
            - 바스켓 없음, 조리 준비: NO_MENU, COOKING_READY
            - 조리 중: MOVE_TO_FRY, SHAKE, MOVE_FROM_FRY
            - 조리 완료: FINISH
        '''

        ''' Basket UI LED '''
        for idx in range(1, 9):
            bb.set(f"ui/state/basket/sensor{idx}", int(bb.get(f"indy_state/basket{idx}")))

        ''' Basket state '''
        if global_config.get("frying_coco_version") == "AType":
            for fsm in self.recipe_fsm:
                context = fsm.context
                state = fsm.get_state()

                cooking_state = 0

                if state == RecipeFsmState.NO_MENU:
                    if int(bb.get(f"indy_state/basket{context.basket_index}")) == 1:
                        cooking_state = CookingState.BEFORE_COOKING
                    else:
                        cooking_state = CookingState.NONE
                elif state == RecipeFsmState.COOKING_READY:
                    cooking_state = CookingState.BEFORE_COOKING
                elif state in {RecipeFsmState.MOVE_TO_FRYER, RecipeFsmState.FRY,
                             RecipeFsmState.SHAKE, RecipeFsmState.MOVE_FROM_FRYER}:
                    cooking_state = CookingState.COOKING
                elif state == RecipeFsmState.FINISH:
                    cooking_state = CookingState.DONE_COOKING

                bb.set(f"ui/state/basket{context.basket_index}/state", int(cooking_state))
        else:
            ui_slots = [False, False, False, False]

            for fsm in self.recipe_fsm:
                context = fsm.context
                state = fsm.get_state()

                if state == RecipeFsmState.COOKING_READY:
                    ui_slots[context.slot_index - 1] = True
                    cooking_state = CookingState.BEFORE_COOKING
                elif state == RecipeFsmState.MOVE_TO_FRYER:
                    ui_slots[context.slot_index - 1] = True
                    cooking_state = CookingState.COOKING
                else:
                    continue

                bb.set(f"ui/state/basket{context.slot_index}/state", int(cooking_state))

            for slot_idx in range(4):
                if not ui_slots[slot_idx]:
                    if int(bb.get(f"indy_state/basket{slot_idx + 1}")) == 1:
                        cooking_state = CookingState.BEFORE_COOKING
                    else:
                        cooking_state = CookingState.NONE

                    bb.set(f"ui/state/basket{slot_idx + 1}/state", int(cooking_state))


    def handle_app_command(self):
        ''' App 입력 대응 '''

        ''' 수동 흔들기 버튼: 버튼 stacking 해놓았다가 소진 '''
        for idx in range(1, 5):
            for shake_type, cmd_key in [(0, "shake_h"), (1, "shake_v")]:
                if int(bb.get(f"ui/command/{cmd_key}/fryer{idx}")) > 0:
                    for fsm in self.recipe_fsm:
                        ctx = fsm.context
                        if ctx.fryer_index == idx and ctx.state in {RecipeFsmState.FRY, RecipeFsmState.SHAKE}:
                            if len(self.shake_buffer[idx - 1]) < 10:
                                self.shake_buffer[idx - 1].append(shake_type)
                                Logger.info(f"{get_time()}: [RecipeManager] Manual shake fryer {idx}, {cmd_key}")
                            break
                    bb.set(f"ui/reset/{cmd_key}/fryer{idx}", True)


        ''' 바스켓 흔들기 옵션 버튼 '''
        max_shake = int(bb.get("ui/command/priority/max_shake"))
        if max_shake > 0:
            bb.set("ui/reset/priority/max_shake", True)
            if max_shake == 1:
                global_config.set("maximum_shake", True)
                global_config.save()
                Logger.info(f"{get_time()}: [RecipeManager] Maximum shake mode ON")
            elif max_shake == 2:
                global_config.set("maximum_shake", False)
                global_config.save()
                Logger.info(f"{get_time()}: [RecipeManager] Maximum shake mode OFF")

            bb.set("ui/state/priority/max_shake", max_shake)

        
        ''' "조리 상태 초기화" 버튼 '''
        if bb.get("ui/command/reset_logic"):
            bb.set("ui/command/reset_logic", False)
            bb.set("ui/reset/reset_logic", True)
            Logger.info(f"{get_time()}: [RecipeManager] Reset all recipes!")

            self.reset_all_fsms()
            self.reset_app()
            self.reset_motion()


    def reset_all_fsms(self):
        Logger.info("[SYSTEM] Resetting all Recipe FSMs...")
        # 1. 모든 FSM 정지
        for fsm in self.recipe_fsm:
            fsm.stop()  # stop_flag = True
            fsm.wait_thread()  # thread.join()

        # 2. FSM 인스턴스 재생성 (권장: 완전 초기화)
        self.recipe_fsm = [
            RecipeFsmSequence(RecipeContext(i)) for i in range(1, 9)
        ]

        # 3. FSM 다시 시작
        for fsm in self.recipe_fsm:
            fsm.start_service_background()

        Logger.info("[SYSTEM] All Recipe FSMs restarted.")

    def handle_error_stop(self):
        ''' Robot FSM error '''
        self.robot_error = (self.robot_fsm.get_state() == FsmState.ERROR)

        ''' Program stop '''
        current_prog_state = bb.get("indy")["program_state"]
        self.prog_stopped = (self.prev_program_state == ProgramState.PROG_RUNNING and
                        current_prog_state != ProgramState.PROG_RUNNING)


        self.prev_program_state = current_prog_state

        if self.robot_error or self.prog_stopped:
            if self.working_recipe_index != None:
                working_fsm = self.recipe_fsm[self.working_recipe_index]
                state = working_fsm.get_state()
                context = working_fsm.context

                Logger.info(f"{get_time()}: [Basket {context.basket_index} FSM] "
                            f"Error/Stop during {working_fsm.get_state()}.")

                if state == RecipeFsmState.MOVE_TO_FRYER:
                    working_fsm.trigger(RecipeFsmEvent.ERROR_DETECT)

                    self.robot_fsm.context.trigger_move_to_fryer = False
                    context.cooking_start_time = time.time()

                elif state == RecipeFsmState.MOVE_FROM_FRYER:
                    working_fsm.trigger(RecipeFsmEvent.ERROR_DETECT)

                    self.robot_fsm.context.trigger_move_from_fryer = False

                elif state == RecipeFsmState.SHAKE:
                    working_fsm.trigger(RecipeFsmEvent.ERROR_DETECT)

                    self.robot_fsm.context.trigger_shake = False

    def check_fryer_conflict(self):
        if global_config.get("frying_coco_version") == "AType":
            fryer_map = {
                1: (1, 3),
                2: (2, 4),
                3: (5, 7),
                4: (6, 8),
            }
            for fryer_id, (primary_basket, secondary_basket) in fryer_map.items():
                primary_fsm = None
                secondary_fsm = None

                for fsm in self.recipe_fsm:
                    context = fsm.context
                    if context.fryer_index != fryer_id:
                        continue

                    if fsm.get_state() == RecipeFsmState.MOVE_TO_FRYER:
                        if context.basket_index == primary_basket:
                            primary_fsm = fsm
                        elif context.basket_index == secondary_basket:
                            secondary_fsm = fsm

                if primary_fsm and secondary_fsm:
                    # conflict 발생 → secondary FSM을 RETURN_READY 시킴
                    secondary_fsm.trigger(RecipeFsmEvent.RETURN_READY)
                    Logger.warn(
                        f"[Conflict] Fryer {fryer_id} has double assignment: "
                        f"Basket {primary_basket} and {secondary_basket}. "
                        f"Returning Basket {secondary_basket} FSM to COOKING_READY."
                    )


    def start(self):
        self.reset_app()
        if not self.running:
            self.running = True
            self.thread = threading.Thread(target=self.run, daemon=True)
            self.thread.start()

    def stop(self):
        self.running = False

        for fsm in self.recipe_fsm:
            fsm.stop()

        if self.thread:
            self.thread.join()

    def run(self):
        while self.running:
            time.sleep(APP_UPDATE_PERIOD)
            self.priority_schedule()
            self.handle_error_stop()
            self.check_fryer_conflict()

            self.update_cooking_state()
            self.add_new_recipe()
            self.handle_app_command()

            self.fsm_logger.log_if_changed()



