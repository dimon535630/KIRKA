# KIRKA Launcher

Простой Windows-лаунчер с интерфейсом `Start/Stop`, горячими клавишами `+` и `-`, а также конфигом `JSON` для переназначения клавиш.

## Что делает проект

- Запускает и останавливает целевой процесс через GUI.
- Поддерживает горячие клавиши из `config/hotkeys.json`.
- Упаковывается в один `exe` (все Python-модули внутри) через **PyInstaller**.
- Изображения хранятся в отдельной папке `images/` рядом с `exe`.

## Локальный запуск (для разработки)

```bash
python3 main.py
```

## Конфиг горячих клавиш

Файл: `config/hotkeys.json`

```json
{
  "start_key": "+",
  "stop_key": "-"
}
```

Допустимы значения формата `+`, `-`, `F5`, `space`, `Return` и т.п. (Tkinter keysyms).

## Сборка в exe локально

```bash
python3 -m pip install -r requirements.txt
python3 -m PyInstaller --noconfirm --onefile --windowed --name KIRKA-Launcher main.py
```

После сборки:
- `dist/KIRKA-Launcher.exe` — готовый exe
- `images/` — держите рядом с exe как отдельную папку
- `config/hotkeys.json` — можно положить рядом с exe в `config/`

## GitHub Actions упаковка

Workflow `.github/workflows/build-windows-exe.yml` автоматически собирает Windows-артефакт:
- `KIRKA-Launcher.exe`
- `images/`
- `config/hotkeys.json`

Подходит для пользователей **без установленного Python**.
