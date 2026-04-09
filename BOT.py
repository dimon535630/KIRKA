import time
import cv2
import numpy as np
import mss
import pyautogui
import pydirectinput
import keyboard
from enum import Enum

# отключаем встроенную паузу, чтобы клики были точнее по времени
pyautogui.PAUSE = 0
pydirectinput.PAUSE = 0

# =========================
# Настройки
# =========================
CONFIDENCE = 0.80
CHECK_DELAY = 0.03

# ROI (для экрана 1920x1080)
ROI_GAME1 = {"left": 13,   "top": 11,  "width": 413, "height": 79}
ROI_GAME2 = {"left": 1585, "top": 984, "width": 319, "height": 39}
ROI_GAME3 = {"left": 654,  "top": 309, "width": 669, "height": 390}
ROI_FONAR = {"left": 1309, "top": 197, "width": 222, "height": 133}

# Шаблоны
TEMPLATE_1_PATH = "1.png"
TEMPLATE_BAR_PATH = "Bar.png"
TEMPLATE_FONAR_PATH = "fonar.png"
FULL_HD_MONITOR = {"left": 0, "top": 0, "width": 1920, "height": 1080}

# HSV-маски
COLOR_MASKS = {
    "red": [
        (np.array([4, 20, 36]), np.array([25, 255, 255])),
    ],
    "cyan": [
        (np.array([40, 0, 122]), np.array([98, 255, 255])),
    ],
    "yellow": [
        (np.array([8, 19, 50]), np.array([103, 255, 255])),
    ],
    "dark": [
        (np.array([0, 0, 10]),  np.array([85, 150, 150])),
    ],
}

# Фильтр по площади (убрать шум)
MIN_CONTOUR_AREA = 40


# =========================
# Вспомогательные функции
# =========================
def load_template(path: str):
    tpl = cv2.imread(path, cv2.IMREAD_COLOR)
    if tpl is None:
        raise FileNotFoundError(f"Не удалось загрузить шаблон: {path}")
    return tpl


def grab_roi(sct, roi):
    """Скрин ROI -> BGR numpy image"""
    shot = sct.grab(roi)
    img = np.array(shot)[:, :, :3]  # BGRA -> BGR
    return img


def match_template(region_bgr, template_bgr, threshold=CONFIDENCE):
    """Возвращает (found, max_val, max_loc)."""
    if region_bgr.shape[0] < template_bgr.shape[0] or region_bgr.shape[1] < template_bgr.shape[1]:
        return False, 0.0, (0, 0)

    res = cv2.matchTemplate(region_bgr, template_bgr, cv2.TM_CCOEFF_NORMED)
    _, max_val, _, max_loc = cv2.minMaxLoc(res)
    return max_val >= threshold, max_val, max_loc


def click_screen(_x=None, _y=None):
    # Если переданы координаты — наводим мышь в точку клика
    if _x is not None and _y is not None:
        pydirectinput.click(int(_x), int(_y))

    # Кликаем ЛКМ
    pydirectinput.click(button='left')
    time.sleep(0.03)


def click_lmb_without_move():
    """
    Отдельный клик ЛКМ без перемещения курсора.
    Нужен для MG2, где камера может резко поворачиваться,
    и лишнее движение мыши ломает механику.
    """
    pydirectinput.mouseDown(button='left')
    time.sleep(0.1)
    pydirectinput.mouseUp(button='left')


# =========================
# 1 мини-игра
# =========================
def mini_game_1(sct, template_1):
    """
    В ROI_GAME1 ждём появление 1.png.
    Когда найдено -> нажимаем E один раз.
    """
    print("[MG1] Ожидание 1.png ...")
    while True:
        frame = grab_roi(sct, ROI_GAME1)
        found, conf, _ = match_template(frame, template_1, threshold=CONFIDENCE)
        if found:
            keyboard.press_and_release("e")
            print(f"[MG1] Найдено (conf={conf:.2f}) -> нажата E")
            time.sleep(0.15)
            return
        time.sleep(CHECK_DELAY)


# =========================
# 2 мини-игра
# =========================
def mini_game_2(sct, template_bar):
    print("[MG2] Ожидание Bar.png ...")
    # Порог чуть ниже для стабильности
    threshold = 0.72

    # ждём появление
    while True:
        frame = grab_roi(sct, ROI_GAME2)
        found, conf, _ = match_template(frame, template_bar, threshold=threshold)
        print(f"[MG2] check appear: found={found}, conf={conf:.3f}")
        if found:
            print("[MG2] Bar найден. Старт кликов.")
            break
        time.sleep(0.05)

    interval = 1
    clicks_done = 0
    no_bar_checks = 0
    required_no_bar_checks = 3

    while True:
        frame = grab_roi(sct, ROI_GAME2)
        found, conf, _ = match_template(frame, template_bar, threshold=threshold)
        print(f"[MG2] before click {clicks_done + 1}: found={found}, conf={conf:.3f}")

        if not found:
            no_bar_checks += 1
            if no_bar_checks >= required_no_bar_checks:
                print(f"[MG2] Bar исчез. Переход в MG3. Сделано {clicks_done} кликов.")
                return
            time.sleep(0.03)
            continue

        no_bar_checks = 0
        click_lmb_without_move()
        clicks_done += 1
        print(f"[MG2] CLICK {clicks_done} (без движения мыши)")

        time.sleep(interval)


