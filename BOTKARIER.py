import json
import os
import sys
import threading
import time
from enum import Enum
from pathlib import Path
import tkinter as tk

import cv2
import keyboard
import mss
import numpy as np
import pyautogui
import pydirectinput

# =========================
# Пути и конфиг
# =========================
if getattr(sys, "frozen", False):
    APP_DIR = Path(sys.executable).resolve().parent
else:
    APP_DIR = Path(__file__).resolve().parent

ASSETS_DIR = APP_DIR / "assets"
CONFIG_PATH = APP_DIR / "config.json"

# fallback, если каталог с exe недоступен для записи
USER_CONFIG_DIR = Path(os.getenv("APPDATA", Path.home())) / "KIRKA"
FALLBACK_CONFIG_PATH = USER_CONFIG_DIR / "config.json"

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

DEFAULT_CONFIG = {
    "hotkeys": {
        "start": "+",
        "stop": "-",
    }
}

MG1_ACTION_KEY = "e"
MOUSE_LEFT_BUTTON = "left"
TEMPLATE_MATCH_METHOD = cv2.TM_CCOEFF_NORMED
CONTOUR_RETRIEVAL_MODE = cv2.RETR_EXTERNAL
CONTOUR_APPROX_MODE = cv2.CHAIN_APPROX_SIMPLE

ROI_GAME1 = {"left": 13, "top": 11, "width": 413, "height": 79}
ROI_GAME2 = {"left": 1585, "top": 984, "width": 319, "height": 39}
ROI_GAME3 = {"left": 654, "top": 309, "width": 669, "height": 390}
ROI_FONAR = {"left": 1309, "top": 197, "width": 222, "height": 133}

TEMPLATE_1_PATH = ASSETS_DIR / "1.PNG"
TEMPLATE_BAR_PATH = ASSETS_DIR / "Bar.png"
TEMPLATE_FONAR_PATH = ASSETS_DIR / "fonar.png"
FULL_HD_MONITOR = {"left": 0, "top": 0, "width": 1920, "height": 1080}

COLOR_MASKS = {
    "red": [
        (np.array([3, 20, 36]), np.array([25, 255, 255])),
    ],
    "cyan": [
        (np.array([40, 0, 122]), np.array([98, 255, 255])),
    ],
    "yellow": [
        (np.array([8, 40, 50]), np.array([29, 255, 255])),
    ],
    "dark": [
        (np.array([0, 0, 10]), np.array([85, 150, 150])),
    ],
}

pyautogui.PAUSE = AUTO_GUI_INTERNAL_PAUSE
pydirectinput.PAUSE = AUTO_GUI_INTERNAL_PAUSE


def ensure_config(path: Path) -> dict:
    if not path.parent.exists():
        path.parent.mkdir(parents=True, exist_ok=True)

    if not path.exists():
        try:
            path.write_text(json.dumps(DEFAULT_CONFIG, indent=2, ensure_ascii=False), encoding="utf-8")
            return DEFAULT_CONFIG.copy()
        except OSError:
            FALLBACK_CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
            FALLBACK_CONFIG_PATH.write_text(json.dumps(DEFAULT_CONFIG, indent=2, ensure_ascii=False), encoding="utf-8")
            return DEFAULT_CONFIG.copy()

    try:
        with path.open("r", encoding="utf-8") as f:
            loaded = json.load(f)
    except (OSError, json.JSONDecodeError):
        loaded = DEFAULT_CONFIG.copy()

    hotkeys = loaded.get("hotkeys", {})
    if "start" not in hotkeys or "stop" not in hotkeys:
        loaded = DEFAULT_CONFIG.copy()
        try:
            path.write_text(json.dumps(loaded, indent=2, ensure_ascii=False), encoding="utf-8")
        except OSError:
            FALLBACK_CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
            FALLBACK_CONFIG_PATH.write_text(json.dumps(loaded, indent=2, ensure_ascii=False), encoding="utf-8")
    return loaded


def load_template(path: Path):
    tpl = cv2.imread(str(path), cv2.IMREAD_COLOR)
    if tpl is None:
        raise FileNotFoundError(f"Не удалось загрузить шаблон: {path}")
    return tpl


def grab_roi(sct, roi):
    shot = sct.grab(roi)
    img = np.array(shot)[:, :, :3]
    return img


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


def mini_game_1(sct, template_1, stop_event: threading.Event):
    print("[MG1] Ожидание 1.png ...")
    while not stop_event.is_set():
        frame = grab_roi(sct, ROI_GAME1)
        found, conf, _ = match_template(frame, template_1, threshold=TEMPLATE_MATCH_CONFIDENCE)
        if found:
            keyboard.press_and_release(MG1_ACTION_KEY)
            print(f"[MG1] Найдено (conf={conf:.2f}) -> нажата E")
            time.sleep(MG1_POST_SUCCESS_DELAY)
            return True
        time.sleep(CHECK_DELAY)
    return False


def mini_game_2(sct, template_bar, stop_event: threading.Event):
    print("[MG2] Ожидание Bar.png ...")
    threshold = MG2_TEMPLATE_THRESHOLD

    for appear_check in range(1, MG2_MAX_APPEAR_CHECKS + 1):
        if stop_event.is_set():
            return False
        frame = grab_roi(sct, ROI_GAME2)
        found, conf, _ = match_template(frame, template_bar, threshold=threshold)
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

    while not stop_event.is_set():
        frame = grab_roi(sct, ROI_GAME2)
        found, conf, _ = match_template(frame, template_bar, threshold=threshold)
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


