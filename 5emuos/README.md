# 5emuos

Экспериментальный эмулятор PS5, написанный с нуля. Финальная цель — GTA 5 🏁

## Как это работает

PS5 построена на AMD Zen 2, то есть на обычном x86-64. Поэтому код игры **не эмулируется**,
а выполняется прямо на процессоре ПК. Эмулятор делает остальное:

1. **Загрузчик** (`src/loader`) читает расшифрованный ELF (eboot.bin) с SCE-расширениями Sony.
2. **Линкер** (`src/core/linker.cpp`) размещает сегменты в памяти, применяет релокации
   и связывает импорты. Игры импортируют системные функции не по имени, а по **NID**:
   это 8 байт SHA-1 от имени с солью в base64 (`printf` → `hcuQgD53UxM`).
3. **HLE** (`src/hle`) — наши реализации системных библиотек (libc, libkernel, ...).
   Всё, что ещё не реализовано, заменяется заглушкой, которая пишет в лог
   `Unimplemented: <функция>` и возвращает 0. Лог — это наш список задач.

## Сборка (Windows)

Нужен **Clang**: MSVC не умеет `sysv_abi`, а без него не вызвать код PS5.

1. Visual Studio 2022 с компонентами «Desktop development with C++» и
   **«C++ Clang Compiler for Windows»** (или LLVM с llvm.org) и CMake.
2. В «x64 Native Tools Command Prompt»:
   ```
   cd 5emuos
   cmake -S . -B build -G Ninja -DCMAKE_C_COMPILER=clang-cl -DCMAKE_CXX_COMPILER=clang-cl
   cmake --build build
   ```
   Или через генератор Visual Studio: `cmake -S . -B build -T ClangCL`.

## Сборка и тесты (Linux)

```
cmake -S . -B build -G Ninja -DCMAKE_C_COMPILER=clang -DCMAKE_CXX_COMPILER=clang++
cmake --build build && cd build && ctest --output-on-failure
```
Тест `run_hello_guest` собирает крошечную «игру» (`tests/hello_guest.c`) с импортами по NID
и запускает её в эмуляторе.

## Запуск

```
5emuos [--info] [--debug] [--names names.txt] eboot.elf
```
- `--info` — только показать структуру ELF и импорты, не запускать.
- `--names` — список имён функций (по одному на строку). Тогда в логах вместо
  непонятных NID будут нормальные имена.

## Легальность

В репозиторий **никогда** не кладём ключи, прошивки или игры. Дампы делаешь только
со своей консоли и своих копий. Зашифрованные SELF эмулятор распознаёт и отказывается грузить.

## Дорожная карта

- [x] Этап 1: загрузчик ELF, NID, релокации, HLE-реестр, заглушки, запуск кода
- [ ] Этап 2: hello world от настоящего PS5 homebrew (TLS через `fs`, свой стек и поток, procparam)
- [ ] Этап 3: VideoOut — вывод фреймбуфера в окно
- [ ] Этап 4: Pad и AudioOut
- [ ] Этап 5: AGC и компилятор шейдеров RDNA2 → SPIR-V, первый треугольник (Vulkan)
- [ ] Этап 6: загрузка системных .prx модулей, файловая система, потоки, синхронизация
- [ ] ...
- [ ] GTA 5 показывает логотип Rockstar