# =========================
# 3 мини-игра
# =========================
def mini_game_3(sct, template_fonar):
    """
    MG3 активируется только когда найден fonar.png в ROI_FONAR.
    Пока fonar.png не найден — HSV-обработка не выполняется.
    Как только fonar.png пропадает — MG3 сразу завершается.
    """
    print("[MG3] Ожидание появления fonar.png для активации HSV-обработки...")
    mg3_active = False

    while True:
        # Покадровая проверка состояния fonar.png
        fonar_frame = grab_roi(sct, ROI_FONAR)
        fonar_found, fonar_conf, _ = match_template(fonar_frame, template_fonar, threshold=CONFIDENCE)

        if not mg3_active:
            if fonar_found:
                mg3_active = True
                print(f"[MG3] fonar.png найден (conf={fonar_conf:.2f}) -> запуск HSV-обработки")
            else:
                time.sleep(0.02)
                continue
        elif not fonar_found:
            print(f"[MG3] fonar.png исчез (conf={fonar_conf:.2f}) -> остановка MG3")
            return

        frame = grab_roi(sct, ROI_GAME3)
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)

        for color_name, ranges in COLOR_MASKS.items():
            mask_total = None
            for low, high in ranges:
                mask = cv2.inRange(hsv, low, high)
                mask_total = mask if mask_total is None else cv2.bitwise_or(mask_total, mask)

            # немного морфологии против шумов
            kernel = np.ones((3, 3), np.uint8)
            mask_total = cv2.morphologyEx(mask_total, cv2.MORPH_OPEN, kernel, iterations=1)
            mask_total = cv2.morphologyEx(mask_total, cv2.MORPH_DILATE, kernel, iterations=1)

            contours, _ = cv2.findContours(mask_total, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            for cnt in contours:
                area = cv2.contourArea(cnt)
                if area < MIN_CONTOUR_AREA:
                    continue

                x, y, w, h = cv2.boundingRect(cnt)
                cx = ROI_GAME3["left"] + x + w // 2
                cy = ROI_GAME3["top"] + y + h // 2
                click_screen(cx, cy)
                # небольшая задержка между кликами
                time.sleep(0.01)

        time.sleep(0.01)


def wait_fonar_disappear(sct, template_fonar):
    """
    После 3 мини-игры ждём исчезновение fonar.png.
    Только после этого стартуем снова с MG1.
    """
    print("[WAIT] Жду исчезновение fonar.png ...")
    while True:
        # Можно проверять на всём экране 1920x1080
        full = grab_roi(sct, FULL_HD_MONITOR)
        found, conf, _ = match_template(full, template_fonar, threshold=CONFIDENCE)
        if not found:
            print("[WAIT] fonar.png исчез -> новый цикл")
            return
        time.sleep(0.08)


class BotState(Enum):
    MG1 = "MG1"
    MG2 = "MG2"
    MG3 = "MG3"
    WAIT_RESET = "WAIT_RESET"


def run_main_cycle(sct, template_1, template_bar, template_fonar):
    """
    Основной управляющий цикл:
      MG1 -> MG2 -> MG3 -> WAIT_RESET -> MG1 ...
    Выход:
      - Ctrl+C в консоли
      - клавиша F8 во время работы
    """
    state = BotState.MG1
    cycle_num = 1

    while True:
        if keyboard.is_pressed("f8"):
            print("[MAIN] Нажата F8 -> остановка бота.")
            return

        print(f"[MAIN] Цикл #{cycle_num} | state={state.value}")

        if state == BotState.MG1:
            mini_game_1(sct, template_1)
            state = BotState.MG2

        elif state == BotState.MG2:
            mini_game_2(sct, template_bar)
            state = BotState.MG3

        elif state == BotState.MG3:
            mini_game_3(sct, template_fonar)
            state = BotState.WAIT_RESET

        elif state == BotState.WAIT_RESET:
            wait_fonar_disappear(sct, template_fonar)
            cycle_num += 1
            state = BotState.MG1


def main():
    print("Загрузка шаблонов...")
    template_1 = load_template(TEMPLATE_1_PATH)
    template_bar = load_template(TEMPLATE_BAR_PATH)
    template_fonar = load_template(TEMPLATE_FONAR_PATH)

    print("Старт. Для выхода нажми Ctrl+C")
    with mss.mss() as sct:
        run_main_cycle(sct, template_1, template_bar, template_fonar)


if __name__ == "__main__":
    pyautogui.FAILSAFE = True  # увести мышь в верхний левый угол для аварийной остановки
    try:
        main()
    except KeyboardInterrupt:
        print("\n[MAIN] Остановлено пользователем (Ctrl+C).")