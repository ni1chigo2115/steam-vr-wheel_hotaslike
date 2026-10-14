import os
import random
import threading
import time

import openvr
import sys

from steam_vr_wheel._double_joystick import DoubleJoystick
from steam_vr_wheel._joystick import Joystick
from steam_vr_wheel._touchwheel import TouchWheel
from steam_vr_wheel._virtualpad import VirtualPad
from steam_vr_wheel._wheel import Wheel
from steam_vr_wheel.vrcontroller import Controller
from steam_vr_wheel.configurator import run

FREQUENCY = 60

if 'DEBUG' in sys.argv:
    DEBUG = True
    FREQUENCY = 1
else:
    DEBUG = False

# ==============================================================================
# 案B: getControllerState() の ulButtonTouched / ulButtonPressed を直接読む
# (ビット番号 = ボタンID。0: System, 1: AppMenu, 2: Grip, 32: Touchpad, 34: Axis2 ...)
# ==============================================================================
_last_masks = {}  # {(hand, 'touched'|'pressed'): mask} DEBUG時の変化検出用


def _log_mask_change(hand, kind, new_mask):
    """DEBUG時のみ: 前回から変化したビット(=ボタンID)を表示する"""
    key = (hand, kind)
    old_mask = _last_masks.get(key, 0)
    if new_mask != old_mask:
        changed = old_mask ^ new_mask
        for bit in range(64):
            if (changed >> bit) & 1:
                state = "ON " if (new_mask >> bit) & 1 else "OFF"
                print("[MASK]", hand.upper(), kind.upper(), "ID", bit, state)
        _last_masks[key] = new_mask


def poll_controller_state(vrsystem, controller, hand, wheel):
    try:
        result = vrsystem.getControllerState(controller.id.value)
        # pyopenvr のバージョンにより (成功フラグ, state) のタプル or state単体
        state = result[1] if isinstance(result, tuple) else result
        touched = int(state.ulButtonTouched)
        pressed = int(state.ulButtonPressed)
    except Exception as e:
        if DEBUG:
            print("[MASK] getControllerState failed:", hand, repr(e))
        return

    if DEBUG:
        _log_mask_change(hand, 'touched', touched)
        _log_mask_change(hand, 'pressed', pressed)

    if hasattr(wheel, 'set_touch_mask'):
        wheel.set_touch_mask(hand, touched)


