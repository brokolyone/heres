#include <cmath>
#include <cstdlib>
#include <cstring>
#include <filesystem>

#include <SDL_opengl.h>
#include <imgui_internal.h>
#include <imgui_stdlib.h>

#include "editor.h"
#include "filters.h"
#include "icons.h"
#include "io.h"

namespace ag {

ImFont* gTitleFont = nullptr;
ImFont* gMediumFont = nullptr;

namespace {

const char* kToolsWin = "Инструменты";
const char* kCanvasWin = "Холст";
const char* kColorWin = "Цвет";
const char* kBrushesWin = "Кисти";
const char* kLayersWin = "Слои";
const char* kHistoryWin = "История";
const char* kNavWin = "Навигатор";

const ImU32 kAccent = IM_COL32(38, 128, 235, 255);
const ImU32 kAccent2 = IM_COL32(38, 128, 235, 255);

bool exists(const std::string& p) {
    std::error_code ec;
#if defined(__cpp_char8_t)
    return std::filesystem::exists(std::filesystem::path(std::u8string(p.begin(), p.end())), ec);
#else
    return std::filesystem::exists(std::filesystem::u8path(p), ec);
#endif
}

std::string winDir() { return std::getenv("WINDIR") ? std::getenv("WINDIR") : "C:/Windows"; }

void sectionTitle(const char* text) {
    if (gMediumFont) ImGui::PushFont(gMediumFont);
    ImGui::TextUnformatted(text);
    if (gMediumFont) ImGui::PopFont();
}

}  // namespace

void drawGradientStrip(ImDrawList* dl, ImVec2 a, ImVec2 b, const Gradient& g, float rounding) {
    float cs = 6;
    dl->PushClipRect(a, b, true);
    for (float y = a.y; y < b.y; y += cs)
        for (float x = a.x; x < b.x; x += cs) {
            bool odd = (int((x - a.x) / cs) + int((y - a.y) / cs)) & 1;
            dl->AddRectFilled(ImVec2(x, y), ImVec2(std::min(x + cs, b.x), std::min(y + cs, b.y)),
                              odd ? IM_COL32(90, 90, 96, 255) : IM_COL32(150, 150, 156, 255));
        }
    const int N = 48;
    for (int i = 0; i < N; i++) {
        float x0 = a.x + (b.x - a.x) * i / N, x1 = a.x + (b.x - a.x) * (i + 1) / N;
        ImU32 c0 = toU32(g.sample(float(i) / N)), c1 = toU32(g.sample(float(i + 1) / N));
        dl->AddRectFilledMultiColor(ImVec2(x0, a.y), ImVec2(x1 + 0.5f, b.y), c0, c1, c1, c0);
    }
    dl->PopClipRect();
    dl->AddRect(a, b, IM_COL32(0, 0, 0, 120), rounding, 0, 1.f);
}

// ---------------------------------------------------------------- setup

void Editor::scanFonts() {
    fonts.clear();
    std::string wf = winDir() + "/Fonts/";
    const std::pair<const char*, const char*> windowsFonts[] = {
        {"Arial", "arial.ttf"},          {"Arial Bold", "arialbd.ttf"},       {"Arial Italic", "ariali.ttf"},
        {"Arial Black", "ariblk.ttf"},   {"Segoe UI", "segoeui.ttf"},         {"Segoe UI Bold", "segoeuib.ttf"},
        {"Segoe UI Light", "segoeuil.ttf"}, {"Segoe Print", "segoepr.ttf"},  {"Segoe Script", "segoesc.ttf"},
        {"Calibri", "calibri.ttf"},      {"Calibri Bold", "calibrib.ttf"},    {"Candara", "candara.ttf"},
        {"Verdana", "verdana.ttf"},      {"Tahoma", "tahoma.ttf"},            {"Trebuchet MS", "trebuc.ttf"},
        {"Times New Roman", "times.ttf"}, {"Times New Roman Bold", "timesbd.ttf"}, {"Georgia", "georgia.ttf"},
        {"Palatino Linotype", "pala.ttf"}, {"Cambria", "cambria.ttc"},       {"Constantia", "constan.ttf"},
        {"Courier New", "cour.ttf"},     {"Consolas", "consola.ttf"},         {"Lucida Console", "lucon.ttf"},
        {"Comic Sans MS", "comic.ttf"},  {"Impact", "impact.ttf"},            {"Gabriola", "gabriola.ttf"},
        {"Bahnschrift", "bahnschrift.ttf"}, {"Franklin Gothic", "framd.ttf"}, {"Monotype Corsiva", "mtcorsva.ttf"},
    };
    for (auto& f : windowsFonts)
        if (exists(wf + f.second)) fonts.push_back({f.first, wf + f.second});
    const std::pair<const char*, const char*> linuxFonts[] = {
        {"DejaVu Sans", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"},
        {"DejaVu Sans Bold", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"},
        {"DejaVu Serif", "/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf"},
        {"DejaVu Sans Mono", "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"},
        {"Liberation Sans", "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf"},
        {"Liberation Serif", "/usr/share/fonts/truetype/liberation/LiberationSerif-Regular.ttf"},
    };
    for (auto& f : linuxFonts)
        if (exists(f.second)) fonts.push_back({f.first, f.second});
}

void Editor::loadFonts(float scale) {
    ImGuiIO& io = ImGui::GetIO();
    static ImVector<ImWchar> ranges;
    if (ranges.empty()) {
        ImFontGlyphRangesBuilder b;
        b.AddRanges(io.Fonts->GetGlyphRangesCyrillic());
        static const ImWchar extra[] = {0x2010, 0x205E, 0x2190, 0x21FF, 0x2212, 0x2212, 0x2300, 0x23FF, 0x25A0, 0x25FF, 0x2600, 0x26FF, 0};
        b.AddRanges(extra);
        b.BuildRanges(&ranges);
    }
    auto add = [&](const std::vector<std::string>& candidates, float px) -> ImFont* {
        for (auto& path : candidates) {
            std::vector<uint8_t> data;
            if (!readFile(path, data) || data.empty()) continue;
            ImFontConfig cfg;
            cfg.FontDataOwnedByAtlas = true;
            cfg.OversampleH = 2;
            void* mem = IM_ALLOC(data.size());
            std::memcpy(mem, data.data(), data.size());
            if (ImFont* f = io.Fonts->AddFontFromMemoryTTF(mem, int(data.size()), std::round(px * scale), &cfg, ranges.Data)) return f;
        }
        return nullptr;
    };
    std::string wf = winDir() + "/Fonts/";
    std::string dv = "/usr/share/fonts/truetype/dejavu/";
    ImFont* main = add({wf + "segoeui.ttf", wf + "arial.ttf", dv + "DejaVuSans.ttf",
                        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf"}, 15.f);
    if (!main) {
        ImFontConfig cfg;
        cfg.SizePixels = std::round(13.f * scale);
        io.Fonts->AddFontDefault(&cfg);
    }
    gMediumFont = add({wf + "segoeuib.ttf", wf + "arialbd.ttf", dv + "DejaVuSans-Bold.ttf"}, 17.f);
    gTitleFont = add({wf + "segoeuib.ttf", wf + "arialbd.ttf", dv + "DejaVuSans-Bold.ttf"}, 30.f);
}

void Editor::setupStyle(float scale) {
    ImGuiStyle& s = ImGui::GetStyle();
    ImGui::StyleColorsDark();
    s.WindowRounding = 10;
    s.ChildRounding = 8;
    s.FrameRounding = 7;
    s.PopupRounding = 10;
    s.GrabRounding = 7;
    s.TabRounding = 7;
    s.ScrollbarRounding = 8;
    s.WindowBorderSize = 1;
    s.ChildBorderSize = 1;
    s.PopupBorderSize = 1;
    s.FrameBorderSize = 0;
    s.TabBorderSize = 0;
    s.WindowPadding = ImVec2(10, 10);
    s.FramePadding = ImVec2(8, 5);
    s.ItemSpacing = ImVec2(8, 7);
    s.ItemInnerSpacing = ImVec2(6, 5);
    s.ScrollbarSize = 12;
    s.GrabMinSize = 12;
    s.WindowMenuButtonPosition = ImGuiDir_None;
    s.SeparatorTextBorderSize = 1;
    s.DockingSeparatorSize = 3;
    ImVec4* c = s.Colors;
    auto rgb = [](int r, int g, int b, float a = 1.f) { return ImVec4(r / 255.f, g / 255.f, b / 255.f, a); };
    c[ImGuiCol_Text] = rgb(228, 229, 235);
    c[ImGuiCol_TextDisabled] = rgb(118, 120, 132);
    c[ImGuiCol_WindowBg] = rgb(22, 23, 27);
    c[ImGuiCol_ChildBg] = rgb(17, 18, 21);
    c[ImGuiCol_PopupBg] = rgb(26, 27, 32, 0.98f);
    c[ImGuiCol_MenuBarBg] = rgb(16, 17, 20);
    c[ImGuiCol_Border] = rgb(42, 44, 52);
    c[ImGuiCol_BorderShadow] = rgb(0, 0, 0, 0);
    c[ImGuiCol_FrameBg] = rgb(32, 34, 40);
    c[ImGuiCol_FrameBgHovered] = rgb(42, 44, 52);
    c[ImGuiCol_FrameBgActive] = rgb(50, 52, 62);
    c[ImGuiCol_TitleBg] = rgb(16, 17, 20);
    c[ImGuiCol_TitleBgActive] = rgb(16, 17, 20);
    c[ImGuiCol_TitleBgCollapsed] = rgb(16, 17, 20);
    c[ImGuiCol_Button] = rgb(36, 38, 45);
    c[ImGuiCol_ButtonHovered] = rgb(50, 52, 62);
    c[ImGuiCol_ButtonActive] = rgb(38, 128, 235);
    c[ImGuiCol_Header] = rgb(38, 128, 235, 0.30f);
    c[ImGuiCol_HeaderHovered] = rgb(38, 128, 235, 0.45f);
    c[ImGuiCol_HeaderActive] = rgb(38, 128, 235, 0.70f);
    c[ImGuiCol_CheckMark] = rgb(90, 162, 248);
    c[ImGuiCol_SliderGrab] = rgb(38, 128, 235);
    c[ImGuiCol_SliderGrabActive] = rgb(90, 162, 248);
    c[ImGuiCol_ScrollbarBg] = rgb(0, 0, 0, 0);
    c[ImGuiCol_ScrollbarGrab] = rgb(52, 54, 64);
    c[ImGuiCol_ScrollbarGrabHovered] = rgb(70, 72, 84);
    c[ImGuiCol_ScrollbarGrabActive] = rgb(38, 128, 235);
    c[ImGuiCol_Separator] = rgb(38, 40, 48);
    c[ImGuiCol_SeparatorHovered] = rgb(38, 128, 235, 0.6f);
    c[ImGuiCol_SeparatorActive] = rgb(38, 128, 235);
    c[ImGuiCol_ResizeGrip] = rgb(0, 0, 0, 0);
    c[ImGuiCol_ResizeGripHovered] = rgb(38, 128, 235, 0.5f);
    c[ImGuiCol_Tab] = rgb(22, 23, 27);
    c[ImGuiCol_TabHovered] = rgb(50, 52, 62);
    c[ImGuiCol_TabSelected] = rgb(34, 36, 43);
    c[ImGuiCol_TabSelectedOverline] = rgb(38, 128, 235);
    c[ImGuiCol_TabDimmed] = rgb(22, 23, 27);
    c[ImGuiCol_TabDimmedSelected] = rgb(30, 31, 37);
    c[ImGuiCol_TabDimmedSelectedOverline] = rgb(40, 78, 128);
    c[ImGuiCol_DockingPreview] = rgb(38, 128, 235, 0.55f);
    c[ImGuiCol_DockingEmptyBg] = rgb(11, 12, 14);
    c[ImGuiCol_ModalWindowDimBg] = rgb(0, 0, 0, 0.6f);
    c[ImGuiCol_NavHighlight] = rgb(38, 128, 235);
    c[ImGuiCol_TableRowBgAlt] = rgb(255, 255, 255, 0.025f);
    s.ScaleAllSizes(scale);
}

// ---------------------------------------------------------------- frame

void Editor::beforeFrame() { files.runPending(); }

void Editor::frame() {
    handleShortcuts();
    drawMenuBar();
    drawOptionsBar();
    drawStatusBar();
    drawDockspace();
    drawToolbox();
    drawCanvas();
    drawColors();
    drawBrushes();
    drawLayers();
    drawHistory();
    drawNavigator();
    drawDialogs();
    files.draw();
    updateTitle();
}

void Editor::drawDockspace() {
    ImGuiViewport* vp = ImGui::GetMainViewport();
    ImGuiID dock = ImGui::GetID("ArtGrafDock2");
    if (layoutReset) {
        layoutReset = false;
        ImGui::DockBuilderRemoveNode(dock);
        ImGui::DockBuilderAddNode(dock, ImGuiDockNodeFlags_DockSpace);
        ImGui::DockBuilderSetNodeSize(dock, vp->WorkSize);
        ImGuiID center = dock;
        float toolW = ImGui::GetFrameHeight() * 2.6f + 22;
        ImGuiID left = ImGui::DockBuilderSplitNode(center, ImGuiDir_Left, toolW / vp->WorkSize.x, nullptr, &center);
        ImGuiID right = ImGui::DockBuilderSplitNode(center, ImGuiDir_Right, 0.23f, nullptr, &center);
        ImGuiID rightBottom;
        ImGuiID rightTop = ImGui::DockBuilderSplitNode(right, ImGuiDir_Up, 0.42f, nullptr, &rightBottom);
        ImGuiID rightLow;
        ImGuiID rightMid = ImGui::DockBuilderSplitNode(rightBottom, ImGuiDir_Up, 0.64f, nullptr, &rightLow);
        ImGui::DockBuilderDockWindow(kToolsWin, left);
        ImGui::DockBuilderDockWindow(kCanvasWin, center);
        ImGui::DockBuilderDockWindow(kNavWin, rightTop);
        ImGui::DockBuilderDockWindow(kBrushesWin, rightTop);
        ImGui::DockBuilderDockWindow(kColorWin, rightTop);
        ImGui::DockBuilderDockWindow(kLayersWin, rightMid);
        ImGui::DockBuilderDockWindow(kHistoryWin, rightLow);
        ImGui::DockBuilderFinish(dock);
        colorTabFocus = 3;  // bring "Цвет" to front once the windows exist
    }
    ImGui::DockSpaceOverViewport(dock, vp);
}

// ---------------------------------------------------------------- menu

void Editor::drawMenuBar() {
    ImGui::PushStyleVar(ImGuiStyleVar_FramePadding, ImVec2(8, 7));
    bool open = ImGui::BeginMainMenuBar();
    ImGui::PopStyleVar();
    if (!open) return;
    bool d = doc != nullptr;
    bool sel = d && doc->sel.active();
    float h = ImGui::GetFrameHeight();
    drawLogo(ImGui::GetWindowDrawList(), ImVec2(ImGui::GetCursorScreenPos().x, ImGui::GetCursorScreenPos().y + 3), h - 6);
    ImGui::Dummy(ImVec2(h - 2, 0));

    if (ImGui::BeginMenu("Файл")) {
        if (ImGui::MenuItem("Создать…", "Ctrl+N")) cmdNew();
        if (ImGui::MenuItem("Открыть…", "Ctrl+O")) cmdOpen();
        if (ImGui::BeginMenu("Последние файлы", !recentFiles.empty())) {
            for (auto& r : recentFiles)
                if (ImGui::MenuItem(fileName(r).c_str())) openPath(r);
            ImGui::Separator();
            if (ImGui::MenuItem("Очистить список")) {
                recentFiles.clear();
                savePrefs();
            }
            ImGui::EndMenu();
        }
        if (ImGui::BeginMenu("Импорт")) {
            if (ImGui::MenuItem("Изображение как слой…", "Ctrl+Shift+P", false, d)) cmdPlace();
            if (ImGui::MenuItem("Несколько изображений как слои…")) cmdImportLayers();
            if (ImGui::MenuItem("Новый документ из буфера обмена", "Ctrl+Alt+N")) cmdNewFromClipboard();
            ImGui::Separator();
            if (ImGui::MenuItem("Кисть из изображения…")) cmdBrushFromFile();
            if (ImGui::MenuItem("Кисть из выделения", nullptr, false, d)) cmdBrushFromSelection();
            ImGui::EndMenu();
        }
        ImGui::Separator();
        if (ImGui::MenuItem("Сохранить проект", "Ctrl+S", false, d)) cmdSave(false);
        if (ImGui::MenuItem("Сохранить проект как…", "Ctrl+Shift+S", false, d)) cmdSave(true);
        if (ImGui::MenuItem("Экспорт (PNG, JPEG, BMP, TGA)…", "Ctrl+Shift+E", false, d)) cmdExport();
        ImGui::Separator();
        if (ImGui::MenuItem("Закрыть", "Ctrl+W", false, d)) closeTab(current);
        if (ImGui::MenuItem("Выход", "Alt+F4")) requestQuit();
        ImGui::EndMenu();
    }
    if (ImGui::BeginMenu("Редактирование")) {
        std::string undoLabel = d && doc->canUndo() ? "Отменить: " + doc->undoStack.back().name : "Отменить";
        std::string redoLabel = d && doc->canRedo() ? "Повторить: " + doc->redoStack.back().name : "Повторить";
        if (ImGui::MenuItem(undoLabel.c_str(), "Ctrl+Z", false, d && doc->canUndo())) cmdUndo();
        if (ImGui::MenuItem(redoLabel.c_str(), "Ctrl+Shift+Z", false, d && doc->canRedo())) cmdRedo();
        ImGui::Separator();
        if (ImGui::MenuItem("Вырезать", "Ctrl+X", false, d)) cmdCut();
        if (ImGui::MenuItem("Копировать", "Ctrl+C", false, d)) cmdCopy(false);
        if (ImGui::MenuItem("Копировать совмещённые данные", "Ctrl+Shift+C", false, d)) cmdCopy(true);
        if (ImGui::MenuItem("Вставить", "Ctrl+V")) cmdPaste();
        ImGui::Separator();
        if (ImGui::MenuItem("Залить основным цветом", "Alt+Backspace", false, d)) cmdFill(primary, "Заливка основным цветом");
        if (ImGui::MenuItem("Залить фоновым цветом", "Ctrl+Backspace", false, d)) cmdFill(secondary, "Заливка фоновым цветом");
        if (ImGui::MenuItem("Выполнить обводку…", nullptr, false, sel)) popupToOpen = "Обводка";
        if (ImGui::MenuItem("Очистить", "Delete", false, d)) cmdClear();
        ImGui::Separator();
        if (ImGui::MenuItem("Трансформирование слоя…", "Ctrl+T", false, d)) cmdTransform();
        ImGui::EndMenu();
    }
    if (ImGui::BeginMenu("Изображение")) {
        if (ImGui::BeginMenu("Коррекция", d)) {
            if (ImGui::MenuItem("Яркость/Контраст…"))
                openFilter({"Яркость/Контраст", {{"Яркость", -100, 100, 0}, {"Контраст", -100, 100, 0}},
                            [](Image& i, const std::vector<float>& v) { brightnessContrast(i, v[0], v[1]); }, {}});
            if (ImGui::MenuItem("Уровни…", "Ctrl+L"))
                openFilter({"Уровни",
                            {{"Чёрная точка", 0, 254, 0, true}, {"Белая точка", 1, 255, 255, true}, {"Гамма", 0.1f, 5.f, 1.f},
                             {"Выход: чёрный", 0, 255, 0, true}, {"Выход: белый", 0, 255, 255, true}},
                            [](Image& i, const std::vector<float>& v) { levels(i, int(v[0]), int(v[1]), v[2], int(v[3]), int(v[4])); }, {}});
            if (ImGui::MenuItem("Кривые…", "Ctrl+M")) openCurves();
            if (ImGui::MenuItem("Экспозиция…"))
                openFilter({"Экспозиция", {{"Экспозиция, EV", -5, 5, 0}, {"Сдвиг", -0.5f, 0.5f, 0}, {"Гамма", 0.1f, 3, 1}},
                            [](Image& i, const std::vector<float>& v) { exposure(i, v[0], v[1], v[2]); }, {}});
            ImGui::Separator();
            if (ImGui::MenuItem("Сочность…"))
                openFilter({"Сочность", {{"Сочность", -100, 100, 30}, {"Насыщенность", -100, 100, 0}},
                            [](Image& i, const std::vector<float>& v) { vibrance(i, v[0], v[1]); }, {}});
            if (ImGui::MenuItem("Цветовой тон/Насыщенность…", "Ctrl+U"))
                openFilter({"Цветовой тон/Насыщенность",
                            {{"Цветовой тон", -180, 180, 0}, {"Насыщенность", -100, 100, 0}, {"Яркость", -100, 100, 0}},
                            [](Image& i, const std::vector<float>& v) { hueSaturation(i, v[0], v[1], v[2]); }, {}});
            if (ImGui::MenuItem("Цветовой баланс…", "Ctrl+B"))
                openFilter({"Цветовой баланс",
                            {{"Голубой — Красный", -100, 100, 0}, {"Пурпурный — Зелёный", -100, 100, 0}, {"Жёлтый — Синий", -100, 100, 0}},
                            [](Image& i, const std::vector<float>& v) { colorBalance(i, v[0], v[1], v[2]); }, {}});
            if (ImGui::MenuItem("Чёрно-белое…", "Alt+Shift+Ctrl+B"))
                openFilter({"Чёрно-белое",
                            {{"Красные", -200, 300, 40}, {"Жёлтые", -200, 300, 60}, {"Зелёные", -200, 300, 40},
                             {"Голубые", -200, 300, 60}, {"Синие", -200, 300, 20}, {"Пурпурные", -200, 300, 80}},
                            [](Image& i, const std::vector<float>& v) { blackWhite(i, v[0], v[1], v[2], v[3], v[4], v[5]); }, {}});
            if (ImGui::MenuItem("Фотофильтр…")) openPhotoFilter();
            if (ImGui::MenuItem("Микширование каналов…"))
                openFilter({"Микширование каналов",
                            {{"R ← красный", -200, 200, 100}, {"R ← зелёный", -200, 200, 0}, {"R ← синий", -200, 200, 0},
                             {"G ← красный", -200, 200, 0}, {"G ← зелёный", -200, 200, 100}, {"G ← синий", -200, 200, 0},
                             {"B ← красный", -200, 200, 0}, {"B ← зелёный", -200, 200, 0}, {"B ← синий", -200, 200, 100}},
                            [](Image& i, const std::vector<float>& v) { channelMixer(i, v[0], v[1], v[2], v[3], v[4], v[5], v[6], v[7], v[8]); }, {}});
            if (ImGui::MenuItem("Карта градиента…")) openGradientMap();
            ImGui::Separator();
            if (ImGui::MenuItem("Автоконтраст", "Ctrl+Shift+L")) instantFilter("Автоконтраст", autoContrast);
            if (ImGui::MenuItem("Обесцветить", "Ctrl+Shift+U")) instantFilter("Обесцветить", desaturate);
            if (ImGui::MenuItem("Инверсия", "Ctrl+I")) instantFilter("Инверсия", invert);
            if (ImGui::MenuItem("Сепия")) instantFilter("Сепия", sepia);
            if (ImGui::MenuItem("Соляризация")) instantFilter("Соляризация", solarize);
            if (ImGui::MenuItem("Постеризация…"))
                openFilter({"Постеризация", {{"Уровни", 2, 32, 4, true}}, [](Image& i, const std::vector<float>& v) { posterize(i, int(v[0])); }, {}});
            if (ImGui::MenuItem("Порог…"))
                openFilter({"Порог", {{"Порог", 1, 255, 128, true}}, [](Image& i, const std::vector<float>& v) { threshold(i, int(v[0])); }, {}});
            ImGui::EndMenu();
        }
        ImGui::Separator();
        if (ImGui::MenuItem("Размер изображения…", "Ctrl+Alt+I", false, d)) {
            sizeW = doc->w;
            sizeH = doc->h;
            popupToOpen = "Размер изображения";
        }
        if (ImGui::MenuItem("Размер холста…", "Ctrl+Alt+C", false, d)) {
            sizeW = doc->w;
            sizeH = doc->h;
            anchor = 4;
            popupToOpen = "Размер холста";
        }
        if (ImGui::BeginMenu("Вращение изображения", d)) {
            if (ImGui::MenuItem("90° по часовой")) imageAction("Поворот 90° по часовой", [](Document& x) { x.rotateCW(); });
            if (ImGui::MenuItem("90° против часовой")) imageAction("Поворот 90° против часовой", [](Document& x) { x.rotateCCW(); });
            if (ImGui::MenuItem("180°")) imageAction("Поворот 180°", [](Document& x) { x.rotate180(); });
            ImGui::Separator();
            if (ImGui::MenuItem("Отразить холст по горизонтали")) imageAction("Отразить по горизонтали", [](Document& x) { x.flipH(); });
            if (ImGui::MenuItem("Отразить холст по вертикали")) imageAction("Отразить по вертикали", [](Document& x) { x.flipV(); });
            ImGui::EndMenu();
        }
        ImGui::Separator();
        if (ImGui::MenuItem("Кадрировать по выделению", nullptr, false, sel)) cmdCropToSelection();
        if (ImGui::MenuItem("Обрезать прозрачные края", nullptr, false, d)) cmdTrim();
        ImGui::EndMenu();
    }
    if (ImGui::BeginMenu("Слой")) {
        if (ImGui::MenuItem("Новый слой", "Ctrl+Shift+N", false, d)) layerAction("Новый слой", [](Document& x) { x.addLayer(x.nextLayerName()); });
        if (ImGui::MenuItem("Скопировать на новый слой", "Ctrl+J", false, d)) cmdLayerViaCopy();
        if (ImGui::MenuItem("Дублировать слой", nullptr, false, d)) layerAction("Дублировать слой", [](Document& x) { x.duplicateLayer(); });
        if (ImGui::MenuItem("Удалить слой", nullptr, false, d && doc->layers.size() > 1)) layerAction("Удалить слой", [](Document& x) { x.deleteLayer(); });
        ImGui::Separator();
        if (ImGui::BeginMenu("Стиль слоя", d)) {
            if (ImGui::MenuItem("Параметры наложения…")) cmdOpenLayerStyle();
            if (ImGui::MenuItem("Растрировать стиль", nullptr, false, doc->layer().fx.any()))
                layerAction("Растрировать стиль", [](Document& x) {
                    Image baked = x.layer().styled();
                    x.layer().img = std::move(baked);
                    x.layer().fx = {};
                    x.layer().touch();
                });
            if (ImGui::MenuItem("Очистить стиль", nullptr, false, doc->layer().fx.any()))
                layerAction("Очистить стиль", [](Document& x) { x.layer().fx = {}; x.layer().touch(); });
            ImGui::EndMenu();
        }
        ImGui::Separator();
        if (ImGui::MenuItem("Слой выше", "Ctrl+]", false, d)) layerAction("Порядок слоёв", [](Document& x) { x.moveLayer(1); });
        if (ImGui::MenuItem("Слой ниже", "Ctrl+[", false, d)) layerAction("Порядок слоёв", [](Document& x) { x.moveLayer(-1); });
        ImGui::Separator();
        if (ImGui::MenuItem("Отразить слой по горизонтали", nullptr, false, d)) cmdFlipLayer(true);
        if (ImGui::MenuItem("Отразить слой по вертикали", nullptr, false, d)) cmdFlipLayer(false);
        ImGui::Separator();
        if (ImGui::MenuItem("Объединить с нижним", "Ctrl+E", false, d && doc->active > 0)) layerAction("Объединить с нижним", [](Document& x) { x.mergeDown(); });
        if (ImGui::MenuItem("Выполнить сведение", nullptr, false, d)) layerAction("Выполнить сведение", [](Document& x) { x.flattenAll(); });
        ImGui::EndMenu();
    }
    if (ImGui::BeginMenu("Выделение")) {
        if (ImGui::MenuItem("Всё", "Ctrl+A", false, d)) cmdSelectAll();
        if (ImGui::MenuItem("Отменить выделение", "Ctrl+D", false, sel)) cmdDeselect();
        if (ImGui::MenuItem("Инверсия", "Ctrl+Shift+I", false, sel)) cmdInvertSelection();
        ImGui::Separator();
        if (ImGui::MenuItem("Растушевка…", "Shift+F6", false, sel)) popupToOpen = "Растушевка";
        ImGui::EndMenu();
    }
    if (ImGui::BeginMenu("Фильтр", d)) {
        if (ImGui::BeginMenu("Размытие")) {
            if (ImGui::MenuItem("Размытие по Гауссу…"))
                openFilter({"Размытие по Гауссу", {{"Радиус, px", 0.5f, 100, 4}}, [](Image& i, const std::vector<float>& v) { gaussianBlur(i, v[0]); }, {}});
            if (ImGui::MenuItem("Размытие в движении…"))
                openFilter({"Размытие в движении", {{"Угол, °", -180, 180, 0}, {"Смещение, px", 1, 200, 20, true}},
                            [](Image& i, const std::vector<float>& v) { motionBlur(i, v[0], int(v[1])); }, {}});
            if (ImGui::MenuItem("Радиальное размытие (зум)…"))
                openFilter({"Радиальное размытие", {{"Сила", 1, 100, 25}}, [](Image& i, const std::vector<float>& v) { zoomBlur(i, v[0]); }, {}});
            if (ImGui::MenuItem("Размытие вращением…"))
                openFilter({"Размытие вращением", {{"Угол, °", 1, 90, 12}}, [](Image& i, const std::vector<float>& v) { spinBlur(i, v[0]); }, {}});
            if (ImGui::MenuItem("Наклон-смещение (тилт-шифт)…"))
                openFilter({"Тилт-шифт", {{"Центр фокуса, %", 0, 100, 55}, {"Зона фокуса, %", 0, 100, 22}, {"Размытие, px", 1, 40, 10}},
                            [](Image& i, const std::vector<float>& v) { tiltShift(i, v[0] / 100, v[1] / 100, v[2]); }, {}});
            ImGui::EndMenu();
        }
        if (ImGui::BeginMenu("Искажение")) {
            if (ImGui::MenuItem("Скручивание…"))
                openFilter({"Скручивание", {{"Угол, °", -720, 720, 180}}, [](Image& i, const std::vector<float>& v) { twirl(i, v[0]); }, {}});
            if (ImGui::MenuItem("Сферизация…"))
                openFilter({"Сферизация", {{"Сила, %", -100, 100, 50}}, [](Image& i, const std::vector<float>& v) { spherize(i, v[0]); }, {}});
            if (ImGui::MenuItem("Волна…"))
                openFilter({"Волна", {{"Амплитуда, px", 0, 100, 10}, {"Длина волны, px", 4, 500, 80}},
                            [](Image& i, const std::vector<float>& v) { wave(i, v[0], v[1]); }, {}});
            if (ImGui::MenuItem("Рябь…"))
                openFilter({"Рябь", {{"Сила, px", 0, 60, 8}, {"Размер, px", 4, 200, 30}},
                            [](Image& i, const std::vector<float>& v) { ripple(i, v[0], v[1]); }, {}});
            if (ImGui::MenuItem("Полярные координаты…"))
                openFilter({"Полярные координаты", {{"0 — в полярные, 1 — обратно", 0, 1, 0, true}},
                            [](Image& i, const std::vector<float>& v) { polarCoordinates(i, v[0] < 0.5f); }, {}});
            ImGui::EndMenu();
        }
        if (ImGui::BeginMenu("Усиление резкости")) {
            if (ImGui::MenuItem("Контурная резкость…"))
                openFilter({"Контурная резкость", {{"Эффект, %", 1, 500, 100}, {"Радиус, px", 0.5f, 50, 1.5f}, {"Порог", 0, 255, 0, true}},
                            [](Image& i, const std::vector<float>& v) { unsharpMask(i, v[1], v[0], int(v[2])); }, {}});
            if (ImGui::MenuItem("Резкость")) instantFilter("Резкость", [](Image& i) { unsharpMask(i, 1.f, 80.f, 0); });
            ImGui::EndMenu();
        }
        if (ImGui::BeginMenu("Шум")) {
            if (ImGui::MenuItem("Добавить шум…"))
                openFilter({"Добавить шум", {{"Количество", 1, 100, 12}, {"Монохромный (0/1)", 0, 1, 0, true}},
                            [](Image& i, const std::vector<float>& v) { addNoise(i, v[0], v[1] > 0.5f, 1234u); }, {}});
            if (ImGui::MenuItem("Медиана…"))
                openFilter({"Медиана", {{"Радиус, px", 1, 8, 2, true}}, [](Image& i, const std::vector<float>& v) { median(i, int(v[0])); }, {}});
            ImGui::EndMenu();
        }
        if (ImGui::BeginMenu("Оформление")) {
            if (ImGui::MenuItem("Пикселизация…"))
                openFilter({"Пикселизация", {{"Размер ячейки, px", 2, 200, 10, true}}, [](Image& i, const std::vector<float>& v) { pixelate(i, int(v[0])); }, {}});
            if (ImGui::MenuItem("Кристаллизация…"))
                openFilter({"Кристаллизация", {{"Размер ячейки, px", 3, 200, 18, true}},
                            [](Image& i, const std::vector<float>& v) { crystallize(i, int(v[0]), 7u); }, {}});
            if (ImGui::MenuItem("Цветные полутона…"))
                openFilter({"Цветные полутона", {{"Размер растра, px", 3, 60, 8, true}}, [](Image& i, const std::vector<float>& v) { halftone(i, int(v[0])); }, {}});
            ImGui::EndMenu();
        }
        if (ImGui::BeginMenu("Рендеринг")) {
            if (ImGui::MenuItem("Облака…")) openClouds();
            if (ImGui::MenuItem("Блик…")) openLensFlare();
            if (ImGui::MenuItem("Виньетка…"))
                openFilter({"Виньетка", {{"Сила, %", 0, 100, 50}}, [](Image& i, const std::vector<float>& v) { vignette(i, v[0]); }, {}});
            ImGui::EndMenu();
        }
        if (ImGui::BeginMenu("Стилизация")) {
            if (ImGui::MenuItem("Тиснение")) instantFilter("Тиснение", emboss);
            if (ImGui::MenuItem("Выделение краёв")) instantFilter("Выделение краёв", findEdges);
            if (ImGui::MenuItem("Масляная краска…"))
                openFilter({"Масляная краска", {{"Радиус, px", 1, 8, 3, true}, {"Уровни", 4, 40, 20, true}},
                            [](Image& i, const std::vector<float>& v) { oilPaint(i, int(v[0]), int(v[1])); }, {}});
            if (ImGui::MenuItem("Набросок карандашом…"))
                openFilter({"Набросок карандашом", {{"Сила, %", 0, 100, 100}}, [](Image& i, const std::vector<float>& v) { sketch(i, v[0]); }, {}});
            if (ImGui::MenuItem("Глитч…"))
                openFilter({"Глитч", {{"Сдвиг, px", 1, 200, 30}, {"Полосы", 1, 80, 18, true}, {"Вариант", 1, 100, 1, true}},
                            [](Image& i, const std::vector<float>& v) { glitch(i, v[0], int(v[1]), uint32_t(v[2])); }, {}});
            if (ImGui::MenuItem("Хроматическая аберрация…"))
                openFilter({"Хроматическая аберрация", {{"Сдвиг, px", 0, 40, 4}},
                            [](Image& i, const std::vector<float>& v) { chromaticAberration(i, v[0]); }, {}});
            ImGui::EndMenu();
        }
        ImGui::EndMenu();
    }
    if (ImGui::BeginMenu("Просмотр")) {
        ImVec2 c(canvasMin.x + canvasSize.x * 0.5f, canvasMin.y + canvasSize.y * 0.5f);
        if (ImGui::MenuItem("Увеличить", "Ctrl+=", false, d)) zoomAt(zoom * 1.25f, c);
        if (ImGui::MenuItem("Уменьшить", "Ctrl+-", false, d)) zoomAt(zoom / 1.25f, c);
        if (ImGui::MenuItem("Показать целиком", "Ctrl+0", false, d)) fitView();
        if (ImGui::MenuItem("Реальный размер (100%)", "Ctrl+1", false, d)) zoomAt(1.f, c);
        ImGui::Separator();
        ImGui::MenuItem("Пиксельная сетка", "Ctrl+'", &showGrid);
        ImGui::EndMenu();
    }
    if (ImGui::BeginMenu("Окно")) {
        ImGui::MenuItem("Настройки кисти", "F5", &showBrushSettings);
        if (ImGui::MenuItem("Сбросить расположение панелей")) layoutReset = true;
        ImGui::EndMenu();
    }
    if (ImGui::BeginMenu("Справка")) {
        if (ImGui::MenuItem("Горячие клавиши", "F1")) showShortcuts = true;
        if (ImGui::MenuItem("О программе")) showAbout = true;
        ImGui::EndMenu();
    }
    ImGui::EndMainMenuBar();
}

// ---------------------------------------------------------------- gradient / brush pickers

bool Editor::gradientCombo(const char* id, Gradient& g, float width) {
    bool changed = false, edited = false;
    ImGui::PushID(id);
    ImVec2 p = ImGui::GetCursorScreenPos();
    float h = ImGui::GetFrameHeight();
    if (ImGui::InvisibleButton("##strip", ImVec2(width, h))) ImGui::OpenPopup("##gradpop");
    drawGradientStrip(ImGui::GetWindowDrawList(), ImVec2(p.x, p.y + 2), ImVec2(p.x + width, p.y + h - 2), g, 5);
    if (ImGui::IsItemHovered()) ImGui::GetWindowDrawList()->AddRect(p, ImVec2(p.x + width, p.y + h), kAccent, 6, 0, 1.5f);
    ImGui::SetItemTooltip("Нажмите, чтобы выбрать или изменить градиент");
    ImGui::SetNextWindowSize(ImVec2(380, 0));
    if (ImGui::BeginPopup("##gradpop")) {
        sectionTitle("Наборы");
        auto presets = gradientPresets(primary, secondary);
        float sw = (ImGui::GetContentRegionAvail().x - 3 * 6) / 4;
        for (size_t i = 0; i < presets.size(); i++) {
            if (i % 4) ImGui::SameLine(0, 6);
            ImGui::PushID(int(i));
            ImVec2 q = ImGui::GetCursorScreenPos();
            if (ImGui::InvisibleButton("##preset", ImVec2(sw, 30))) {
                g = presets[i];
                changed = true;
                if (&g == &gradient) gradPreset = int(i);
            }
            drawGradientStrip(ImGui::GetWindowDrawList(), q, ImVec2(q.x + sw, q.y + 30), presets[i], 6);
            if (ImGui::IsItemHovered()) ImGui::GetWindowDrawList()->AddRect(q, ImVec2(q.x + sw, q.y + 30), IM_COL32_WHITE, 6, 0, 2);
            ImGui::SetItemTooltip("%s", presets[i].name.c_str());
            ImGui::PopID();
        }
        ImGui::Spacing();
        sectionTitle("Редактор");
        ImGui::TextDisabled("Клик по полосе — новая точка");
        static int selStop = 0;
        float ew = ImGui::GetContentRegionAvail().x;
        ImVec2 a = ImGui::GetCursorScreenPos();
        ImDrawList* dl = ImGui::GetWindowDrawList();
        drawGradientStrip(dl, a, ImVec2(a.x + ew, a.y + 28), g, 4);
        ImGui::InvisibleButton("##edit", ImVec2(ew, 28));
        if (ImGui::IsItemClicked()) {
            float t = std::clamp((ImGui::GetIO().MousePos.x - a.x) / ew, 0.f, 1.f);
            g.stops.push_back({t, g.sample(t)});
            selStop = int(g.stops.size()) - 1;
            edited = true;
        }
        selStop = std::clamp(selStop, 0, int(g.stops.size()) - 1);
        for (size_t i = 0; i < g.stops.size(); i++) {
            float x = a.x + g.stops[i].pos * ew;
            ImVec2 m(x, a.y + 30);
            ImGui::SetCursorScreenPos(ImVec2(x - 7, a.y + 29));
            ImGui::PushID(int(i) + 100);
            ImGui::InvisibleButton("##stop", ImVec2(14, 18));
            if (ImGui::IsItemActivated()) selStop = int(i);
            if (ImGui::IsItemActive() && ImGui::IsMouseDragging(0, 1.f)) {
                g.stops[i].pos = std::clamp((ImGui::GetIO().MousePos.x - a.x) / ew, 0.f, 1.f);
                edited = true;
            }
            ImGui::PopID();
            ImU32 border = int(i) == selStop ? kAccent : IM_COL32(200, 200, 210, 255);
            dl->AddTriangleFilled(ImVec2(m.x, m.y - 2), ImVec2(m.x - 6, m.y + 6), ImVec2(m.x + 6, m.y + 6), border);
            dl->AddRectFilled(ImVec2(m.x - 6, m.y + 6), ImVec2(m.x + 6, m.y + 16),
                              toU32({g.stops[i].color.r, g.stops[i].color.g, g.stops[i].color.b, 255}), 2);
            dl->AddRect(ImVec2(m.x - 6, m.y + 6), ImVec2(m.x + 6, m.y + 16), border, 2, 0, 1.5f);
        }
        ImGui::SetCursorScreenPos(ImVec2(a.x, a.y + 52));
        GradientStop& st = g.stops[size_t(selStop)];
        ImVec4 cv = toVec4(st.color);
        if (ImGui::ColorEdit4("Цвет точки", &cv.x, ImGuiColorEditFlags_AlphaBar | ImGuiColorEditFlags_AlphaPreviewHalf)) {
            st.color = fromVec4(cv);
            edited = true;
        }
        float pos = st.pos * 100;
        ImGui::SetNextItemWidth(140);
        if (ImGui::SliderFloat("Позиция", &pos, 0, 100, "%.0f%%")) {
            st.pos = pos / 100;
            edited = true;
        }
        ImGui::SameLine();
        ImGui::BeginDisabled(g.stops.size() <= 2);
        if (ImGui::Button("Удалить точку")) {
            g.stops.erase(g.stops.begin() + selStop);
            selStop = 0;
            edited = true;
        }
        ImGui::EndDisabled();
        if (edited && !ImGui::IsMouseDown(0)) {
            // re-sort once the drag is over, keeping the selection on the same stop
            GradientStop keep = g.stops[size_t(std::clamp(selStop, 0, int(g.stops.size()) - 1))];
            g.sort();
            for (size_t i = 0; i < g.stops.size(); i++)
                if (g.stops[i].pos == keep.pos && g.stops[i].color == keep.color) selStop = int(i);
        }
        ImGui::EndPopup();
    }
    ImGui::PopID();
    if (edited) {
        changed = true;
        if (&g == &gradient) gradPreset = -1;  // an edit turns the preset into a custom gradient
    }
    return changed;
}

bool Editor::brushPresetButton(const BrushPreset& p, bool selected, float w) {
    float h = 56;
    std::string key = p.name + "#" + std::to_string(int(p.shape)) + "#" + std::to_string(p.customId);
    auto it = brushPreviewTex.find(key);
    if (it == brushPreviewTex.end()) {
        // Render a sample S-stroke with the preset into a small texture.
        const int W = 160, H = 48;
        Coverage c;
        c.reset(W, H);
        BrushPreset q = p;
        q.size = std::clamp(p.size, 4.f, 26.f);
        q.scatter = std::min(q.scatter, 0.6f);
        q.aliased = false;
        if (q.buildup) q.flow = std::max(q.flow, 0.25f);
        BrushStamper st;
        st.reset(7);
        const BrushTip& tip = tipOf(q);
        float spacing = std::max(0.5f, q.size * q.spacing);
        Stroker sk;
        Vec2 prev{12, H * 0.5f};
        auto at = [&](float t) { return Vec2{12 + t * (W - 24), H * 0.5f + std::sin(t * 6.2831f) * H * 0.22f}; };
        sk.begin(at(0), [&](Vec2 v) { st.dab(c, q, tip, v.x, v.y, 0); });
        for (int i = 1; i <= 60; i++) {
            Vec2 v = at(i / 60.f);
            float dir = std::atan2(v.y - prev.y, v.x - prev.x) * 57.2958f;
            prev = v;
            sk.to(v, spacing, [&](Vec2 u) { st.dab(c, q, tip, u.x, u.y, dir); });
        }
        std::vector<uint8_t> rgba(size_t(W) * H * 4);
        for (size_t i = 0; i < c.v.size(); i++) {
            rgba[i * 4] = rgba[i * 4 + 1] = rgba[i * 4 + 2] = 255;
            rgba[i * 4 + 3] = c.v[i];
        }
        GLuint t;
        glGenTextures(1, &t);
        glBindTexture(GL_TEXTURE_2D, t);
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR);
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR);
        glPixelStorei(GL_UNPACK_ALIGNMENT, 1);
        glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA, W, H, 0, GL_RGBA, GL_UNSIGNED_BYTE, rgba.data());
        it = brushPreviewTex.emplace(key, t).first;
    }
    float iw = std::min(w - 8, 150.f), ih = iw * 48 / 160;
    h = ih + ImGui::GetFontSize() + 8;  // preview on top, label below
    ImVec2 a = ImGui::GetCursorScreenPos();
    bool pressed = ImGui::InvisibleButton(key.c_str(), ImVec2(w, h));
    bool hov = ImGui::IsItemHovered();
    ImDrawList* dl = ImGui::GetWindowDrawList();
    dl->AddRectFilled(a, ImVec2(a.x + w, a.y + h), selected ? IM_COL32(38, 128, 235, 70) : hov ? IM_COL32(255, 255, 255, 16) : IM_COL32(255, 255, 255, 6), 8);
    if (selected) dl->AddRect(a, ImVec2(a.x + w, a.y + h), kAccent, 8, 0, 1.5f);
    dl->AddImage(ImTextureID(uintptr_t(it->second)), ImVec2(a.x + (w - iw) * 0.5f, a.y + 2), ImVec2(a.x + (w + iw) * 0.5f, a.y + 2 + ih),
                 ImVec2(0, 0), ImVec2(1, 1), IM_COL32(230, 230, 240, 255));
    ImVec2 ts = ImGui::CalcTextSize(p.name.c_str());
    dl->PushClipRect(a, ImVec2(a.x + w, a.y + h), true);
    dl->AddText(ImVec2(a.x + std::max(4.f, (w - ts.x) * 0.5f), a.y + h - ts.y - 3), ImGui::GetColorU32(ImGuiCol_TextDisabled), p.name.c_str());
    dl->PopClipRect();
    if (hov) ImGui::SetTooltip("%s", p.name.c_str());
    return pressed;
}

// ---------------------------------------------------------------- bars

void Editor::drawOptionsBar() {
    ImGuiWindowFlags fl = ImGuiWindowFlags_NoScrollbar | ImGuiWindowFlags_NoSavedSettings;
    ImGui::PushStyleVar(ImGuiStyleVar_WindowPadding, ImVec2(10, 6));
    ImGui::PushStyleColor(ImGuiCol_WindowBg, IM_COL32(19, 20, 24, 255));
    float h = ImGui::GetFrameHeight() + 12;
    bool open = ImGui::BeginViewportSideBar("##options", ImGui::GetMainViewport(), ImGuiDir_Up, h, fl);
    ImGui::PopStyleColor();
    ImGui::PopStyleVar();
    if (!open) {
        ImGui::End();
        return;
    }
    {
        ImVec2 p = ImGui::GetCursorScreenPos();
        float s = ImGui::GetFrameHeight();
        ImGui::GetWindowDrawList()->AddRectFilled(p, ImVec2(p.x + s, p.y + s), kAccent, 7);
        drawToolIcon(ImGui::GetWindowDrawList(), tool, ImVec2(p.x + s * 0.5f, p.y + s * 0.5f), s * 0.6f, IM_COL32_WHITE);
        ImGui::Dummy(ImVec2(s, s));
        ImGui::SameLine();
        ImGui::AlignTextToFramePadding();
        if (gMediumFont) ImGui::PushFont(gMediumFont);
        ImGui::TextUnformatted(toolInfo(tool).name);
        if (gMediumFont) ImGui::PopFont();
        ImGui::SameLine(0, 18);
    }
    float sliderW = 120;
    auto pct = [&](const char* label, float& v, float lo = 0, float hi = 100) {
        ImGui::SetNextItemWidth(sliderW);
        float x = v * 100;
        if (ImGui::SliderFloat(label, &x, lo, hi, "%.0f%%")) v = x / 100;
    };
    auto selModeButtons = [&] {
        const char* names[] = {"Новая", "Добавить", "Вычесть", "Пересечь"};
        for (int i = 0; i < 4; i++) {
            if (i) ImGui::SameLine(0, 2);
            bool on = selMode == i;
            if (on) ImGui::PushStyleColor(ImGuiCol_Button, ImGui::GetStyleColorVec4(ImGuiCol_ButtonActive));
            if (ImGui::Button(names[i])) selMode = i;
            if (on) ImGui::PopStyleColor();
        }
        ImGui::SameLine(0, 16);
        ImGui::SetNextItemWidth(sliderW);
        ImGui::SliderFloat("Растушевка", &selFeather, 0, 100, "%.0f px");
    };
    auto tolOpts = [&] {
        ImGui::SetNextItemWidth(sliderW);
        ImGui::SliderInt("Допуск", &tolerance, 0, 255);
        ImGui::SameLine(0, 16);
        ImGui::Checkbox("Смежные", &contiguous);
        ImGui::SameLine(0, 16);
        ImGui::Checkbox("Все слои", &sampleMerged);
    };
    auto brushPicker = [&] {
        BrushPreset& p = brush().preset;
        ImVec2 a = ImGui::GetCursorScreenPos();
        float s = ImGui::GetFrameHeight();
        if (ImGui::Button("##brushpick", ImVec2(s * 2.4f, s))) ImGui::OpenPopup("##brushes");
        ImDrawList* dl = ImGui::GetWindowDrawList();
        ImVec2 c(a.x + s * 0.6f, a.y + s * 0.5f);
        float r = s * 0.34f;
        if (p.shape == TipShape::Round) {
            dl->AddCircleFilled(c, r * (0.55f + 0.45f * p.hardness), IM_COL32(230, 230, 240, 255));
            if (p.hardness < 0.9f) dl->AddCircle(c, r, IM_COL32(230, 230, 240, 90));
        } else {
            drawUiIcon(dl, UiIcon::Brush, c, s * 0.7f, IM_COL32(230, 230, 240, 255));
        }
        char sz[16];
        std::snprintf(sz, sizeof sz, "%.0f", p.size);
        dl->AddText(ImVec2(a.x + s * 1.2f, a.y + (s - ImGui::GetFontSize()) * 0.5f), IM_COL32(230, 230, 240, 255), sz);
        ImGui::SetItemTooltip("Набор кистей: %s", p.name.c_str());
        ImGui::SetNextWindowSize(ImVec2(540, 440));
        if (ImGui::BeginPopup("##brushes")) {
            ImGui::SetNextItemWidth(-1);
            ImGui::SliderFloat("##size", &p.size, 1, 1000, "Размер: %.0f px", ImGuiSliderFlags_Logarithmic);
            ImGui::BeginChild("##grid", ImVec2(0, 0));
            float tw = (ImGui::GetContentRegionAvail().x - 2 * 6) / 3;
            int i = 0;
            auto list = builtinBrushes();
            list.insert(list.end(), userBrushes.begin(), userBrushes.end());
            for (auto& b : list) {
                if (i++ % 3) ImGui::SameLine(0, 6);
                if (brushPresetButton(b, b.name == p.name, tw)) {
                    p = b;
                    if (tool == Tool::Pencil) p.aliased = true;
                }
            }
            ImGui::EndChild();
            ImGui::EndPopup();
        }
        ImGui::SameLine(0, 12);
    };

    switch (tool) {
        case Tool::Brush:
        case Tool::Pencil:
        case Tool::Eraser:
        case Tool::Clone:
        case Tool::SpotHeal: {
            ToolBrush& b = brush();
            brushPicker();
            ImGui::SetNextItemWidth(sliderW);
            ImGui::SliderFloat("Размер", &b.preset.size, 1, 1000, "%.0f px", ImGuiSliderFlags_Logarithmic);
            if (b.preset.shape == TipShape::Round && tool != Tool::Pencil) {
                ImGui::SameLine(0, 14);
                pct("Жёсткость", b.preset.hardness);
            }
            if (tool != Tool::SpotHeal) {
                ImGui::SameLine(0, 14);
                pct("Непрозр.", b.opacity, 1);
                ImGui::SameLine(0, 14);
                pct("Нажим", b.preset.flow, 1);
            }
            ImGui::SameLine(0, 14);
            pct("Сглаживание", smoothing, 0, 95);
            if (tool == Tool::Clone) {
                ImGui::SameLine(0, 14);
                ImGui::Checkbox("Все слои", &sampleMerged);
            }
            ImGui::SameLine(0, 10);
            if (iconButton("##brushset", UiIcon::Brush, "Настройки кисти (F5)")) showBrushSettings = !showBrushSettings;
            break;
        }
        case Tool::Blur:
        case Tool::Sharpen:
        case Tool::Smudge:
        case Tool::Dodge:
        case Tool::Burn:
        case Tool::Sponge: {
            ToolBrush& b = brush();
            ImGui::SetNextItemWidth(sliderW);
            ImGui::SliderFloat("Размер", &b.preset.size, 1, 1000, "%.0f px", ImGuiSliderFlags_Logarithmic);
            ImGui::SameLine(0, 14);
            pct("Жёсткость", b.preset.hardness);
            ImGui::SameLine(0, 14);
            pct(tool == Tool::Dodge || tool == Tool::Burn ? "Экспонир." : "Интенсивность", b.strength, 1);
            if (tool == Tool::Dodge || tool == Tool::Burn) {
                ImGui::SameLine(0, 14);
                const char* ranges[] = {"Тени", "Средние тона", "Света"};
                ImGui::SetNextItemWidth(140);
                ImGui::Combo("Диапазон", &dodgeRange, ranges, 3);
            }
            if (tool == Tool::Sponge) {
                ImGui::SameLine(0, 14);
                int m = spongeSaturate ? 1 : 0;
                const char* modes[] = {"Снизить насыщенность", "Повысить насыщенность"};
                ImGui::SetNextItemWidth(200);
                if (ImGui::Combo("Режим", &m, modes, 2)) spongeSaturate = m == 1;
            }
            ImGui::SameLine(0, 14);
            pct("Сглаживание", smoothing, 0, 95);
            break;
        }
        case Tool::RectSelect:
        case Tool::EllipseSelect:
        case Tool::Lasso:
        case Tool::PolyLasso: selModeButtons(); break;
        case Tool::MagicWand:
            selModeButtons();
            ImGui::SameLine(0, 16);
            tolOpts();
            break;
        case Tool::Bucket:
            tolOpts();
            ImGui::SameLine(0, 16);
            pct("Непрозр.", brush().opacity, 1);
            break;
        case Tool::Gradient: {
            if (gradPreset >= 0) gradient = gradientPresets(primary, secondary)[size_t(gradPreset)];
            gradientCombo("##grad", gradient, 180);
            ImGui::SameLine(0, 14);
            for (int i = 0; i < int(GradientType::Count); i++) {
                if (i) ImGui::SameLine(0, 2);
                bool on = int(gradType) == i;
                if (on) ImGui::PushStyleColor(ImGuiCol_Button, ImGui::GetStyleColorVec4(ImGuiCol_ButtonActive));
                if (ImGui::Button(gradientTypeName(GradientType(i)))) gradType = GradientType(i);
                if (on) ImGui::PopStyleColor();
            }
            ImGui::SameLine(0, 14);
            pct("Непрозр.", gradOpacity, 1);
            ImGui::SameLine(0, 14);
            ImGui::Checkbox("Инверсия", &gradReverse);
            ImGui::SameLine(0, 10);
            ImGui::Checkbox("Дизеринг", &gradDither);
            break;
        }
        case Tool::Text: {
            ImGui::SetNextItemWidth(200);
            const char* cur = fonts.empty() ? "(шрифты не найдены)" : fonts[size_t(std::clamp(fontIndex, 0, int(fonts.size()) - 1))].name.c_str();
            if (ImGui::BeginCombo("##font", cur, ImGuiComboFlags_HeightLarge)) {
                for (int i = 0; i < int(fonts.size()); i++)
                    if (ImGui::Selectable(fonts[size_t(i)].name.c_str(), i == fontIndex)) {
                        fontIndex = i;
                        textPreview();
                    }
                ImGui::EndCombo();
            }
            ImGui::SameLine();
            if (iconButton("##fontfile", UiIcon::Folder, "Загрузить шрифт из файла (.ttf, .otf)"))
                files.request(FileDialog::Mode::Open, "Файл шрифта", {{"Шрифты", "ttf,otf,ttc"}}, "", [this](const std::string& p) {
                    fonts.push_back({fileStem(p), p});
                    fontIndex = int(fonts.size()) - 1;
                    textPreview();
                });
            ImGui::SameLine(0, 16);
            ImGui::SetNextItemWidth(sliderW);
            if (ImGui::SliderFloat("Кегль", &fontSize, 6, 500, "%.0f px", ImGuiSliderFlags_Logarithmic)) textPreview();
            ImGui::SameLine(0, 16);
            ImVec4 v = toVec4(primary);
            if (ImGui::ColorEdit3("Цвет", &v.x, ImGuiColorEditFlags_NoInputs)) {
                primary = fromVec4(v);
                textPreview();
            }
            break;
        }
        case Tool::Shape: {
            const char* kinds[] = {"Прямоугольник", "Скруглённый", "Эллипс", "Линия", "Стрелка", "Многоугольник", "Звезда", "Сердце"};
            int k = int(shapeKind);
            ImGui::SetNextItemWidth(160);
            if (ImGui::Combo("##kind", &k, kinds, 8)) shapeKind = ShapeKind(k);
            bool lineLike = shapeKind == ShapeKind::Line || shapeKind == ShapeKind::Arrow;
            if (!lineLike) {
                ImGui::SameLine(0, 14);
                int f = shapeFilled ? 0 : 1;
                ImGui::RadioButton("Заливка", &f, 0);
                ImGui::SameLine();
                ImGui::RadioButton("Контур", &f, 1);
                shapeFilled = f == 0;
            }
            if (!shapeFilled || lineLike) {
                ImGui::SameLine(0, 14);
                ImGui::SetNextItemWidth(sliderW);
                ImGui::SliderFloat("Толщина", &shapeStroke, 1, 200, "%.0f px", ImGuiSliderFlags_Logarithmic);
            }
            if (shapeKind == ShapeKind::RoundRect) {
                ImGui::SameLine(0, 14);
                ImGui::SetNextItemWidth(sliderW);
                ImGui::SliderFloat("Радиус", &shapeRadius, 1, 300, "%.0f px");
            }
            if (shapeKind == ShapeKind::Polygon || shapeKind == ShapeKind::Star) {
                ImGui::SameLine(0, 14);
                ImGui::SetNextItemWidth(sliderW);
                ImGui::SliderInt("Углы", &shapeSides, 3, 24);
            }
            ImGui::SameLine(0, 14);
            ImGui::Checkbox("На новом слое", &shapeNewLayer);
            break;
        }
        case Tool::Crop:
            if (cropActive) {
                ImGui::Text("%d × %d px", cropRect.w(), cropRect.h());
                ImGui::SameLine(0, 16);
                if (ImGui::Button("Применить  (Enter)")) applyCrop();
                ImGui::SameLine();
                if (ImGui::Button("Отмена  (Esc)")) cropActive = false;
            } else {
                ImGui::TextDisabled("Нарисуйте рамку на холсте");
            }
            break;
        case Tool::Hand:
        case Tool::Zoom: {
            ImVec2 c(canvasMin.x + canvasSize.x * 0.5f, canvasMin.y + canvasSize.y * 0.5f);
            if (ImGui::Button("100%")) zoomAt(1.f, c);
            ImGui::SameLine();
            if (ImGui::Button("Целиком")) fitView();
            ImGui::SameLine();
            if (ImGui::Button(" + ")) zoomAt(zoom * 1.25f, c);
            ImGui::SameLine();
            if (ImGui::Button(" − ")) zoomAt(zoom / 1.25f, c);
            break;
        }
        case Tool::Move: ImGui::TextDisabled("Shift — только по горизонтали или вертикали"); break;
        case Tool::Eyedropper: ImGui::TextDisabled("Берёт цвет со всех видимых слоёв"); break;
        default: break;
    }
    ImGui::End();

    if (showBrushSettings) {
        ImGui::SetNextWindowSize(ImVec2(340, 0), ImGuiCond_FirstUseEver);
        ImGui::SetNextWindowPos(ImVec2(ImGui::GetMainViewport()->Pos.x + 100, ImGui::GetMainViewport()->Pos.y + 120), ImGuiCond_FirstUseEver);
        if (ImGui::Begin("Настройки кисти", &showBrushSettings, ImGuiWindowFlags_NoDocking | ImGuiWindowFlags_AlwaysAutoResize)) {
            if (!isBrushTool(tool)) {
                ImGui::TextDisabled("Выберите кисть, ластик или штамп");
            } else {
                BrushPreset& p = brush().preset;
                ImGui::Text("Кисть: %s", p.name.c_str());
                ImGui::SeparatorText("Отпечаток");
                ImGui::SliderFloat("Размер", &p.size, 1, 1000, "%.0f px", ImGuiSliderFlags_Logarithmic);
                if (p.shape == TipShape::Round) {
                    float hh = p.hardness * 100;
                    if (ImGui::SliderFloat("Жёсткость", &hh, 0, 100, "%.0f%%")) p.hardness = hh / 100;
                }
                float sp = p.spacing * 100;
                if (ImGui::SliderFloat("Интервалы", &sp, 1, 300, "%.0f%%")) p.spacing = sp / 100;
                ImGui::SliderFloat("Угол", &p.angle, -180, 180, "%.0f°");
                float rn = p.roundness * 100;
                if (ImGui::SliderFloat("Форма (округлость)", &rn, 5, 100, "%.0f%%")) p.roundness = rn / 100;
                ImGui::SeparatorText("Динамика");
                float sj = p.sizeJitter * 100, aj = p.angleJitter * 100, fj = p.flowJitter * 100, sc = p.scatter * 100;
                if (ImGui::SliderFloat("Колебание размера", &sj, 0, 100, "%.0f%%")) p.sizeJitter = sj / 100;
                if (ImGui::SliderFloat("Колебание угла", &aj, 0, 100, "%.0f%%")) p.angleJitter = aj / 100;
                if (ImGui::SliderFloat("Колебание нажима", &fj, 0, 100, "%.0f%%")) p.flowJitter = fj / 100;
                if (ImGui::SliderFloat("Рассеивание", &sc, 0, 500, "%.0f%%")) p.scatter = sc / 100;
                ImGui::SliderInt("Счётчик", &p.count, 1, 16);
                ImGui::Checkbox("Аэрограф (накопление)", &p.buildup);
                ImGui::Checkbox("Поворот по направлению штриха", &p.followStroke);
                ImGui::Checkbox("Пиксельные края", &p.aliased);
                ImGui::Spacing();
                if (ImGui::Button("Сохранить как новую кисть", ImVec2(-1, 0))) {
                    BrushPreset c = p;
                    c.name = p.name + " (моя)";
                    userBrushes.push_back(c);
                    p.name = c.name;
                }
            }
        }
        ImGui::End();
    }
}

void Editor::drawStatusBar() {
    ImGuiWindowFlags fl = ImGuiWindowFlags_NoScrollbar | ImGuiWindowFlags_NoSavedSettings;
    float pad = 5.f;
    ImGui::PushStyleVar(ImGuiStyleVar_WindowPadding, ImVec2(12, pad));
    ImGui::PushStyleColor(ImGuiCol_WindowBg, IM_COL32(16, 17, 20, 255));
    bool open = ImGui::BeginViewportSideBar("##status", ImGui::GetMainViewport(), ImGuiDir_Down, ImGui::GetTextLineHeight() + pad * 2, fl);
    ImGui::PopStyleColor();
    ImGui::PopStyleVar();
    if (!open) {
        ImGui::End();
        return;
    }
    ImGui::PushStyleVar(ImGuiStyleVar_ItemSpacing, ImVec2(22, 0));
    if (doc) {
        ImGui::Text("%.0f%%", zoom * 100);
        ImGui::SameLine();
        ImGui::Text("%d × %d px", doc->w, doc->h);
        ImGui::SameLine();
        ImGui::Text("Слоёв: %d", int(doc->layers.size()));
        ImGui::SameLine();
        int x = int(std::floor(curPt.x)), y = int(std::floor(curPt.y));
        if (x >= 0 && y >= 0 && x < doc->w && y < doc->h) {
            RGBA c = mergedPixel(x, y);
            ImGui::Text("X: %d  Y: %d", x, y);
            ImGui::SameLine();
            ImVec2 p = ImGui::GetCursorScreenPos();
            float s = ImGui::GetTextLineHeight();
            ImGui::GetWindowDrawList()->AddRectFilled(p, ImVec2(p.x + s, p.y + s), toU32({c.r, c.g, c.b, 255}), 3);
            ImGui::Dummy(ImVec2(s, s));
            ImGui::SameLine(0, 6);
            ImGui::Text("#%02X%02X%02X", c.r, c.g, c.b);
        } else {
            ImGui::TextDisabled("—");
        }
        ImGui::SameLine();
    }
    ImGui::TextDisabled("%s", status.empty() ? toolInfo(tool).hint : status.c_str());
    ImGui::PopStyleVar();
    ImGui::End();
}

// ---------------------------------------------------------------- panels

void Editor::drawToolbox() {
    ImGuiWindowClass wc;
    wc.DockNodeFlagsOverrideSet = ImGuiDockNodeFlags_NoTabBar;
    ImGui::SetNextWindowClass(&wc);
    ImGui::PushStyleVar(ImGuiStyleVar_WindowPadding, ImVec2(6, 8));
    ImGui::PushStyleColor(ImGuiCol_WindowBg, IM_COL32(19, 20, 24, 255));
    bool open = ImGui::Begin(kToolsWin, nullptr, ImGuiWindowFlags_NoScrollbar);
    ImGui::PopStyleColor();
    ImGui::PopStyleVar();
    if (!open) return ImGui::End();
    float bs = std::round(ImGui::GetFrameHeight() * 1.25f);
    float availW = ImGui::GetContentRegionAvail().x;
    int cols = std::max(1, int((availW + 3) / (bs + 3)));
    ImDrawList* dl = ImGui::GetWindowDrawList();
    const auto& groups = toolGroups();
    const std::vector<int> breaks = {1, 6, 9, 12, 14};
    int col = 0;
    for (int g = 0; g < int(groups.size()); g++) {
        if (std::find(breaks.begin(), breaks.end(), g) != breaks.end()) {
            if (col % cols) ImGui::NewLine();
            col = 0;
            ImVec2 p = ImGui::GetCursorScreenPos();
            dl->AddLine(ImVec2(p.x + 4, p.y + 2), ImVec2(p.x + availW - 4, p.y + 2), IM_COL32(48, 50, 60, 255));
            ImGui::Dummy(ImVec2(0, 4));
        }
        if (col++ % cols) ImGui::SameLine(0, 3);
        Tool t = groupTool.count(g) ? groupTool[g] : groups[size_t(g)][0];
        ImGui::PushID(g);
        ImVec2 p = ImGui::GetCursorScreenPos();
        bool clicked = ImGui::InvisibleButton("##tool", ImVec2(bs, bs), ImGuiButtonFlags_MouseButtonLeft | ImGuiButtonFlags_MouseButtonRight);
        bool hov = ImGui::IsItemHovered();
        bool multi = groups[size_t(g)].size() > 1;
        if (clicked && !ImGui::IsMouseReleased(ImGuiMouseButton_Right)) setTool(t);
        if (multi && (ImGui::IsItemClicked(ImGuiMouseButton_Right) || (ImGui::IsItemActive() && ImGui::GetIO().MouseDownDuration[0] > 0.35f)))
            ImGui::OpenPopup("##flyout");
        bool active = std::find(groups[size_t(g)].begin(), groups[size_t(g)].end(), tool) != groups[size_t(g)].end();
        if (active) {
            dl->AddRectFilled(p, ImVec2(p.x + bs, p.y + bs), kAccent, 8);
        } else if (hov) {
            dl->AddRectFilled(p, ImVec2(p.x + bs, p.y + bs), IM_COL32(44, 46, 56, 255), 8);
        }
        drawToolIcon(dl, t, ImVec2(p.x + bs * 0.5f, p.y + bs * 0.5f), bs * 0.56f, active ? IM_COL32_WHITE : IM_COL32(196, 198, 210, 255));
        if (multi)
            dl->AddTriangleFilled(ImVec2(p.x + bs - 3, p.y + bs - 8), ImVec2(p.x + bs - 3, p.y + bs - 3), ImVec2(p.x + bs - 8, p.y + bs - 3),
                                  IM_COL32(200, 202, 212, 170));
        if (ImGui::BeginItemTooltip()) {
            ImGui::Text("%s (%c)", toolInfo(t).name, char(std::toupper(int(toolInfo(t).key))));
            ImGui::TextDisabled("%s", toolInfo(t).hint);
            if (multi) ImGui::TextDisabled("Правый клик — другие инструменты группы, Shift+%c — переключить",
                                           char(std::toupper(int(toolInfo(t).key))));
            ImGui::EndTooltip();
        }
        if (ImGui::BeginPopup("##flyout")) {
            for (Tool x : groups[size_t(g)]) {
                ImGui::PushID(int(x));
                ImVec2 q = ImGui::GetCursorScreenPos();
                float rh = ImGui::GetFrameHeight() + 4;
                if (ImGui::Selectable("##item", x == tool, 0, ImVec2(290, rh))) setTool(x);
                ImDrawList* pdl = ImGui::GetWindowDrawList();
                drawToolIcon(pdl, x, ImVec2(q.x + rh * 0.5f, q.y + rh * 0.5f), rh * 0.6f, IM_COL32(220, 222, 230, 255));
                pdl->AddText(ImVec2(q.x + rh + 8, q.y + (rh - ImGui::GetFontSize()) * 0.5f), ImGui::GetColorU32(ImGuiCol_Text), toolInfo(x).name);
                char key[2] = {char(std::toupper(int(toolInfo(x).key))), 0};
                pdl->AddText(ImVec2(q.x + 274, q.y + (rh - ImGui::GetFontSize()) * 0.5f), ImGui::GetColorU32(ImGuiCol_TextDisabled), key);
                ImGui::PopID();
            }
            ImGui::EndPopup();
        }
        ImGui::PopID();
    }
    if (col % cols) ImGui::NewLine();
    ImGui::Dummy(ImVec2(0, 8));
    ImVec2 p = ImGui::GetCursorScreenPos();
    float s = bs * 0.95f;
    p.x += std::max(0.f, (availW - s * 1.45f) * 0.5f);
    ImGui::SetCursorScreenPos(ImVec2(p.x + s * 0.45f, p.y + s * 0.45f));
    if (ImGui::ColorButton("##sec", toVec4(secondary), ImGuiColorEditFlags_NoTooltip, ImVec2(s, s))) ImGui::OpenPopup("##secpick");
    ImGui::SetCursorScreenPos(p);
    if (ImGui::ColorButton("##pri", toVec4(primary), ImGuiColorEditFlags_NoTooltip, ImVec2(s, s))) ImGui::OpenPopup("##pripick");
    ImGui::SetCursorScreenPos(ImVec2(p.x, p.y + s * 1.5f));
    if (ImGui::SmallButton("⇄")) std::swap(primary, secondary);
    ImGui::SetItemTooltip("Поменять цвета (X)");
    for (int i = 0; i < 2; i++) {
        if (ImGui::BeginPopup(i ? "##secpick" : "##pripick")) {
            ImVec4 v = toVec4(i ? secondary : primary);
            if (ImGui::ColorPicker4("##pick", &v.x, ImGuiColorEditFlags_NoAlpha | ImGuiColorEditFlags_PickerHueWheel))
                (i ? secondary : primary) = fromVec4(v);
            ImGui::EndPopup();
        }
    }
    ImGui::End();
}

void Editor::drawHomeScreen() {
    ImDrawList* dl = ImGui::GetWindowDrawList();

    float w = std::min(canvasSize.x - 80, 940.f);
    float x0 = canvasMin.x + (canvasSize.x - w) * 0.5f, y = canvasMin.y + std::max(36.f, canvasSize.y * 0.07f);
    ImFont* mid = gMediumFont ? gMediumFont : ImGui::GetFont();
    drawLogo(dl, ImVec2(x0, y), 64);
    if (gTitleFont) dl->AddText(gTitleFont, gTitleFont->FontSize, ImVec2(x0 + 82, y + 2), IM_COL32(240, 240, 248, 255), "Добро пожаловать в ArtGraf");
    dl->AddText(ImVec2(x0 + 84, y + 42), IM_COL32(140, 142, 156, 255), "Создайте новый документ, откройте файл или перетащите картинку в окно");
    y += 94;

    ImGui::SetCursorScreenPos(ImVec2(x0, y));
    ImGui::PushStyleColor(ImGuiCol_Button, IM_COL32(38, 128, 235, 255));
    ImGui::PushStyleColor(ImGuiCol_ButtonHovered, IM_COL32(66, 146, 245, 255));
    ImGui::PushStyleVar(ImGuiStyleVar_FrameRounding, 10);
    if (ImGui::Button("Новый файл", ImVec2(170, 42))) cmdNew();
    ImGui::PopStyleColor(2);
    ImGui::SameLine(0, 10);
    if (ImGui::Button("Открыть…", ImVec2(150, 42))) cmdOpen();
    ImGui::PopStyleVar();
    y += 70;

    dl->AddText(mid, mid->FontSize, ImVec2(x0, y), IM_COL32(220, 220, 230, 255), "Быстрый старт");
    y += 32;
    struct Q { const char* name; int w, h; };
    const Q quick[] = {{"Full HD", 1920, 1080}, {"Квадрат", 1080, 1080}, {"A4", 2480, 3508}, {"Сторис", 1080, 1920}, {"4K UHD", 3840, 2160}, {"Иконка", 512, 512}};
    float cw = (w - 5 * 12) / 6, ch = 122;
    for (int i = 0; i < 6; i++) {
        ImVec2 a(x0 + i * (cw + 12), y);
        ImGui::SetCursorScreenPos(a);
        ImGui::PushID(i);
        bool clicked = ImGui::InvisibleButton("##quick", ImVec2(cw, ch));
        bool hov = ImGui::IsItemHovered();
        ImGui::PopID();
        dl->AddRectFilled(a, ImVec2(a.x + cw, a.y + ch), hov ? IM_COL32(38, 40, 50, 255) : IM_COL32(26, 27, 33, 255), 14);
        dl->AddRect(a, ImVec2(a.x + cw, a.y + ch), hov ? kAccent : IM_COL32(42, 44, 54, 255), 14, 0, 1.5f);
        float k = std::min((cw - 40) / quick[i].w, 56.f / quick[i].h);
        float rw = quick[i].w * k, rh = quick[i].h * k;
        ImVec2 r0(a.x + (cw - rw) * 0.5f, a.y + 16 + (56 - rh) * 0.5f);
        dl->AddRectFilled(r0, ImVec2(r0.x + rw, r0.y + rh), hov ? IM_COL32(255, 255, 255, 255) : IM_COL32(220, 220, 232, 255), 3);
        ImVec2 ts = ImGui::CalcTextSize(quick[i].name);
        dl->AddText(ImVec2(a.x + (cw - ts.x) * 0.5f, a.y + 80), IM_COL32(230, 230, 240, 255), quick[i].name);
        char buf[32];
        std::snprintf(buf, sizeof buf, "%d × %d", quick[i].w, quick[i].h);
        ts = ImGui::CalcTextSize(buf);
        dl->AddText(ImVec2(a.x + (cw - ts.x) * 0.5f, a.y + 99), IM_COL32(128, 130, 146, 255), buf);
        if (clicked) {
            auto d = std::make_unique<Document>(Document::blank(quick[i].w, quick[i].h, {255, 255, 255, 255}));
            d->title = "Без имени-" + std::to_string(docCounter++);
            openTab(std::move(d));
        }
    }
    y += ch + 34;

    dl->AddText(mid, mid->FontSize, ImVec2(x0, y), IM_COL32(220, 220, 230, 255), "Недавние файлы");
    y += 32;
    if (recentFiles.empty())
        dl->AddText(ImVec2(x0, y), IM_COL32(120, 122, 136, 255), "Здесь появятся файлы, которые вы открывали.");
    for (size_t i = 0; i < recentFiles.size() && i < 8; i++) {
        ImVec2 a(x0, y + i * 38.f);
        ImGui::SetCursorScreenPos(a);
        ImGui::PushID(int(i) + 50);
        bool clicked = ImGui::InvisibleButton("##recent", ImVec2(w, 34));
        bool hov = ImGui::IsItemHovered();
        ImGui::PopID();
        if (hov) dl->AddRectFilled(a, ImVec2(a.x + w, a.y + 34), IM_COL32(34, 36, 44, 255), 10);
        drawUiIcon(dl, lowerExt(recentFiles[i]) == "agf" ? UiIcon::Fx : UiIcon::File, ImVec2(a.x + 20, a.y + 17), 18, IM_COL32(90, 162, 248, 255));
        std::string nm = fileName(recentFiles[i]);
        dl->AddText(ImVec2(a.x + 40, a.y + 8), IM_COL32(230, 230, 240, 255), nm.c_str());
        float nameW = ImGui::CalcTextSize(nm.c_str()).x;
        dl->PushClipRect(a, ImVec2(a.x + w - 8, a.y + 34), true);
        dl->AddText(ImVec2(a.x + 56 + nameW, a.y + 8), IM_COL32(104, 106, 120, 255), recentFiles[i].c_str());
        dl->PopClipRect();
        if (clicked) openPath(recentFiles[i]);
    }
}

void Editor::drawTabs() {
    if (tabs.empty()) return;
    ImGui::PushStyleVar(ImGuiStyleVar_FramePadding, ImVec2(12, 6));
    if (ImGui::BeginTabBar("##docs", ImGuiTabBarFlags_FittingPolicyScroll | ImGuiTabBarFlags_TabListPopupButton)) {
        int closeReq = -1;
        for (int i = 0; i < int(tabs.size()); i++) {
            Document* d = tabs[size_t(i)].doc.get();
            char label[300];
            std::snprintf(label, sizeof label, "%s @ %.0f%%###tab%p", d->title.c_str(), (i == current ? zoom : tabs[size_t(i)].zoom) * 100,
                          static_cast<void*>(d));
            bool open = true;
            ImGuiTabItemFlags fl = d->dirty ? ImGuiTabItemFlags_UnsavedDocument : 0;
            if (i == current && tabSelectRequest) fl |= ImGuiTabItemFlags_SetSelected;
            if (ImGui::BeginTabItem(label, &open, fl)) {
                if (i != current && !tabSelectRequest) switchTab(i);
                ImGui::EndTabItem();
            }
            if (!open) closeReq = i;
        }
        ImGui::EndTabBar();
        tabSelectRequest = false;
        if (closeReq >= 0) closeTab(closeReq);
    }
    ImGui::PopStyleVar();
}

void Editor::drawCanvas() {
    ImGuiWindowClass wc;
    wc.DockNodeFlagsOverrideSet = ImGuiDockNodeFlags_NoTabBar;
    ImGui::SetNextWindowClass(&wc);
    ImGui::PushStyleVar(ImGuiStyleVar_WindowPadding, ImVec2(0, 0));
    ImGui::PushStyleColor(ImGuiCol_WindowBg, IM_COL32(11, 12, 14, 255));
    bool open = ImGui::Begin(kCanvasWin, nullptr, ImGuiWindowFlags_NoScrollbar | ImGuiWindowFlags_NoScrollWithMouse);
    ImGui::PopStyleColor();
    ImGui::PopStyleVar();
    if (!open) return ImGui::End();
    drawTabs();
    canvasMin = ImGui::GetCursorScreenPos();
    canvasSize = ImGui::GetContentRegionAvail();
    if (canvasSize.x < 8 || canvasSize.y < 8) return ImGui::End();
    if (!doc) {
        drawHomeScreen();
        return ImGui::End();
    }
    if (fitPending) {
        fitView();
        if (zoom > 1.f) {
            zoom = 1.f;
            pan = ImVec2((canvasSize.x - doc->w) * 0.5f, (canvasSize.y - doc->h) * 0.5f);
        }
        fitPending = false;
    }
    updateTexture();
    ImDrawList* dl = ImGui::GetWindowDrawList();
    dl->PushClipRect(canvasMin, ImVec2(canvasMin.x + canvasSize.x, canvasMin.y + canvasSize.y), true);
    ImVec2 a = toScreen({0, 0}), b = toScreen({float(doc->w), float(doc->h)});
    for (int i = 1; i <= 5; i++)
        dl->AddRectFilled(ImVec2(a.x - i * 2 + 3, a.y - i * 2 + 6), ImVec2(b.x + i * 2 + 3, b.y + i * 2 + 6), IM_COL32(0, 0, 0, 24), 4.f * i);
    dl->AddImage(ImTextureID(uintptr_t(tex)), a, b);
    dl->PopClipRect();

    ImGui::SetCursorScreenPos(canvasMin);
    ImGui::InvisibleButton("##canvas", canvasSize,
                           ImGuiButtonFlags_MouseButtonLeft | ImGuiButtonFlags_MouseButtonMiddle | ImGuiButtonFlags_MouseButtonRight);
    bool hovered = ImGui::IsItemHovered();
    canvasInput(hovered, ImGui::IsItemActive());
    if (!doc) return ImGui::End();
    dl->PushClipRect(canvasMin, ImVec2(canvasMin.x + canvasSize.x, canvasMin.y + canvasSize.y), true);
    drawOverlays(dl);
    dl->PopClipRect();
    ImGui::End();

    if (textEditing) {
        ImVec2 at = toScreen({textPos.x, textPos.y + fontSize * 1.3f});
        at.x = std::clamp(at.x, canvasMin.x, canvasMin.x + std::max(0.f, canvasSize.x - 380));
        at.y = std::clamp(at.y, canvasMin.y, canvasMin.y + std::max(0.f, canvasSize.y - 220));
        ImGui::SetNextWindowPos(at, ImGuiCond_Appearing);
        ImGui::SetNextWindowBgAlpha(0.97f);
        if (ImGui::Begin("Текст##edit", nullptr,
                         ImGuiWindowFlags_NoDocking | ImGuiWindowFlags_AlwaysAutoResize | ImGuiWindowFlags_NoSavedSettings | ImGuiWindowFlags_NoCollapse)) {
            if (textFocus) {
                ImGui::SetKeyboardFocusHere();
                textFocus = false;
            }
            if (ImGui::InputTextMultiline("##text", &textBuf, ImVec2(360, ImGui::GetTextLineHeight() * 4.5f))) textPreview();
            bool ctrlEnter = ImGui::IsItemFocused() && ImGui::GetIO().KeyCtrl && ImGui::IsKeyPressed(ImGuiKey_Enter);
            ImVec4 v = toVec4(primary);
            if (ImGui::ColorEdit3("##col", &v.x, ImGuiColorEditFlags_NoInputs)) {
                primary = fromVec4(v);
                textPreview();
            }
            ImGui::SameLine();
            ImGui::SetNextItemWidth(160);
            if (ImGui::SliderFloat("Кегль", &fontSize, 6, 500, "%.0f px", ImGuiSliderFlags_Logarithmic)) textPreview();
            ImGui::PushStyleColor(ImGuiCol_Button, IM_COL32(38, 128, 235, 255));
            bool apply = ImGui::Button("Применить");
            ImGui::PopStyleColor();
            if (apply || ctrlEnter) {
                while (!textBuf.empty() && (textBuf.back() == '\n' || textBuf.back() == '\r')) textBuf.pop_back();
                commitText();
            }
            ImGui::SameLine();
            if (ImGui::Button("Отмена")) cancelText();
            ImGui::SameLine();
            ImGui::TextDisabled("Ctrl+Enter");
        }
        ImGui::End();
    }
}

void Editor::drawColors() {
    if (colorTabFocus > 0 && --colorTabFocus == 0) ImGui::SetWindowFocus(kColorWin);
    if (!ImGui::Begin(kColorWin)) return ImGui::End();
    static bool editSecondary = false;
    if (ImGui::RadioButton("Основной", !editSecondary)) editSecondary = false;
    ImGui::SameLine();
    if (ImGui::RadioButton("Фоновый", editSecondary)) editSecondary = true;
    ImGui::SameLine();
    if (ImGui::SmallButton("⇄")) std::swap(primary, secondary);
    ImGui::SetItemTooltip("Поменять местами (X)");
    ImGui::SameLine();
    if (ImGui::SmallButton("Ч/Б")) {
        primary = {0, 0, 0, 255};
        secondary = {255, 255, 255, 255};
    }
    ImGui::SetItemTooltip("Цвета по умолчанию (D)");
    RGBA& c = editSecondary ? secondary : primary;
    ImVec4 v = toVec4(c);
    float fh = ImGui::GetFrameHeightWithSpacing();
    float pickerW = std::min({ImGui::GetContentRegionAvail().x, 280.f, ImGui::GetContentRegionAvail().y - fh * 5.4f});
    ImGui::SetNextItemWidth(std::max(pickerW, 120.f));
    if (ImGui::ColorPicker4("##picker", &v.x,
                            ImGuiColorEditFlags_NoAlpha | ImGuiColorEditFlags_PickerHueWheel | ImGuiColorEditFlags_NoSidePreview |
                                ImGuiColorEditFlags_DisplayRGB | ImGuiColorEditFlags_DisplayHex))
        c = fromVec4(v);
    static const RGBA palette[] = {
        {0, 0, 0, 255},       {64, 64, 64, 255},    {128, 128, 128, 255}, {192, 192, 192, 255}, {255, 255, 255, 255},
        {231, 76, 60, 255},   {230, 126, 34, 255},  {241, 196, 15, 255},  {46, 204, 113, 255},  {26, 188, 156, 255},
        {52, 152, 219, 255},  {128, 64, 200, 255},  {155, 89, 182, 255},  {232, 67, 147, 255},  {121, 85, 72, 255},
        {255, 205, 178, 255}, {181, 131, 90, 255},  {44, 62, 80, 255},    {127, 0, 0, 255},     {0, 100, 0, 255},
        {0, 0, 139, 255},     {255, 0, 255, 255},   {0, 255, 255, 255},   {255, 255, 0, 255},
    };
    float sw = ImGui::GetFrameHeight() * 0.8f;
    int perRow = std::max(1, int(ImGui::GetContentRegionAvail().x / (sw + 4)));
    auto swatches = [&](const RGBA* list, int n, int base) {
        for (int i = 0; i < n; i++) {
            if (i % perRow) ImGui::SameLine(0, 4);
            ImGui::PushID(base + i);
            if (ImGui::ColorButton("##p", toVec4(list[i]), ImGuiColorEditFlags_NoTooltip, ImVec2(sw, sw))) primary = list[i];
            if (ImGui::IsItemClicked(ImGuiMouseButton_Right)) secondary = list[i];
            ImGui::PopID();
        }
    };
    swatches(palette, int(std::size(palette)), 0);
    if (!recentColors.empty()) {
        ImGui::TextDisabled("Недавние");
        swatches(recentColors.data(), int(recentColors.size()), 100);
    }
    ImGui::End();
}

void Editor::drawBrushes() {
    if (!ImGui::Begin(kBrushesWin)) return ImGui::End();
    Tool target = isBrushTool(tool) && !isRetouchTool(tool) ? tool : Tool::Brush;
    BrushPreset& cur = tb[target].preset;
    ImGui::SetNextItemWidth(-ImGui::GetFrameHeight() * 2 - 12);
    ImGui::SliderFloat("##bsize", &cur.size, 1, 1000, "Размер: %.0f px", ImGuiSliderFlags_Logarithmic);
    ImGui::SameLine();
    if (iconButton("##bimport", UiIcon::Folder, "Кисть из изображения…")) cmdBrushFromFile();
    ImGui::SameLine();
    if (iconButton("##bset", UiIcon::Brush, "Настройки кисти (F5)")) showBrushSettings = !showBrushSettings;
    ImGui::BeginChild("##bgrid");
    float avail = ImGui::GetContentRegionAvail().x;
    int cols = std::max(1, int((avail + 6) / 110));
    float tw = (avail - (cols - 1) * 6) / cols;
    auto list = builtinBrushes();
    list.insert(list.end(), userBrushes.begin(), userBrushes.end());
    int i = 0;
    for (auto& b : list) {
        if (i++ % cols) ImGui::SameLine(0, 6);
        if (brushPresetButton(b, b.name == cur.name, tw)) {
            if (!isBrushTool(tool) || isRetouchTool(tool)) setTool(Tool::Brush);
            BrushPreset& dst = tb[tool].preset;
            dst = b;
            if (tool == Tool::Pencil) dst.aliased = true;
        }
    }
    ImGui::EndChild();
    ImGui::End();
}

void Editor::drawLayers() {
    if (!ImGui::Begin(kLayersWin)) return ImGui::End();
    if (!doc) {
        ImGui::TextDisabled("Нет документа");
        return ImGui::End();
    }
    updateThumbs();
    Layer& cur = doc->layer();
    ImGui::SetNextItemWidth(ImGui::GetContentRegionAvail().x * 0.55f);
    if (ImGui::BeginCombo("##blend", blendName(cur.blend), ImGuiComboFlags_HeightLarge)) {
        for (int i = 0; i < int(BlendMode::Count); i++) {
            if (i == 1 || i == 5 || i == 9 || i == 12) ImGui::Separator();
            if (ImGui::Selectable(blendName(BlendMode(i)), cur.blend == BlendMode(i)) && cur.blend != BlendMode(i)) {
                doc->push("Режим наложения");
                doc->layer().blend = BlendMode(i);
                invalidateAll();
            }
        }
        ImGui::EndCombo();
    }
    ImGui::SameLine();
    float op = doc->layer().opacity * 100;
    ImGui::SetNextItemWidth(-1);
    bool changed = ImGui::SliderFloat("##opacity", &op, 0, 100, "%.0f%%");
    ImGui::SetItemTooltip("Непрозрачность слоя");
    if (ImGui::IsItemActivated()) doc->push("Непрозрачность слоя");
    if (changed) {
        doc->layer().opacity = op / 100;
        invalidateAll();
    }

    float rowH = 50;
    float buttonsH = ImGui::GetFrameHeightWithSpacing() + 6;
    ImGui::PushStyleColor(ImGuiCol_ChildBg, IM_COL32(15, 16, 19, 255));
    ImGui::BeginChild("##list", ImVec2(0, -buttonsH), ImGuiChildFlags_Borders);
    ImGui::PopStyleColor();
    int moveFrom = -1, moveTo = -1;
    std::function<void()> deferred;
    for (int i = int(doc->layers.size()) - 1; i >= 0; i--) {
        Layer& L = doc->layers[size_t(i)];
        ImGui::PushID(i);
        ImVec2 rowMin = ImGui::GetCursorScreenPos();
        float rowW = ImGui::GetContentRegionAvail().x;
        bool selected = i == doc->active;
        ImDrawList* dl = ImGui::GetWindowDrawList();
        if (selected) dl->AddRectFilled(rowMin, ImVec2(rowMin.x + rowW, rowMin.y + rowH), IM_COL32(38, 128, 235, 60), 8);
        if (ImGui::Selectable("##row", false, ImGuiSelectableFlags_AllowDoubleClick | ImGuiSelectableFlags_AllowOverlap, ImVec2(rowW, rowH))) {
            if (doc->active != i) {
                cancelLive();
                if (textEditing) commitText();
                doc->active = i;
            }
            if (ImGui::IsMouseDoubleClicked(0)) {
                renaming = i;
                renameBuf = L.name;
            }
        }
        if (ImGui::BeginDragDropSource()) {
            ImGui::SetDragDropPayload("AG_LAYER", &i, sizeof(int));
            ImGui::Text("%s", L.name.c_str());
            ImGui::EndDragDropSource();
        }
        if (ImGui::BeginDragDropTarget()) {
            if (const ImGuiPayload* pl = ImGui::AcceptDragDropPayload("AG_LAYER")) {
                moveFrom = *static_cast<const int*>(pl->Data);
                moveTo = i;
            }
            ImGui::EndDragDropTarget();
        }
        if (ImGui::BeginPopupContextItem("##ctx")) {
            if (ImGui::MenuItem("Переименовать")) { renaming = i; renameBuf = L.name; }
            if (ImGui::MenuItem("Параметры наложения…")) deferred = [this, i] { doc->active = i; cmdOpenLayerStyle(); };
            if (ImGui::MenuItem("Дублировать"))
                deferred = [this, i] { doc->active = i; layerAction("Дублировать слой", [](Document& d) { d.duplicateLayer(); }); };
            if (ImGui::MenuItem("Объединить с нижним", nullptr, false, i > 0))
                deferred = [this, i] { doc->active = i; layerAction("Объединить с нижним", [](Document& d) { d.mergeDown(); }); };
            if (ImGui::MenuItem("Удалить", nullptr, false, doc->layers.size() > 1))
                deferred = [this, i] { doc->active = i; layerAction("Удалить слой", [](Document& d) { d.deleteLayer(); }); };
            ImGui::EndPopup();
        }
        float ib = ImGui::GetFrameHeight();
        ImGui::SetCursorScreenPos(ImVec2(rowMin.x + 4, rowMin.y + (rowH - ib) * 0.5f));
        if (iconButton("##vis", L.visible ? UiIcon::Eye : UiIcon::EyeOff, "Видимость слоя")) {
            doc->layers[size_t(i)].visible = !L.visible;
            doc->dirty = true;
            dirty = {0, 0, doc->w, doc->h};
        }
        float tx = rowMin.x + 10 + ib;
        if (size_t(i) < thumbs.size()) {
            float k = std::min(56.f / doc->w, 40.f / doc->h);
            ImVec2 ts(doc->w * k, doc->h * k);
            ImVec2 tp(tx + (56 - ts.x) * 0.5f, rowMin.y + (rowH - ts.y) * 0.5f);
            dl->AddImageRounded(ImTextureID(uintptr_t(thumbs[size_t(i)])), tp, ImVec2(tp.x + ts.x, tp.y + ts.y), ImVec2(0, 0), ImVec2(1, 1),
                                IM_COL32_WHITE, 4);
            dl->AddRect(ImVec2(tp.x - 1, tp.y - 1), ImVec2(tp.x + ts.x + 1, tp.y + ts.y + 1), selected ? kAccent : IM_COL32(60, 62, 72, 255), 5);
        }
        ImVec2 np(tx + 66, rowMin.y + (rowH - ImGui::GetFrameHeight()) * 0.5f);
        ImGui::SetCursorScreenPos(np);
        float fxW = L.fx.any() ? ib + 4 : 0;
        if (renaming == i) {
            ImGui::SetNextItemWidth(rowW - (np.x - rowMin.x) - 6 - fxW);
            ImGui::SetKeyboardFocusHere();
            if (ImGui::InputText("##name", &renameBuf, ImGuiInputTextFlags_EnterReturnsTrue | ImGuiInputTextFlags_AutoSelectAll)) {
                if (!renameBuf.empty() && renameBuf != L.name) {
                    doc->push("Переименовать слой");
                    doc->layers[size_t(i)].name = renameBuf;
                }
                renaming = -1;
            } else if (ImGui::IsItemDeactivated()) {
                renaming = -1;
            }
        } else {
            ImVec2 tpos(np.x, np.y + ImGui::GetStyle().FramePadding.y);
            ImU32 tc = ImGui::GetColorU32(L.visible ? ImGuiCol_Text : ImGuiCol_TextDisabled);
            dl->PushClipRect(np, ImVec2(rowMin.x + rowW - fxW - 4, rowMin.y + rowH), true);
            dl->AddText(tpos, tc, L.name.c_str());
            dl->PopClipRect();
        }
        if (L.fx.any()) {
            ImGui::SetCursorScreenPos(ImVec2(rowMin.x + rowW - ib - 4, rowMin.y + (rowH - ib) * 0.5f));
            if (iconButton("##fx", UiIcon::Fx, "Стиль слоя")) deferred = [this, i] { doc->active = i; cmdOpenLayerStyle(); };
        }
        ImGui::SetCursorScreenPos(ImVec2(rowMin.x, rowMin.y + rowH + 3));
        ImGui::Dummy(ImVec2(0, 0));
        ImGui::PopID();
    }
    ImGui::EndChild();
    if (deferred) deferred();
    if (moveFrom >= 0 && moveTo >= 0 && moveFrom != moveTo) {
        layerAction("Порядок слоёв", [moveFrom, moveTo](Document& d) {
            Layer l = std::move(d.layers[size_t(moveFrom)]);
            d.layers.erase(d.layers.begin() + moveFrom);
            d.layers.insert(d.layers.begin() + moveTo, std::move(l));
            d.active = moveTo;
        });
    }

    ImGui::Dummy(ImVec2(0, 2));
    if (iconButton("##lfx", UiIcon::Fx, "Стиль слоя (тень, свечение, обводка…)")) cmdOpenLayerStyle();
    ImGui::SameLine(0, 2);
    if (iconButton("##lnew", UiIcon::Plus, "Новый слой (Ctrl+Shift+N)")) layerAction("Новый слой", [](Document& d) { d.addLayer(d.nextLayerName()); });
    ImGui::SameLine(0, 2);
    if (iconButton("##ldup", UiIcon::Duplicate, "Дублировать слой")) layerAction("Дублировать слой", [](Document& d) { d.duplicateLayer(); });
    ImGui::SameLine(0, 2);
    if (iconButton("##lup", UiIcon::Up, "Выше (Ctrl+])", doc->active + 1 < int(doc->layers.size())))
        layerAction("Порядок слоёв", [](Document& d) { d.moveLayer(1); });
    ImGui::SameLine(0, 2);
    if (iconButton("##ldown", UiIcon::Down, "Ниже (Ctrl+[)", doc->active > 0)) layerAction("Порядок слоёв", [](Document& d) { d.moveLayer(-1); });
    ImGui::SameLine(0, 2);
    if (iconButton("##lmerge", UiIcon::Merge, "Объединить с нижним (Ctrl+E)", doc->active > 0))
        layerAction("Объединить с нижним", [](Document& d) { d.mergeDown(); });
    ImGui::SameLine(0, 2);
    if (iconButton("##ldel", UiIcon::Trash, "Удалить слой", doc->layers.size() > 1)) layerAction("Удалить слой", [](Document& d) { d.deleteLayer(); });
    ImGui::End();
}

void Editor::drawHistory() {
    if (!ImGui::Begin(kHistoryWin)) return ImGui::End();
    if (!doc) {
        ImGui::TextDisabled("Нет документа");
        return ImGui::End();
    }
    size_t nu = doc->undoStack.size(), nr = doc->redoStack.size();
    int target = -1;
    for (size_t k = 0; k <= nu + nr; k++) {
        std::string name;
        if (k == 0) name = "Исходное состояние";
        else if (k <= nu) name = doc->undoStack[k - 1].name;
        else name = doc->redoStack[nr - (k - nu)].name;
        bool currentStep = k == nu;
        if (k > nu) ImGui::PushStyleColor(ImGuiCol_Text, ImGui::GetStyleColorVec4(ImGuiCol_TextDisabled));
        ImGui::PushID(int(k));
        if (ImGui::Selectable(name.c_str(), currentStep)) target = int(k);
        if (currentStep && ImGui::IsWindowAppearing()) ImGui::SetScrollHereY();
        ImGui::PopID();
        if (k > nu) ImGui::PopStyleColor();
    }
    if (target >= 0) {
        while (int(doc->undoStack.size()) > target) cmdUndo();
        while (int(doc->undoStack.size()) < target && doc->canRedo()) cmdRedo();
    }
    ImGui::End();
}

void Editor::drawNavigator() {
    if (!ImGui::Begin(kNavWin)) return ImGui::End();
    if (!doc || !tex) {
        ImGui::TextDisabled("Нет документа");
        return ImGui::End();
    }
    ImVec2 avail = ImGui::GetContentRegionAvail();
    avail.y -= ImGui::GetFrameHeightWithSpacing();
    float k = std::min(avail.x / doc->w, avail.y / doc->h);
    if (k <= 0) return ImGui::End();
    ImVec2 sz(doc->w * k, doc->h * k);
    ImVec2 p = ImGui::GetCursorScreenPos();
    p.x += (avail.x - sz.x) * 0.5f;
    ImGui::SetCursorScreenPos(p);
    ImGui::Image(ImTextureID(uintptr_t(tex)), sz);
    if (ImGui::IsItemHovered() && ImGui::IsMouseDown(0)) {
        ImVec2 m = ImGui::GetIO().MousePos;
        Vec2 d{(m.x - p.x) / k, (m.y - p.y) / k};
        pan = ImVec2(canvasSize.x * 0.5f - d.x * zoom, canvasSize.y * 0.5f - d.y * zoom);
    }
    Vec2 a = toDoc(canvasMin), b = toDoc(ImVec2(canvasMin.x + canvasSize.x, canvasMin.y + canvasSize.y));
    ImVec2 ra(p.x + std::max(0.f, a.x) * k, p.y + std::max(0.f, a.y) * k);
    ImVec2 rb(p.x + std::min(float(doc->w), b.x) * k, p.y + std::min(float(doc->h), b.y) * k);
    ImGui::GetWindowDrawList()->AddRect(ra, rb, kAccent2, 3, 0, 2.f);
    float z = zoom * 100;
    ImGui::SetNextItemWidth(-1);
    if (ImGui::SliderFloat("##zoom", &z, 1, 3200, "%.0f%%", ImGuiSliderFlags_Logarithmic))
        zoomAt(z / 100, ImVec2(canvasMin.x + canvasSize.x * 0.5f, canvasMin.y + canvasSize.y * 0.5f));
    ImGui::End();
}

// ---------------------------------------------------------------- shortcuts

void Editor::handleShortcuts() {
    ImGuiIO& io = ImGui::GetIO();
    if (io.WantTextInput) return;
    if (ImGui::IsPopupOpen("", ImGuiPopupFlags_AnyPopupId)) return;
    bool C = io.KeyCtrl, S = io.KeyShift, A = io.KeyAlt;
    auto pressed = [](ImGuiKey k) { return ImGui::IsKeyPressed(k, false); };
    auto repeat = [](ImGuiKey k) { return ImGui::IsKeyPressed(k, true); };
    ImVec2 center(canvasMin.x + canvasSize.x * 0.5f, canvasMin.y + canvasSize.y * 0.5f);

    if (C) {
        if (pressed(ImGuiKey_N) && S) layerAction("Новый слой", [](Document& d) { d.addLayer(d.nextLayerName()); });
        else if (pressed(ImGuiKey_N) && A) cmdNewFromClipboard();
        else if (pressed(ImGuiKey_N)) cmdNew();
        if (pressed(ImGuiKey_O)) cmdOpen();
        if (pressed(ImGuiKey_P) && S) cmdPlace();
        if (pressed(ImGuiKey_S)) cmdSave(S);
        if (pressed(ImGuiKey_E) && S) cmdExport();
        else if (pressed(ImGuiKey_E) && doc && doc->active > 0) layerAction("Объединить с нижним", [](Document& d) { d.mergeDown(); });
        if (pressed(ImGuiKey_W) && doc) closeTab(current);
        if (pressed(ImGuiKey_Tab) && tabs.size() > 1) switchTab((current + (S ? int(tabs.size()) - 1 : 1)) % int(tabs.size()));
        if (repeat(ImGuiKey_Z)) (S ? cmdRedo() : cmdUndo());
        if (repeat(ImGuiKey_Y)) cmdRedo();
        if (pressed(ImGuiKey_X)) cmdCut();
        if (pressed(ImGuiKey_C) && A) {
            if (doc) { sizeW = doc->w; sizeH = doc->h; anchor = 4; popupToOpen = "Размер холста"; }
        } else if (pressed(ImGuiKey_C)) cmdCopy(S);
        if (pressed(ImGuiKey_V)) cmdPaste();
        if (pressed(ImGuiKey_A)) cmdSelectAll();
        if (pressed(ImGuiKey_D)) cmdDeselect();
        if (pressed(ImGuiKey_I) && S) cmdInvertSelection();
        else if (pressed(ImGuiKey_I) && A) {
            if (doc) { sizeW = doc->w; sizeH = doc->h; popupToOpen = "Размер изображения"; }
        } else if (pressed(ImGuiKey_I)) instantFilter("Инверсия", invert);
        if (pressed(ImGuiKey_U) && S) instantFilter("Обесцветить", desaturate);
        else if (pressed(ImGuiKey_U))
            openFilter({"Цветовой тон/Насыщенность", {{"Цветовой тон", -180, 180, 0}, {"Насыщенность", -100, 100, 0}, {"Яркость", -100, 100, 0}},
                        [](Image& i, const std::vector<float>& v) { hueSaturation(i, v[0], v[1], v[2]); }, {}});
        if (pressed(ImGuiKey_L) && S) instantFilter("Автоконтраст", autoContrast);
        else if (pressed(ImGuiKey_L))
            openFilter({"Уровни", {{"Чёрная точка", 0, 254, 0, true}, {"Белая точка", 1, 255, 255, true}, {"Гамма", 0.1f, 5.f, 1.f},
                                   {"Выход: чёрный", 0, 255, 0, true}, {"Выход: белый", 0, 255, 255, true}},
                        [](Image& i, const std::vector<float>& v) { levels(i, int(v[0]), int(v[1]), v[2], int(v[3]), int(v[4])); }, {}});
        if (pressed(ImGuiKey_M)) openCurves();
        if (pressed(ImGuiKey_B) && A && S)
            openFilter({"Чёрно-белое",
                        {{"Красные", -200, 300, 40}, {"Жёлтые", -200, 300, 60}, {"Зелёные", -200, 300, 40},
                         {"Голубые", -200, 300, 60}, {"Синие", -200, 300, 20}, {"Пурпурные", -200, 300, 80}},
                        [](Image& i, const std::vector<float>& v) { blackWhite(i, v[0], v[1], v[2], v[3], v[4], v[5]); }, {}});
        else if (pressed(ImGuiKey_B))
            openFilter({"Цветовой баланс", {{"Голубой — Красный", -100, 100, 0}, {"Пурпурный — Зелёный", -100, 100, 0}, {"Жёлтый — Синий", -100, 100, 0}},
                        [](Image& i, const std::vector<float>& v) { colorBalance(i, v[0], v[1], v[2]); }, {}});
        if (pressed(ImGuiKey_T)) cmdTransform();
        if (pressed(ImGuiKey_J)) cmdLayerViaCopy();
        if (pressed(ImGuiKey_RightBracket)) layerAction("Порядок слоёв", [](Document& d) { d.moveLayer(1); });
        if (pressed(ImGuiKey_LeftBracket)) layerAction("Порядок слоёв", [](Document& d) { d.moveLayer(-1); });
        if (repeat(ImGuiKey_Equal) || repeat(ImGuiKey_KeypadAdd)) zoomAt(zoom * 1.25f, center);
        if (repeat(ImGuiKey_Minus) || repeat(ImGuiKey_KeypadSubtract)) zoomAt(zoom / 1.25f, center);
        if (pressed(ImGuiKey_0)) fitView();
        if (pressed(ImGuiKey_1)) zoomAt(1.f, center);
        if (pressed(ImGuiKey_Apostrophe)) showGrid = !showGrid;
        if (pressed(ImGuiKey_Backspace)) cmdFill(secondary, "Заливка фоновым цветом");
        return;
    }
    if (A && pressed(ImGuiKey_Backspace)) return cmdFill(primary, "Заливка основным цветом");
    if (A) return;
    if (pressed(ImGuiKey_F1)) showShortcuts = !showShortcuts;
    if (pressed(ImGuiKey_F5)) showBrushSettings = !showBrushSettings;
    if (S && pressed(ImGuiKey_F6) && doc && doc->sel.active()) popupToOpen = "Растушевка";
    // Tool keys: plain key selects the group's current tool, Shift+key cycles through the group.
    const auto& groups = toolGroups();
    for (int g = 0; g < int(groups.size()); g++) {
        SDL_Keycode k = toolInfo(groups[size_t(g)][0]).key;
        if (!pressed(ImGuiKey(ImGuiKey_A + (k - SDLK_a)))) continue;
        const auto& list = groups[size_t(g)];
        Tool curT = groupTool.count(g) ? groupTool[g] : list[0];
        if (S && list.size() > 1) {
            size_t idx = size_t(std::find(list.begin(), list.end(), curT) - list.begin());
            setTool(list[(idx + 1) % list.size()]);
        } else if (!S) {
            setTool(curT);
        }
    }
    if (pressed(ImGuiKey_K) && !S) setTool(Tool::Bucket);
    if (S) {
        if (tool == Tool::Move && doc) {
            if (repeat(ImGuiKey_LeftArrow)) nudge(-10, 0);
            if (repeat(ImGuiKey_RightArrow)) nudge(10, 0);
            if (repeat(ImGuiKey_UpArrow)) nudge(0, -10);
            if (repeat(ImGuiKey_DownArrow)) nudge(0, 10);
        }
        return;
    }
    if (pressed(ImGuiKey_X)) std::swap(primary, secondary);
    if (pressed(ImGuiKey_D)) {
        primary = {0, 0, 0, 255};
        secondary = {255, 255, 255, 255};
    }
    if (isBrushTool(tool) || tool == Tool::Bucket) {
        ToolBrush& b = brush();
        float& sz = b.preset.size;
        if (repeat(ImGuiKey_LeftBracket)) sz = std::max(1.f, sz < 10 ? sz - 1 : sz / 1.15f);
        if (repeat(ImGuiKey_RightBracket)) sz = std::min(1000.f, sz < 10 ? sz + 1 : sz * 1.15f);
        for (int i = 0; i <= 9; i++)
            if (pressed(ImGuiKey(ImGuiKey_0 + i))) b.opacity = i == 0 ? 1.f : i / 10.f;
    }
    if (pressed(ImGuiKey_Delete) || pressed(ImGuiKey_Backspace)) cmdClear();
    if (pressed(ImGuiKey_Enter) || pressed(ImGuiKey_KeypadEnter)) {
        if (cropActive) applyCrop();
        if (polyActive) finishPolyLasso();
    }
    if (pressed(ImGuiKey_Escape)) {
        if (cropActive) cropActive = false;
        else if (polyActive) {
            polyActive = false;
            lasso.clear();
        } else if (dragging) {
            dragging = false;
            cancelLive();
            lasso.clear();
        }
    }
    if (tool == Tool::Move && doc) {
        if (repeat(ImGuiKey_LeftArrow)) nudge(-1, 0);
        if (repeat(ImGuiKey_RightArrow)) nudge(1, 0);
        if (repeat(ImGuiKey_UpArrow)) nudge(0, -1);
        if (repeat(ImGuiKey_DownArrow)) nudge(0, 1);
    }
}

}  // namespace ag
