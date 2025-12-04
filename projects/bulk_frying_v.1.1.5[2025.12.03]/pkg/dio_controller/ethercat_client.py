import sys
import os

current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(current_dir, "impl"))

from ethercat_pb2_grpc import EtherCATStub
from common_msgs_pb2 import *
from ethercat_msgs_pb2 import *


import common as Common
import grpc
import time

OP_MODE_NO_MODE = 0x00
OP_MODE_PROFILE_POSITION = 0x01
OP_MODE_VELOCITY = 0x02
OP_MODE_PROFILE_VELOCITY = 0x03
OP_MODE_TORQUE_PROFILE = 0x04
OP_MODE_HOMING = 0x06
OP_MODE_INTERPOLATED_POSITION = 0x07
OP_MODE_CYCLIC_SYNC_POSITION = 0x08
OP_MODE_CYCLIC_SYNC_VELOCITY = 0x09
OP_MODE_CYCLIC_SYNC_TORQUE = 0x0a

def status2string(statusword):
    if (((statusword) & 0x004f) == 0x0000):   # x0xx 0000
        return "NOT_READY"
    elif (((statusword) & 0x004f) == 0x0040): # x1xx 0000
        return "SWITCH_DISABLED"
    elif (((statusword) & 0x006f) == 0x0021): # x01x 0001
        return "READY_SWITCH"
    elif (((statusword) & 0x006f) == 0x0023): # x01x 0011
        return "SWITCHED_ON"
    elif (((statusword) & 0x006f) == 0x0027): # x01x 0111
        return "OPERATION_ENABLED"
    elif (((statusword) & 0x006f) == 0x0007): # x00x 0111
        return "QUICK_STOP"
    elif (((statusword) & 0x004f) == 0x000f): # x0xx 1111
        return "FAULT_REACTION"
    elif (((statusword) & 0x004f) == 0x0008): # x0xx 1000
        return "FAULT"
    else:
        return "UNKNOWN"
    
    
def modeop2string(modeop):
    if modeop == 0x00:
        return "None"
    elif modeop == 0x01:
        return "PP"
    elif modeop == 0x03:
        return "PV"
    elif modeop == 0x04:
        return "TP"
    elif modeop == 0x06:
        return "Homing"
    elif modeop == 0x08:
        return "CSP"
    elif modeop == 0x09:
        return "CSV"
    elif modeop == 0x0a:
        return "CST"


def error_code(mode_op, status_word):
    string_out = []
    if mode_op == OP_MODE_PROFILE_POSITION:
        if (status_word & 0x2000):
            string_out.append("Following error")
        if (status_word & 0x1000):
            string_out.append("Set-point acknowledge")
        if (status_word & 0x0400):
            string_out.append("Target reached")

    elif mode_op == OP_MODE_PROFILE_VELOCITY:
        if (status_word & 0x2000):
            string_out.append("Max slippage error")
        if (status_word & 0x1000):
            string_out.append("Speed")
        if (status_word & 0x0400):
            string_out.append("Target reached")

    elif mode_op == OP_MODE_CYCLIC_SYNC_POSITION:
        if (status_word & 0x2000):
            string_out.append("Following error")
        if (status_word & 0x1000):
            string_out.append("Drive follows command value")

    elif mode_op == OP_MODE_CYCLIC_SYNC_VELOCITY:
        if (status_word & 0x1000):
            string_out.append("Drive follows command value")

    elif mode_op == OP_MODE_CYCLIC_SYNC_TORQUE:
        if (status_word & 0x1000):
            string_out.append("Drive follows command value")
    return string_out

