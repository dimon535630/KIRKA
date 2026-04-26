# KIRKA Bot

Бот с GUI (кнопки **Старт/Стоп**) и горячими клавишами из `config.json`.
Если глобальные hotkeys недоступны в системе, остаются рабочими кнопки GUI и `+ / -` в активном окне приложения.

## Быстрый старт (локально)

1. Установить зависимости:
   ```bash
   pip install -r requirements.txt
   ```
2. Запустить:
   ```bash
   python BOTKARIER.py
   ```

## Конфиг горячих клавиш

Файл `config.json`:

```json
{
  "hotkeys": {
    "start": "+",
    "stop": "-"
  },
  "cursor_movement": {
    "min_duration": 0.12,
    "max_duration": 0.28,
    "jitter_pixels": 3
  }
}
```

- `min_duration` / `max_duration` — диапазон времени (сек) плавного движения курсора.
- `jitter_pixels` — небольшой случайный сдвиг точки клика для более живого движения.

## Структура

- `BOTKARIER.py` — основная логика бота + GUI.
- `assets/` — шаблоны изображений для CV.
- `.github/workflows/build-exe.yml` — сборка `.exe` в GitHub Actions.

## Сборка `.exe` через GitHub Actions

1. Запушить репозиторий в GitHub.
2. Открыть вкладку **Actions**.
3. Запустить workflow **Build Windows EXE**.
4. Скачать артефакт `KIRKA-Bot-exe`.

Внутри артефакта будет `BOTKARIER.exe` + папка `assets` + `config.json`.
`assets` и `config.json` должны лежать рядом с `.exe`.
