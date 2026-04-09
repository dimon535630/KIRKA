import time
import cv2
import numpy as np
import mss
import pyautogui
import pydirectinput
import keyboard
from enum import Enum

# =========================
# Глобальные константы
# =========================
# Базовый порог совпадения шаблонов (0.0..1.0) для большинства проверок.
TEMPLATE_MATCH_CONFIDENCE = 0.80
# Частота опроса в циклах ожидания (сек), чтобы не перегружать CPU.
CHECK_DELAY = 0.03

# Отключаем внутренние паузы библиотек автоклика для максимальной точности.
AUTO_GUI_INTERNAL_PAUSE = 0

# Задержка после обычного клика ЛКМ (сек), чтобы не спамить кликами.
POST_CLICK_DELAY = 0.03
# Длительность удержания ЛКМ в MG2 (сек) для "чистого" клика без движения.
LMB_HOLD_DURATION = 0.1
# Задержка после срабатывания MG1 (нажатие E), чтобы дать интерфейсу обновиться.
MG1_POST_SUCCESS_DELAY = 0.15

# Специальный порог совпадения для Bar.png в MG2 (чуть мягче, чем базовый).
MG2_TEMPLATE_THRESHOLD = 0.72
# Частота опроса появления Bar.png до начала кликов (сек).
MG2_APPEAR_CHECK_DELAY = 0.05
# Максимум проверок появления Bar.png перед возвратом в MG1.
MG2_MAX_APPEAR_CHECKS = 20
# Интервал между кликами в MG2 (сек).
MG2_CLICK_INTERVAL = 1
# Сколько подряд проверок без Bar.png нужно, чтобы завершить MG2.
MG2_REQUIRED_NO_BAR_CHECKS = 3
# Задержка между "пустыми" проверками без Bar.png (сек).
MG2_NO_BAR_RECHECK_DELAY = 0.03

# Пауза перед повторной проверкой fonar.png, пока MG3 ещё не активирована (сек).
MG3_WAIT_ACTIVATION_DELAY = 0.02
# Размер ядра морфологии в MG3 для подавления шумов маски.
MG3_MORPH_KERNEL_SIZE = (3, 3)
# Количество итераций морфологического открытия.
MG3_MORPH_OPEN_ITERATIONS = 1
# Количество итераций морфологического закрытия (закрывает разрывы в цели).
MG3_MORPH_CLOSE_ITERATIONS = 1
# Количество итераций дилатации после открытия.
MG3_MORPH_DILATE_ITERATIONS = 1
# Яркость "активных" пикселей в итоговой маске (серый вместо белого).
MG3_MASK_ACTIVE_GRAY_VALUE = 170

# Исключение серого фона: низкая насыщенность и средняя яркость.
MG3_GRAY_EXCLUDE_LOW = np.array([0, 0, 25])
MG3_GRAY_EXCLUDE_HIGH = np.array([180, 45, 210])
# Минимальная площадь контура (px), ниже считаем шумом.
MIN_CONTOUR_AREA = 40
# Пауза после клика по найденному контуру в MG3 (сек).
MG3_POST_TARGET_CLICK_DELAY = 0.01
# Пауза между кадрами обработки MG3 (сек).
MG3_FRAME_DELAY = 0.01

# Частота проверки исчезновения fonar.png в WAIT_RESET (сек).
WAIT_RESET_CHECK_DELAY = 0.08

# Горячая клавиша ручной остановки бота.
STOP_HOTKEY = "f8"
# Клавиша действия для MG1.
MG1_ACTION_KEY = "e"
# Кнопка мыши для обычного клика.
MOUSE_LEFT_BUTTON = "left"
# Режим сопоставления шаблонов OpenCV.
TEMPLATE_MATCH_METHOD = cv2.TM_CCOEFF_NORMED
# Режимы поиска контуров OpenCV.
CONTOUR_RETRIEVAL_MODE = cv2.RETR_EXTERNAL
CONTOUR_APPROX_MODE = cv2.CHAIN_APPROX_SIMPLE

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
    # Белые цели: почти без цвета и высокая яркость.
    "white": [
        (np.array([0, 0, 215]), np.array([180, 40, 255])),
    ],
    "red": [
        (np.array([4, 20, 36]), np.array([25, 255, 255])),
    ],
    "cyan": [
        (np.array([40, 0, 122]), np.array([98, 255, 255])),
    ],
    "yellow": [
        (np.array([8, 19, 50]), np.array([103, 255, 255])),
    ],
}

# отключаем встроенную паузу, чтобы клики были точнее по времени
pyautogui.PAUSE = AUTO_GUI_INTERNAL_PAUSE
pydirectinput.PAUSE = AUTO_GUI_INTERNAL_PAUSE


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


def match_template(region_bgr, template_bgr, threshold=TEMPLATE_MATCH_CONFIDENCE):
    """Возвращает (found, max_val, max_loc)."""
    if region_bgr.shape[0] < template_bgr.shape[0] or region_bgr.shape[1] < template_bgr.shape[1]:
        return False, 0.0, (0, 0)

    res = cv2.matchTemplate(region_bgr, template_bgr, TEMPLATE_MATCH_METHOD)
    _, max_val, _, max_loc = cv2.minMaxLoc(res)
    return max_val >= threshold, max_val, max_loc