class EtherCATClient(metaclass=Common.SingletonMeta):
    """
    gRPC client to EtherCAT Server in C++ IndyFramework v3.0
    """
    __ethercat_stub: EtherCATStub

    def __init__(self, ip_addr, port=20000):
        self.channel_name = "{}:{}".format(ip_addr, port)
        self.channel = None
        while True:
            try:
                self.connect()
                grpc.channel_ready_future(self.channel).result(timeout=0.5)  # Adjust timeout as needed
                print("EtherCATClient channel is ready for communication.")
                break
            except grpc.FutureTimeoutError:
                try:
                    self.disconnect()
                finally:
                    time.sleep(0.5)
            except Exception as e:
                raise(e)

    def connect(self):
        self.channel = grpc.insecure_channel(self.channel_name)
        self.__ethercat_stub = EtherCATStub(self.channel)

    def disconnect(self):
        self.channel.close()

    @Common.Utils.exception_handler
    def get_master_status(self):
        """
        Master status
            status -> int
        """
        status = self.__ethercat_stub.GetMasterStatus(Empty()).status
        if status == 1:
            return "INIT"
        elif status == 2:
            return "PRE-OP"
        elif status == 4:
            return "SAFE-OP"
        elif status == 8:
            return "OP"
        else:
            return "None"

    @Common.Utils.exception_handler
    def get_slave_status(self):
        """
        Slave status

        """
        status = (self.__ethercat_stub.GetSlaveStatus(Empty()).status)
        slave_status = []
        for stat in status:
            if stat == 1:
                slave_status.append("INIT")
            elif stat == 2:
                slave_status.append("PRE-OP")
            elif stat == 4:
                slave_status.append("SAFE-OP")
            elif stat == 8:
                slave_status.append("OP")
            else:
                slave_status.append("None")
        return slave_status

    @Common.Utils.exception_handler
    def get_txdomain_status(self):
        """
        PDO Tx Domain status
        """
        status = self.__ethercat_stub.GetTxDomainStatus(Empty()).status
        if status == 0:
            return "ZERO"
        elif status == 1:
            return "INCOMPLETE"
        elif status == 2:
            return "COMPLETE"
        else:
            return "None"

    @Common.Utils.exception_handler
    def get_rxdomain_status(self):
        """
        PDO Rx Domain status
        """
        status = self.__ethercat_stub.GetRxDomainStatus(Empty()).status
        if status == 0:
            return "ZERO"
        elif status == 1:
            return "INCOMPLETE"
        elif status == 2:
            return "COMPLETE"
        else:
            return "None"

    @Common.Utils.exception_handler
    def is_system_ready(self):
        """
        System ready state
        """
        return list(self.__ethercat_stub.IsSystemReady(Empty()).ready)

    @Common.Utils.exception_handler
    def is_servo_on(self):
        """
        Servo on state
        """
        return list(self.__ethercat_stub.IsServoOn(Empty()).servo)

    @Common.Utils.exception_handler
    def get_slave_type_num(self):
        """
        Servo on state
        """
        return self.__ethercat_stub.GetSlaveTypeNum(Empty())

    @Common.Utils.exception_handler
    def set_servo(self, servo_idx, on):
        """
        Servo on state
        """
        if on:
            self.__ethercat_stub.SetServoOn(ServoIndex(servoIndex=servo_idx))
        else:
            self.__ethercat_stub.SetServoOff(ServoIndex(servoIndex=servo_idx))

    @Common.Utils.exception_handler
    def get_servo_tx(self, servo_idx):
        """
        Get Servo driver's Tx PDO values
        """
        res = self.__ethercat_stub.GetServoTx(ServoIndex(servoIndex=servo_idx))
        return [status2string(res.statusWord), modeop2string(res.modeOpDisp), res.actualPosition, res.actualVelocity, res.actualTorque]

    @Common.Utils.exception_handler
    def get_servo_rx(self, servo_idx):
        """
        Get Servo driver's Rx PDO values
        """
        res = self.__ethercat_stub.GetServoRx(ServoIndex(servoIndex=servo_idx))
        return [res.controlWord, res.modeOp, res.targetPosition, res.targetVelocity, res.targetTorque]

    @Common.Utils.exception_handler
    def set_servo_rx(self, servo_idx, control_word, mode_op, target_pos, target_vel, target_tor):
        """
        Set Servo driver's Rx PDO values
        """
        print(servo_idx, control_word, mode_op, target_pos, target_vel, target_tor)
        servo_rx = ServoRx(controlWord=control_word, modeOp=mode_op, targetPosition=target_pos, targetVelocity=target_vel, targetTorque=target_tor)
        return self.__ethercat_stub.SetServoRx(ServoRxIndex(servoIndex=servo_idx, rx=servo_rx))

    @Common.Utils.exception_handler
    def get_servo_temperature(self, servo_idx):
        """
        Get Servo SDO temperatures
        """
        return self.__ethercat_stub.GetServoTemperature(ServoIndex(servoIndex=servo_idx)).temperature

    @Common.Utils.exception_handler
    def get_servo_errorcode(self, servo_idx):
        """
        Get Servo SDO error code
        """
        return self.__ethercat_stub.GetServoErrorCode(ServoIndex(servoIndex=servo_idx)).errorCode

    @Common.Utils.exception_handler
    def reset_servo(self, servo_idx):
        """
        Reset servo error
        """
        return self.__ethercat_stub.ResetServo(ServoIndex(servoIndex=servo_idx))

    @Common.Utils.exception_handler
    def set_endtool_rx(self, endtool_rx):
        """
        Set endtool Rx data
        """
        eqc = endtool_rx["eqc"]
        gripper = endtool_rx["gripper"]
        ft_param = endtool_rx["ft_param"]
        led_mode = endtool_rx["led_mode"]
        led_g = endtool_rx["led_g"]
        led_r = endtool_rx["led_r"]
        led_b = endtool_rx["led_b"]
        return self.__ethercat_stub.SetEndtoolRx(EndtoolRx(eqc=eqc, gripper=gripper, ft_param=ft_param, led_mode=led_mode, led_g=led_g, led_r=led_r, led_b=led_b))

    @Common.Utils.exception_handler
    def get_endtool_rx(self):
        """
        Get endtool Rx data
        """
        endtool_rx = {}
        data = self.__ethercat_stub.GetEndtoolRx(Empty())
        endtool_rx["eqc"] = data.eqc
        endtool_rx["gripper"] = data.gripper
        endtool_rx["ft_param"] = data.ft_param
        endtool_rx["led_mode"] = data.led_mode
        endtool_rx["led_g"] = data.led_g
        endtool_rx["led_r"] = data.led_r
        endtool_rx["led_b"] = data.led_b
        return endtool_rx

    @Common.Utils.exception_handler
    def get_endtool_tx(self):
        """
        Get endtool Tx data
        """
        endtool_tx = {}
        data = self.__ethercat_stub.GetEndtoolTx(Empty())
        endtool_tx["status"] = data.status
        endtool_tx["button"] = data.button
        endtool_tx["ft_sensor"] = data.ft_sensor
        endtool_tx["ft_state"] = data.ft_state
        endtool_tx["ft_error"] = data.ft_error
        return endtool_tx

    @Common.Utils.exception_handler
    def get_ioboard_tx(self):
        """
        Get ioboard Tx data
        """
        ioboard_tx = {}
        data = self.__ethercat_stub.GetIOBoardTx(Empty())
        ioboard_tx["di5v"] = data.di5v
        ioboard_tx["di24v1"] = data.di24v1
        ioboard_tx["di24v2"] = data.di24v2
        ioboard_tx["ai1"] = data.ai1
        ioboard_tx["ai2"] = data.ai2
        return ioboard_tx

    @Common.Utils.exception_handler
    def get_ioboard_rx(self):
        """
        Get ioboard Rx data
        """
        ioboard_rx = {}
        data = self.__ethercat_stub.GetIOBoardRx(Empty())
        ioboard_rx["do5v"] = data.do5v
        ioboard_rx["do24v1"] = data.do24v1
        ioboard_rx["do24v2"] = data.do24v2
        ioboard_rx["ao1"] = data.ao1
        ioboard_rx["ao2"] = data.ao2
        ioboard_rx["ft_param"] = data.ft_param
        return ioboard_rx

    @Common.Utils.exception_handler
    def set_ioboard_rx(self, ioboard_rx):
        """
        Set ioboard Rx data
        """
        do5v = ioboard_rx["do5v"]
        do24v1 = ioboard_rx["do24v1"]
        do24v2 = ioboard_rx["do24v2"]
        ao1 = ioboard_rx["ao1"]
        ao2 = ioboard_rx["ao2"]
        ft_param = ioboard_rx["ft_param"]
        return self.__ethercat_stub.SetIOBoardRx(
            EndtoolRx(do5v=do5v, do24v1=do24v1, do24v2=do24v2, ao1=ao1, ao2=ao2, ft_param=ft_param))


    @Common.Utils.exception_handler
    def get_di(self, dio_index):
        """
        Get DIO Tx data
        """
        return self.__ethercat_stub.GetDI(DIOIndex(dioIndex=dio_index))

    @Common.Utils.exception_handler
    def get_do(self, dio_index):
        """
        Set ioboard Rx data
        """
        return self.__ethercat_stub.GetDO(DIOIndex(dioIndex=dio_index))
    
    @Common.Utils.exception_handler
    def set_do(self, dio_index, dio):
        """
        Set ioboard Rx data
        """
        return self.__ethercat_stub.SetDO(DIODigitalOutput(dioIndex=dio_index, do_list=dio))
        
    
