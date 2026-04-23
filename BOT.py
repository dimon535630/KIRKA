import threading
import time
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

import cv2
import keyboard
import mss
import numpy as np
import pydirectinput
import pyautogui
import tkinter as tk
from tkinter import ttk

# =========================
# Глобальные константы
# =========================
TEMPLATE_MATCH_CONFIDENCE = 0.80
CHECK_DELAY = 0.03
AUTO_GUI_INTERNAL_PAUSE = 0
POST_CLICK_DELAY = 0.05
LMB_HOLD_DURATION = 0.1
MG1_POST_SUCCESS_DELAY = 0.15
MG2_TEMPLATE_THRESHOLD = 0.72
MG2_APPEAR_CHECK_DELAY = 0.05
MG2_MAX_APPEAR_CHECKS = 20
MG2_CLICK_INTERVAL = 1
MG2_REQUIRED_NO_BAR_CHECKS = 3
MG2_NO_BAR_RECHECK_DELAY = 0.03
MG3_WAIT_ACTIVATION_DELAY = 0.05
MG3_MORPH_KERNEL_SIZE = (3, 3)
MG3_MORPH_OPEN_ITERATIONS = 1
MG3_MORPH_DILATE_ITERATIONS = 1
MIN_CONTOUR_AREA = 35
MG3_POST_TARGET_CLICK_DELAY = 0.05
MG3_FRAME_DELAY = 0.01
WAIT_RESET_CHECK_DELAY = 0.08

START_STOP_HOTKEY = "f5"
MG1_ACTION_KEY = "e"
MOUSE_LEFT_BUTTON = "left"
TEMPLATE_MATCH_METHOD = cv2.TM_CCOEFF_NORMED
CONTOUR_RETRIEVAL_MODE = cv2.RETR_EXTERNAL
CONTOUR_APPROX_MODE = cv2.CHAIN_APPROX_SIMPLE

ROI_GAME1 = {"left": 13, "top": 11, "width": 413, "height": 79}
ROI_GAME2 = {"left": 1585, "top": 984, "width": 319, "height": 39}
ROI_GAME3 = {"left": 654, "top": 309, "width": 669, "height": 390}
ROI_FONAR = {"left": 1309, "top": 197, "width": 222, "height": 133}
FULL_HD_MONITOR = {"left": 0, "top": 0, "width": 1920, "height": 1080}

TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"
TEMPLATE_1_BASE = "1"
TEMPLATE_BAR_BASE = "Bar"
TEMPLATE_FONAR_BASE = "fonar"

COLOR_MASKS = {
    "red": [(np.array([3, 20, 36]), np.array([25, 255, 255]))],
    "cyan": [(np.array([40, 0, 122]), np.array([98, 255, 255]))],
    "yellow": [(np.array([8, 40, 50]), np.array([29, 255, 255]))],
    "dark": [(np.array([0, 0, 10]), np.array([85, 150, 150]))],
}

pyautogui.PAUSE = AUTO_GUI_INTERNAL_PAUSE
pydirectinput.PAUSE = AUTO_GUI_INTERNAL_PAUSE


class BotState(Enum):
    MG1 = "MG1"
    MG2 = "MG2"
    MG3 = "MG3"
    WAIT_RESET = "WAIT_RESET"


@dataclass
class RuntimeControl:
    stop_event: threading.Event


def load_template(template_base_name: str):
    """
    Загружает шаблон из папки templates с поддержкой .png/.PNG.
    """
    candidates = [
        TEMPLATES_DIR / f"{template_base_name}.png",
        TEMPLATES_DIR / f"{template_base_name}.PNG",
    ]

    for path in candidates:
        tpl = cv2.imread(str(path), cv2.IMREAD_COLOR)
        if tpl is not None:
            return tpl

    raise FileNotFoundError(
        f"Не удалось загрузить шаблон '{template_base_name}'. "
        f"Положите файл в папку: {TEMPLATES_DIR}"
    )


def grab_roi(sct, roi):
    shot = sct.grab(roi)
    return np.array(shot)[:, :, :3]


def match_template(region_bgr, template_bgr, threshold=TEMPLATE_MATCH_CONFIDENCE):
    if region_bgr.shape[0] < template_bgr.shape[0] or region_bgr.shape[1] < template_bgr.shape[1]:
        return False, 0.0, (0, 0)

    res = cv2.matchTemplate(region_bgr, template_bgr, TEMPLATE_MATCH_METHOD)
    _, max_val, _, max_loc = cv2.minMaxLoc(res)
    return max_val >= threshold, max_val, max_loc


def click_screen(_x=None, _y=None):
    if _x is not None and _y is not None:
        pydirectinput.click(int(_x), int(_y))

    pydirectinput.click(button=MOUSE_LEFT_BUTTON)
    time.sleep(POST_CLICK_DELAY)


def click_lmb_without_move():
    pydirectinput.mouseDown(button=MOUSE_LEFT_BUTTON)
    time.sleep(LMB_HOLD_DURATION)
    pydirectinput.mouseUp(button=MOUSE_LEFT_BUTTON)


