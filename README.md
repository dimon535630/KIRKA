# KIRKA Minimal Bot

Минималистичное приложение с GUI, состоянием **ВКЛ/ВЫКЛ**, горячей клавишей **F5** (старт/стоп) и сборкой в `.exe` для запуска на ПК без Python.

## Что внутри
- `BOT.py` — основной код (логика + интерфейс).
- `templates/` — папка под ваши шаблоны изображений (бинарники в репозитории не хранятся).
- `build_exe.bat` — локальная сборка в `dist/KirkaBot.exe`.
- `.github/workflows/build-exe.yml` — автоматическая сборка `.exe` через GitHub Actions.
- `requirements.txt` — зависимости.

## Подготовка шаблонов
Перед запуском положите в `templates/` файлы:
- `1.PNG` (или `1.png`)
- `Bar.png` (или `Bar.PNG`)
- `fonar.PNG` (или `fonar.png`)

## Запуск в режиме Python
```bash
pip install -r requirements.txt
python BOT.py
```

## Сборка EXE локально (Windows)
1. Запусти `build_exe.bat`.
2. После сборки возьми файл `dist/KirkaBot.exe`.

## Сборка EXE через GitHub
1. Запушь проект в GitHub.
2. Открой вкладку **Actions**.
3. Выбери workflow **Build Windows EXE**.
4. Нажми **Run workflow**.
5. Дождись успешного билда и скачай артефакт **KirkaBot-Windows**.

В артефакте будет:
```text
release/
  KirkaBot.exe
  templates/
```

## Что отправлять другому человеку
Чтобы приложение работало у человека без Python:
1. Отправь `KirkaBot.exe`.
2. Рядом с `.exe` положи папку `templates` с нужными шаблонами.

## Управление
- Кнопка в интерфейсе: включить/выключить.
- Горячая клавиша: `F5` (переключает старт/стоп).
- `PyAutoGUI FAILSAFE` включён (уведи курсор в верхний левый угол для аварийной остановки).
