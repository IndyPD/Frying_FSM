# process_manager.py
import threading
import time
import json # Added import
import os
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
from .cooking_logger import cooking_logger
from .eco import EcoSensor


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
        Logger.info(f"ProcessManager initialized with fry_type: {self.fry_type}")


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

        # process_manager.py의 __init__ 메서드에서 EcoSensor 부분 수정
        self.eco_sensor = None
        # Load app_config.json specifically for eco_sensor configuration
        # APP_CONFIG_FILE = "/home/user/release/codex_agents_indycare/projects/bulk_frying/configs/app_config.json"
        script_dir = os.path.dirname(os.path.abspath(__file__))
        config_path = os.path.join(script_dir, 'configs', 'app_config.json')
        # --- Debugging logs for config loading ---
        # import os # Already imported at the top
        Logger.info(f"[ProcessManager Init] Current Working Directory: {os.getcwd()}")

        Logger.info(f"[ProcessManager Init] Attempting to load config from: {config_path}")
        # --- End Debugging logs ---

        try:
            with open(config_path, "r") as f:
                self.app_config = json.load(f)
        except FileNotFoundError:
            Logger.error(f"[ProcessManager Init] Error: app_config.json not found at {config_path}")
            self.app_config = {} # Set to empty dict to xavoid KeyError later
        except json.JSONDecodeError as e:
            Logger.error(f"[ProcessManager Init] Error decoding app_config.json: {e}")
            self.app_config = {} # Set to empty dict to avoid KeyError later
        
        # --- Debugging logs for loaded config ---
        # Logger.info(f"[ProcessManager Init] Loaded app_config: {self.app_config}")
        self.eco_sensor_config = self.app_config.get("eco_sensor")
        self.indycare_enabled = self.app_config.get("indycare", True) #Default True
        Logger.info(f"[ProcessManager Init] Extracted eco_sensor_config: {self.eco_sensor_config}")
        # --- End Debugging logs ---

        self.last_eco_sensor_read_time = 0
        self.eco_sensor_first_run = True  # 첫 실행 플래그 추가

        if self.eco_sensor_config and self.eco_sensor_config.get("enabled"):
            Logger.info(f"[ProcessManager Init] EcoSensor enabled: {self.eco_sensor_config.get('enabled')}")
            self.eco_sensor = EcoSensor()
            self.eco_sensor.connect_mqtt()
            Logger.info("EcoSensor initialized and connected to MQTT.")
        else:
            Logger.warn("[ProcessManager Init] EcoSensor is not enabled or config not found. Skipping initialization.")
            
            # 첫 실행 시 바로 데이터 전송 여부 설정
            send_on_startup = self.eco_sensor_config.get("send_on_startup", True)
            if send_on_startup:
                Logger.info("EcoSensor: Will send data immediately on first run.")


        ''' For FSM logging '''
        self.fsm_logger = FSMCSVLogger(self.dry_recipe_fsm, self.robot_fsm)

        ''' Shake option '''
        if bool(global_config.get("maximum_shake")):
            bb.set("ui/state/priority/max_shake", 1)
        else:
            bb.set("ui/state/priority/max_shake", 2)

        # Pickup done 신호를 받을 프라이기를 지정하기 위한 변수
        bb.set("int_var/pickup_target_fryer/val", 0)

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
            bb.set(f"ui/state/fryer{fryer_idx}/elapsed_time", 0)
        
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
        # self.robot_fsm.context.putin_shake = 0
        self.robot_fsm.context.shake_num = 0
        # self.robot_fsm.context.shake_break = 0

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

        # 새로운 바스켓 투입 직전 shake_break 강제 리셋
        bb.set(f"wet_recipe/fryer{context.fryer_index}/shake_break_active", False)

        Logger.info(f"{get_time()}: [ProcessManager] Trigger move_to_fryer motion "
                    f"[FSM {context.fsm_index}, Basket {context.basket_index}, Fryer {context.fryer_index}]")

    def trigger_from_fryer_motion(self, context):
        ''' Move from fryer motion command '''
        bb.set("int_var/pickup_target_fryer/val", context.fryer_index)
        Logger.info(f"[ProcessManager] Set int_var/pickup_target_fryer/val to {context.fryer_index}")
        self.robot_fsm.context.basket_index = context.basket_index
        self.robot_fsm.context.fryer_index = context.fryer_index
        self.robot_fsm.context.fsm_index = context.fsm_index
        self.robot_fsm.context.trigger_move_from_fryer = True

        Logger.info(f"{get_time()}: [ProcessManager] Trigger move_from_fryer motion "
                    f"[FSM {context.fsm_index}, Basket {context.basket_index}, Fryer {context.fryer_index}]")

    def trigger_shift_motion(self, context):
        # 다음 pickup_done 신호가 어떤 프라이기를 위한 것인지 지정
        bb.set("int_var/pickup_target_fryer/val", context.fryer_index)
        Logger.info(f"[ProcessManager] Set int_var/pickup_target_fryer/val to {context.fryer_index}")

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
        is_save_event = False
        keys = ["type", "input_shake", "first_fry_time", "fry_time"]
        
        for recipe_idx in range(1, 11):
            # 기존 레시피 정보 가져오기
            existing_recipe = self.config.get(f"recipe{recipe_idx}", {})
            
            # 숫자 값들 처리
            try:
                new_recipe = [int(bb.get(f"ui/recipe{recipe_idx}/{key}")) for key in keys]
            except (KeyError, TypeError):
                new_recipe = [0, 0, 0, 0]

            # 레시피명 처리 - 유효한 새 값이 있으면 사용, 없으면 기존값 유지
            bb_recipe_name = bb.get(f"ui/recipe{recipe_idx}/recipe_name")
            if bb_recipe_name and bb_recipe_name not in [0, "0", ""]:
                recipe_name = str(bb_recipe_name)
            else:
                recipe_name = existing_recipe.get("recipe_name", "")

            # 저장 이벤트 확인 - 실제 변경이 있을 때만
            has_new_data = any(new_recipe)
            has_new_recipe_name = bb_recipe_name and bb_recipe_name not in [0, "0", ""]
                
            if has_new_data or has_new_recipe_name:
                is_save_event = True
                
                # 기존 레시피 정보와 병합
                recipe_data = existing_recipe.copy()
                recipe_data.update({
                    "recipe_index": recipe_idx,
                    "recipe_name": recipe_name
                })
                
                # 새로운 숫자 데이터가 있을 때만 업데이트
                if has_new_data:
                    recipe_data.update(dict(zip(keys, new_recipe)))
                
                # config에 저장
                self.config[f"recipe{recipe_idx}"] = recipe_data
                
                # 실제 변경된 필드만 리셋
                if has_new_data:
                    for i, key in enumerate(keys):
                        if new_recipe[i] != 0:  # 0이 아닌 새 값이 있을 때만
                            bb.set(f"ui/recipe{recipe_idx}/reset/{key}", True)
                
                # 레시피명 리셋 (새 값이 있을 때만)
                if has_new_recipe_name:
                    bb.set(f"ui/recipe{recipe_idx}/reset/recipe_name", True)
        
        # print(f"[DEBUG] process_manager.py: is_save_event = {is_save_event}")

        if is_save_event:
            # print("[DEBUG] process_manager.py: Save event is TRUE. Saving JSON and preparing MQTT message.")
            save_json(self.config_file, self.config)
            
            # Format data for MQTT (recipe_name 포함)
            recipe_list_for_mqtt = []
            for recipe_key, recipe_data in self.config.items():
                if recipe_data and 'fry_time' in recipe_data:
                    recipe_list_for_mqtt.append({
                        "label": recipe_data.get('recipe_name', ''),
                        "time": recipe_data.get('fry_time', 0)
                    })
            
            if recipe_list_for_mqtt:
                cooking_logger.send_recipe_list_mqtt(recipe_list_for_mqtt)
                print(f"[DEBUG] process_manager.py: Sent recipe list update to MQTT: {recipe_list_for_mqtt}")
            else:
                print("[DEBUG] process_manager.py: MQTT payload is empty. Nothing to send.")
    # def add_new_recipe(self):
    #     # print("[DEBUG] process_manager.py: add_new_recipe() called.")
    #     is_save_event = False
    #     keys = ["type", "input_shake", "first_fry_time", "fry_time"]
    #     i = 0
    #     for recipe_idx in range(1, 11):
    #         try:
    #             new_recipe = [int(bb.get(f"ui/recipe{recipe_idx}/{key}")) for key in keys]
    #         except (KeyError, TypeError):
    #             new_recipe = [0, 0, 0, 0]

    #         # recipe_name 처리
    #         try:
    #             recipe_name = bb.get(f"ui/recipe{recipe_idx}/recipe_name")
    #             if recipe_name is None:
    #                 recipe_name = ""
    #         except (KeyError, TypeError):
    #             recipe_name = ""

    #         # 기존 데이터나 recipe_name이 있으면 저장 이벤트 발생
    #         if any(new_recipe) or recipe_name:
    #             # print(f"[DEBUG] process_manager.py: New data found for recipe{recipe_idx}: {new_recipe}, recipe_name: {recipe_name}")
    #             is_save_event = True
                
    #             # config에 저장 (recipe_name 포함)
    #             self.config[f"recipe{recipe_idx}"] = {
    #                 "recipe_index": recipe_idx, 
    #                 "recipe_name": recipe_name,
    #                 **dict(zip(keys, new_recipe))
    #             }
                
    #             # 기존 키들 리셋
    #             for key in keys:
    #                 bb.set(f"ui/recipe{recipe_idx}/reset/{key}", True)
                
    #             # recipe_name 리셋
    #             bb.set(f"ui/recipe{recipe_idx}/reset/recipe_name", True)
                
    #         i += 1
        
    #     # print(f"[DEBUG] process_manager.py: is_save_event = {is_save_event}")

    #     if is_save_event:
    #         # print("[DEBUG] process_manager.py: Save event is TRUE. Saving JSON and preparing MQTT message.")
    #         save_json(self.config_file, self.config)
            
    #         # Format data for MQTT (recipe_name 포함)
    #         recipe_list_for_mqtt = []
    #         for recipe_key, recipe_data in self.config.items():
    #             if recipe_data and 'fry_time' in recipe_data:
    #                 recipe_list_for_mqtt.append({
    #                     "label": recipe_data.get('recipe_name', ''),
    #                     "time": recipe_data.get('fry_time', 0)
    #                 })
            
    #         if recipe_list_for_mqtt:
    #             cooking_logger.send_recipe_list_mqtt(recipe_list_for_mqtt)
    #             print(f"[DEBUG] process_manager.py: Sent recipe list update to MQTT: {recipe_list_for_mqtt}")
    #         else:
    #             print("[DEBUG] process_manager.py: MQTT payload is empty. Nothing to send.")
    # else:
        # print("[DEBUG] process_manager.py: Save event is FALSE. No changes to save or send.")
    # def add_new_recipe(self):
    #     # print("[DEBUG] process_manager.py: add_new_recipe() called.")
    #     is_save_event = False
    #     keys = ["type", "input_shake", "first_fry_time", "fry_time"]
    #     i = 0
    #     for recipe_idx in range(1, 11):
    #         try:
    #             new_recipe = [int(bb.get(f"ui/recipe{recipe_idx}/{key}")) for key in keys]
    #         except (KeyError, TypeError):
    #             new_recipe = [0, 0, 0, 0]

    #         if any(new_recipe):
    #             # print(f"[DEBUG] process_manager.py: New data found for recipe{recipe_idx}: {new_recipe}")
    #             is_save_event = True
    #             self.config[f"recipe{recipe_idx}"] = {"recipe_index": recipe_idx, **dict(zip(keys, new_recipe))}
    #             for key in keys:
    #                 bb.set(f"ui/recipe{recipe_idx}/reset/{key}", True)
    #         i += 1
        
    #     # print(f"[DEBUG] process_manager.py: is_save_event = {is_save_event}")

    #     if is_save_event:
    #         # print("[DEBUG] process_manager.py: Save event is TRUE. Saving JSON and preparing MQTT message.")
    #         save_json(self.config_file, self.config)
            
    #         # Format data for MQTT
    #         recipe_list_for_mqtt = []
    #         for recipe_key, recipe_data in self.config.items():
    #             if recipe_data and 'fry_time' in recipe_data:
    #                 recipe_list_for_mqtt.append({
    #                     "label": recipe_key,
    #                     "time": recipe_data.get('fry_time', 0)
    #                 })
            
    #         if recipe_list_for_mqtt:
    #             cooking_logger.send_recipe_list_mqtt(recipe_list_for_mqtt)
    #             print(f"[DEBUG] process_manager.py: Sent recipe list update to MQTT: {recipe_list_for_mqtt}")
    #         else:
    #             print("[DEBUG] process_manager.py: MQTT payload is empty. Nothing to send.")
        # else:
            # print("[DEBUG] process_manager.py: Save event is FALSE. No changes to save or send.")

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
                    fsm1_state = self.wet_recipe_fsm[0].context.state
                    Logger.info(f"[Debug] Checking basket 3 PUTIN. Basket 1 state is: {fsm1_state.name}")
                    if self.wet_recipe_fsm[0].context.state in [
                                                                WetRecipeFsmState.PUTIN, 
                                                                WetRecipeFsmState.WAIT_MENU,
                                                                WetRecipeFsmState.PRE_FRY, 
                                                                WetRecipeFsmState.SHIFT_BASKET
                                                                ] :
                        Logger.info(f"[Debug] Basket 3 PUTIN deferred due to basket 1 state.")
                        # break
                        continue

                if fsm.context.basket_index == 8 :
                    fsm6_state = self.wet_recipe_fsm[2].context.state
                    Logger.info(f"[Debug] Checking basket 8 PUTIN. Basket 6 state is: {fsm6_state.name}")
                    if self.wet_recipe_fsm[2].context.state in [
                                                                WetRecipeFsmState.PUTIN, 
                                                                WetRecipeFsmState.WAIT_MENU,
                                                                WetRecipeFsmState.PRE_FRY, 
                                                                WetRecipeFsmState.SHIFT_BASKET
                                                                ] :
                        Logger.info(f"[Debug] Basket 8 PUTIN deferred due to basket 6 state.")
                        # break
                        continue

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
                
                delay_sig = True
                # 투입 시간 조정 50초 대기 (습식 레시피는 1, 4번 프라이어만 사용)
                for j in [1, 4]:
                    fryer_elapsed_time = bb.get(f"ui/state/fryer{j}/elapsed_time")
                    Logger.info(f"[PUTIN_CHECK] Basket {context.basket_index}: Checking fryer {j}, elapsed_time = {fryer_elapsed_time:.2f}s")
                    if 0 < fryer_elapsed_time < 50:
                        delay_sig = False
                        Logger.info(f"[PUTIN_DELAY] Basket {context.basket_index}: Delaying PUTIN because fryer {j} elapsed_time is {fryer_elapsed_time:.2f}s (< 50s).")
                        break 
                
                if not is_conflict and delay_sig:
                    Logger.info(f"[PUTIN_PROCEED] Basket {context.basket_index}: Proceeding with PUTIN.")
                    priority_list.append((3, context))
                elif not delay_sig:
                    # This else block is just for logging, it doesn't change the logic.
                    Logger.info(f"[PUTIN_SKIP] Basket {context.basket_index}: Skipping PUTIN this cycle due to 50s rule.")

            elif state == WetRecipeFsmState.SHAKE:
                ''' Priority 4: SHAKE '''
                priority_list.append((4, context))
            
            elif state == WetRecipeFsmState.SHIFT_BASKET:
                ''' Priority 5: SHIFT_BASKET '''
                if fsm.context.basket_index == 3 :
                    if self.wet_recipe_fsm[0].context.state in [WetRecipeFsmState.FRY]:
                        break
                        # continue

                elif fsm.context.basket_index == 8 :
                    if self.wet_recipe_fsm[2].context.state in [WetRecipeFsmState.FRY]:
                        break
                        # continue

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
            ''''Logger.info(f"[PriorityScheduler] Skipped: Robot is busy. Flags: "
                        f"to_fryer={self.robot_fsm.context.trigger_move_to_fryer}, "
                        f"from_fryer={self.robot_fsm.context.trigger_move_from_fryer}, "
                        f"shift={self.robot_fsm.context.trigger_shift}, "
                        f"shake={self.robot_fsm.context.trigger_shake}")'''
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
        for i in range(1, 5): # putin_shake1 부터 4까지 확인
            putin_shake_cmd = f"ui/command/putin_shake{i}"
            if bb.get(putin_shake_cmd) == 1:
                Logger.info(f"[ProcessManager] Resetting command {putin_shake_cmd}")
                bb.set(f"ui/reset/putin_shake{i}", True)
                
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

            # [FIX] 'prog_stopped' 플래그를 직접 리셋하여 스케줄러가 다시 동작하도록 함
            self.prog_stopped = False
            Logger.info("[ProcessManager] `prog_stopped` flag has been manually reset.")


    # def reset_all_fsms(self):
    #     Logger.info("[SYSTEM] Resetting all Recipe FSMs...")
    #     # 1. 모든 FSM 정지
    #     for fsm in self.dry_recipe_fsm:
    #         fsm.stop()  # stop_flag = True
    #         fsm.wait_thread()  # thread.join()
    #     self.dry_recipe_fsm = [
    #             DryRecipeFsmSequence(DryRecipeContext(i)) for i in range(1, 9)
    #             ]
    #     for fsm in self.dry_recipe_fsm:
    #         fsm.start_service_background()
    #
    #     for fsm in self.wet_recipe_fsm:
    #         fsm.stop()  # stop_flag = True
    #         fsm.wait_thread()  # thread.join()
    #     self.wet_recipe_fsm = [
    #     WetRecipeFsmSequence(WetRecipeContext(i)) for i in [1,3,6,8]
    #     ]
    #     for fsm in self.wet_recipe_fsm:
    #         fsm.start_service_background()
    #     
    #     Logger.info("[SYSTEM] All Recipe FSMs restarted.")

    def reset_all_fsms(self):
        Logger.info("[SYSTEM] [DEBUG] Received request for full FSM reset.")

        # [FIX] stop_program()이 블로킹되어 reset_all_fsms가 멈추는 현상 방지
        if self.robot_fsm and self.robot_fsm.context.check_program_running():
            Logger.warn("[SYSTEM] [DEBUG] Robot program is RUNNING. Stopping it before FSM reset.")
            self.robot_fsm.context.stop_program()
            Logger.info("[SYSTEM] [DEBUG] Robot program stopped successfully.")

        Logger.info("[SYSTEM] [DEBUG] Re-initializing all FSMs without waiting for old threads.")

        # 1. Robot FSM 재시작 (기존 스레드 join을 기다리지 않음)
        if self.robot_fsm:
            self.robot_fsm.stop() # 스레드에 정지 플래그만 설정
        self.robot_control = RobotActionsContext()
        self.robot_fsm = RobotFsmSequence(self.robot_control)
        self.robot_fsm.start_service_background()
        Logger.info("[SYSTEM] [DEBUG] Robot FSM re-initialized.")

        # 2. Recipe FSMs 재시작 (기존 스레드 join을 기다리지 않음)
        for fsm in self.dry_recipe_fsm:
            fsm.stop()
        self.dry_recipe_fsm = [
                DryRecipeFsmSequence(DryRecipeContext(i)) for i in range(1, 9)
                ]
        for fsm in self.dry_recipe_fsm:
            fsm.start_service_background()

        for fsm in self.wet_recipe_fsm:
            fsm.stop()
        self.wet_recipe_fsm = [
        WetRecipeFsmSequence(WetRecipeContext(i)) for i in [1,3,6,8]
        ]
        for fsm in self.wet_recipe_fsm:
            fsm.start_service_background()
        
        Logger.info("[SYSTEM] [DEBUG] All FSMs re-initialized.")

    def handle_error_stop(self):
        ''' Robot FSM error '''
        self.robot_error = (self.robot_fsm.get_state() == RobotFsmState.ERROR)

        ''' Program stop '''
        current_prog_state = bb.get("indy")["program_state"]
        self.prog_stopped = (self.prev_program_state == ProgramState.PROG_RUNNING and
                        current_prog_state != ProgramState.PROG_RUNNING)


        self.prev_program_state = current_prog_state

        if self.robot_error or self.prog_stopped:
            # [FIX] 프로그램이 정지되면, 모든 동작 트리거를 리셋하여 스케줄러 데드락을 방지한다.
            if self.prog_stopped:
                Logger.warn("[ProcessManager] Program stop detected. Resetting all motion triggers to prevent deadlock.")
                self.reset_motion()

            if self.working_recipe_index != None:
                working_fsm = self.dry_recipe_fsm[self.working_recipe_index]
                state = working_fsm.get_state()
                context = working_fsm.context

                Logger.info(f"{get_time()}: [ProcessManager] Error/Stop detected for Basket {context.basket_index} (FSM {context.fsm_index}) in state {state.name}. Triggering ERROR_DETECT.")
                if self.fry_type == "dry" :
                    if state == DryRecipeFsmState.MOVE_TO_FRYER:
                        working_fsm.trigger(DryRecipeFsmEvent.ERROR_DETECT)

                        self.robot_fsm.context.trigger_move_to_fryer = False

                    elif state == DryRecipeFsmState.FRY:
                        working_fsm.trigger(DryRecipeFsmEvent.ERROR_DETECT)

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

    def handle_eco_sensor(self):
        """환경센서 데이터를 읽고 MQTT로 전송하는 메서드"""
        if not self.eco_sensor:
            # Logger.debug("EcoSensor is not enabled or initialized. Skipping.")
            return

        interval = self.eco_sensor_config.get("read_interval_minutes", 10) * 60
        current_time = time.time()
        
        # Logger.info(f"[EcoSensor Handler] Current time: {current_time:.2f}, Last read time: {self.last_eco_sensor_read_time:.2f}, Interval: {interval}s")

        # 첫 실행이거나 지정된 간격이 지났을 때 실행
        should_read = (
            self.last_eco_sensor_read_time == 0 or  # 첫 실행
            current_time - self.last_eco_sensor_read_time >= interval  # 간격 지남
        )
        
        # Logger.info(f"[EcoSensor Handler] Should read sensor: {should_read}")

        if should_read:
            Logger.info("Reading data from EcoSensor...")
            
            # MQTT 연결 상태 확인 및 재연결
            mqtt_connected = self.eco_sensor.is_mqtt_connected()
            Logger.info(f"[EcoSensor Handler] MQTT initially connected: {mqtt_connected}")
            if not mqtt_connected:
                Logger.warn("EcoSensor MQTT session is not connected. Attempting to reconnect...")
                reconnected = self.eco_sensor.connect_mqtt()
                Logger.info(f"[EcoSensor Handler] MQTT reconnected status: {reconnected}")
                
                # 재연결 실패 시 다음 주기에 다시 시도
                if not reconnected:
                    Logger.error("Failed to reconnect EcoSensor MQTT. Will retry in next cycle.")
                    return
            
            # 센서 데이터 읽기
            Logger.info(f"[EcoSensor Handler] Attempting to read sensor data with config: {self.eco_sensor_config}")
            sensor_data = self.eco_sensor.read_data(self.eco_sensor_config)
            
            if sensor_data:
                Logger.info(f"[EcoSensor Handler] Sensor data read successfully: {sensor_data}")
                # 데이터 읽기 성공 시 MQTT 전송
                try:
                    self.eco_sensor.send_data_mqtt(sensor_data)
                    Logger.info(f"EcoSensor data sent successfully: {sensor_data}")
                    
                    # 성공적으로 전송한 경우에만 시간 업데이트
                    self.last_eco_sensor_read_time = current_time
                    Logger.info(f"[EcoSensor Handler] Last read time updated to: {self.last_eco_sensor_read_time:.2f}")
                    
                except Exception as e:
                    Logger.error(f"Failed to send EcoSensor data via MQTT: {e}")
                    # MQTT 전송 실패 시 시간을 업데이트하지 않아서 다음 주기에 재시도
            else:
                Logger.warn("Failed to read EcoSensor data. Will retry in next cycle.")
                # 센서 데이터 읽기 실패 시 시간을 업데이트하지 않아서 다음 주기에 재시도
        # else:
            # Logger.info(f"[EcoSensor Handler] Skipping read. Next read in {(self.last_eco_sensor_read_time + interval - current_time):.2f} seconds.")

    def start(self):
        self.reset_app()
        if not self.running:
            self.running = True
            self.thread = threading.Thread(target=self.run, daemon=True)
            self.thread.start()

    def stop(self):
        self.running = False

        if self.eco_sensor:
            self.eco_sensor.close()

        for fsm in self.wet_recipe_fsm:
            fsm.stop()
        for fsm in self.dry_recipe_fsm:
            fsm.stop()

        if self.robot_fsm:
            self.robot_fsm.stop()

        if self.thread:
            self.thread.join()
    # process_manager.py에 추가할 메서드

    def manage_shake_break_for_wet_recipe(self):
        """
        Wet recipe에서 shake_break와 shake_done 값을 관리
        """
        # Logger.info(f"{get_time()}: [DEBUG] manage_shake_break_for_wet_recipe() 호출됨")
        
        needs_shake = False
        has_recipe_in_putin = False
        
        # Logger.info(f"[DEBUG] wet_recipe_fsm 개수: {len(self.wet_recipe_fsm) if self.wet_recipe_fsm else 0}")
        
        # Wet recipe FSM들의 상태 확인
        for i, fsm in enumerate(self.wet_recipe_fsm):
            context = fsm.context
            state = fsm.get_state()
            recipe_index = context.recipe_index
            
            Logger.info(f"[DEBUG] FSM {i}: Basket {context.basket_index}, State: {state}, Recipe: {recipe_index}")
            
            # PUTIN 상태인 바스켓 중에서
            if state == WetRecipeFsmState.PUTIN:
                if recipe_index > 0:
                    has_recipe_in_putin = True
                    # Logger.info(f"[DEBUG] Basket {context.basket_index}: PUTIN 상태에서 recipe 할당됨!")
                else:
                    needs_shake = True
                    # Logger.info(f"[DEBUG] Basket {context.basket_index}: PUTIN 상태에서 recipe 없음, 흔들기 필요")
            
            elif state == WetRecipeFsmState.WAIT_PUTIN:
                needs_shake = True
                # Logger.info(f"[DEBUG] Basket {context.basket_index}: WAIT_PUTIN 상태, 흔들기 필요")
        
        # shake_break 설정 로직
        if has_recipe_in_putin:
            should_shake_break = 1
            # Logger.info(f"[DEBUG] recipe 할당된 PUTIN 바스켓 있음 -> shake_break=1")
        elif needs_shake:
            should_shake_break = 0
            # Logger.info(f"[DEBUG] 흔들기 필요한 바스켓 있음 -> shake_break=0")
        else:
            should_shake_break = 1
            # Logger.info(f"[DEBUG] 관련 바스켓 없음 -> shake_break=1")
        
        current_shake_break = bb.get("int_var/shake_break/val")
        Logger.info(f"[DEBUG] Current shake_break: {current_shake_break}, Should be: {should_shake_break}")
        
        if current_shake_break != should_shake_break:
            bb.set("int_var/shake_break/val", should_shake_break)
            Logger.info(f"{get_time()}: [ProcessManager] *** shake_break 변경: {current_shake_break} -> {should_shake_break} ***")
        else:
            Logger.info(f"[DEBUG] shake_break 변경 없음: {current_shake_break}")
    def run(self):
        while self.running:
            time.sleep(APP_UPDATE_PERIOD)
            self.priority_schedule()
            self.handle_error_stop()
            self.check_fryer_conflict()
            self.handle_eco_sensor()
            self.update_cooking_state()
            self.add_new_recipe()
            self.handle_app_command()
            
            # 디버깅용 로그 추가
            # if hasattr(self, 'wet_recipe_fsm') and self.wet_recipe_fsm:
            #     Logger.info(f"[DEBUG] manage_shake_break_for_wet_recipe 호출 중...")
            #     self.manage_shake_break_for_wet_recipe()
            # else:
            #     Logger.info(f"[DEBUG] wet_recipe_fsm 없음 또는 빈 리스트")
            
            self.fsm_logger.log_if_changed()
    # def run(self):
    #     while self.running:
    #         time.sleep(APP_UPDATE_PERIOD)
    #         self.priority_schedule()
    #         self.handle_error_stop()
    #         self.check_fryer_conflict()

    #         # --- 전역 putin_shake 신호 업데이트 ---
    #         putin_shake_active = False
    #         for fryer_idx in [1, 4]: # 1번과 4번 프라이어만 고려
    #             key = f"wet_recipe/fryer{fryer_idx}/putin_shake_active"
    #             try:
    #                 if bb.get(key) is True:
    #                     putin_shake_active = True
    #                     break
    #             except KeyError:
    #                 pass # Key not found, treat as False
            
    #         new_putin_shake_val = 1 if putin_shake_active else 0
    #         if bb.get("int_var/putin_shake/val") != new_putin_shake_val:
    #             bb.set("int_var/putin_shake/val", new_putin_shake_val)
    #             Logger.info(f"{get_time()}: [ProcessManager] int_var/putin_shake/val updated to {new_putin_shake_val}")

    #         # --- 전역 shake_break 신호 업데이트 ---
    #         shake_break_active = False
    #         for fryer_idx in [1, 4]: # 1번과 4번 프라이어만 고려
    #             key = f"wet_recipe/fryer{fryer_idx}/shake_break_active"
    #             try:
    #                 if bb.get(key) is True:
    #                     shake_break_active = True
    #                     break
    #             except KeyError:
    #                 pass # Key not found, treat as False
            
    #         new_shake_break_val = 1 if shake_break_active else 0
    #         if bb.get("int_var/shake_break/val") != new_shake_break_val:
    #             bb.set("int_var/shake_break/val", new_shake_break_val)
    #             Logger.info(f"{get_time()}: [ProcessManager] int_var/shake_break/val updated to {new_shake_break_val}")


    #         self.update_cooking_state()
    #         self.add_new_recipe()
    #         self.handle_app_command()

    #         self.fsm_logger.log_if_changed()