def should_stop(ctrl: RuntimeControl):
    return ctrl.stop_event.is_set()


def mini_game_1(sct, template_1, ctrl: RuntimeControl):
    print("[MG1] Ожидание 1.png ...")
    while not should_stop(ctrl):
        frame = grab_roi(sct, ROI_GAME1)
        found, conf, _ = match_template(frame, template_1, threshold=TEMPLATE_MATCH_CONFIDENCE)
        if found:
            keyboard.press_and_release(MG1_ACTION_KEY)
            print(f"[MG1] Найдено (conf={conf:.2f}) -> нажата E")
            time.sleep(MG1_POST_SUCCESS_DELAY)
            return True
        time.sleep(CHECK_DELAY)
    return False


def mini_game_2(sct, template_bar, ctrl: RuntimeControl):
    print("[MG2] Ожидание Bar.png ...")

    for appear_check in range(1, MG2_MAX_APPEAR_CHECKS + 1):
        if should_stop(ctrl):
            return False

        frame = grab_roi(sct, ROI_GAME2)
        found, conf, _ = match_template(frame, template_bar, threshold=MG2_TEMPLATE_THRESHOLD)
        print(f"[MG2] check appear {appear_check}/{MG2_MAX_APPEAR_CHECKS}: found={found}, conf={conf:.3f}")
        if found:
            print("[MG2] Bar найден. Старт кликов.")
            break
        time.sleep(MG2_APPEAR_CHECK_DELAY)
    else:
        print("[MG2] Bar.png не найден в ROI -> возврат в MG1.")
        return False

    clicks_done = 0
    no_bar_checks = 0

    while not should_stop(ctrl):
        frame = grab_roi(sct, ROI_GAME2)
        found, conf, _ = match_template(frame, template_bar, threshold=MG2_TEMPLATE_THRESHOLD)
        print(f"[MG2] before click {clicks_done + 1}: found={found}, conf={conf:.3f}")

        if not found:
            no_bar_checks += 1
            if no_bar_checks >= MG2_REQUIRED_NO_BAR_CHECKS:
                print(f"[MG2] Bar исчез. Переход в MG3. Сделано {clicks_done} кликов.")
                return True
            time.sleep(MG2_NO_BAR_RECHECK_DELAY)
            continue

        no_bar_checks = 0
        click_lmb_without_move()
        clicks_done += 1
        print(f"[MG2] CLICK {clicks_done} (без движения мыши)")
        time.sleep(MG2_CLICK_INTERVAL)

    return False


def mini_game_3(sct, template_fonar, ctrl: RuntimeControl):
    print("[MG3] Ожидание появления fonar.png для активации HSV-обработки...")
    mg3_active = False

    while not should_stop(ctrl):
        fonar_frame = grab_roi(sct, ROI_FONAR)
        fonar_found, fonar_conf, _ = match_template(
            fonar_frame,
            template_fonar,
            threshold=TEMPLATE_MATCH_CONFIDENCE,
        )

        if not mg3_active:
            if fonar_found:
                mg3_active = True
                print(f"[MG3] fonar.png найден (conf={fonar_conf:.2f}) -> запуск HSV-обработки")
            else:
                time.sleep(MG3_WAIT_ACTIVATION_DELAY)
                continue
        elif not fonar_found:
            print(f"[MG3] fonar.png исчез (conf={fonar_conf:.2f}) -> остановка MG3")
            return True

        frame = grab_roi(sct, ROI_GAME3)
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)

        for ranges in COLOR_MASKS.values():
            mask_total = None
            for low, high in ranges:
                mask = cv2.inRange(hsv, low, high)
                mask_total = mask if mask_total is None else cv2.bitwise_or(mask_total, mask)

            kernel = np.ones(MG3_MORPH_KERNEL_SIZE, np.uint8)
            mask_total = cv2.morphologyEx(mask_total, cv2.MORPH_OPEN, kernel, iterations=MG3_MORPH_OPEN_ITERATIONS)
            mask_total = cv2.morphologyEx(mask_total, cv2.MORPH_DILATE, kernel, iterations=MG3_MORPH_DILATE_ITERATIONS)

            contours, _ = cv2.findContours(mask_total, CONTOUR_RETRIEVAL_MODE, CONTOUR_APPROX_MODE)
            for cnt in contours:
                area = cv2.contourArea(cnt)
                if area < MIN_CONTOUR_AREA:
                    continue

                x, y, w, h = cv2.boundingRect(cnt)
                cx = ROI_GAME3["left"] + x + w // 2
                cy = ROI_GAME3["top"] + y + h // 2
                click_screen(cx, cy)
                time.sleep(MG3_POST_TARGET_CLICK_DELAY)

        time.sleep(MG3_FRAME_DELAY)

    return False