def click_screen(_x=None, _y=None):
    # Если переданы координаты — наводим мышь в точку клика
    if _x is not None and _y is not None:
        pydirectinput.click(int(_x), int(_y))

    # Кликаем ЛКМ
    pydirectinput.click(button=MOUSE_LEFT_BUTTON)
    time.sleep(POST_CLICK_DELAY)


def click_lmb_without_move():
    """
    Отдельный клик ЛКМ без перемещения курсора.
    Нужен для MG2, где камера может резко поворачиваться,
    и лишнее движение мыши ломает механику.
    """
    pydirectinput.mouseDown(button=MOUSE_LEFT_BUTTON)
    time.sleep(LMB_HOLD_DURATION)
    pydirectinput.mouseUp(button=MOUSE_LEFT_BUTTON)


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
        found, conf, _ = match_template(frame, template_1, threshold=TEMPLATE_MATCH_CONFIDENCE)
        if found:
            keyboard.press_and_release(MG1_ACTION_KEY)
            print(f"[MG1] Найдено (conf={conf:.2f}) -> нажата E")
            time.sleep(MG1_POST_SUCCESS_DELAY)
            return
        time.sleep(CHECK_DELAY)


# =========================
# 2 мини-игра
# =========================
def mini_game_2(sct, template_bar):
    print("[MG2] Ожидание Bar.png ...")
    # Порог чуть ниже для стабильности
    threshold = MG2_TEMPLATE_THRESHOLD

    # ждём появление
    for appear_check in range(1, MG2_MAX_APPEAR_CHECKS + 1):
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

    interval = MG2_CLICK_INTERVAL
    clicks_done = 0
    no_bar_checks = 0
    required_no_bar_checks = MG2_REQUIRED_NO_BAR_CHECKS

    while True:
        frame = grab_roi(sct, ROI_GAME2)
        found, conf, _ = match_template(frame, template_bar, threshold=threshold)
        print(f"[MG2] before click {clicks_done + 1}: found={found}, conf={conf:.3f}")

        if not found:
            no_bar_checks += 1
            if no_bar_checks >= required_no_bar_checks:
                print(f"[MG2] Bar исчез. Переход в MG3. Сделано {clicks_done} кликов.")
                return True
            time.sleep(MG2_NO_BAR_RECHECK_DELAY)
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
            return

        frame = grab_roi(sct, ROI_GAME3)
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)

        for color_name, ranges in COLOR_MASKS.items():
            mask_total = None
            for low, high in ranges:
                mask = cv2.inRange(hsv, low, high)
                mask_total = mask if mask_total is None else cv2.bitwise_or(mask_total, mask)

            # немного морфологии против шумов
            kernel = np.ones(MG3_MORPH_KERNEL_SIZE, np.uint8)
            mask_total = cv2.morphologyEx(mask_total, cv2.MORPH_OPEN, kernel, iterations=MG3_MORPH_OPEN_ITERATIONS)
            mask_total = cv2.morphologyEx(mask_total, cv2.MORPH_CLOSE, kernel, iterations=MG3_MORPH_CLOSE_ITERATIONS)
            mask_total = cv2.morphologyEx(mask_total, cv2.MORPH_DILATE, kernel, iterations=MG3_MORPH_DILATE_ITERATIONS)

            # Убираем серые области (камень/фон), чтобы не было ложных срабатываний.
            gray_mask = cv2.inRange(hsv, MG3_GRAY_EXCLUDE_LOW, MG3_GRAY_EXCLUDE_HIGH)
            mask_total = cv2.bitwise_and(mask_total, cv2.bitwise_not(gray_mask))

            # Делаем активную область серой (не белой) — при этом для контуров это всё ещё "не ноль".
            mask_total = np.where(mask_total > 0, MG3_MASK_ACTIVE_GRAY_VALUE, 0).astype(np.uint8)

            contours, _ = cv2.findContours(mask_total, CONTOUR_RETRIEVAL_MODE, CONTOUR_APPROX_MODE)
            for cnt in contours:
                area = cv2.contourArea(cnt)
                if area < MIN_CONTOUR_AREA:
                    continue

                x, y, w, h = cv2.boundingRect(cnt)
                cx = ROI_GAME3["left"] + x + w // 2
                cy = ROI_GAME3["top"] + y + h // 2
                click_screen(cx, cy)
                # небольшая задержка между кликами
                time.sleep(MG3_POST_TARGET_CLICK_DELAY)

        time.sleep(MG3_FRAME_DELAY)


def wait_fonar_disappear(sct, template_fonar):
    """
    После 3 мини-игры ждём исчезновение fonar.png.
    Только после этого стартуем снова с MG1.
    """
    print("[WAIT] Жду исчезновение fonar.png ...")
    while True:
        # Можно проверять на всём экране 1920x1080
        full = grab_roi(sct, FULL_HD_MONITOR)
        found, conf, _ = match_template(full, template_fonar, threshold=TEMPLATE_MATCH_CONFIDENCE)
        if not found:
            print("[WAIT] fonar.png исчез -> новый цикл")
            return
        time.sleep(WAIT_RESET_CHECK_DELAY)


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
        if keyboard.is_pressed(STOP_HOTKEY):
            print("[MAIN] Нажата F8 -> остановка бота.")
            return

        print(f"[MAIN] Цикл #{cycle_num} | state={state.value}")

        if state == BotState.MG1:
            mini_game_1(sct, template_1)
            state = BotState.MG2

        elif state == BotState.MG2:
            mg2_completed = mini_game_2(sct, template_bar)
            state = BotState.MG3 if mg2_completed else BotState.MG1

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