def do_work(vrsystem, left_controller: Controller, right_controller: Controller, wheel: Wheel, poses):
    vrsystem.getDeviceToAbsoluteTrackingPose(openvr.TrackingUniverseSeated, 0, len(poses), poses)
    left_controller.update(poses[left_controller.id.value])
    right_controller.update(poses[right_controller.id.value])
    event = openvr.VREvent_t()
    while vrsystem.pollNextEvent(event):
        hand = None
        if event.trackedDeviceIndex == left_controller.id.value:
            if event.eventType == openvr.VREvent_ButtonTouch:
                button = event.data.controller.button
                if DEBUG:
                    print("LEFT HAND EVENT: BUTTON TOUCH, BUTTON ID", button)

                # 全ボタンタッチ状態を集合に記録
                if hasattr(wheel, 'set_button_touch'):
                    wheel.set_button_touch(button, 'left')

                # 個別対応メソッドの呼び出し
                if button == openvr.k_EButton_SteamVR_Touchpad:
                    wheel.set_trackpad_touch_left()
                elif button == openvr.k_EButton_SteamVR_Trigger:
                    wheel.set_trigger_touch_left()
                elif button == openvr.k_EButton_System and hasattr(wheel, 'set_system_touch_left'):
                    wheel.set_system_touch_left()

            elif event.eventType == openvr.VREvent_ButtonUntouch:
                button = event.data.controller.button
                if DEBUG:
                    print("LEFT HAND EVENT: BUTTON UNTOUCH, BUTTON ID", button)

                # 全ボタンタッチ解除状態を集合に記録
                if hasattr(wheel, 'set_button_untouch'):
                    wheel.set_button_untouch(button, 'left')

                # 個別対応メソッドの呼び出し
                if button == openvr.k_EButton_SteamVR_Touchpad:
                    wheel.set_trackpad_untouch_left()
                elif button == openvr.k_EButton_SteamVR_Trigger:
                    wheel.set_trigger_untouch_left()
                elif button == openvr.k_EButton_System and hasattr(wheel, 'set_system_untouch_left'):
                    wheel.set_system_untouch_left()

            hand = 'left'

        if event.trackedDeviceIndex == right_controller.id.value:
            if event.eventType == openvr.VREvent_ButtonTouch:
                button = event.data.controller.button
                if DEBUG:
                    print("RIGHT HAND EVENT: BUTTON TOUCH, BUTTON ID", button)

                if hasattr(wheel, 'set_button_touch'):
                    wheel.set_button_touch(button, 'right')

                if button == openvr.k_EButton_SteamVR_Touchpad:
                    wheel.set_trackpad_touch_right()
                elif button == openvr.k_EButton_SteamVR_Trigger:
                    wheel.set_trigger_touch_right()
                elif button == openvr.k_EButton_System and hasattr(wheel, 'set_system_touch_right'):
                    wheel.set_system_touch_right()

            elif event.eventType == openvr.VREvent_ButtonUntouch:
                button = event.data.controller.button
                if DEBUG:
                    print("RIGHT HAND EVENT: BUTTON UNTOUCH, BUTTON ID", button)

                if hasattr(wheel, 'set_button_untouch'):
                    wheel.set_button_untouch(button, 'right')

                if button == openvr.k_EButton_SteamVR_Touchpad:
                    wheel.set_trackpad_untouch_right()
                elif button == openvr.k_EButton_SteamVR_Trigger:
                    wheel.set_trigger_untouch_right()
                elif button == openvr.k_EButton_System and hasattr(wheel, 'set_system_untouch_right'):
                    wheel.set_system_untouch_right()

            hand = 'right'

        if hand:
            if event.eventType == openvr.VREvent_ButtonPress:
                if DEBUG:
                    print(hand, "HAND EVENT: BUTTON PRESS, BUTTON ID", event.data.controller.button)
                button = event.data.controller.button
                wheel.set_button_press(button, hand)
            if event.eventType == openvr.VREvent_ButtonUnpress:
                if DEBUG:
                    print(hand, "HAND EVENT: BUTTON UNPRESS, BUTTON ID", event.data.controller.button)
                button = event.data.controller.button
                wheel.set_button_unpress(button, hand)

    # 案B: イベントとは別経路でタッチ状態(ビットマスク)を毎フレーム取得
    poll_controller_state(vrsystem, left_controller, 'left', wheel)
    poll_controller_state(vrsystem, right_controller, 'right', wheel)

    if wheel.config.edit_mode:
        wheel.edit_mode(left_controller, right_controller)
    else:
        wheel.update(left_controller, right_controller)


def get_controller_ids():
    vrsys = openvr.VRSystem()
    for i in range(openvr.k_unMaxTrackedDeviceCount):
        device_class = vrsys.getTrackedDeviceClass(i)
        if device_class == openvr.TrackedDeviceClass_Controller:
            role = vrsys.getControllerRoleForTrackedDeviceIndex(i)
            if role == openvr.TrackedControllerRole_RightHand:
                 right = i
            if role == openvr.TrackedControllerRole_LeftHand:
                 left = i
    return left, right


def main(type='wheel'):
    openvr.init(openvr.VRApplication_Overlay)
    vrsystem = openvr.VRSystem()
    hands_got = False

    while not hands_got:
        try:
            print('Searching for left and right hand controllers')
            left, right = get_controller_ids()
            hands_got = True
            for i in range(4):
                openvr.VRSystem().triggerHapticPulse(right, 0, 3000)
                time.sleep(0.2)
            print('left and right hands found')
        except NameError:
            pass
        time.sleep(0.1)

    left_controller = Controller(left, name='left', vrsys=vrsystem)
    right_controller = Controller(right, name='right', vrsys=vrsystem)
    if type == 'wheel':
        wheel = Wheel()
    elif type == 'joystick':
        wheel = Joystick()
    elif type == 'doublejoystick':
        wheel = DoubleJoystick()
    elif type == 'touchwheel':
        wheel = TouchWheel()
    elif type == 'pad':
        wheel = VirtualPad()
    poses_t = openvr.TrackedDevicePose_t * openvr.k_unMaxTrackedDeviceCount
    poses = poses_t()
    while True:
        before_work = time.time()
        do_work(vrsystem, left_controller, right_controller, wheel, poses)
        after_work = time.time()
        left = 1/FREQUENCY - (after_work - before_work)
        if left>0:
            time.sleep(left)

if __name__ == '__main__':
    main()