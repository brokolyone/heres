// ArtGraf — raster graphics editor. Entry point: window, GL context, ImGui, main loop.
#include <cmath>
#include <filesystem>
#include <functional>
#include <memory>
#include <string>

#include <SDL.h>
#include "gl.h"
#include <imgui.h>
#include <imgui_impl_opengl3.h>
#include <imgui_impl_sdl2.h>

#include "editor.h"

int main(int argc, char** argv) {
    SDL_SetHint(SDL_HINT_WINDOWS_DPI_AWARENESS, "permonitorv2");
    SDL_SetHint(SDL_HINT_IME_SHOW_UI, "1");
    SDL_SetHint(SDL_HINT_MOUSE_FOCUS_CLICKTHROUGH, "1");
    if (SDL_Init(SDL_INIT_VIDEO | SDL_INIT_TIMER) != 0) {
        SDL_ShowSimpleMessageBox(SDL_MESSAGEBOX_ERROR, "ArtGraf", SDL_GetError(), nullptr);
        return 1;
    }
    SDL_GL_SetAttribute(SDL_GL_CONTEXT_MAJOR_VERSION, 3);
    SDL_GL_SetAttribute(SDL_GL_CONTEXT_MINOR_VERSION, 0);  // OpenGL 3.0 on desktop, OpenGL ES 3.0 on Android
    SDL_GL_SetAttribute(SDL_GL_DOUBLEBUFFER, 1);
    SDL_GL_SetAttribute(SDL_GL_DEPTH_SIZE, 0);
    SDL_GL_SetAttribute(SDL_GL_STENCIL_SIZE, 8);

    float scale = 1.f;
    float ddpi = 0;
#ifdef __ANDROID__
    // Phones report ~400 dpi; aim for a UI a bit denser than Android's own 160-dpi "dp" unit.
    if (SDL_GetDisplayDPI(0, &ddpi, nullptr, nullptr) == 0 && ddpi > 0) scale = std::clamp(ddpi / 160.f * 0.85f, 1.f, 3.5f);
    SDL_SetHint(SDL_HINT_ORIENTATIONS, "LandscapeLeft LandscapeRight");
#else
    if (SDL_GetDisplayDPI(0, &ddpi, nullptr, nullptr) == 0 && ddpi > 0) scale = std::clamp(ddpi / 96.f, 1.f, 3.f);
#endif

    // The window starts as a borderless splash screen and turns into the main window once loaded.
    const int splashW = int(960 * scale), splashH = int(560 * scale);
#ifdef __ANDROID__
    SDL_GL_SetAttribute(SDL_GL_CONTEXT_PROFILE_MASK, SDL_GL_CONTEXT_PROFILE_ES);
    SDL_Window* window = SDL_CreateWindow("ArtGraf", 0, 0, 0, 0, SDL_WINDOW_OPENGL | SDL_WINDOW_FULLSCREEN | SDL_WINDOW_ALLOW_HIGHDPI);
    (void)splashW;
    (void)splashH;
#else
    SDL_Window* window = SDL_CreateWindow("ArtGraf", SDL_WINDOWPOS_CENTERED, SDL_WINDOWPOS_CENTERED, splashW, splashH,
                                          SDL_WINDOW_OPENGL | SDL_WINDOW_BORDERLESS | SDL_WINDOW_ALLOW_HIGHDPI);
#endif
    if (!window) {
        SDL_ShowSimpleMessageBox(SDL_MESSAGEBOX_ERROR, "ArtGraf", SDL_GetError(), nullptr);
        return 1;
    }
    SDL_GLContext gl = SDL_GL_CreateContext(window);
    if (!gl) {
        std::string msg = std::string("Нужен OpenGL 3.0 или новее.\n\n") + SDL_GetError();
        SDL_ShowSimpleMessageBox(SDL_MESSAGEBOX_ERROR, "ArtGraf", msg.c_str(), window);
        return 1;
    }
    SDL_GL_MakeCurrent(window, gl);
    SDL_GL_SetSwapInterval(1);

    IMGUI_CHECKVERSION();
    ImGui::CreateContext();
    ImGuiIO& io = ImGui::GetIO();
    io.ConfigFlags |= ImGuiConfigFlags_DockingEnable;
    io.ConfigWindowsMoveFromTitleBarOnly = true;

    // Panel layout lives in the user's app-data folder.
    static std::string iniPath;
    std::string prefDir;
    if (char* pref = SDL_GetPrefPath("ArtGraf", "ArtGraf")) {
        prefDir = pref;
        SDL_free(pref);
    }
    iniPath = prefDir + "layout2.ini";
    io.IniFilename = iniPath.c_str();

    auto editorPtr = std::make_unique<ag::Editor>(window);
    ag::Editor& editor = *editorPtr;
    {
        std::error_code ec;
        editor.layoutReset = !std::filesystem::exists(std::filesystem::u8path(iniPath), ec);
    }
    editor.iniPath = iniPath;
    editor.prefDir = prefDir;
    editor.loadFonts(scale);
    editor.setupStyle(scale);

    ImGui_ImplSDL2_InitForOpenGL(window, gl);
#ifdef __ANDROID__
    ImGui_ImplOpenGL3_Init("#version 300 es");
#else
    ImGui_ImplOpenGL3_Init("#version 130");
#endif
    editor.loadAssets();

    auto renderFrame = [&](const std::function<void()>& ui) {
        ImGui_ImplOpenGL3_NewFrame();
        ImGui_ImplSDL2_NewFrame();
        ImGui::NewFrame();
        ui();
        ImGui::Render();
        glViewport(0, 0, int(io.DisplaySize.x * io.DisplayFramebufferScale.x), int(io.DisplaySize.y * io.DisplayFramebufferScale.y));
        glClearColor(0.043f, 0.047f, 0.055f, 1.f);
        glClear(GL_COLOR_BUFFER_BIT);
        ImGui_ImplOpenGL3_RenderDrawData(ImGui::GetDrawData());
        SDL_GL_SwapWindow(window);
    };

    // ---- splash screen while the rest loads
    {
        struct Stage { const char* text; std::function<void()> work; };
        const Stage stages[] = {
            {"Запуск модулей…", [] {}},
            {"Загрузка кистей…", [] {
                 for (int s = 0; s < int(ag::TipShape::Custom); s++) ag::tipFor(ag::TipShape(s), 0.5f);
                 ag::builtinBrushes();
             }},
            {"Поиск шрифтов…", [&] { editor.scanFonts(); }},
            {"Загрузка градиентов и стилей…", [] { ag::gradientPresets({0, 0, 0, 255}, {255, 255, 255, 255}); }},
            {"Чтение настроек…", [&] { editor.loadPrefs(); }},
            {"Подготовка рабочей среды…", [] {}},
        };
        const int n = int(std::size(stages));
        Uint32 start = SDL_GetTicks();
        const Uint32 minTime = 1900;  // long enough to actually see the splash
        int done = 0;
        while (true) {
            SDL_Event e;
            while (SDL_PollEvent(&e)) ImGui_ImplSDL2_ProcessEvent(&e);
            Uint32 t = SDL_GetTicks() - start;
            float timeProgress = std::min(1.f, float(t) / minTime);
            int want = std::min(n, int(timeProgress * n) + 1);
            while (done < want) stages[done++].work();
            renderFrame([&] { editor.drawSplash(timeProgress, stages[std::max(0, done - 1)].text); });
            if (done >= n && t >= minTime) break;
            SDL_Delay(15);
        }
    }

    // ---- switch to the main window
#ifndef __ANDROID__
    SDL_SetWindowBordered(window, SDL_TRUE);
    SDL_SetWindowResizable(window, SDL_TRUE);
    SDL_SetWindowMinimumSize(window, 900, 560);
    SDL_SetWindowSize(window, int(1440 * scale), int(900 * scale));
    SDL_SetWindowPosition(window, SDL_WINDOWPOS_CENTERED, SDL_WINDOWPOS_CENTERED);
    SDL_MaximizeWindow(window);
#endif

    if (argc > 1) editor.openPath(argv[1]);

    int busyFrames = 10;  // keep rendering a few frames after input so ImGui settles
    bool running = true;
    while (running) {
        SDL_Event e;
        // Idle: sleep until input. Only the selection outline animating: ~30 fps is plenty.
        bool got;
        if (busyFrames > 0) got = SDL_PollEvent(&e) != 0;
        else got = SDL_WaitEventTimeout(&e, editor.animating() ? 33 : 500) != 0;
        while (got) {
            busyFrames = 3;
            ImGui_ImplSDL2_ProcessEvent(&e);
            if (e.type == SDL_QUIT) editor.requestQuit();
            if (e.type == SDL_WINDOWEVENT && e.window.event == SDL_WINDOWEVENT_CLOSE &&
                e.window.windowID == SDL_GetWindowID(window))
                editor.requestQuit();
            // Touch: count fingers; two fingers pinch-zoom and pan the canvas.
            if (e.type == SDL_FINGERDOWN) editor.touchFingers++;
            if (e.type == SDL_FINGERUP) editor.touchFingers = std::max(0, editor.touchFingers - 1);
            if (e.type == SDL_MULTIGESTURE && e.mgesture.numFingers >= 2) {
                static float lastX = -1, lastY = -1;
                static Uint32 lastT = 0;
                float w = io.DisplaySize.x, h = io.DisplaySize.y;
                float cx = e.mgesture.x * w, cy = e.mgesture.y * h;
                if (SDL_GetTicks() - lastT > 200) { lastX = cx; lastY = cy; }  // new gesture
                lastT = SDL_GetTicks();
                editor.touchGesture(1.f + e.mgesture.dDist * 2.2f, cx, cy, cx - lastX, cy - lastY);
                lastX = cx;
                lastY = cy;
            }
            if (e.type == SDL_DROPFILE) {
                editor.dropPath(e.drop.file);
                SDL_free(e.drop.file);
            }
            got = SDL_PollEvent(&e) != 0;
        }
        if (editor.wantsQuit()) break;
        if (SDL_GetWindowFlags(window) & SDL_WINDOW_MINIMIZED) {
            SDL_Delay(50);
            continue;
        }
        busyFrames--;

        editor.beforeFrame();
        renderFrame([&] { editor.frame(); });
#ifdef __ANDROID__
        // Show the on-screen keyboard while a text field is focused.
        if (io.WantTextInput && !SDL_IsTextInputActive()) SDL_StartTextInput();
        else if (!io.WantTextInput && SDL_IsTextInputActive()) SDL_StopTextInput();
#endif
    }

    editorPtr.reset();  // frees GL textures while the context is alive
    ImGui_ImplOpenGL3_Shutdown();
    ImGui_ImplSDL2_Shutdown();
    ImGui::DestroyContext();
    SDL_GL_DeleteContext(gl);
    SDL_DestroyWindow(window);
    SDL_Quit();
    return 0;
}
