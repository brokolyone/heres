#include <cmath>
#include <cstdlib>
#include <cstring>
#include <filesystem>

#include <imgui_internal.h>
#include <imgui_stdlib.h>

#include "editor.h"
#include "filters.h"
#include "icons.h"
#include "io.h"

namespace ag {

namespace {

const char* kToolsWin = "Инструменты";
const char* kCanvasWin = "Холст";
const char* kColorWin = "Цвет";
const char* kLayersWin = "Слои";
const char* kHistoryWin = "История";
const char* kNavWin = "Навигатор";

bool exists(const std::string& p) {
    std::error_code ec;
#if defined(__cpp_char8_t)
    return std::filesystem::exists(std::filesystem::path(std::u8string(p.begin(), p.end())), ec);
#else
    return std::filesystem::exists(std::filesystem::u8path(p), ec);
#endif
}

}  // namespace

// ---------------------------------------------------------------- setup

void Editor::scanFonts() {
    fonts.clear();
    std::string win = std::getenv("WINDIR") ? std::getenv("WINDIR") : "C:/Windows";
    std::string wf = win + "/Fonts/";
    const std::pair<const char*, const char*> windowsFonts[] = {
        {"Arial", "arial.ttf"},          {"Arial Bold", "arialbd.ttf"},       {"Arial Italic", "ariali.ttf"},
        {"Segoe UI", "segoeui.ttf"},     {"Segoe UI Bold", "segoeuib.ttf"},   {"Calibri", "calibri.ttf"},
        {"Verdana", "verdana.ttf"},      {"Tahoma", "tahoma.ttf"},            {"Trebuchet MS", "trebuc.ttf"},
        {"Times New Roman", "times.ttf"}, {"Times New Roman Bold", "timesbd.ttf"}, {"Georgia", "georgia.ttf"},
        {"Cambria", "cambria.ttc"},      {"Courier New", "cour.ttf"},         {"Consolas", "consola.ttf"},
        {"Comic Sans MS", "comic.ttf"},  {"Impact", "impact.ttf"},
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
        static const ImWchar extra[] = {0x2010, 0x205E, 0x2190, 0x21FF, 0x2212, 0x2212, 0x2300, 0x23FF, 0x25A0, 0x25FF, 0};
        b.AddRanges(extra);
        b.BuildRanges(&ranges);
    }
    std::string win = std::getenv("WINDIR") ? std::getenv("WINDIR") : "C:/Windows";
    const std::string candidates[] = {win + "/Fonts/segoeui.ttf", win + "/Fonts/arial.ttf",
                                      "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
                                      "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf"};
    for (auto& path : candidates) {
        std::vector<uint8_t> data;
        if (!readFile(path, data) || data.empty()) continue;
        ImFontConfig cfg;
        cfg.FontDataOwnedByAtlas = true;
        void* mem = IM_ALLOC(data.size());
        std::memcpy(mem, data.data(), data.size());
        if (io.Fonts->AddFontFromMemoryTTF(mem, int(data.size()), std::round(15.f * scale), &cfg, ranges.Data)) return;
    }
    ImFontConfig cfg;
    cfg.SizePixels = std::round(13.f * scale);
    io.Fonts->AddFontDefault(&cfg);  // ASCII only: Cyrillic will show as '?'
}

void Editor::setupStyle(float scale) {
    ImGuiStyle& s = ImGui::GetStyle();
    ImGui::StyleColorsDark();
    s.WindowRounding = 4;
    s.FrameRounding = 4;
    s.PopupRounding = 6;
    s.GrabRounding = 4;
    s.TabRounding = 4;
    s.ScrollbarRounding = 6;
    s.WindowBorderSize = 1;
    s.FrameBorderSize = 0;
    s.WindowPadding = ImVec2(8, 8);
    s.FramePadding = ImVec2(6, 4);
    s.ItemSpacing = ImVec2(8, 6);
    s.WindowMenuButtonPosition = ImGuiDir_None;
    ImVec4* c = s.Colors;
    auto rgb = [](int r, int g, int b, float a = 1.f) { return ImVec4(r / 255.f, g / 255.f, b / 255.f, a); };
    c[ImGuiCol_WindowBg] = rgb(43, 45, 49);
    c[ImGuiCol_ChildBg] = rgb(36, 37, 41);
    c[ImGuiCol_PopupBg] = rgb(43, 45, 49);
    c[ImGuiCol_MenuBarBg] = rgb(36, 37, 41);
    c[ImGuiCol_Border] = rgb(68, 71, 78);
    c[ImGuiCol_FrameBg] = rgb(30, 31, 34);
    c[ImGuiCol_FrameBgHovered] = rgb(52, 54, 60);
    c[ImGuiCol_FrameBgActive] = rgb(60, 63, 70);
    c[ImGuiCol_TitleBg] = rgb(36, 37, 41);
    c[ImGuiCol_TitleBgActive] = rgb(36, 37, 41);
    c[ImGuiCol_Button] = rgb(52, 54, 60);
    c[ImGuiCol_ButtonHovered] = rgb(66, 69, 77);
    c[ImGuiCol_ButtonActive] = rgb(61, 139, 253);
    c[ImGuiCol_Header] = rgb(61, 139, 253, 0.35f);
    c[ImGuiCol_HeaderHovered] = rgb(61, 139, 253, 0.55f);
    c[ImGuiCol_HeaderActive] = rgb(61, 139, 253, 0.8f);
    c[ImGuiCol_CheckMark] = rgb(61, 139, 253);
    c[ImGuiCol_SliderGrab] = rgb(61, 139, 253);
    c[ImGuiCol_SliderGrabActive] = rgb(110, 168, 254);
    c[ImGuiCol_Tab] = rgb(36, 37, 41);
    c[ImGuiCol_TabHovered] = rgb(61, 139, 253, 0.6f);
    c[ImGuiCol_TabSelected] = rgb(52, 54, 60);
    c[ImGuiCol_TabDimmed] = rgb(36, 37, 41);
    c[ImGuiCol_TabDimmedSelected] = rgb(46, 48, 53);
    c[ImGuiCol_DockingPreview] = rgb(61, 139, 253, 0.6f);
    c[ImGuiCol_DockingEmptyBg] = rgb(24, 25, 27);
    c[ImGuiCol_Separator] = rgb(68, 71, 78);
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
    drawLayers();
    drawHistory();
    drawNavigator();
    drawDialogs();
    files.draw();
    updateTitle();
}

void Editor::drawDockspace() {
    ImGuiViewport* vp = ImGui::GetMainViewport();
    ImGuiID dock = ImGui::GetID("ArtGrafDock");
    if (layoutReset) {
        layoutReset = false;
        ImGui::DockBuilderRemoveNode(dock);
        ImGui::DockBuilderAddNode(dock, ImGuiDockNodeFlags_DockSpace);
        ImGui::DockBuilderSetNodeSize(dock, vp->WorkSize);
        ImGuiID center = dock;
        float toolW = 58.f * ImGui::GetStyle().ItemSpacing.x / 8.f;
        ImGuiID left = ImGui::DockBuilderSplitNode(center, ImGuiDir_Left, toolW / vp->WorkSize.x, nullptr, &center);
        ImGuiID right = ImGui::DockBuilderSplitNode(center, ImGuiDir_Right, 0.22f, nullptr, &center);
        ImGuiID rightBottom;
        ImGuiID rightTop = ImGui::DockBuilderSplitNode(right, ImGuiDir_Up, 0.40f, nullptr, &rightBottom);
        ImGuiID rightLow;
        ImGuiID rightMid = ImGui::DockBuilderSplitNode(rightBottom, ImGuiDir_Up, 0.62f, nullptr, &rightLow);
        ImGui::DockBuilderDockWindow(kToolsWin, left);
        ImGui::DockBuilderDockWindow(kCanvasWin, center);
        ImGui::DockBuilderDockWindow(kColorWin, rightTop);
        ImGui::DockBuilderDockWindow(kLayersWin, rightMid);
        ImGui::DockBuilderDockWindow(kHistoryWin, rightLow);
        ImGui::DockBuilderDockWindow(kNavWin, rightLow);
        ImGui::DockBuilderFinish(dock);
    }
    ImGui::DockSpaceOverViewport(dock, vp);
}

// ---------------------------------------------------------------- menu

void Editor::drawMenuBar() {
    if (!ImGui::BeginMainMenuBar()) return;
    bool d = doc != nullptr;
    bool sel = d && doc->sel.active();
    drawLogo(ImGui::GetWindowDrawList(), ImVec2(ImGui::GetCursorScreenPos().x, ImGui::GetCursorScreenPos().y + 2),
             ImGui::GetFrameHeight() - 4);
    ImGui::Dummy(ImVec2(ImGui::GetFrameHeight() - 2, 0));

    if (ImGui::BeginMenu("Файл")) {
        if (ImGui::MenuItem("Новый…", "Ctrl+N")) cmdNew();
        if (ImGui::MenuItem("Открыть…", "Ctrl+O")) cmdOpen();
        if (ImGui::MenuItem("Поместить как слой…", "Ctrl+Shift+P", false, d)) cmdPlace();
        ImGui::Separator();
        if (ImGui::MenuItem("Сохранить проект", "Ctrl+S", false, d)) cmdSave(false);
        if (ImGui::MenuItem("Сохранить проект как…", "Ctrl+Shift+S", false, d)) cmdSave(true);
        if (ImGui::MenuItem("Экспорт в PNG/JPEG/BMP/TGA…", "Ctrl+Shift+E", false, d)) cmdExport();
        ImGui::Separator();
        if (ImGui::MenuItem("Закрыть документ", "Ctrl+W", false, d)) guardUnsaved([this] { setDocument(nullptr); });
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
        if (ImGui::MenuItem("Очистить", "Delete", false, d)) cmdClear();
        ImGui::Separator();
        if (ImGui::MenuItem("Трансформирование слоя…", "Ctrl+T", false, d)) cmdTransform();
        ImGui::EndMenu();
    }
    if (ImGui::BeginMenu("Изображение")) {
        if (ImGui::BeginMenu("Коррекция", d)) {
            if (ImGui::MenuItem("Яркость/Контраст…"))
                openFilter({"Яркость/Контраст", {{"Яркость", -100, 100, 0}, {"Контраст", -100, 100, 0}},
                            [](Image& i, const std::vector<float>& v) { brightnessContrast(i, v[0], v[1]); }});
            if (ImGui::MenuItem("Уровни…", "Ctrl+L"))
                openFilter({"Уровни",
                            {{"Чёрная точка", 0, 254, 0, true}, {"Белая точка", 1, 255, 255, true}, {"Гамма", 0.1f, 5.f, 1.f},
                             {"Выход: чёрный", 0, 255, 0, true}, {"Выход: белый", 0, 255, 255, true}},
                            [](Image& i, const std::vector<float>& v) {
                                levels(i, int(v[0]), int(v[1]), v[2], int(v[3]), int(v[4]));
                            }});
            if (ImGui::MenuItem("Цветовой тон/Насыщенность…", "Ctrl+U"))
                openFilter({"Цветовой тон/Насыщенность",
                            {{"Цветовой тон", -180, 180, 0}, {"Насыщенность", -100, 100, 0}, {"Яркость", -100, 100, 0}},
                            [](Image& i, const std::vector<float>& v) { hueSaturation(i, v[0], v[1], v[2]); }});
            if (ImGui::MenuItem("Цветовой баланс…", "Ctrl+B"))
                openFilter({"Цветовой баланс",
                            {{"Голубой — Красный", -100, 100, 0}, {"Пурпурный — Зелёный", -100, 100, 0},
                             {"Жёлтый — Синий", -100, 100, 0}},
                            [](Image& i, const std::vector<float>& v) { colorBalance(i, v[0], v[1], v[2]); }});
            ImGui::Separator();
            if (ImGui::MenuItem("Автоконтраст", "Ctrl+Shift+L")) instantFilter("Автоконтраст", autoContrast);
            if (ImGui::MenuItem("Обесцветить", "Ctrl+Shift+U")) instantFilter("Обесцветить", desaturate);
            if (ImGui::MenuItem("Инверсия", "Ctrl+I")) instantFilter("Инверсия", invert);
            if (ImGui::MenuItem("Сепия")) instantFilter("Сепия", sepia);
            if (ImGui::MenuItem("Постеризация…"))
                openFilter({"Постеризация", {{"Уровни", 2, 32, 4, true}},
                            [](Image& i, const std::vector<float>& v) { posterize(i, int(v[0])); }});
            if (ImGui::MenuItem("Порог…"))
                openFilter({"Порог", {{"Порог", 1, 255, 128, true}},
                            [](Image& i, const std::vector<float>& v) { threshold(i, int(v[0])); }});
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
        if (ImGui::MenuItem("Новый слой", "Ctrl+Shift+N", false, d))
            layerAction("Новый слой", [](Document& x) { x.addLayer(x.nextLayerName()); });
        if (ImGui::MenuItem("Скопировать на новый слой", "Ctrl+J", false, d)) cmdLayerViaCopy();
        if (ImGui::MenuItem("Дублировать слой", nullptr, false, d)) layerAction("Дублировать слой", [](Document& x) { x.duplicateLayer(); });
        if (ImGui::MenuItem("Удалить слой", nullptr, false, d && doc->layers.size() > 1))
            layerAction("Удалить слой", [](Document& x) { x.deleteLayer(); });
        ImGui::Separator();
        if (ImGui::MenuItem("Слой выше", "Ctrl+]", false, d)) layerAction("Порядок слоёв", [](Document& x) { x.moveLayer(1); });
        if (ImGui::MenuItem("Слой ниже", "Ctrl+[", false, d)) layerAction("Порядок слоёв", [](Document& x) { x.moveLayer(-1); });
        ImGui::Separator();
        if (ImGui::MenuItem("Отразить слой по горизонтали", nullptr, false, d)) cmdFlipLayer(true);
        if (ImGui::MenuItem("Отразить слой по вертикали", nullptr, false, d)) cmdFlipLayer(false);
        ImGui::Separator();
        if (ImGui::MenuItem("Объединить с нижним", "Ctrl+E", false, d && doc->active > 0))
            layerAction("Объединить с нижним", [](Document& x) { x.mergeDown(); });
        if (ImGui::MenuItem("Выполнить сведение", nullptr, false, d))
            layerAction("Выполнить сведение", [](Document& x) { x.flattenAll(); });
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
                openFilter({"Размытие по Гауссу", {{"Радиус, px", 0.5f, 100, 4}},
                            [](Image& i, const std::vector<float>& v) { gaussianBlur(i, v[0]); }});
            if (ImGui::MenuItem("Размытие в движении…"))
                openFilter({"Размытие в движении", {{"Угол, °", -180, 180, 0}, {"Смещение, px", 1, 200, 20, true}},
                            [](Image& i, const std::vector<float>& v) { motionBlur(i, v[0], int(v[1])); }});
            ImGui::EndMenu();
        }
        if (ImGui::BeginMenu("Усиление резкости")) {
            if (ImGui::MenuItem("Контурная резкость…"))
                openFilter({"Контурная резкость", {{"Эффект, %", 1, 500, 100}, {"Радиус, px", 0.5f, 50, 1.5f}, {"Порог", 0, 255, 0, true}},
                            [](Image& i, const std::vector<float>& v) { unsharpMask(i, v[1], v[0], int(v[2])); }});
            if (ImGui::MenuItem("Резкость"))
                instantFilter("Резкость", [](Image& i) { unsharpMask(i, 1.f, 80.f, 0); });
            ImGui::EndMenu();
        }
        if (ImGui::BeginMenu("Шум")) {
            if (ImGui::MenuItem("Добавить шум…"))
                openFilter({"Добавить шум", {{"Количество", 1, 100, 12}, {"Монохромный (0/1)", 0, 1, 0, true}},
                            [](Image& i, const std::vector<float>& v) { addNoise(i, v[0], v[1] > 0.5f, 1234u); }});
            if (ImGui::MenuItem("Медиана (уменьшить шум)"))
                instantFilter("Уменьшить шум", [](Image& i) { gaussianBlur(i, 0.8f); });
            ImGui::EndMenu();
        }
        if (ImGui::BeginMenu("Оформление")) {
            if (ImGui::MenuItem("Пикселизация…"))
                openFilter({"Пикселизация", {{"Размер ячейки, px", 2, 200, 10, true}},
                            [](Image& i, const std::vector<float>& v) { pixelate(i, int(v[0])); }});
            ImGui::EndMenu();
        }
        if (ImGui::BeginMenu("Стилизация")) {
            if (ImGui::MenuItem("Тиснение")) instantFilter("Тиснение", emboss);
            if (ImGui::MenuItem("Выделение краёв")) instantFilter("Выделение краёв", findEdges);
            if (ImGui::MenuItem("Масляная краска…"))
                openFilter({"Масляная краска", {{"Радиус, px", 1, 8, 3, true}, {"Уровни", 4, 40, 20, true}},
                            [](Image& i, const std::vector<float>& v) { oilPaint(i, int(v[0]), int(v[1])); }});
            ImGui::EndMenu();
        }
        if (ImGui::MenuItem("Виньетка…"))
            openFilter({"Виньетка", {{"Сила, %", 0, 100, 50}},
                        [](Image& i, const std::vector<float>& v) { vignette(i, v[0]); }});
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

// ---------------------------------------------------------------- bars

void Editor::drawOptionsBar() {
    ImGuiWindowFlags fl = ImGuiWindowFlags_NoScrollbar | ImGuiWindowFlags_NoSavedSettings;
    float h = ImGui::GetFrameHeight() + ImGui::GetStyle().WindowPadding.y * 2;
    if (!ImGui::BeginViewportSideBar("##options", ImGui::GetMainViewport(), ImGuiDir_Up, h, fl)) {
        ImGui::End();
        return;
    }
    ImGui::AlignTextToFramePadding();
    ImGui::TextUnformatted(toolInfo(tool).name);
    ImGui::SameLine(0, 20);
    float sliderW = 130;
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
        ImGui::Checkbox("Смежные пиксели", &contiguous);
        ImGui::SameLine(0, 16);
        ImGui::Checkbox("Все слои", &sampleMerged);
    };
    switch (tool) {
        case Tool::Brush:
        case Tool::Pencil:
        case Tool::Eraser:
        case Tool::Clone: {
            BrushOptions& b = brush();
            ImGui::SetNextItemWidth(sliderW);
            ImGui::SliderFloat("Размер", &b.size, 1, 1000, "%.0f px", ImGuiSliderFlags_Logarithmic);
            if (tool != Tool::Pencil) {
                ImGui::SameLine(0, 16);
                ImGui::SetNextItemWidth(sliderW);
                float hp = b.hardness * 100;
                if (ImGui::SliderFloat("Жёсткость", &hp, 0, 100, "%.0f%%")) b.hardness = hp / 100;
            }
            ImGui::SameLine(0, 16);
            ImGui::SetNextItemWidth(sliderW);
            float op = b.opacity * 100;
            if (ImGui::SliderFloat("Непрозрачность", &op, 1, 100, "%.0f%%")) b.opacity = op / 100;
            if (tool == Tool::Clone) {
                ImGui::SameLine(0, 16);
                ImGui::Checkbox("Образец со всех слоёв", &sampleMerged);
            }
            break;
        }
        case Tool::RectSelect:
        case Tool::EllipseSelect:
        case Tool::Lasso: selModeButtons(); break;
        case Tool::MagicWand:
            selModeButtons();
            ImGui::SameLine(0, 16);
            tolOpts();
            break;
        case Tool::Bucket: {
            tolOpts();
            ImGui::SameLine(0, 16);
            ImGui::SetNextItemWidth(sliderW);
            float op = brush().opacity * 100;
            if (ImGui::SliderFloat("Непрозрачность", &op, 1, 100, "%.0f%%")) brush().opacity = op / 100;
            break;
        }
        case Tool::Gradient: {
            int type = gradRadial ? 1 : 0;
            ImGui::RadioButton("Линейный", &type, 0);
            ImGui::SameLine();
            ImGui::RadioButton("Радиальный", &type, 1);
            gradRadial = type == 1;
            ImGui::SameLine(0, 16);
            ImGui::Checkbox("Основной → прозрачный", &gradToTransparent);
            ImGui::SameLine(0, 16);
            ImVec2 p = ImGui::GetCursorScreenPos();
            float gh = ImGui::GetFrameHeight();
            RGBA c1 = gradToTransparent ? RGBA{primary.r, primary.g, primary.b, 0} : secondary;
            ImGui::GetWindowDrawList()->AddRectFilledMultiColor(p, ImVec2(p.x + 140, p.y + gh), toU32(primary), toU32(c1),
                                                                 toU32(c1), toU32(primary));
            ImGui::Dummy(ImVec2(140, gh));
            break;
        }
        case Tool::Text: {
            ImGui::SetNextItemWidth(200);
            const char* cur = fonts.empty() ? "(шрифты не найдены)" : fonts[size_t(std::clamp(fontIndex, 0, int(fonts.size()) - 1))].name.c_str();
            if (ImGui::BeginCombo("Шрифт", cur)) {
                for (int i = 0; i < int(fonts.size()); i++)
                    if (ImGui::Selectable(fonts[size_t(i)].name.c_str(), i == fontIndex)) {
                        fontIndex = i;
                        textPreview();
                    }
                ImGui::EndCombo();
            }
            ImGui::SameLine();
            if (ImGui::Button("Другой…"))
                files.request(FileDialog::Mode::Open, "Файл шрифта", {{"Шрифты", "ttf,otf,ttc"}}, "", [this](const std::string& p) {
                    fonts.push_back({fileStem(p), p});
                    fontIndex = int(fonts.size()) - 1;
                    textPreview();
                });
            ImGui::SameLine(0, 16);
            ImGui::SetNextItemWidth(sliderW);
            if (ImGui::SliderFloat("Размер", &fontSize, 6, 500, "%.0f px", ImGuiSliderFlags_Logarithmic)) textPreview();
            break;
        }
        case Tool::Shape: {
            const char* kinds[] = {"Прямоугольник", "Эллипс", "Линия"};
            int k = int(shapeKind);
            ImGui::SetNextItemWidth(150);
            if (ImGui::Combo("##kind", &k, kinds, 3)) shapeKind = ShapeKind(k);
            if (shapeKind != ShapeKind::Line) {
                ImGui::SameLine(0, 16);
                int f = shapeFilled ? 0 : 1;
                ImGui::RadioButton("Заливка", &f, 0);
                ImGui::SameLine();
                ImGui::RadioButton("Обводка", &f, 1);
                shapeFilled = f == 0;
            }
            if (!shapeFilled || shapeKind == ShapeKind::Line) {
                ImGui::SameLine(0, 16);
                ImGui::SetNextItemWidth(sliderW);
                ImGui::SliderFloat("Толщина", &shapeStroke, 1, 200, "%.0f px", ImGuiSliderFlags_Logarithmic);
            }
            ImGui::SameLine(0, 16);
            ImGui::Checkbox("На новом слое", &shapeNewLayer);
            break;
        }
        case Tool::Crop:
            if (cropActive) {
                ImGui::Text("%d × %d px", cropRect.w(), cropRect.h());
                ImGui::SameLine(0, 16);
                if (ImGui::Button("Применить (Enter)")) applyCrop();
                ImGui::SameLine();
                if (ImGui::Button("Отмена (Esc)")) cropActive = false;
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
            if (ImGui::Button("+")) zoomAt(zoom * 1.25f, c);
            ImGui::SameLine();
            if (ImGui::Button("−")) zoomAt(zoom / 1.25f, c);
            break;
        }
        case Tool::Move:
            ImGui::TextDisabled("Shift — только по горизонтали или вертикали");
            break;
        case Tool::Eyedropper:
            ImGui::TextDisabled("Берёт цвет со всех видимых слоёв");
            break;
        default: break;
    }
    ImGui::End();
}

void Editor::drawStatusBar() {
    ImGuiWindowFlags fl = ImGuiWindowFlags_NoScrollbar | ImGuiWindowFlags_NoSavedSettings;
    float pad = 4.f;
    ImGui::PushStyleVar(ImGuiStyleVar_WindowPadding, ImVec2(10, pad));
    bool open = ImGui::BeginViewportSideBar("##status", ImGui::GetMainViewport(), ImGuiDir_Down,
                                            ImGui::GetTextLineHeight() + pad * 2, fl);
    ImGui::PopStyleVar();
    if (!open) {
        ImGui::End();
        return;
    }
    ImGui::PushStyleVar(ImGuiStyleVar_ItemSpacing, ImVec2(24, 0));
    if (doc) {
        ImGui::Text("%.0f%%", zoom * 100);
        ImGui::SameLine();
        ImGui::Text("%d × %d px", doc->w, doc->h);
        ImGui::SameLine();
        int x = int(std::floor(curPt.x)), y = int(std::floor(curPt.y));
        if (x >= 0 && y >= 0 && x < doc->w && y < doc->h) {
            RGBA c = mergedPixel(x, y);
            ImGui::Text("X: %d  Y: %d", x, y);
            ImGui::SameLine();
            ImVec2 p = ImGui::GetCursorScreenPos();
            float s = ImGui::GetTextLineHeight();
            ImGui::GetWindowDrawList()->AddRectFilled(p, ImVec2(p.x + s, p.y + s), toU32({c.r, c.g, c.b, 255}));
            ImGui::Dummy(ImVec2(s, s));
            ImGui::SameLine(0, 6);
            ImGui::Text("#%02X%02X%02X  A:%d", c.r, c.g, c.b, c.a);
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
    ImGui::PushStyleVar(ImGuiStyleVar_WindowPadding, ImVec2(4, 6));
    bool open = ImGui::Begin(kToolsWin, nullptr, ImGuiWindowFlags_NoScrollbar);
    ImGui::PopStyleVar();
    if (!open) return ImGui::End();
    float bs = std::round(ImGui::GetFrameHeight() * 1.45f);
    int cols = std::max(1, int((ImGui::GetContentRegionAvail().x + 2) / (bs + 2)));
    ImDrawList* dl = ImGui::GetWindowDrawList();
    const Tool groups[][4] = {
        {Tool::Move, Tool::Count},
        {Tool::RectSelect, Tool::EllipseSelect, Tool::Lasso, Tool::MagicWand},
        {Tool::Crop, Tool::Eyedropper, Tool::Count},
        {Tool::Brush, Tool::Pencil, Tool::Eraser, Tool::Clone},
        {Tool::Gradient, Tool::Bucket, Tool::Count},
        {Tool::Text, Tool::Shape, Tool::Count},
        {Tool::Hand, Tool::Zoom, Tool::Count},
    };
    for (auto& g : groups) {
        int col = 0;
        for (Tool t : g) {
            if (t == Tool::Count) break;
            if (col++ % cols) ImGui::SameLine(0, 2);
            ImGui::PushID(int(t));
            ImVec2 p = ImGui::GetCursorScreenPos();
            if (ImGui::InvisibleButton("##tool", ImVec2(bs, bs))) setTool(t);
            bool hov = ImGui::IsItemHovered();
            ImU32 bg = t == tool ? IM_COL32(61, 139, 253, 255) : hov ? IM_COL32(66, 69, 77, 255) : 0;
            if (bg) dl->AddRectFilled(p, ImVec2(p.x + bs, p.y + bs), bg, 4);
            drawToolIcon(dl, t, ImVec2(p.x + bs * 0.5f, p.y + bs * 0.5f), bs * 0.56f, IM_COL32(225, 226, 230, 255));
            if (ImGui::BeginItemTooltip()) {
                char key = char(std::toupper(int(toolInfo(t).key)));
                ImGui::Text("%s (%c)", toolInfo(t).name, key);
                ImGui::TextDisabled("%s", toolInfo(t).hint);
                ImGui::EndTooltip();
            }
            ImGui::PopID();
        }
        ImGui::Dummy(ImVec2(0, 2));
    }
    // Color swatches: primary overlaps secondary.
    ImGui::Dummy(ImVec2(0, 4));
    ImVec2 p = ImGui::GetCursorScreenPos();
    float s = bs * 0.8f;
    ImVec2 secMin(p.x + s * 0.45f, p.y + s * 0.45f);
    ImGui::SetCursorScreenPos(secMin);
    if (ImGui::ColorButton("##sec", toVec4(secondary), ImGuiColorEditFlags_NoTooltip, ImVec2(s, s))) ImGui::OpenPopup("##secpick");
    ImGui::SetCursorScreenPos(p);
    if (ImGui::ColorButton("##pri", toVec4(primary), ImGuiColorEditFlags_NoTooltip, ImVec2(s, s))) ImGui::OpenPopup("##pripick");
    ImGui::SetCursorScreenPos(ImVec2(p.x, p.y + s * 1.5f));
    if (ImGui::SmallButton("⇄")) std::swap(primary, secondary);
    ImGui::SetItemTooltip("Поменять цвета (X)");
    for (int i = 0; i < 2; i++) {
        if (ImGui::BeginPopup(i ? "##secpick" : "##pripick")) {
            ImVec4 v = toVec4(i ? secondary : primary);
            if (ImGui::ColorPicker4("##pick", &v.x, ImGuiColorEditFlags_NoAlpha | ImGuiColorEditFlags_PickerHueBar))
                (i ? secondary : primary) = fromVec4(v);
            ImGui::EndPopup();
        }
    }
    ImGui::End();
}

void Editor::drawStartScreen() {
    ImDrawList* dl = ImGui::GetWindowDrawList();
    ImVec2 c(canvasMin.x + canvasSize.x * 0.5f, canvasMin.y + canvasSize.y * 0.5f);
    float s = 96;
    drawLogo(dl, ImVec2(c.x - s * 0.5f, c.y - s - 70), s);
    const char* title = "ArtGraf";
    ImFont* f = ImGui::GetFont();
    float fs = ImGui::GetFontSize() * 2.6f;
    ImVec2 ts = f->CalcTextSizeA(fs, FLT_MAX, 0, title);
    dl->AddText(f, fs, ImVec2(c.x - ts.x * 0.5f, c.y - 60), IM_COL32(230, 231, 235, 255), title);
    const char* sub = "Растровый графический редактор";
    ImVec2 ss = ImGui::CalcTextSize(sub);
    dl->AddText(ImVec2(c.x - ss.x * 0.5f, c.y - 60 + ts.y + 4), IM_COL32(141, 144, 151, 255), sub);
    float bw = 170;
    ImGui::SetCursorScreenPos(ImVec2(c.x - bw - 6, c.y + 20));
    if (ImGui::Button("Новый документ", ImVec2(bw, 0))) cmdNew();
    ImGui::SameLine(0, 12);
    if (ImGui::Button("Открыть файл…", ImVec2(bw, 0))) cmdOpen();
    const char* hint = "или перетащите картинку в окно";
    ImVec2 hs = ImGui::CalcTextSize(hint);
    dl->AddText(ImVec2(c.x - hs.x * 0.5f, c.y + 20 + ImGui::GetFrameHeight() + 14), IM_COL32(141, 144, 151, 255), hint);
}

void Editor::drawCanvas() {
    ImGuiWindowClass wc;
    wc.DockNodeFlagsOverrideSet = ImGuiDockNodeFlags_NoTabBar;
    ImGui::SetNextWindowClass(&wc);
    ImGui::PushStyleVar(ImGuiStyleVar_WindowPadding, ImVec2(0, 0));
    ImGui::PushStyleColor(ImGuiCol_WindowBg, IM_COL32(24, 25, 27, 255));
    bool open = ImGui::Begin(kCanvasWin, nullptr, ImGuiWindowFlags_NoScrollbar | ImGuiWindowFlags_NoScrollWithMouse);
    ImGui::PopStyleColor();
    ImGui::PopStyleVar();
    if (!open) return ImGui::End();
    canvasMin = ImGui::GetCursorScreenPos();
    canvasSize = ImGui::GetContentRegionAvail();
    if (canvasSize.x < 8 || canvasSize.y < 8) return ImGui::End();
    if (!doc) {
        drawStartScreen();
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
    ImVec2 a = toScreen({0, 0}), b = toScreen({float(doc->w), float(doc->h)});
    dl->AddRectFilled(ImVec2(a.x + 4, a.y + 4), ImVec2(b.x + 4, b.y + 4), IM_COL32(0, 0, 0, 90));
    dl->AddImage(ImTextureID(uintptr_t(tex)), a, b);
    dl->AddRect(ImVec2(a.x - 1, a.y - 1), ImVec2(b.x + 1, b.y + 1), IM_COL32(0, 0, 0, 160));

    ImGui::SetCursorScreenPos(canvasMin);
    ImGui::InvisibleButton("##canvas", canvasSize,
                           ImGuiButtonFlags_MouseButtonLeft | ImGuiButtonFlags_MouseButtonMiddle | ImGuiButtonFlags_MouseButtonRight);
    bool hovered = ImGui::IsItemHovered();
    canvasInput(hovered, ImGui::IsItemActive());
    if (!doc) return ImGui::End();  // a tool may have closed it (not currently, but stay safe)
    dl->PushClipRect(canvasMin, ImVec2(canvasMin.x + canvasSize.x, canvasMin.y + canvasSize.y), true);
    drawOverlays(dl);
    dl->PopClipRect();
    ImGui::End();

    // Floating text editor for the text tool
    if (textEditing) {
        ImVec2 at = toScreen({textPos.x, textPos.y + fontSize * 1.3f});
        at.x = std::clamp(at.x, canvasMin.x, canvasMin.x + std::max(0.f, canvasSize.x - 360));
        at.y = std::clamp(at.y, canvasMin.y, canvasMin.y + std::max(0.f, canvasSize.y - 220));
        ImGui::SetNextWindowPos(at, ImGuiCond_Appearing);
        ImGui::SetNextWindowBgAlpha(0.96f);
        if (ImGui::Begin("Текст##edit", nullptr,
                         ImGuiWindowFlags_NoDocking | ImGuiWindowFlags_AlwaysAutoResize | ImGuiWindowFlags_NoSavedSettings |
                             ImGuiWindowFlags_NoCollapse)) {
            if (textFocus) {
                ImGui::SetKeyboardFocusHere();
                textFocus = false;
            }
            if (ImGui::InputTextMultiline("##text", &textBuf, ImVec2(340, ImGui::GetTextLineHeight() * 4.5f))) textPreview();
            bool ctrlEnter = ImGui::IsItemFocused() && ImGui::GetIO().KeyCtrl && ImGui::IsKeyPressed(ImGuiKey_Enter);
            ImVec4 v = toVec4(primary);
            if (ImGui::ColorEdit3("Цвет", &v.x, ImGuiColorEditFlags_NoInputs)) {
                primary = fromVec4(v);
                textPreview();
            }
            ImGui::SameLine();
            ImGui::SetNextItemWidth(150);
            if (ImGui::SliderFloat("Размер", &fontSize, 6, 500, "%.0f px", ImGuiSliderFlags_Logarithmic)) textPreview();
            if (ImGui::Button("Применить") || ctrlEnter) {
                while (!textBuf.empty() && (textBuf.back() == '\n' || textBuf.back() == '\r')) textBuf.pop_back();
                commitText();
            }
            ImGui::SameLine();
            if (ImGui::Button("Отмена")) cancelText();
            ImGui::SameLine();
            ImGui::TextDisabled("Ctrl+Enter — применить");
        }
        ImGui::End();
    }
}

void Editor::drawColors() {
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
    // Keep the palette below the picker visible: the picker is about as tall as it is wide.
    float fh = ImGui::GetFrameHeightWithSpacing();
    float pickerW = std::min({ImGui::GetContentRegionAvail().x, 260.f, ImGui::GetContentRegionAvail().y - fh * 4.2f});
    ImGui::SetNextItemWidth(std::max(pickerW, 120.f));
    if (ImGui::ColorPicker4("##picker", &v.x,
                            ImGuiColorEditFlags_NoAlpha | ImGuiColorEditFlags_PickerHueBar | ImGuiColorEditFlags_NoSidePreview |
                                ImGuiColorEditFlags_DisplayRGB | ImGuiColorEditFlags_DisplayHex))
        c = fromVec4(v);
    static const RGBA palette[] = {
        {0, 0, 0, 255},       {64, 64, 64, 255},    {128, 128, 128, 255}, {192, 192, 192, 255}, {255, 255, 255, 255},
        {231, 76, 60, 255},   {230, 126, 34, 255},  {241, 196, 15, 255},  {46, 204, 113, 255},  {26, 188, 156, 255},
        {52, 152, 219, 255},  {61, 139, 253, 255},  {155, 89, 182, 255},  {232, 67, 147, 255},  {121, 85, 72, 255},
        {255, 205, 178, 255}, {181, 131, 90, 255},  {44, 62, 80, 255},    {127, 0, 0, 255},     {0, 100, 0, 255},
        {0, 0, 139, 255},     {255, 0, 255, 255},   {0, 255, 255, 255},   {255, 255, 0, 255},
    };
    float sw = ImGui::GetFrameHeight() * 0.85f;
    int perRow = std::max(1, int(ImGui::GetContentRegionAvail().x / (sw + 3)));
    for (int i = 0; i < int(std::size(palette)); i++) {
        if (i % perRow) ImGui::SameLine(0, 3);
        ImGui::PushID(i);
        if (ImGui::ColorButton("##p", toVec4(palette[i]), ImGuiColorEditFlags_NoTooltip, ImVec2(sw, sw))) primary = palette[i];
        if (ImGui::IsItemClicked(ImGuiMouseButton_Right)) secondary = palette[i];
        ImGui::PopID();
    }
    ImGui::TextDisabled("ЛКМ — основной, ПКМ — фоновый");
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
    ImGui::SetNextItemWidth(-1);
    if (ImGui::BeginCombo("##blend", blendName(cur.blend))) {
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
    float op = doc->layer().opacity * 100;
    ImGui::SetNextItemWidth(-1);
    bool changed = ImGui::SliderFloat("##opacity", &op, 0, 100, "Непрозрачность: %.0f%%");
    if (ImGui::IsItemActivated()) doc->push("Непрозрачность слоя");
    if (changed) {
        doc->layer().opacity = op / 100;
        invalidateAll();
    }

    float rowH = 46;
    float buttonsH = ImGui::GetFrameHeightWithSpacing() + 4;
    ImGui::BeginChild("##list", ImVec2(0, -buttonsH), ImGuiChildFlags_Borders);
    int moveFrom = -1, moveTo = -1;
    std::function<void()> deferred;
    for (int i = int(doc->layers.size()) - 1; i >= 0; i--) {
        Layer& L = doc->layers[size_t(i)];
        ImGui::PushID(i);
        ImVec2 rowMin = ImGui::GetCursorScreenPos();
        float rowW = ImGui::GetContentRegionAvail().x;
        bool selected = i == doc->active;
        if (ImGui::Selectable("##row", selected, ImGuiSelectableFlags_AllowDoubleClick | ImGuiSelectableFlags_AllowOverlap,
                              ImVec2(rowW, rowH))) {
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
        // Layer list changes are deferred until after the loop: `L` must stay valid while drawing.
        if (ImGui::BeginPopupContextItem("##ctx")) {
            if (ImGui::MenuItem("Переименовать")) { renaming = i; renameBuf = L.name; }
            if (ImGui::MenuItem("Дублировать"))
                deferred = [this, i] { doc->active = i; layerAction("Дублировать слой", [](Document& d) { d.duplicateLayer(); }); };
            if (ImGui::MenuItem("Объединить с нижним", nullptr, false, i > 0))
                deferred = [this, i] { doc->active = i; layerAction("Объединить с нижним", [](Document& d) { d.mergeDown(); }); };
            if (ImGui::MenuItem("Удалить", nullptr, false, doc->layers.size() > 1))
                deferred = [this, i] { doc->active = i; layerAction("Удалить слой", [](Document& d) { d.deleteLayer(); }); };
            ImGui::EndPopup();
        }
        // eye toggle
        ImGui::SetCursorScreenPos(ImVec2(rowMin.x + 4, rowMin.y + (rowH - ImGui::GetFrameHeight()) * 0.5f));
        bool vis = L.visible;
        if (ImGui::Checkbox("##vis", &vis)) {
            doc->layers[size_t(i)].visible = vis;
            doc->dirty = true;
            invalidateAll();
        }
        ImGui::SetItemTooltip("Видимость слоя");
        // thumbnail
        float tx = rowMin.x + 8 + ImGui::GetFrameHeight();
        if (size_t(i) < thumbs.size()) {
            float k = std::min(56.f / doc->w, 42.f / doc->h);
            ImVec2 ts(doc->w * k, doc->h * k);
            ImVec2 tp(tx + (56 - ts.x) * 0.5f, rowMin.y + (rowH - ts.y) * 0.5f);
            ImGui::GetWindowDrawList()->AddImage(ImTextureID(uintptr_t(thumbs[size_t(i)])), tp, ImVec2(tp.x + ts.x, tp.y + ts.y));
            ImGui::GetWindowDrawList()->AddRect(ImVec2(tp.x - 1, tp.y - 1), ImVec2(tp.x + ts.x + 1, tp.y + ts.y + 1),
                                                IM_COL32(90, 93, 100, 255));
        }
        ImVec2 np(tx + 64, rowMin.y + (rowH - ImGui::GetFrameHeight()) * 0.5f);
        ImGui::SetCursorScreenPos(np);
        if (renaming == i) {
            ImGui::SetNextItemWidth(rowW - (np.x - rowMin.x) - 4);
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
            ImGui::SetCursorScreenPos(ImVec2(np.x, np.y + ImGui::GetStyle().FramePadding.y));
            if (!L.visible) ImGui::PushStyleColor(ImGuiCol_Text, ImGui::GetStyleColorVec4(ImGuiCol_TextDisabled));
            ImGui::TextUnformatted(L.name.c_str());
            if (!L.visible) ImGui::PopStyleColor();
        }
        ImGui::SetCursorScreenPos(ImVec2(rowMin.x, rowMin.y + rowH + ImGui::GetStyle().ItemSpacing.y));
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

    auto btn = [](const char* label, const char* tip, bool enabled = true) {
        ImGui::BeginDisabled(!enabled);
        bool r = ImGui::Button(label);
        ImGui::EndDisabled();
        ImGui::SetItemTooltip("%s", tip);
        ImGui::SameLine(0, 3);
        return r;
    };
    if (btn("+", "Новый слой (Ctrl+Shift+N)")) layerAction("Новый слой", [](Document& d) { d.addLayer(d.nextLayerName()); });
    if (btn("Копия", "Дублировать слой")) layerAction("Дублировать слой", [](Document& d) { d.duplicateLayer(); });
    if (btn("↑", "Выше (Ctrl+])", doc->active + 1 < int(doc->layers.size())))
        layerAction("Порядок слоёв", [](Document& d) { d.moveLayer(1); });
    if (btn("↓", "Ниже (Ctrl+[)", doc->active > 0)) layerAction("Порядок слоёв", [](Document& d) { d.moveLayer(-1); });
    if (btn("Слить", "Объединить с нижним (Ctrl+E)", doc->active > 0))
        layerAction("Объединить с нижним", [](Document& d) { d.mergeDown(); });
    if (btn("Удалить", "Удалить слой", doc->layers.size() > 1)) layerAction("Удалить слой", [](Document& d) { d.deleteLayer(); });
    ImGui::NewLine();
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
    // Entry k = state after k actions; entry 0 is the opened document.
    for (size_t k = 0; k <= nu + nr; k++) {
        std::string name;
        if (k == 0) name = "Исходное состояние";
        else if (k <= nu) name = doc->undoStack[k - 1].name;
        else name = doc->redoStack[nr - (k - nu)].name;
        bool current = k == nu;
        if (k > nu) ImGui::PushStyleColor(ImGuiCol_Text, ImGui::GetStyleColorVec4(ImGuiCol_TextDisabled));
        ImGui::PushID(int(k));
        if (ImGui::Selectable(name.c_str(), current)) target = int(k);
        if (current && ImGui::IsWindowAppearing()) ImGui::SetScrollHereY();
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
    ImGui::GetWindowDrawList()->AddRect(ra, rb, IM_COL32(231, 76, 60, 255), 0, 0, 1.5f);
    float z = zoom * 100;
    ImGui::SetNextItemWidth(-1);
    if (ImGui::SliderFloat("##zoom", &z, 1, 3200, "%.0f%%", ImGuiSliderFlags_Logarithmic))
        zoomAt(z / 100, ImVec2(canvasMin.x + canvasSize.x * 0.5f, canvasMin.y + canvasSize.y * 0.5f));
    ImGui::End();
}

// ---------------------------------------------------------------- dialogs

void Editor::drawDialogs() {
    if (!popupToOpen.empty()) {
        ImGui::OpenPopup(popupToOpen.c_str());
        popupToOpen.clear();
    }
    ImVec2 center = ImGui::GetMainViewport()->GetCenter();
    auto modal = [&](const char* name) {
        ImGui::SetNextWindowPos(center, ImGuiCond_Appearing, ImVec2(0.5f, 0.5f));
        return ImGui::BeginPopupModal(name, nullptr, ImGuiWindowFlags_AlwaysAutoResize);
    };
    float bw = 120;

    if (modal("Новый документ")) {
        struct Preset { const char* name; int w, h; };
        static const Preset presets[] = {{"Full HD 1920×1080", 1920, 1080}, {"HD 1280×720", 1280, 720},
                                         {"4K 3840×2160", 3840, 2160},      {"Квадрат 1080×1080", 1080, 1080},
                                         {"A4 300 dpi 2480×3508", 2480, 3508}, {"800×600", 800, 600},
                                         {"Иконка 512×512", 512, 512},      {"Пиксель-арт 64×64", 64, 64}};
        ImGui::SetNextItemWidth(260);
        if (ImGui::BeginCombo("Шаблон", "Выберите…")) {
            for (auto& p : presets)
                if (ImGui::Selectable(p.name)) { newW = p.w; newH = p.h; }
            ImGui::EndCombo();
        }
        ImGui::SetNextItemWidth(260);
        ImGui::InputInt("Ширина, px", &newW);
        ImGui::SetNextItemWidth(260);
        ImGui::InputInt("Высота, px", &newH);
        newW = std::clamp(newW, 1, 16384);
        newH = std::clamp(newH, 1, 16384);
        const char* bgs[] = {"Белый", "Чёрный", "Прозрачный", "Фоновый цвет"};
        ImGui::SetNextItemWidth(260);
        ImGui::Combo("Фон", &newBg, bgs, 4);
        ImGui::Spacing();
        if (ImGui::Button("Создать", ImVec2(bw, 0)) || ImGui::IsKeyPressed(ImGuiKey_Enter)) {
            RGBA bg = newBg == 0 ? RGBA{255, 255, 255, 255} : newBg == 1 ? RGBA{0, 0, 0, 255} : newBg == 2 ? RGBA{} : secondary;
            setDocument(std::make_unique<Document>(Document::blank(newW, newH, bg)));
            ImGui::CloseCurrentPopup();
        }
        ImGui::SameLine();
        if (ImGui::Button("Отмена", ImVec2(bw, 0)) || ImGui::IsKeyPressed(ImGuiKey_Escape)) ImGui::CloseCurrentPopup();
        ImGui::EndPopup();
    }

    if (modal("Размер изображения")) {
        int ow = doc ? doc->w : 1, oh = doc ? doc->h : 1;
        ImGui::Text("Сейчас: %d × %d px", ow, oh);
        ImGui::SetNextItemWidth(200);
        if (ImGui::InputInt("Ширина, px", &sizeW) && keepRatio) sizeH = std::max(1, int(std::lround(sizeW * double(oh) / ow)));
        ImGui::SetNextItemWidth(200);
        if (ImGui::InputInt("Высота, px", &sizeH) && keepRatio) sizeW = std::max(1, int(std::lround(sizeH * double(ow) / oh)));
        ImGui::Checkbox("Сохранять пропорции", &keepRatio);
        for (int pct : {25, 50, 200}) {
            ImGui::SameLine();
            if (ImGui::SmallButton((std::to_string(pct) + "%").c_str())) {
                sizeW = std::max(1, ow * pct / 100);
                sizeH = std::max(1, oh * pct / 100);
            }
        }
        sizeW = std::clamp(sizeW, 1, 16384);
        sizeH = std::clamp(sizeH, 1, 16384);
        ImGui::Spacing();
        if (ImGui::Button("OK", ImVec2(bw, 0))) {
            int w = sizeW, h = sizeH;
            imageAction("Размер изображения", [w, h](Document& d) { d.resizeImage(w, h); });
            ImGui::CloseCurrentPopup();
        }
        ImGui::SameLine();
        if (ImGui::Button("Отмена", ImVec2(bw, 0)) || ImGui::IsKeyPressed(ImGuiKey_Escape)) ImGui::CloseCurrentPopup();
        ImGui::EndPopup();
    }

    if (modal("Размер холста")) {
        int ow = doc ? doc->w : 1, oh = doc ? doc->h : 1;
        ImGui::Text("Сейчас: %d × %d px", ow, oh);
        ImGui::SetNextItemWidth(200);
        ImGui::InputInt("Ширина, px", &sizeW);
        ImGui::SetNextItemWidth(200);
        ImGui::InputInt("Высота, px", &sizeH);
        sizeW = std::clamp(sizeW, 1, 16384);
        sizeH = std::clamp(sizeH, 1, 16384);
        ImGui::TextUnformatted("Расположение:");
        for (int i = 0; i < 9; i++) {
            if (i % 3) ImGui::SameLine(0, 2);
            ImGui::PushID(i);
            bool on = anchor == i;
            if (on) ImGui::PushStyleColor(ImGuiCol_Button, ImGui::GetStyleColorVec4(ImGuiCol_ButtonActive));
            if (ImGui::Button(on ? "●" : " ", ImVec2(28, 28))) anchor = i;
            if (on) ImGui::PopStyleColor();
            ImGui::PopID();
        }
        ImGui::Spacing();
        if (ImGui::Button("OK", ImVec2(bw, 0))) {
            int w = sizeW, h = sizeH;
            int ox = (anchor % 3) * (w - ow) / 2, oy = (anchor / 3) * (h - oh) / 2;
            imageAction("Размер холста", [w, h, ox, oy](Document& d) { d.resizeCanvas(w, h, ox, oy); });
            ImGui::CloseCurrentPopup();
        }
        ImGui::SameLine();
        if (ImGui::Button("Отмена", ImVec2(bw, 0)) || ImGui::IsKeyPressed(ImGuiKey_Escape)) ImGui::CloseCurrentPopup();
        ImGui::EndPopup();
    }

    if (modal("Растушевка")) {
        ImGui::SetNextItemWidth(220);
        ImGui::SliderFloat("Радиус, px", &featherRadius, 0.5f, 250, "%.1f", ImGuiSliderFlags_Logarithmic);
        if (ImGui::Button("OK", ImVec2(bw, 0))) {
            if (doc) {
                doc->sel.feather(featherRadius);
                selectionChanged();
            }
            ImGui::CloseCurrentPopup();
        }
        ImGui::SameLine();
        if (ImGui::Button("Отмена", ImVec2(bw, 0)) || ImGui::IsKeyPressed(ImGuiKey_Escape)) ImGui::CloseCurrentPopup();
        ImGui::EndPopup();
    }

    if (filter) {
        ImGui::SetNextWindowPos(ImVec2(center.x + 200, center.y), ImGuiCond_Appearing, ImVec2(0.5f, 0.5f));
        if (ImGui::BeginPopupModal("##filter", nullptr, ImGuiWindowFlags_AlwaysAutoResize | ImGuiWindowFlags_NoTitleBar)) {
            ImGui::TextUnformatted(filter->title.c_str());
            ImGui::Separator();
            bool released = false;
            for (size_t i = 0; i < filter->params.size(); i++) {
                auto& p = filter->params[i];
                ImGui::SetNextItemWidth(260);
                if (p.integer) {
                    int v = int(std::lround(filterVals[i]));
                    if (ImGui::SliderInt(p.label, &v, int(p.min), int(p.max))) filterVals[i] = float(v);
                } else {
                    ImGui::SliderFloat(p.label, &filterVals[i], p.min, p.max, "%.1f");
                }
                released |= ImGui::IsItemDeactivatedAfterEdit();
            }
            bool prevToggled = ImGui::Checkbox("Просмотр", &filterPreview);
            // Large images: only recompute when the slider is released.
            bool heavy = doc && size_t(doc->w) * doc->h > 4'000'000;
            bool stale = filterVals != filterShown;
            if (filterPreview && stale && (!heavy || released || filterShown.empty() || prevToggled)) filterApplyPreview();
            if (!filterPreview && prevToggled) {
                doc->layer().img = filterBackup;
                filterShown.clear();
                invalidateAll();
            }
            ImGui::Spacing();
            if (ImGui::Button("OK", ImVec2(bw, 0)) || ImGui::IsKeyPressed(ImGuiKey_Enter)) {
                filterFinish(true);
                ImGui::CloseCurrentPopup();
            }
            ImGui::SameLine();
            if (ImGui::Button("Отмена", ImVec2(bw, 0)) || ImGui::IsKeyPressed(ImGuiKey_Escape)) {
                filterFinish(false);
                ImGui::CloseCurrentPopup();
            }
            ImGui::SameLine();
            if (ImGui::Button("Сброс")) {
                for (size_t i = 0; i < filter->params.size(); i++) filterVals[i] = filter->params[i].value;
            }
            ImGui::EndPopup();
        }
    }

    if (modal("Сохранить изменения?")) {
        ImGui::Text("Сохранить изменения в «%s» перед закрытием?", doc ? doc->title.c_str() : "");
        ImGui::Spacing();
        if (ImGui::Button("Сохранить", ImVec2(bw, 0))) {
            ImGui::CloseCurrentPopup();
            auto then = std::move(pendingDiscard);
            pendingDiscard = nullptr;
            cmdSave(false, then);
        }
        ImGui::SameLine();
        if (ImGui::Button("Не сохранять", ImVec2(bw, 0))) {
            ImGui::CloseCurrentPopup();
            auto then = std::move(pendingDiscard);
            pendingDiscard = nullptr;
            if (doc) doc->dirty = false;
            if (then) then();
        }
        ImGui::SameLine();
        if (ImGui::Button("Отмена", ImVec2(bw, 0)) || ImGui::IsKeyPressed(ImGuiKey_Escape)) {
            pendingDiscard = nullptr;
            ImGui::CloseCurrentPopup();
        }
        ImGui::EndPopup();
    }

    if (modal("Ошибка")) {
        ImGui::PushTextWrapPos(ImGui::GetFontSize() * 30);
        ImGui::TextUnformatted(errorText.c_str());
        ImGui::PopTextWrapPos();
        if (ImGui::Button("OK", ImVec2(bw, 0)) || ImGui::IsKeyPressed(ImGuiKey_Enter) || ImGui::IsKeyPressed(ImGuiKey_Escape))
            ImGui::CloseCurrentPopup();
        ImGui::EndPopup();
    }

    if (showAbout) {
        ImGui::SetNextWindowPos(center, ImGuiCond_Appearing, ImVec2(0.5f, 0.5f));
        if (ImGui::Begin("О программе", &showAbout, ImGuiWindowFlags_AlwaysAutoResize | ImGuiWindowFlags_NoDocking)) {
            drawLogo(ImGui::GetWindowDrawList(), ImGui::GetCursorScreenPos(), 48);
            ImGui::Dummy(ImVec2(48, 48));
            ImGui::SameLine();
            ImGui::BeginGroup();
            ImGui::Text("ArtGraf 1.0");
            ImGui::TextDisabled("Растровый графический редактор");
            ImGui::EndGroup();
            ImGui::Separator();
            ImGui::TextUnformatted("Сделано на: SDL2, Dear ImGui, OpenGL, stb_image / stb_image_write /\n"
                                   "stb_image_resize2 / stb_truetype, nlohmann/json, miniz,\n"
                                   "nativefiledialog-extended.");
        }
        ImGui::End();
    }

    if (showShortcuts) {
        ImGui::SetNextWindowPos(center, ImGuiCond_Appearing, ImVec2(0.5f, 0.5f));
        ImGui::SetNextWindowSize(ImVec2(560, 520), ImGuiCond_Appearing);
        if (ImGui::Begin("Горячие клавиши", &showShortcuts, ImGuiWindowFlags_NoDocking)) {
            if (ImGui::BeginTable("##keys", 2, ImGuiTableFlags_RowBg | ImGuiTableFlags_BordersInnerV)) {
                auto row = [](const char* k, const char* v) {
                    ImGui::TableNextRow();
                    ImGui::TableNextColumn();
                    ImGui::TextUnformatted(k);
                    ImGui::TableNextColumn();
                    ImGui::TextUnformatted(v);
                };
                for (int t = 0; t < int(Tool::Count); t++) {
                    char key[2] = {char(std::toupper(int(toolInfo(Tool(t)).key))), 0};
                    row(key, toolInfo(Tool(t)).name);
                }
                row("Ctrl+Z / Ctrl+Shift+Z", "Отменить / повторить");
                row("Ctrl+C / X / V", "Копировать / вырезать / вставить");
                row("Ctrl+A / Ctrl+D", "Выделить всё / снять выделение");
                row("Ctrl+Shift+I", "Инвертировать выделение");
                row("Delete", "Очистить выделенное");
                row("Alt+Backspace / Ctrl+Backspace", "Залить основным / фоновым");
                row("Ctrl+J", "Скопировать на новый слой");
                row("Ctrl+Shift+N", "Новый слой");
                row("Ctrl+E", "Объединить с нижним");
                row("Ctrl+T", "Трансформирование");
                row("Ctrl+I / Ctrl+U / Ctrl+L / Ctrl+B", "Инверсия / тон-насыщенность / уровни / цветовой баланс");
                row("[ / ]", "Размер кисти");
                row("1 … 0", "Непрозрачность кисти 10 … 100%");
                row("X / D", "Поменять цвета / цвета по умолчанию");
                row("Пробел + мышь", "Двигать вид");
                row("Колесо мыши", "Масштаб");
                row("Ctrl+0 / Ctrl+1", "Целиком / 100%");
                row("Ctrl+S / Ctrl+Shift+E", "Сохранить проект / экспорт");
                ImGui::EndTable();
            }
        }
        ImGui::End();
    }
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
        else if (pressed(ImGuiKey_N)) cmdNew();
        if (pressed(ImGuiKey_O)) cmdOpen();
        if (pressed(ImGuiKey_P) && S) cmdPlace();
        if (pressed(ImGuiKey_S)) cmdSave(S);
        if (pressed(ImGuiKey_E) && S) cmdExport();
        else if (pressed(ImGuiKey_E) && doc && doc->active > 0) layerAction("Объединить с нижним", [](Document& d) { d.mergeDown(); });
        if (pressed(ImGuiKey_W) && doc) guardUnsaved([this] { setDocument(nullptr); });
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
                        [](Image& i, const std::vector<float>& v) { hueSaturation(i, v[0], v[1], v[2]); }});
        if (pressed(ImGuiKey_L) && S) instantFilter("Автоконтраст", autoContrast);
        else if (pressed(ImGuiKey_L))
            openFilter({"Уровни", {{"Чёрная точка", 0, 254, 0, true}, {"Белая точка", 1, 255, 255, true}, {"Гамма", 0.1f, 5.f, 1.f},
                                   {"Выход: чёрный", 0, 255, 0, true}, {"Выход: белый", 0, 255, 255, true}},
                        [](Image& i, const std::vector<float>& v) { levels(i, int(v[0]), int(v[1]), v[2], int(v[3]), int(v[4])); }});
        if (pressed(ImGuiKey_B))
            openFilter({"Цветовой баланс", {{"Голубой — Красный", -100, 100, 0}, {"Пурпурный — Зелёный", -100, 100, 0}, {"Жёлтый — Синий", -100, 100, 0}},
                        [](Image& i, const std::vector<float>& v) { colorBalance(i, v[0], v[1], v[2]); }});
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
    if (S && pressed(ImGuiKey_F6) && doc && doc->sel.active()) popupToOpen = "Растушевка";
    if (S) {
        if (tool == Tool::Move && doc) {
            if (repeat(ImGuiKey_LeftArrow)) nudge(-10, 0);
            if (repeat(ImGuiKey_RightArrow)) nudge(10, 0);
            if (repeat(ImGuiKey_UpArrow)) nudge(0, -10);
            if (repeat(ImGuiKey_DownArrow)) nudge(0, 10);
        }
        return;
    }
    for (int t = 0; t < int(Tool::Count); t++) {
        SDL_Keycode k = toolInfo(Tool(t)).key;
        if (pressed(ImGuiKey(ImGuiKey_A + (k - SDLK_a)))) setTool(Tool(t));
    }
    if (pressed(ImGuiKey_X)) std::swap(primary, secondary);
    if (pressed(ImGuiKey_D)) {
        primary = {0, 0, 0, 255};
        secondary = {255, 255, 255, 255};
    }
    if (isBrushTool(tool) || tool == Tool::Bucket) {
        BrushOptions& b = brush();
        if (repeat(ImGuiKey_LeftBracket)) b.size = std::max(1.f, b.size < 10 ? b.size - 1 : b.size / 1.15f);
        if (repeat(ImGuiKey_RightBracket)) b.size = std::min(1000.f, b.size < 10 ? b.size + 1 : b.size * 1.15f);
        for (int i = 0; i <= 9; i++)
            if (pressed(ImGuiKey(ImGuiKey_0 + i))) b.opacity = i == 0 ? 1.f : i / 10.f;
    }
    if (pressed(ImGuiKey_Delete) || pressed(ImGuiKey_Backspace)) cmdClear();
    if (pressed(ImGuiKey_Enter) || pressed(ImGuiKey_KeypadEnter)) {
        if (cropActive) applyCrop();
    }
    if (pressed(ImGuiKey_Escape)) {
        if (cropActive) cropActive = false;
        else if (dragging) {
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
