from pkg.fsm.base import *
from datetime import datetime
import inspect
import threading



def get_time():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

''' Robot FSM related '''
class FsmState(OpState):
    INACTIVE = INACTIVE_STATE

    ERROR = 1
    RECOVERING = 2
    NOT_READY = 3
    NOT_READY_IDLE = 4
    WARMING_ROBOT = 5
    MOVE_TO_READY = 6
    READY_IDLE = 7

    MOVE_BASKET_TO_FRYER = 8
    MOVE_BASKET_FROM_FRYER = 9
    SHAKE_BASKET = 10
    SHIFT_BASKET = 11
    CLEAN_BASKET = 12

    BYPASS_TO_FRYER = 13
    BYPASS_FROM_FRYER = 14
    BYPASS_SHAKE = 15
    BYPASS_SHIFT = 16
    BYPASS_CLEAN = 17


class FsmEvent(OpEvent):
    NONE = NONE_EVENT

    RECOVER = 1  #
    ERROR_DETECT = 2
    DONE = 3

    STOP = 4

    START_PROGRAM = 5
    START_WARMING = 6

    RUN_SHAKE = 7
    RUN_BASKET_TO_FRYER = 8
    RUN_BASKET_FROM_FRYER = 9
    RUN_SHIFT = 10
    RUN_CLEAN = 11


class MyViolation(ViolationType):
    NONE = 0
    NOT_READY = 1
    VIOLATION = 2
    COLLISION = 3
    RECOVERING = 4
    BRAKE_CONTROL = 5


class RobotState(IntEnum):
    # Indy's FSM state
    OP_SYSTEM_OFF = 0
    OP_SYSTEM_ON = 1
    OP_VIOLATE = 2
    OP_RECOVER_HARD = 3
    OP_RECOVER_SOFT = 4
    OP_IDLE = 5
    OP_MOVING = 6
    OP_TEACHING = 7
    OP_COLLISION = 8
    OP_STOP_AND_OFF = 9
    OP_COMPLIANCE = 10
    OP_BRAKE_CONTROL = 11
    OP_SYSTEM_RESET = 12
    OP_SYSTEM_SWITCH = 13
    OP_VIOLATE_HARD = 15
    OP_MANUAL_RECOVER = 16
    TELE_OP = 17


class ProgramState(IntEnum):
    PROG_IDLE = 0
    PROG_RUNNING = 1
    PROG_PAUSING = 2
    PROG_STOPPING = 3


class ProgramControl(IntEnum):
    PROG_IDLE = 0
    PROG_START = 1
    PROG_RESUME = 2
    PROG_PAUSE = 3
    PROG_STOP = 4


class DigitalState(IntEnum):
    OFF_STATE = 0
    ON_STATE = 1
    UNUSED_STATE = 2


class EndtoolState(IntEnum):
    UNUSED = 0
    HIGH_PNP = 2
    HIGH_NPN = 1
    LOW_NPN = -1
    LOW_PNP = -2


''' Recipe FSM related '''
MOVE_TO_FRY_MOTION_TIME = 10
MOVE_FROM_FRY_MOTION_TIME = 27
SHAKE_MOTION_TIME = 11

fsm_assign_lock = threading.Lock()
fryer_locks = {
    1: threading.Lock(),
    2: threading.Lock(),
    3: threading.Lock(),
    4: threading.Lock()
}

CONFIG_FILE = "configs/frying_recipe.json"
BASKET_TO_FRYER_MAP = {
    1: 1, 2: 2, 3: 1, 4: 2,
    5: 3, 6: 4, 7: 3, 8: 4
}
OPPOSITE_BASKET_MAP = {
    1: 3, 2: 4, 3: 1, 4: 2,
    5: 7, 6: 8, 7: 5, 8: 6
}

ASSIGN_READY_INDEX = 0  # 0~7 (basket_index 1~8)


APP_UPDATE_PERIOD = 0.5
FSM_UPDATE_PERIOD = 0.02
SENSOR_MISSING_TIME_SEC = 5


class RecipeFsmState(OpState):
    INACTIVE = INACTIVE_STATE
    NO_MENU             = 1
    COOKING_READY       = 2
    FRY                 = 3
    MOVE_TO_FRYER       = 4
    MOVE_FROM_FRYER     = 5
    SHAKE               = 6
    FINISH              = 7


class RecipeFsmEvent(OpEvent):
    NONE = NONE_EVENT

    ERROR_DETECT      = 1
    ASSIGN_MENU       = 2
    START_MENU        = 3
    SHAKE_TIME_DONE   = 4
    COOKING_TIME_DONE = 5
    MOTION_DONE       = 6
    RESET_MENU        = 7
    CANCEL_MENU       = 8
    DONE              = 9
    RETURN_READY      = 10


class WorkStatus(IntEnum):
    MANUAL      = 0
    IDLE        = 1
    TO_FRYER    = 2
    SHAKE       = 3
    TO_STATION  = 4
    WARMING     = 5


class CookingState(IntEnum):
    NONE = 0
    BEFORE_COOKING = 1
    DONE_COOKING = 2
    COOKING = 3

class ProgramState(IntEnum):
    PROG_IDLE = 0
    PROG_RUNNING = 1
    PROG_PAUSING = 2
    PROG_STOPPING = 3

''' Others '''

class ContyCommand(IntEnum):
    NONE = 0

    INIT_ADD_APPROACH = 300
    INIT_ADD_VALUE    = 400

    HOME = 100

    MOVE_BASKET_TO_FRYER_A      = 100
    MOVE_BASKET_FROM_FRYER_A    = 110
    SHAKE_BASKET_A              = 120

    MOVE_BASKET_TO_FRYER_B      = 200
    MOVE_BASKET_FROM_FRYER_B    = 250
    SHAKE_BASKET_B              = 260

    MOVE_BASKET_TO_FRYER_C      = 300
    MOVE_BASKET_FROM_FRYER_C    = 340
    SHAKE_BASKET_C              = 380
    SHIFT_BASKET                = 430
    CLEAN_BASKET                = 430



class WorkStatus(IntEnum):
    MANUAL     = 0
    IDLE       = 1
    SHAKE      = 2
    TO_FRYER   = 3
    TO_STATION = 4
    WARMING    = 5


class GripFailure(IntEnum):
    SUCCESS = 1
    CLOSE_FAIL = 2
    OPEN_FAIL = 3