def mini_game_3(sct, template_fonar, stop_event: threading.Event):
    print("[MG3] Ожидание появления fonar.png для активации HSV-обработки...")
    mg3_active = False

    while not stop_event.is_set():
        fonar_frame = grab_roi(sct, ROI_FONAR)
        fonar_found, fonar_conf, _ = match_template(fonar_frame, template_fonar, threshold=TEMPLATE_MATCH_CONFIDENCE)

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


def wait_fonar_disappear(sct, template_fonar, stop_event: threading.Event):
    print("[WAIT] Жду исчезновение fonar.png ...")
    while not stop_event.is_set():
        full = grab_roi(sct, FULL_HD_MONITOR)
        found, _, _ = match_template(full, template_fonar, threshold=TEMPLATE_MATCH_CONFIDENCE)
        if not found:
            print("[WAIT] fonar.png исчез -> новый цикл")
            return True
        time.sleep(WAIT_RESET_CHECK_DELAY)
    return False


class BotState(Enum):
    MG1 = "MG1"
    MG2 = "MG2"
    MG3 = "MG3"
    WAIT_RESET = "WAIT_RESET"


class BotController:
    def __init__(self):
        self.stop_event = threading.Event()
        self.thread = None
        self.running = False

    def is_running(self):
        return self.running and self.thread is not None and self.thread.is_alive()

    def start(self):
        if self.is_running():
            return
        self.stop_event.clear()
        self.thread = threading.Thread(target=self._worker, daemon=True)
        self.thread.start()
        self.running = True

    def stop(self):
        self.stop_event.set()
        self.running = False

    def _worker(self):
        try:
            print("Загрузка шаблонов...")
            template_1 = load_template(TEMPLATE_1_PATH)
            template_bar = load_template(TEMPLATE_BAR_PATH)
            template_fonar = load_template(TEMPLATE_FONAR_PATH)

            with mss.mss() as sct:
                self.run_main_cycle(sct, template_1, template_bar, template_fonar)
        except Exception as e:
            print(f"[ERROR] {e}")
        finally:
            self.running = False

    def run_main_cycle(self, sct, template_1, template_bar, template_fonar):
        state = BotState.MG1
        cycle_num = 1

        while not self.stop_event.is_set():
            print(f"[MAIN] Цикл #{cycle_num} | state={state.value}")

            if state == BotState.MG1:
                if not mini_game_1(sct, template_1, self.stop_event):
                    break
                state = BotState.MG2

            elif state == BotState.MG2:
                mg2_completed = mini_game_2(sct, template_bar, self.stop_event)
                if self.stop_event.is_set():
                    break
                state = BotState.MG3 if mg2_completed else BotState.MG1

            elif state == BotState.MG3:
                if not mini_game_3(sct, template_fonar, self.stop_event):
                    break
                state = BotState.WAIT_RESET

            elif state == BotState.WAIT_RESET:
                if not wait_fonar_disappear(sct, template_fonar, self.stop_event):
                    break
                cycle_num += 1
                state = BotState.MG1


class BotApp:
    def __init__(self, root: tk.Tk, controller: BotController, config: dict):
        self.root = root
        self.controller = controller
        self.config = config
        self.start_hotkey = self.config["hotkeys"]["start"]
        self.stop_hotkey = self.config["hotkeys"]["stop"]

        self.root.title("KIRKA Bot Launcher")
        self.root.geometry("320x180")
        self.root.resizable(False, False)

        self.status_var = tk.StringVar(value="Статус: остановлен")

        tk.Label(root, text="Управление ботом", font=("Arial", 14, "bold")).pack(pady=10)
        tk.Button(root, text="Старт", width=20, command=self.start_bot).pack(pady=5)
        tk.Button(root, text="Стоп", width=20, command=self.stop_bot).pack(pady=5)
        tk.Label(root, textvariable=self.status_var).pack(pady=8)
        tk.Label(root, text=f"Горячие клавиши: старт [{self.start_hotkey}] / стоп [{self.stop_hotkey}]").pack()

        self.hotkeys_registered = self._register_hotkeys()
        if not self.hotkeys_registered:
            self.root.bind("+", lambda _e: self.start_bot())
            self.root.bind("-", lambda _e: self.stop_bot())

        root.protocol("WM_DELETE_WINDOW", self.on_close)

    def _register_hotkeys(self):
        try:
            keyboard.add_hotkey(self.start_hotkey, self.start_bot)
            keyboard.add_hotkey(self.stop_hotkey, self.stop_bot)
            return True
        except Exception as e:
            print(f"[WARN] Не удалось зарегистрировать global hotkeys через keyboard: {e}")
            print("[WARN] Будут работать кнопки GUI и горячие клавиши окна (+/-).")
            return False

    def start_bot(self):
        if self.controller.is_running():
            return
        self.controller.start()
        self.status_var.set("Статус: запущен")

    def stop_bot(self):
        if not self.controller.is_running():
            self.status_var.set("Статус: остановлен")
            return
        self.controller.stop()
        self.status_var.set("Статус: остановка...")

    def on_close(self):
        self.controller.stop()
        if self.hotkeys_registered:
            keyboard.clear_all_hotkeys()
        self.root.destroy()


def main():
    pyautogui.FAILSAFE = True
    config = ensure_config(CONFIG_PATH)

    root = tk.Tk()
    controller = BotController()
    app = BotApp(root, controller, config)
    root.after(300, lambda: app.status_var.set("Статус: запущен" if controller.is_running() else "Статус: остановлен"))
    root.mainloop()


if __name__ == "__main__":
    main()
