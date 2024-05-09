#!/usr/bin/env python3

from selectors import EVENT_READ, DefaultSelector
import sys
import threading
import time

from evdev import InputDevice, UInput, categorize, ecodes, list_devices
from loguru import logger

sys.path.extend([".", ".."])
import settings


class DeviceMacro:
    def __init__(self, mouse_name: str = "MOUSE", keyboard_name: str = "USB Keyboard"):
        # 获取鼠标设备
        for device_path in list_devices():
            device = InputDevice(device_path)

            if mouse_name in device.name:
                mouse = device
            elif keyboard_name in device.name:
                keyboard = device
            else:
                continue

            logger.info(device.capabilities(verbose=True))

        if not mouse:
            logger.error("Mouse not found")

        if not keyboard:
            logger.error("Keyboard not found")

        self.mouse = mouse
        self.keyboard = keyboard

        self.right_button_held = False
        self.space_locked = False

    def click_thread(self, ui: UInput = None, sleep_ms=settings.click_ms):
        count = 0
        device = ui or self.mouse
        while self.right_button_held:
            # 模拟鼠标左键按下
            device.write(ecodes.EV_KEY, ecodes.BTN_LEFT | ecodes.BTN_MOUSE, 1)
            if ui:
                # 同步鼠标事件
                device.syn()

            # 模拟鼠标左键释放
            device.write(ecodes.EV_KEY, ecodes.BTN_LEFT | ecodes.BTN_MOUSE, 0)
            if ui:
                # 同步鼠标事件
                device.syn()

            # 等待事件响应
            time.sleep(sleep_ms / 1000)

            # 打印点击次数
            logger.info(f"Click count: {count}")
            count += 1

    def space_thread(self, ui: UInput = None, sleep_ms=settings.space_ms):
        count = 0
        device = ui or self.keyboard
        while self.space_locked:
            # 模拟键盘按下空格键
            device.write(ecodes.EV_KEY, ecodes.KEY_SPACE, 1)
            device.write(ecodes.EV_KEY, ecodes.KEY_SPACE, 0)
            if ui:
                # 同步键盘事件
                device.syn()

            # 等待事件响应
            time.sleep(sleep_ms / 1000)

            # 打印点击次数
            logger.info(f"Space count: {count}")
            count += 1

    def keynum_click_key2(
        self, num: int, mouse_u: UInput = None, keyboard_u: UInput = None
    ):
        logger.info(f"key_{num}-clicked-key_3")

        key_num = f"KEY_{num}"
        keyboard = keyboard_u or self.keyboard
        mouse = mouse_u or self.mouse

        # 模拟键盘按下对应的数字键
        keyboard.write(ecodes.EV_KEY, ecodes.ecodes[key_num], 1)
        keyboard.write(ecodes.EV_KEY, ecodes.ecodes[key_num], 0)
        if keyboard_u:
            keyboard.syn()

        # # 等待键盘事件响应
        time.sleep(0.8)

        # 模拟鼠标左键按下
        mouse.write(ecodes.EV_KEY, ecodes.BTN_LEFT | ecodes.BTN_MOUSE, 1)
        if mouse_u:
            mouse.syn()
        mouse.write(ecodes.EV_KEY, ecodes.BTN_LEFT | ecodes.BTN_MOUSE, 0)
        if mouse_u:
            mouse.syn()

        # 等待点击事件响应
        time.sleep(0.5)

        # 模拟键盘按下数字键2
        keyboard.write(ecodes.EV_KEY, ecodes.KEY_2, 1)
        keyboard.write(ecodes.EV_KEY, ecodes.KEY_2, 0)
        if keyboard_u:
            keyboard.syn()

        # # 等待键盘事件响应
        # time.sleep(0.5)

    def handle_mouse(
        self,
        event,
        mouse_u: UInput = None,
        keyboard_u: UInput = None,
        *,
        sleep_ms=settings.click_ms,
        use_proxy=False,
    ):
        logger.debug(f"Mouse event: {event}")

        if event.type != ecodes.EV_KEY:
            if use_proxy:
                # 代理鼠标事件
                mouse_u.write_event(event)
            return

        keyboard = keyboard_u or self.keyboard
        key_event = categorize(event)

        match key_event.keycode, key_event.keystate:
            case "BTN_RIGHT", key_event.key_down:
                self.right_button_held = True
                threading.Thread(
                    target=self.click_thread, args=(mouse_u, sleep_ms)
                ).start()
            case "BTN_RIGHT", key_event.key_up:
                self.right_button_held = False
            case "BTN_EXTRA", key_event.key_down:
                # threading.Thread(
                #     target=self.keynum_click_key2, args=(1, mouse_u, keyboard_u)
                # ).start()
                keyboard.write(ecodes.EV_KEY, ecodes.KEY_1, 1)
                keyboard.write(ecodes.EV_KEY, ecodes.KEY_1, 0)
                if keyboard_u:
                    keyboard_u.syn()
            case "BTN_SIDE", key_event.key_down:
                # threading.Thread(
                #     target=self.keynum_click_key2, args=(4, mouse_u, keyboard_u)
                # ).start()
                keyboard.write(ecodes.EV_KEY, ecodes.KEY_2, 1)
                keyboard.write(ecodes.EV_KEY, ecodes.KEY_2, 0)
                if keyboard_u:
                    keyboard_u.syn()
            case _, _:
                if use_proxy:
                    # 代理鼠标事件
                    mouse_u.write_event(event)

    def handle_keyboard(
        self, event, ui: UInput = None, *, sleep_ms=settings.space_ms, use_proxy=False
    ):
        logger.debug(f"Keyboard event: {event}")

        if event.type != ecodes.EV_KEY:
            if use_proxy:
                # 代理键盘事件
                ui.write_event(event)
            return

        device = ui or self.keyboard

        key_event = categorize(event)
        match key_event.keycode, key_event.keystate:
            case "KEY_SPACE", key_event.key_down:
                self.space_locked = True
                threading.Thread(
                    target=self.space_thread, args=(device, sleep_ms)
                ).start()
            case "KEY_SPACE", key_event.key_up:
                self.space_locked = False
            case "KEY_Q", key_event.key_down:
                self.space_locked = not self.space_locked
                threading.Thread(
                    target=self.space_thread, args=(device, sleep_ms)
                ).start()
            case _, _:
                if use_proxy:
                    # 代理键盘事件
                    ui.write_event(event)

    def run(
        self,
        *,
        mouse_ms=settings.click_ms,
        space_ms=settings.space_ms,
        use_uinput=True,
        use_proxy=False,
        virtual_mouse_name="Virtual Mouse",
        virtual_keyboard_name="Virtual Keyboard",
    ):
        if use_uinput:
            # 创建一个虚拟输入设备
            if use_proxy:
                # 独占原始输入设备
                self.mouse.grab()
                self.keyboard.grab()

            mouse_u = UInput.from_device(self.mouse, name=virtual_mouse_name)
            keyboard_u = UInput.from_device(self.keyboard, name=virtual_keyboard_name)

        # 创建一个事件选择器
        selector = DefaultSelector()

        selector.register(self.mouse, EVENT_READ)
        selector.register(self.keyboard, EVENT_READ)
        while True:
            for key, mask in selector.select():
                device = key.fileobj

                for event in device.read():
                    if device == self.mouse:
                        self.handle_mouse(event, mouse_u, sleep_ms=mouse_ms)
                    elif device == self.keyboard:
                        self.handle_keyboard(event, keyboard_u, sleep_ms=space_ms)


# %%
if __name__ == "__main__":
    logger.remove()
    logger.add(sys.stderr, level="INFO")
    device_macro = DeviceMacro()
    device_macro.run()