def wait_fonar_disappear(sct, template_fonar, ctrl: RuntimeControl):
    print("[WAIT] Жду исчезновение fonar.png ...")
    while not should_stop(ctrl):
        full = grab_roi(sct, FULL_HD_MONITOR)
        found, _, _ = match_template(full, template_fonar, threshold=TEMPLATE_MATCH_CONFIDENCE)
        if not found:
            print("[WAIT] fonar.png исчез -> новый цикл")
            return True
        time.sleep(WAIT_RESET_CHECK_DELAY)

    return False


def run_main_cycle(ctrl: RuntimeControl):
    print("Загрузка шаблонов...")
    template_1 = load_template(TEMPLATE_1_BASE)
    template_bar = load_template(TEMPLATE_BAR_BASE)
    template_fonar = load_template(TEMPLATE_FONAR_BASE)

    state = BotState.MG1
    cycle_num = 1

    with mss.mss() as sct:
        while not should_stop(ctrl):
            print(f"[MAIN] Цикл #{cycle_num} | state={state.value}")

            if state == BotState.MG1:
                if not mini_game_1(sct, template_1, ctrl):
                    break
                state = BotState.MG2

            elif state == BotState.MG2:
                mg2_completed = mini_game_2(sct, template_bar, ctrl)
                if should_stop(ctrl):
                    break
                state = BotState.MG3 if mg2_completed else BotState.MG1

            elif state == BotState.MG3:
                if not mini_game_3(sct, template_fonar, ctrl):
                    break
                state = BotState.WAIT_RESET

            elif state == BotState.WAIT_RESET:
                if not wait_fonar_disappear(sct, template_fonar, ctrl):
                    break
                cycle_num += 1
                state = BotState.MG1


class App:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("KIRKA Bot")
        self.root.geometry("430x230")
        self.root.resizable(False, False)
        self.root.configure(bg="#101318")

        self.status_var = tk.StringVar(value="Состояние: ВЫКЛ")
        self.hint_var = tk.StringVar(value=f"Горячая клавиша запуска/остановки: {START_STOP_HOTKEY.upper()}")

        self.worker_thread = None
        self.ctrl = RuntimeControl(stop_event=threading.Event())

        self._build_ui()
        keyboard.add_hotkey(START_STOP_HOTKEY, self.toggle_bot)
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    def _build_ui(self):
        frame = ttk.Frame(self.root, padding=18)
        frame.pack(fill="both", expand=True)

        style = ttk.Style()
        style.theme_use("clam")
        style.configure("TFrame", background="#101318")
        style.configure("TLabel", background="#101318", foreground="#e8ecf2", font=("Segoe UI", 11))
        style.configure("Title.TLabel", font=("Segoe UI Semibold", 18), foreground="#ffffff")
        style.configure("StateOn.TLabel", foreground="#51d88a", font=("Segoe UI Semibold", 12))
        style.configure("StateOff.TLabel", foreground="#ff6b6b", font=("Segoe UI Semibold", 12))

        self.title = ttk.Label(frame, text="KIRKA Minimal Bot", style="Title.TLabel")
        self.title.pack(anchor="w", pady=(0, 18))

        self.status_label = ttk.Label(frame, textvariable=self.status_var, style="StateOff.TLabel")
        self.status_label.pack(anchor="w", pady=(0, 8))

        self.hint_label = ttk.Label(frame, textvariable=self.hint_var)
        self.hint_label.pack(anchor="w", pady=(0, 18))

        self.toggle_button = ttk.Button(frame, text="Включить", command=self.toggle_bot)
        self.toggle_button.pack(anchor="w")

        foot = ttk.Label(
            frame,
            text="Совет: положите шаблоны в папку templates рядом с .exe",
            foreground="#9aa4b2",
        )
        foot.pack(anchor="w", pady=(18, 0))

    def is_running(self):
        return self.worker_thread is not None and self.worker_thread.is_alive()

    def start_bot(self):
        if self.is_running():
            return

        self.ctrl.stop_event.clear()
        self.worker_thread = threading.Thread(target=self._worker, daemon=True)
        self.worker_thread.start()

        self.status_var.set("Состояние: ВКЛ")
        self.status_label.configure(style="StateOn.TLabel")
        self.toggle_button.configure(text="Выключить")

    def stop_bot(self):
        if not self.is_running():
            return

        self.ctrl.stop_event.set()
        self.status_var.set("Состояние: ВЫКЛ")
        self.status_label.configure(style="StateOff.TLabel")
        self.toggle_button.configure(text="Включить")

    def toggle_bot(self):
        if self.is_running():
            self.stop_bot()
        else:
            self.start_bot()

    def _worker(self):
        try:
            run_main_cycle(self.ctrl)
        except Exception as ex:
            print(f"[ERROR] {ex}")
        finally:
            self.root.after(0, self._set_stopped)

    def _set_stopped(self):
        self.ctrl.stop_event.set()
        self.status_var.set("Состояние: ВЫКЛ")
        self.status_label.configure(style="StateOff.TLabel")
        self.toggle_button.configure(text="Включить")

    def on_close(self):
        keyboard.clear_all_hotkeys()
        self.stop_bot()
        self.root.after(150, self.root.destroy)


def main():
    pyautogui.FAILSAFE = True
    root = tk.Tk()
    app = App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
