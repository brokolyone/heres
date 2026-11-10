# Отряд на мосту — Android

Мобильный 3D-раннер: ведёшь стреляющий отряд по мосту, проходишь ворота (+N, ×2, −N),
расстреливаешь врагов и баррикады, в конце бьёшь босса. Между уровнями — магазин улучшений.

**Готовый APK:** `otryad-na-mostu.apk` (Android 7.0+). Скачай на телефон и установи
(разреши установку из неизвестных источников).

## Структура
- `models/` — 3D-модели (GLB) и Blender-скрипты, которые их строят (`models/src/*.py`, нужен `pip install bpy`).
  Контракт для моделей — `models/CONTRACT.md`, превью — `models/previews/`.
- `web/` — игра на three.js. `npm install && npm run build` собирает один файл `web/dist/index.html`
  со встроенными моделями и шрифтом.
- `android/` — оболочка-WebView. `./build.sh` собирает и подписывает APK без Gradle
  (нужны Android SDK build-tools 35 и platform 34, путь в `ANDROID_HOME`, по умолчанию `/opt/android`).
