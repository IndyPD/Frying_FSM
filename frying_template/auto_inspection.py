import time
from datetime import datetime
from frying_template.fsm import FsmSequence, RobotActionsContext
from pkg.utils.blackboard import GlobalBlackboard
from pkg.utils.logging import Logger
from .constants import *

bb = GlobalBlackboard()

def wait_until_robot_idle(terminate_flag):
    while not terminate_flag.is_set():
        if int(bb.get("int_var/cmd/val")) == 0:
            return True
        time.sleep(1)
    Logger.warn("[INSPECT] Interrupted while waiting for robot idle.")
    return False

def trigger_motion(robot_ctx, command_type: str, basket_idx: int, terminate_flag, extra_vars: dict = None):
    if extra_vars:
        for key, val in extra_vars.items():
            setattr(robot_ctx, key, val)

    Logger.info(f"[INSPECT] Triggering {command_type.upper()} for Basket {basket_idx}")

    if command_type == "move_to_fryer":
        robot_ctx.trigger_move_to_fryer = True
    elif command_type == "move_from_fryer":
        robot_ctx.trigger_move_from_fryer = True
    elif command_type == "shake":
        robot_ctx.trigger_shake = True

    robot_ctx.basket_index = basket_idx  # 공통 설정
    return wait_until_robot_idle(terminate_flag)


def auto_inspection(robot_fsm, terminate_flag):
    robot_ctx = robot_fsm.context
    Logger.info("===== Auto Inspection Started =====")

    Logger.info("Wait until Start...")
    while not terminate_flag.is_set():
        time.sleep(0.1)
        state = robot_fsm.get_state()
        if state == FsmState.READY_IDLE:
            break

    cycle_count = 0
    while not terminate_flag.is_set():
        for b in [1, 2, 5, 6]:
            trigger_motion(robot_ctx, "move_to_fryer", b, terminate_flag)
            time.sleep(1)

        fryer_map = {1: [1], 2: [2], 3: [5], 4: [6]}
        for fryer, baskets in fryer_map.items():
            for b in baskets:
                for i in range(3):
                    trigger_motion(robot_ctx, "shake", b, terminate_flag,
                                   {"shake_num": 1})
                    time.sleep(1)

        for b in [1, 2, 5, 6]:
            trigger_motion(robot_ctx, "move_from_fryer", b, terminate_flag,
                           {"drain_num": 0})

        for b in [3, 4, 7, 8]:
            trigger_motion(robot_ctx, "move_to_fryer", b, terminate_flag)

        fryer_map2 = {1: [3], 2: [4], 3: [7], 4: [8]}
        for fryer, baskets in fryer_map2.items():
            for b in baskets:
                trigger_motion(robot_ctx, "shake", b, terminate_flag,
                               {"shake_num": 1})

        for b in [3, 4, 7, 8]:
            trigger_motion(robot_ctx, "move_from_fryer", b, terminate_flag,
                           {"drain_num": 0})

        cycle_count += 1
        Logger.info(f"===== Auto Inspection Completed: {cycle_count} cycle =====")
