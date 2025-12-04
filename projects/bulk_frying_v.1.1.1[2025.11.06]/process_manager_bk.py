# process_manager.py
import threading
import time
from .constants import *
from .robot_fsm import RobotFsmSequence
from .robot_context import RobotActionsContext
from . import indy_control
from .dry_recipe_fsm import DryRecipeFsmSequence
from .dry_recipe_context import DryRecipeContext
from .wet_recipe_fsm import WetRecipeFsmSequence
from .wet_recipe_context import WetRecipeContext
from pkg.utils.file_io import load_json, save_json
from pkg.utils.blackboard import GlobalBlackboard
from pkg.configs.global_config import GlobalConfig

from .fsm_logger import FSMCSVLogger


bb = GlobalBlackboard()
global_config = GlobalConfig()


class ProcessManager:
    def __init__(self):
        self.running = False
        self.thread = None

        self.config_file = CONFIG_FILE
        self.config = load_json(self.config_file)

        ''' Priority '''
        self.prev_program_state = ProgramState.PROG_IDLE
        self.priority_recipe = None
        self.working_recipe_index = None

        ''' Fry time '''
        self.fry_type = "dry" # or wet

        ''' Manual command buffer '''
        self.shake_buffer = [False, False, False, False]
        self.shift_buffer = [False, False]
        self.serve_buffer = [False, False]

        ''' Robot FSM '''
        self.robot_control = RobotActionsContext()
        self.robot_fsm = RobotFsmSequence(self.robot_control)
        self.robot_fsm.start_service_background()
        self.robot_error = None
        self.prog_stopped = None

        Logger.info(f"robot fsm run")

        ''' Initialize Recipe FSMs '''
        self.dry_recipe_fsm = [
            DryRecipeFsmSequence(DryRecipeContext(i)) for i in range(1, 9)
        ]
        for fsm in self.dry_recipe_fsm:
            fsm.start_service_background()

        Logger.info(f"dry fsm run")

        self.wet_recipe_fsm = [
            WetRecipeFsmSequence(WetRecipeContext(i)) for i in [1,3,6,8]
        ]
        for fsm in self.wet_recipe_fsm:
            fsm.start_service_background()
        
        Logger.info(f"wet fsm run")

        ''' For FSM logging '''
        self.fsm_logger = FSMCSVLogger(self.dry_recipe_fsm, self.robot_fsm)

        ''' Shake option '''
        if bool(global_config.get("maximum_shake")):
            bb.set("ui/state/priority/max_shake", 1)
        else:
            bb.set("ui/state/priority/max_shake", 2)

    def reset_app(self):
        """
        1. 최초 실행 시,
        2. 조리상태 초기화 버튼 이력 시
        """
        bb.set("recipe/finish_number", 0)
        bb.set("ui/state/finish_number", 0)

        for fryer_idx in range(1, 5):
            bb.set(f"ui/state/fryer{fryer_idx}/recipe", 0)
            bb.set(f"ui/state/fryer{fryer_idx}/min", 0)
            bb.set(f"ui/state/fryer{fryer_idx}/sec", 0)
        
        bb.set("recipe/enable/fryer1",0)
        bb.set("recipe/enable/fryer2",0)
        bb.set("recipe/enable/fryer3",0)
        bb.set("recipe/enable/fryer4",0)
        
        if self.fry_type == "dry":
            for basket_idx in range(1, 9):
                bb.set(f"ui/reset/basket{basket_idx}/state", True)
        elif self.fry_type == "wet":
            for idx in range(1, 5):
                bb.set(f"ui/reset/manual_btn{idx}", True)
        


    def reset_motion(self):
        self.robot_fsm.context.trigger_move_from_fryer = False
        self.robot_fsm.context.trigger_move_to_fryer = False
        self.robot_fsm.context.trigger_shake = False
        self.robot_fsm.context.trigger_shift = False

        bb.set("recipe/command/move_to_fryer_done", 0)
        bb.set("recipe/command/move_from_fryer_done", 0)
        bb.set("recipe/command/shake_done", 0)
        bb.set("recipe/command/shift_done", 0)

        self.robot_fsm.context.basket_index = 0
        self.robot_fsm.context.fryer_index = 0
        self.robot_fsm.context.putin_shake = 0
        self.robot_fsm.context.shake_num = 0
        self.robot_fsm.context.shake_break = 0

    def trigger_to_fryer_motion(self, context):

        Logger.info(f"trigger_to_fryer_motion {context.basket_index}")
        ''' Move to fryer motion command '''
        self.robot_fsm.context.basket_index = context.basket_index

        if context.fry_type == 'wet':
            if context.basket_index in [1, 3] :
                self.robot_fsm.context.fryer_index = 1
            elif context.basket_index in [6, 8] :
                self.robot_fsm.context.fryer_index = 4
        else : 
            self.robot_fsm.context.fryer_index = context.fryer_index

        self.robot_fsm.context.fsm_index = context.fsm_index
        self.robot_fsm.context.trigger_move_to_fryer = True

        Logger.info(f"{get_time()}: [ProcessManager] Trigger move_to_fryer motion "
                    f"[FSM {context.fsm_index}, Basket {context.basket_index}, Fryer {context.fryer_index}]")

    def trigger_from_fryer_motion(self, context):
        ''' Move from fryer motion command '''
        self.robot_fsm.context.basket_index = context.basket_index
        self.robot_fsm.context.fryer_index = context.fryer_index
        self.robot_fsm.context.fsm_index = context.fsm_index
        self.robot_fsm.context.trigger_move_from_fryer = True

        Logger.info(f"{get_time()}: [ProcessManager] Trigger move_from_fryer motion "
                    f"[FSM {context.fsm_index}, Basket {context.basket_index}, Fryer {context.fryer_index}]")

    def trigger_shift_motion(self, context):
        self.robot_fsm.context.basket_index = context.basket_index
        self.robot_fsm.context.fryer_index = context.fryer_index
        self.robot_fsm.context.fsm_index = context.fsm_index
        self.robot_fsm.context.trigger_shift = True

        Logger.info(f"{get_time()}: [ProcessManager] Trigger shift motion "
                    f"[FSM {context.fsm_index}, Basket {context.basket_index}, Fryer {context.fryer_index}]")


    def trigger_shake_motion(self, context):
        '''
        Recipe FSM -> Robot FSM command (shake)
        '''
        # Logger.info(f"trigger_shake_motion : {context.fsm_index}, {context.basket_index}, {context.fryer_index}")
        self.shake_buffer[context.fryer_index-1] = False
        self.robot_fsm.context.basket_index = context.basket_index
        self.robot_fsm.context.fryer_index = context.fryer_index
        self.robot_fsm.context.fsm_index = context.fsm_index
        self.robot_fsm.context.trigger_shake = True

        Logger.info(f"{get_time()}: [ProcessManager] Trigger shake_basket motion "
                    f"[FSM {context.fsm_index}, Basket {context.basket_index}, Fryer {context.fryer_index}]")

    def add_new_recipe(self):
        # TODO recipe_name 넣기
        is_save_event = False
        keys = ["type", "input_shake", "first_fry_time", "fry_time"]
        i = 0
        for recipe_idx in range(1, 11):
            new_recipe = [int(bb.get(f"ui/recipe{recipe_idx}/{key}")) for key in keys]
            # print('sync recipe : ',new_recipe)

            if any(new_recipe):
                # print('sync recipe : ',new_recipe)
                is_save_event = True
                self.config[f"recipe{recipe_idx}"] = {"recipe_index": recipe_idx, **dict(zip(keys, new_recipe))}
                for key in keys:
                    bb.set(f"ui/recipe{recipe_idx}/reset/{key}", True)
            i += 1
        

        if is_save_event:
            save_json(self.config_file, self.config)

    def get_dry_recipe_priority(self):
        priority_list = []
        ''' STEP 1: 우선순위 작업 수집 '''
        for fsm in self.dry_recipe_fsm:            
            context = fsm.context
            state = fsm.get_state()


            if state == DryRecipeFsmState.MOVE_FROM_FRYER:
                ''' Priority 1: 배출 (오버쿠킹 방지 절대 조건) '''
                priority_list.append((1, context))

            elif state == DryRecipeFsmState.FRY:
                elapsed_time = bb.get(f"ui/state/basket{fsm.context.basket_index}/fry_time")
                basket_remain_time = bb.get(f"ui/state/basket{fsm.context.basket_index}/fry_remain_time")
                fryer_remain_time = bb.get(f"ui/state/fryer{fsm.context.fryer_index}/remain_time")
                # Logger.info(f"basket {fsm.context.basket_index} time : {elapsed_time} {basket_remain_time} {fryer_remain_time}")

                ''' Priority 2: FRY → 배출까지 25초 남으면 다른 작업 미할당 '''
                if (context.peek_next_state() == DryRecipeFsmState.MOVE_FROM_FRYER
                        and context.finish_remaining_time < 25):                    
                    priority_list.append((2, context))

                ''' Priority 5: 모션 없을 때 SHAKE 앞당기기 '''
                if global_config.get("maximum_shake"):
                    # 투입 후 60초간 쉐이크 금지 추가, 시간남을 때 쉐이크 한번하면 이후 30초 동안 금지                    
                    if context.peek_next_state() == DryRecipeFsmState.SHAKE and int(elapsed_time) > 60 and context.elapsed_shake_done_time > 30 :
                        # context.shake_option = 0
                        fsm.trigger(DryRecipeFsmEvent.SHAKE_TIME_DONE)
                        priority_list.append((5, context))
                        context.shake_type = "auto"

                ''' Priority 6: App 수동 쉐이크 버튼 '''
                # if self.shake_buffer[context.fryer_index - 1]:
                #     # context.shake_option = self.shake_buffer[context.fryer_index - 1][0]
                #     self.shake_buffer[context.fryer_index - 1].pop(0)
                #     fsm.trigger(DryRecipeFsmEvent.SHAKE_TIME_DONE)
                #     priority_list.append((6, context))
                #     context.shake_type = "manual"

            elif state == DryRecipeFsmState.MOVE_TO_FRYER:
                ''' Priority 3: 투입, 추후 배출 시 오버쿠킹 안되도록 이 레시피 종료와 다른 레시피 종료 10초 차이 유지 '''

                delay_sig = True
                # 투입 시간 조정 50초 대기 
                for j in range(1,5) :
                    fryer_elapsed_time = bb.get(f"ui/state/fryer{j}/elapsed_time")
                    if fryer_elapsed_time < 50 and fryer_elapsed_time > 0:
                        delay_sig = False
                    # Logger.info(f"MOVE_TO_FRYER : {j} {fryer_elapsed_time} {delay_sig}")

                if delay_sig:
                    priority_list.append((3, context))

            elif state == DryRecipeFsmState.SHAKE:
                ''' Priority 4: SHAKE '''
                priority_list.append((4, context))


        """ Trigger priority motion """
        if not priority_list:
            self.working_recipe_index = None
            return
        
        ''' 우선순위 오름차순, 오버쿠킹 시간 내림차순, 쉐이크 횟수 오름차순 '''
        if global_config.get("maximum_shake"):
            priority_list.sort(key=lambda x: (
                x[0],
                -x[1].overcooking_time,
                x[1].shake_num,
                x[1].fryer_index
                
            ))
        else:
            priority_list.sort(key=lambda x: (
                x[0],
                -x[1].overcooking_time,
                x[1].fryer_index))


        Logger.info("[PriorityScheduler] Current priority list:")
        for priority, context in priority_list:
            Logger.info(
                f"  - Basket {context.basket_index} | "
                f"Fryer: {context.fryer_index} | "
                f"type: {context.fry_type} | "
                f"State: {context.state.name} | "
                f"Shake_times : {context.shake_num} | "
                f"Elapsed: {context.elapsed_time:.1f}s | "
                f"FinishRemain: {context.finish_remaining_time:.1f}s | "
                f"Priority: {priority}"
            )

        _, context = priority_list[0]
        self.priority_recipe = context
        self.working_recipe_index = context.basket_index - 1

        state = context.state

        if state == DryRecipeFsmState.MOVE_FROM_FRYER:
            self.trigger_from_fryer_motion(context)

        elif state == DryRecipeFsmState.SHAKE:
            self.trigger_shake_motion(context)

        elif state == DryRecipeFsmState.MOVE_TO_FRYER:
            self.trigger_to_fryer_motion(context)

    def get_wet_recipe_priority(self):
        priority_list = []
        #TODO: wet implementation
        ''' STEP 1: 우선순위 작업 수집 '''
        for fsm in self.wet_recipe_fsm:
            context = fsm.context
            state = fsm.get_state()

            if state == WetRecipeFsmState.MOVE_FROM_FRYER:
                ''' Priority 1: 배출 (오버쿠킹 방지 절대 조건) '''
                priority_list.append((1, context))

            elif state == WetRecipeFsmState.FRY:
                ''' Priority 2: FRY → 배출까지 5초 남으면 다른 작업 미할당 '''
                if (context.peek_next_state() == WetRecipeFsmState.MOVE_FROM_FRYER
                        and context.finish_remaining_time < 5):
                    priority_list.append((2, context))

                ''' Priority 5: 모션 없을 때 SHAKE 앞당기기 '''
                # if global_config.get("maximum_shake"):
                #     if context.peek_next_state() == RecipeFsmState.SHAKE:
                #         context.shake_done_num += 1
                #         context.shake_option = 0
                #         fsm.trigger(RecipeFsmEvent.SHAKE_TIME_DONE)
                #         priority_list.append((5, context))
                #         context.shake_type = "auto"

                ''' Priority 6: App 수동 쉐이크 버튼 '''
                # if self.shake_buffer[context.fryer_index - 1]:
                #     context.shake_option = self.shake_buffer[context.fryer_index - 1][0]
                #     self.shake_buffer[context.fryer_index - 1].pop(0)
                #     fsm.trigger(RecipeFsmEvent.SHAKE_TIME_DONE)
                #     priority_list.append((6, context))
                #     context.shake_type = "manual"

            elif state == WetRecipeFsmState.PUTIN:
                ''' Priority 3: 투입, 추후 배출 시 오버쿠킹 안되도록 이 레시피 종료와 다른 레시피 종료 10초 차이 유지 '''
                # TODO: 다시 구현 (Dry recipe FSM의 remaining time 이용해서 계산)
                # TODO: Frying COCO A타입 코드 참고
                now = time.time()
                fryer_finish_time = {i: 0 for i in [2,3]}  # fryer2~3
                estimated_end_time = now + context.fry_time + MOVE_TO_FRY_MOTION_TIME
                buffer = MOVE_FROM_FRY_MOTION_TIME  - 1
                is_conflict = False

                if fsm.context.basket_index == 3 :
                    if self.wet_recipe_fsm[0].context.state in [
                                                                WetRecipeFsmState.PUTIN, 
                                                                WetRecipeFsmState.WAIT_MENU,
                                                                WetRecipeFsmState.PRE_FRY, 
                                                                WetRecipeFsmState.SHIFT_BASKET
                                                                ] :
                        break

                if fsm.context.basket_index == 8 :
                    if self.wet_recipe_fsm[2].context.state in [
                                                                WetRecipeFsmState.PUTIN, 
                                                                WetRecipeFsmState.WAIT_MENU,
                                                                WetRecipeFsmState.PRE_FRY, 
                                                                WetRecipeFsmState.SHIFT_BASKET
                                                                ] :
                        break

                for fryer_idx, scheduled_finish in fryer_finish_time.items():
                    if scheduled_finish == 0:       
                        continue
                    time_diff = abs(estimated_end_time - scheduled_finish)
                    if time_diff < buffer:
                        is_conflict = True
                        Logger.info(
                            f"[ProcessManager] MOVE_TO_FRYER delayed for Basket {context.basket_index} | "
                            f"Conflict with fryer{fryer_idx} | Δt={time_diff:.1f}s")
                        break                
                if not is_conflict:
                    priority_list.append((3, context))

            elif state == WetRecipeFsmState.SHAKE:
                ''' Priority 4: SHAKE '''
                priority_list.append((4, context))
            
            elif state == WetRecipeFsmState.SHIFT_BASKET:
                ''' Priority 5: SHIFT_BASKET '''
                if fsm.context.basket_index == 3 :
                    if self.wet_recipe_fsm[0].context.state in [WetRecipeFsmState.FRY]:
                        break

                elif fsm.context.basket_index == 8 :
                    if self.wet_recipe_fsm[2].context.state in [WetRecipeFsmState.FRY]:
                        break

                priority_list.append((5, context))
                


        """ Trigger priority motion """
        if not priority_list:
            self.working_recipe_index = None
            return

        ''' 우선순위 오름차순, 오버쿠킹 시간 내림차순, 쉐이크 횟수 오름차순 '''
        if global_config.get("maximum_shake"):
            priority_list.sort(key=lambda x: (
                    x[0],
                    -x[1].overcooking_time,
                    x[1].fryer_index
                ))
                
        else:
            priority_list.sort(key=lambda x: (x[0], -x[1].overcooking_time))

        Logger.info("[PriorityScheduler] Current priority list:")
        for priority, context in priority_list:
            Logger.info(
                f"  - Basket {context.basket_index} | "
                f"Fryer: {context.fryer_index} | "
                f"Fryer: {context.fry_type} | "
                f"State: {context.state.name} | "
                f"Elapsed: {context.elapsed_time:.1f}s | "
                f"FinishRemain: {context.finish_remaining_time:.1f}s | "
                f"Priority: {priority}"
            )

        _, context = priority_list[0]
        self.priority_recipe = context
        self.working_recipe_index = context.basket_index - 1

        state = context.state

        
        if state == WetRecipeFsmState.MOVE_FROM_FRYER:
            self.trigger_from_fryer_motion(context)

        elif state == WetRecipeFsmState.SHAKE:
            self.trigger_shake_motion(context)

        elif state == WetRecipeFsmState.PUTIN:
            self.trigger_to_fryer_motion(context)

        elif state == WetRecipeFsmState.SHIFT_BASKET :            
            self.trigger_shift_motion(context)
    
    def priority_schedule(self):

        # Home pass 체크
        isready = True
        for i in range(1,9) :
            xx = bb.get(f"recipe/basket{i}/state")
            # Logger.info(f"check {i},{xx}")
            if xx in [
                DryRecipeFsmState.NO_MENU,
                DryRecipeFsmState.COOKING_READY,
                DryRecipeFsmState.FRY,
                DryRecipeFsmState.FINISH,
                WetRecipeFsmState.WAIT_PUTIN
                                            ] :
                # Logger.info(f"check : {isready}")
                isready = isready and True
            else :
                isready = isready and False

        bb.set("recipe/state/ready",isready)
        # Logger.info(f"check : {isready}")


        if (int(bb.get("int_var/cmd/val")) != 0 or
            self.robot_fsm.context.trigger_move_to_fryer or
            self.robot_fsm.context.trigger_move_from_fryer or
            self.robot_fsm.context.trigger_shift or
            self.robot_fsm.context.trigger_shake):
            return

        if self.robot_error or self.prog_stopped:
            return
        
        
        self.get_dry_recipe_priority()
        self.get_wet_recipe_priority()
        # if self.fry_type == "dry":
        #     self.get_dry_recipe_priority()
        # elif self.fry_type == "wet":
        #     self.get_wet_recipe_priority()

    def update_cooking_state(self):
        ''' Update all baskets (FSMs) cooking state and send it to app '''
        current_work = 0
        ''' Basket state '''
        for fsm in self.dry_recipe_fsm:
            context = fsm.context
            state = fsm.get_state()

            cooking_state = 0
            if fsm.context.fry_type == "dry" :
                if state == DryRecipeFsmState.NO_MENU:
                    if int(bb.get(f"indy_state/basket{context.basket_index}")) == 1:
                        cooking_state = CookingState.BEFORE_COOKING
                    else:
                        cooking_state = CookingState.NONE
                elif state == DryRecipeFsmState.COOKING_READY:
                    cooking_state = CookingState.BEFORE_COOKING
                    current_work = 1
                elif state in {DryRecipeFsmState.MOVE_TO_FRYER, DryRecipeFsmState.FRY,
                                DryRecipeFsmState.SHAKE, DryRecipeFsmState.MOVE_FROM_FRYER}:
                    cooking_state = CookingState.COOKING
                    current_work = 1
                    # Logger.info(f"{get_time()} {fsm.context.fsm_index} Dry update_cooking_state {state} : {cooking_state}")
                elif state == DryRecipeFsmState.FINISH:
                    cooking_state = CookingState.DONE_COOKING

                bb.set(f"ui/state/basket{context.basket_index}/state", int(cooking_state))
        if current_work == 1 :
            return

        for fsm in self.wet_recipe_fsm:
            context = fsm.context
            state = fsm.get_state()
            # Logger.info(f"{get_time()} {fsm.context.fsm_index} update_cooking_state A : {state}")

            cooking_state = 0
            if fsm.context.fry_type == "wet":
                if state == WetRecipeFsmState.WAIT_PUTIN:
                    if int(bb.get(f"indy_state/basket{context.basket_index}")) == 1:
                        cooking_state = CookingState.BEFORE_COOKING
                    else:
                        cooking_state = CookingState.NONE

                # elif state == WetRecipeFsmState.COOKING_READY:
                #     cooking_state = CookingState.BEFORE_COOKING

                elif state in {
                        WetRecipeFsmState.PRE_FRY,
                        WetRecipeFsmState.FRY,
                        WetRecipeFsmState.SHAKE,
                        WetRecipeFsmState.MOVE_FROM_FRYER
                    }:                    
                    cooking_state = CookingState.COOKING
                    # Logger.info(f"{get_time()} {fsm.context.fsm_index} Wet update_cooking_state {state} : {cooking_state}")
                elif state == WetRecipeFsmState.FINISH:
                    cooking_state = CookingState.DONE_COOKING

                bb.set(f"ui/state/basket{context.basket_index}/state", int(cooking_state))


    def handle_app_command(self):
        ''' App 입력 대응 '''

        ''' 바스켓 흔들기 옵션 버튼 '''
        # TODO: 항상 max shake   흔들기로 변경
        global_config.set("maximum_shake", True)

        putin_shake1 = bb.get("ui/command/putin_shake1")
        putin_shake2 = bb.get("ui/command/putin_shake2")
        # Logger.info(f"handle_app_command {putin_shake1}, {putin_shake2}")
        
        ''' "조리 상태 초기화" 버튼 '''
        if bb.get("ui/command/reset_logic"):
            bb.set("ui/command/reset_logic", False)
            bb.set("ui/reset/reset_logic", True)
            Logger.info(f"{get_time()}: [ProcessManager] Reset all recipes!")

            self.reset_all_fsms()
            self.reset_app()
            self.reset_motion()


    def reset_all_fsms(self):
        Logger.info("[SYSTEM] Resetting all Recipe FSMs...")
        # 1. 모든 FSM 정지
        for fsm in self.dry_recipe_fsm:
            fsm.stop()  # stop_flag = True
            fsm.wait_thread()  # thread.join()
        self.dry_recipe_fsm = [
                DryRecipeFsmSequence(DryRecipeContext(i)) for i in range(1, 9)
                ]
        for fsm in self.dry_recipe_fsm:
            fsm.start_service_background()

        for fsm in self.wet_recipe_fsm:
            fsm.stop()  # stop_flag = True
            fsm.wait_thread()  # thread.join()
        self.wet_recipe_fsm = [
        WetRecipeFsmSequence(WetRecipeContext(i)) for i in [1,3,6,8]
        ]
        for fsm in self.wet_recipe_fsm:
            fsm.start_service_background()
        
        Logger.info("[SYSTEM] All Recipe FSMs restarted.")

    def handle_error_stop(self):
        ''' Robot FSM error '''
        self.robot_error = (self.robot_fsm.get_state() == RobotFsmState.ERROR)

        ''' Program stop '''
        current_prog_state = bb.get("indy")["program_state"]
        self.prog_stopped = (self.prev_program_state == ProgramState.PROG_RUNNING and
                        current_prog_state != ProgramState.PROG_RUNNING)


        self.prev_program_state = current_prog_state

        if self.robot_error or self.prog_stopped:
            if self.working_recipe_index != None:
                working_fsm = self.dry_recipe_fsm[self.working_recipe_index]
                state = working_fsm.get_state()
                context = working_fsm.context

                Logger.info(f"{get_time()}: [Basket {context.basket_index} FSM] "
                            f"Error/Stop during {working_fsm.get_state()}.")
                if self.fry_type == "dry" :
                    if state == DryRecipeFsmState.MOVE_TO_FRYER:
                        working_fsm.trigger(DryRecipeFsmEvent.ERROR_DETECT)

                        self.robot_fsm.context.trigger_move_to_fryer = False
                        context.cooking_start_time = time.time()

                    elif state == DryRecipeFsmState.MOVE_FROM_FRYER:
                        working_fsm.trigger(DryRecipeFsmEvent.ERROR_DETECT)

                        self.robot_fsm.context.trigger_move_from_fryer = False

                    elif state == DryRecipeFsmState.SHAKE:
                        working_fsm.trigger(DryRecipeFsmEvent.ERROR_DETECT)

                        self.robot_fsm.context.trigger_shake = False
                elif self.fry_type == "wet" :
                    if state == WetRecipeFsmState.WAIT_PUTIN:
                        working_fsm.trigger(WetRecipeFsmEvent.ERROR_DETECT)

                        self.robot_fsm.context.trigger_move_to_fryer = False
                        context.cooking_start_time = time.time()

                    elif state == WetRecipeFsmState.MOVE_FROM_FRYER:
                        working_fsm.trigger(WetRecipeFsmEvent.ERROR_DETECT)

                        self.robot_fsm.context.trigger_move_from_fryer = False

                    elif state == WetRecipeFsmState.SHAKE:
                        working_fsm.trigger(WetRecipeFsmEvent.ERROR_DETECT)

                        self.robot_fsm.context.trigger_shake = False
        
        # TODO wet꺼 넣기
        # if self.robot_error or self.prog_stopped:
        #     if self.working_recipe_index != None:
        #         working_fsm = self.wet_recipe_fsm[self.working_recipe_index]
        #         state = working_fsm.get_state()
        #         context = working_fsm.context

        #         Logger.info(f"{get_time()}: [Basket {context.basket_index} FSM] "
        #                     f"Error/Stop during {working_fsm.get_state()}.")
        #         if self.fry_type == "dry" :
        #             if state == DryRecipeFsmState.MOVE_TO_FRYER:
        #                 working_fsm.trigger(DryRecipeFsmEvent.ERROR_DETECT)

        #                 self.robot_fsm.context.trigger_move_to_fryer = False
        #                 context.cooking_start_time = time.time()

        #             elif state == DryRecipeFsmState.MOVE_FROM_FRYER:
        #                 working_fsm.trigger(DryRecipeFsmEvent.ERROR_DETECT)

        #                 self.robot_fsm.context.trigger_move_from_fryer = False

        #             elif state == DryRecipeFsmState.SHAKE:
        #                 working_fsm.trigger(DryRecipeFsmEvent.ERROR_DETECT)

        #                 self.robot_fsm.context.trigger_shake = False
        #         elif self.fry_type == "wet" :
        #             if state == WetRecipeFsmState.WAIT_PUTIN:
        #                 working_fsm.trigger(WetRecipeFsmEvent.ERROR_DETECT)

        #                 self.robot_fsm.context.trigger_move_to_fryer = False
        #                 context.cooking_start_time = time.time()

        #             elif state == WetRecipeFsmState.MOVE_FROM_FRYER:
        #                 working_fsm.trigger(WetRecipeFsmEvent.ERROR_DETECT)

        #                 self.robot_fsm.context.trigger_move_from_fryer = False

        #             elif state == WetRecipeFsmState.SHAKE:
        #                 working_fsm.trigger(WetRecipeFsmEvent.ERROR_DETECT)

        #                 self.robot_fsm.context.trigger_shake = False

    def check_fryer_conflict(self):
        # Dry recipe related
        fryer_map = {
            1: (1, 3),
            2: (2, 4),
            3: (5, 7),
            4: (6, 8),
        }
        for fryer_id, (primary_basket, secondary_basket) in fryer_map.items():
            primary_fsm = None
            secondary_fsm = None
            i = 0
            for fsm in self.dry_recipe_fsm:
                i += 1
                context = fsm.context
                if context.fryer_index != fryer_id:
                    continue
                
                if fsm.get_state() == DryRecipeFsmState.MOVE_TO_FRYER:
                    if context.basket_index == primary_basket:
                        primary_fsm = fsm
                    elif context.basket_index == secondary_basket:
                        secondary_fsm = fsm

            if primary_fsm and secondary_fsm:
                # conflict 발생 → secondary FSM을 RETURN_READY 시킴
                secondary_fsm.trigger(DryRecipeFsmEvent.RETURN_READY)
                Logger.warn(
                    f"[Conflict] Fryer {fryer_id} has double assignment: "
                    f"Basket {primary_basket} and {secondary_basket}. "
                    f"Returning Basket {secondary_basket} FSM to COOKING_READY."
                )

    def assign_putin_basket(self):
        # TODO: assign putin basket
        for fsm in self.wet_recipe_fsm:
            state = fsm.get_state()
            if state == WetRecipeFsmState.WAIT_PUTIN:
                #TODO: [1, 2], [3, 4]

                fsm.context.putin_done = True


    def start(self):
        self.reset_app()
        if not self.running:
            self.running = True
            self.thread = threading.Thread(target=self.run, daemon=True)
            self.thread.start()

    def stop(self):
        self.running = False

        for fsm in self.wet_recipe_fsm:
            fsm.stop()
        for fsm in self.dry_recipe_fsm:
            fsm.stop()

        if self.robot_fsm:
            self.robot_fsm.stop()

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



