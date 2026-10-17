// ArtGraf — raster graphics editor. Entry point: window, GL context, ImGui, main loop.
#include <cmath>
#include <filesystem>
#include <functional>
#include <memory>
#include <string>

#include <SDL.h>
#include <SDL_opengl.h>
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
    SDL_GL_SetAttribute(SDL_GL_CONTEXT_MINOR_VERSION, 0);
    SDL_GL_SetAttribute(SDL_GL_DOUBLEBUFFER, 1);
    SDL_GL_SetAttribute(SDL_GL_DEPTH_SIZE, 0);
    SDL_GL_SetAttribute(SDL_GL_STENCIL_SIZE, 8);

    float scale = 1.f;
    float ddpi = 0;
    if (SDL_GetDisplayDPI(0, &ddpi, nullptr, nullptr) == 0 && ddpi > 0) scale = std::clamp(ddpi / 96.f, 1.f, 3.f);

    // The window starts as a borderless splash screen and turns into the main window once loaded.
    const int splashW = int(960 * scale), splashH = int(560 * scale);
    SDL_Window* window = SDL_CreateWindow("ArtGraf", SDL_WINDOWPOS_CENTERED, SDL_WINDOWPOS_CENTERED, splashW, splashH,
                                          SDL_WINDOW_OPENGL | SDL_WINDOW_BORDERLESS | SDL_WINDOW_ALLOW_HIGHDPI);
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
    ImGui_ImplOpenGL3_Init("#version 130");
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
    SDL_SetWindowBordered(window, SDL_TRUE);
    SDL_SetWindowResizable(window, SDL_TRUE);
    SDL_SetWindowMinimumSize(window, 900, 560);
    SDL_SetWindowSize(window, int(1440 * scale), int(900 * scale));
    SDL_SetWindowPosition(window, SDL_WINDOWPOS_CENTERED, SDL_WINDOWPOS_CENTERED);
    SDL_MaximizeWindow(window);

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
