#include <array>
#include <cmath>
#include <cstring>
#include <memory>

#include "gl.h"
#include <imgui_internal.h>
#include <imgui_stdlib.h>

#include "assets.h"
#include "editor.h"
#include "filters.h"
#include "icons.h"
#include "io.h"

namespace ag {

namespace {

const ImU32 kAccent = IM_COL32(38, 128, 235, 255);

bool primaryButton(const char* label, ImVec2 size) {
    ImGui::PushStyleColor(ImGuiCol_Button, IM_COL32(38, 128, 235, 255));
    ImGui::PushStyleColor(ImGuiCol_ButtonHovered, IM_COL32(66, 146, 245, 255));
    ImGui::PushStyleColor(ImGuiCol_ButtonActive, IM_COL32(26, 106, 205, 255));
    bool r = ImGui::Button(label, size);
    ImGui::PopStyleColor(3);
    return r;
}

void heading(const char* text) {
    if (gTitleFont) ImGui::PushFont(gTitleFont);
    ImGui::TextUnformatted(text);
    if (gTitleFont) ImGui::PopFont();
}

void subheading(const char* text) {
    if (gMediumFont) ImGui::PushFont(gMediumFont);
    ImGui::TextUnformatted(text);
    if (gMediumFont) ImGui::PopFont();
}

GLuint uploadTexture(const Image& img, bool linear = true) {
    GLuint t;
    glGenTextures(1, &t);
    glBindTexture(GL_TEXTURE_2D, t);
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, linear ? GL_LINEAR : GL_NEAREST);
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, linear ? GL_LINEAR : GL_NEAREST);
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE);
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE);
    glPixelStorei(GL_UNPACK_ALIGNMENT, 1);
    glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA, img.w, img.h, 0, GL_RGBA, GL_UNSIGNED_BYTE, img.px.data());
    return t;
}

struct DocPreset {
    const char* name;
    int w, h;
    float dpi;
};
struct DocCategory {
    const char* name;
    std::vector<DocPreset> presets;
};

const std::vector<DocCategory>& docCategories() {
    static const std::vector<DocCategory> cats = {
        {"Фото", {{"Фото 10×15 см", 1800, 1200, 300}, {"Фото 13×18 см", 2100, 1500, 300}, {"Фото 20×25 см", 3000, 2400, 300},
                  {"Альбомная 3:2", 3000, 2000, 300}, {"Квадрат 1:1", 2000, 2000, 300}, {"Панорама 3:1", 6000, 2000, 300}}},
        {"Печать", {{"A4", 2480, 3508, 300}, {"A5", 1748, 2480, 300}, {"A3", 3508, 4961, 300}, {"Letter", 2550, 3300, 300},
                    {"Визитка", 1050, 600, 300}, {"Плакат 50×70", 5906, 8268, 300}}},
        {"Иллюстрации", {{"Холст 2K", 2048, 2048, 150}, {"Холст 4K", 4096, 4096, 150}, {"Страница комикса", 1988, 3056, 300},
                         {"Концепт 16:9", 3840, 2160, 72}, {"Пиксель-арт 64", 64, 64, 72}, {"Пиксель-арт 256", 256, 256, 72}}},
        {"Веб", {{"Веб 1920×1080", 1920, 1080, 72}, {"Веб 1366×768", 1366, 768, 72}, {"Баннер соцсетей", 1200, 628, 72},
                 {"Обложка YouTube", 2560, 1440, 72}, {"Пост 1080×1080", 1080, 1080, 72}, {"Иконка 512", 512, 512, 72}}},
        {"Мобильные", {{"iPhone 15 Pro", 1179, 2556, 72}, {"Android FHD+", 1080, 2400, 72}, {"Сторис", 1080, 1920, 72},
                       {"iPad Pro", 2048, 2732, 72}, {"Обои телефона", 1440, 3200, 72}, {"Иконка приложения", 1024, 1024, 72}}},
        {"Видео", {{"HD 720p", 1280, 720, 72}, {"Full HD 1080p", 1920, 1080, 72}, {"4K UHD", 3840, 2160, 72},
                   {"Превью видео", 1280, 720, 72}, {"Вертикальное видео", 1080, 1920, 72}, {"Кино 2K", 2048, 858, 72}}},
    };
    return cats;
}

float unitFactor(int unit, float dpi) {  // pixels per unit
    switch (unit) {
        case 1: return dpi / 2.54f;  // cm
        case 2: return dpi / 25.4f;  // mm
        case 3: return dpi;          // inch
        default: return 1.f;
    }
}

}  // namespace

// ---------------------------------------------------------------- assets & splash

void Editor::loadAssets() {
    std::string err;
    Image img;
    if (decodeImage(std::vector<uint8_t>(kLogoPng, kLogoPng + kLogoPngSize), img, err)) {
        logoTex = uploadTexture(img);
        setLogoTexture(ImTextureID(uintptr_t(logoTex)));
    }
    if (decodeImage(std::vector<uint8_t>(kSplashPng, kSplashPng + kSplashPngSize), img, err)) {
        splashTex = uploadTexture(img);
        splashW = img.w;
        splashH = img.h;
    }
}

void Editor::drawSplash(float progress, const char* stage) {
    ImGuiViewport* vp = ImGui::GetMainViewport();
    ImGui::SetNextWindowPos(vp->Pos);
    ImGui::SetNextWindowSize(vp->Size);
    ImGui::PushStyleVar(ImGuiStyleVar_WindowPadding, ImVec2(0, 0));
    ImGui::PushStyleVar(ImGuiStyleVar_WindowRounding, 0);
    ImGui::PushStyleVar(ImGuiStyleVar_WindowBorderSize, 0);
    ImGui::Begin("##splash", nullptr,
                 ImGuiWindowFlags_NoDecoration | ImGuiWindowFlags_NoMove | ImGuiWindowFlags_NoSavedSettings | ImGuiWindowFlags_NoInputs |
                     ImGuiWindowFlags_NoBringToFrontOnFocus);
    ImGui::PopStyleVar(3);
    ImDrawList* dl = ImGui::GetWindowDrawList();
    ImVec2 a = vp->Pos, b(vp->Pos.x + vp->Size.x, vp->Pos.y + vp->Size.y);
    dl->AddRectFilled(a, b, IM_COL32(17, 21, 28, 255));
    // Fit the artwork into the window keeping its aspect (phones are wider than the splash).
    float s = std::min(vp->Size.x / 960.f, vp->Size.y / 560.f);
    a = ImVec2(vp->Pos.x + (vp->Size.x - 960 * s) * 0.5f, vp->Pos.y + (vp->Size.y - 560 * s) * 0.5f);
    b = ImVec2(a.x + 960 * s, a.y + 560 * s);
    if (splashTex) dl->AddImage(ImTextureID(uintptr_t(splashTex)), a, b);
    ImVec2 barA(a.x + 58 * s, a.y + 380 * s), barB(a.x + 360 * s, a.y + 384 * s);
    dl->AddRectFilled(barA, barB, IM_COL32(255, 255, 255, 30), 2);
    dl->AddRectFilled(barA, ImVec2(barA.x + (barB.x - barA.x) * std::clamp(progress, 0.f, 1.f), barB.y), IM_COL32(38, 128, 235, 255), 2);
    dl->AddText(ImVec2(barA.x, barA.y + 12 * s), IM_COL32(170, 180, 196, 255), stage);
    ImGui::End();
}

// ---------------------------------------------------------------- adjustments with custom UI

void Editor::openCurves() {
    struct State {
        int ch = 0;
        std::array<std::vector<std::pair<float, float>>, 4> pts;
        int drag = -1;
        std::array<float, 256> hist{};
    };
    auto st = std::make_shared<State>();
    for (auto& p : st->pts) p = {{0, 0}, {255, 255}};
    if (doc) {
        std::array<int, 256> h{};
        const Image& img = doc->layer().img;
        int mx = 1;
        for (size_t i = 0; i < img.px.size(); i += 4 * 3)
            if (img.px[i + 3]) mx = std::max(mx, ++h[clamp8(img.px[i] * 0.299f + img.px[i + 1] * 0.587f + img.px[i + 2] * 0.114f)]);
        for (int i = 0; i < 256; i++) st->hist[size_t(i)] = std::sqrt(float(h[size_t(i)]) / mx);
    }
    FilterSpec spec;
    spec.title = "Кривые";
    spec.apply = [st](Image& img, const std::vector<float>&) {
        uint8_t m[256], r[256], g[256], b[256], fr[256], fg[256], fb[256];
        curveLut(st->pts[0], m);
        curveLut(st->pts[1], r);
        curveLut(st->pts[2], g);
        curveLut(st->pts[3], b);
        for (int i = 0; i < 256; i++) {
            fr[i] = r[m[i]];
            fg[i] = g[m[i]];
            fb[i] = b[m[i]];
        }
        applyLuts(img, fr, fg, fb);
    };
    spec.customUi = [st]() {
        bool changed = false;
        const char* chans[] = {"RGB", "Красный", "Зелёный", "Синий"};
        ImGui::SetNextItemWidth(160);
        ImGui::Combo("Канал", &st->ch, chans, 4);
        ImGui::SameLine();
        if (ImGui::Button("Сбросить канал")) {
            st->pts[size_t(st->ch)] = {{0, 0}, {255, 255}};
            changed = true;
        }
        const float S = 300;
        ImVec2 a = ImGui::GetCursorScreenPos();
        ImGui::InvisibleButton("##curve", ImVec2(S, S));
        ImDrawList* dl = ImGui::GetWindowDrawList();
        dl->AddRectFilled(a, ImVec2(a.x + S, a.y + S), IM_COL32(14, 15, 18, 255), 6);
        for (int i = 0; i < 256; i++) {
            float x = a.x + i / 255.f * S, hh = st->hist[size_t(i)] * S * 0.9f;
            dl->AddLine(ImVec2(x, a.y + S), ImVec2(x, a.y + S - hh), IM_COL32(255, 255, 255, 22), S / 255.f + 0.5f);
        }
        for (int i = 1; i < 4; i++) {
            float t = i * S / 4;
            dl->AddLine(ImVec2(a.x + t, a.y), ImVec2(a.x + t, a.y + S), IM_COL32(255, 255, 255, 20));
            dl->AddLine(ImVec2(a.x, a.y + t), ImVec2(a.x + S, a.y + t), IM_COL32(255, 255, 255, 20));
        }
        dl->AddLine(ImVec2(a.x, a.y + S), ImVec2(a.x + S, a.y), IM_COL32(255, 255, 255, 30));
        auto& pts = st->pts[size_t(st->ch)];
        const ImU32 colors[] = {IM_COL32(230, 230, 240, 255), IM_COL32(255, 90, 90, 255), IM_COL32(90, 230, 120, 255), IM_COL32(90, 150, 255, 255)};
        uint8_t lut[256];
        curveLut(pts, lut);
        ImVec2 line[256];
        for (int i = 0; i < 256; i++) line[i] = ImVec2(a.x + i / 255.f * S, a.y + S - lut[i] / 255.f * S);
        dl->AddPolyline(line, 256, colors[st->ch], 0, 2.f);
        auto toPt = [&](ImVec2 m) {
            return std::pair<float, float>{std::clamp((m.x - a.x) / S * 255.f, 0.f, 255.f), std::clamp((a.y + S - m.y) / S * 255.f, 0.f, 255.f)};
        };
        ImVec2 m = ImGui::GetIO().MousePos;
        if (ImGui::IsItemActivated()) {
            st->drag = -1;
            for (size_t i = 0; i < pts.size(); i++) {
                ImVec2 p(a.x + pts[i].first / 255.f * S, a.y + S - pts[i].second / 255.f * S);
                if (std::hypot(p.x - m.x, p.y - m.y) < 9) st->drag = int(i);
            }
            if (st->drag < 0) {
                pts.push_back(toPt(m));
                std::sort(pts.begin(), pts.end());
                for (size_t i = 0; i < pts.size(); i++)
                    if (pts[i] == toPt(m)) st->drag = int(i);
            }
            changed = true;
        }
        if (ImGui::IsItemActive() && st->drag >= 0) {
            auto p = toPt(m);
            bool endpoint = st->drag == 0 || st->drag == int(pts.size()) - 1;
            if (!endpoint && (m.y < a.y - 20 || m.y > a.y + S + 20) && pts.size() > 2) {
                pts.erase(pts.begin() + st->drag);  // drag out to remove
                st->drag = -1;
            } else {
                // keep points ordered: clamp between neighbours
                float lo = st->drag > 0 ? pts[size_t(st->drag) - 1].first + 1 : 0.f;
                float hi = st->drag + 1 < int(pts.size()) ? pts[size_t(st->drag) + 1].first - 1 : 255.f;
                p.first = std::clamp(p.first, lo, hi);
                pts[size_t(st->drag)] = p;
            }
            changed = true;
        }
        if (ImGui::IsItemDeactivated()) st->drag = -1;
        if (ImGui::IsItemHovered() && ImGui::IsMouseClicked(ImGuiMouseButton_Right))
            for (size_t i = 1; i + 1 < pts.size(); i++) {
                ImVec2 p(a.x + pts[i].first / 255.f * S, a.y + S - pts[i].second / 255.f * S);
                if (std::hypot(p.x - m.x, p.y - m.y) < 9) {
                    pts.erase(pts.begin() + long(i));
                    changed = true;
                    break;
                }
            }
        for (auto& p : pts) {
            ImVec2 c(a.x + p.first / 255.f * S, a.y + S - p.second / 255.f * S);
            dl->AddCircleFilled(c, 5, IM_COL32(14, 15, 18, 255));
            dl->AddCircle(c, 5, colors[st->ch], 0, 2.f);
        }
        dl->AddRect(a, ImVec2(a.x + S, a.y + S), IM_COL32(60, 62, 72, 255), 6);
        ImGui::TextDisabled("Клик — точка, тяните — изгиб, ПКМ или вынос за край — удалить");
        return changed;
    };
    openFilter(std::move(spec));
}

void Editor::openGradientMap() {
    auto g = std::make_shared<Gradient>(Gradient{"", {{0, {20, 10, 60, 255}}, {0.5f, {220, 60, 120, 255}}, {1, {255, 230, 150, 255}}}});
    FilterSpec spec;
    spec.title = "Карта градиента";
    spec.apply = [g](Image& img, const std::vector<float>&) { gradientMap(img, *g); };
    spec.customUi = [this, g]() {
        bool changed = gradientCombo("##gmap", *g, 300);
        if (ImGui::Button("Инверсия")) {
            *g = g->reversed();
            changed = true;
        }
        return changed;
    };
    openFilter(std::move(spec));
}

void Editor::openPhotoFilter() {
    struct State { int preset = 0; RGBA color{236, 138, 0, 255}; bool keep = true; };
    auto st = std::make_shared<State>();
    FilterSpec spec;
    spec.title = "Фотофильтр";
    spec.params = {{"Плотность, %", 0, 100, 25}};
    spec.apply = [st](Image& img, const std::vector<float>& v) { photoFilter(img, st->color, v[0], st->keep); };
    spec.customUi = [st]() {
        struct P { const char* name; RGBA c; };
        static const P presets[] = {{"Тёплый фильтр (85)", {236, 138, 0, 255}}, {"Холодный фильтр (80)", {0, 109, 255, 255}},
                                    {"Сепия", {172, 122, 51, 255}},              {"Красный", {234, 26, 26, 255}},
                                    {"Зелёный", {25, 201, 25, 255}},             {"Подводный", {0, 194, 177, 255}},
                                    {"Фиолетовый", {128, 64, 200, 255}}};
        bool changed = false;
        ImGui::SetNextItemWidth(220);
        if (ImGui::BeginCombo("Фильтр", presets[st->preset].name)) {
            for (int i = 0; i < int(std::size(presets)); i++)
                if (ImGui::Selectable(presets[i].name, i == st->preset)) {
                    st->preset = i;
                    st->color = presets[i].c;
                    changed = true;
                }
            ImGui::EndCombo();
        }
        ImVec4 v = toVec4(st->color);
        if (ImGui::ColorEdit3("Цвет", &v.x, ImGuiColorEditFlags_NoInputs)) {
            st->color = fromVec4(v);
            changed = true;
        }
        ImGui::SameLine();
        changed |= ImGui::Checkbox("Сохранять яркость", &st->keep);
        return changed;
    };
    openFilter(std::move(spec));
}

void Editor::openClouds() {
    RGBA fg = primary, bg = secondary;
    openFilter({"Облака", {{"Масштаб, px", 8, 600, 140}, {"Вариант", 1, 100, 1, true}},
                [fg, bg](Image& img, const std::vector<float>& v) { renderClouds(img, fg, bg, v[0], uint32_t(v[1])); }, {}});
}

void Editor::openLensFlare() {
    openFilter({"Блик", {{"Позиция X, %", 0, 100, 30}, {"Позиция Y, %", 0, 100, 30}, {"Яркость, %", 10, 300, 100}},
                [](Image& img, const std::vector<float>& v) { lensFlare(img, img.w * v[0] / 100, img.h * v[1] / 100, v[2]); }, {}});
}

// ---------------------------------------------------------------- dialogs

void Editor::drawFilterDialog() {
    if (!filter) return;
    ImVec2 center = ImGui::GetMainViewport()->GetCenter();
    ImGui::SetNextWindowPos(ImVec2(center.x + 260, center.y), ImGuiCond_Appearing, ImVec2(0.5f, 0.5f));
    if (!ImGui::BeginPopupModal("##filter", nullptr, ImGuiWindowFlags_AlwaysAutoResize | ImGuiWindowFlags_NoTitleBar)) return;
    subheading(filter->title.c_str());
    ImGui::Separator();
    ImGui::Spacing();
    bool released = false;
    for (size_t i = 0; i < filter->params.size(); i++) {
        auto& p = filter->params[i];
        ImGui::SetNextItemWidth(280);
        if (p.integer) {
            int v = int(std::lround(filterVals[i]));
            if (ImGui::SliderInt(p.label, &v, int(p.min), int(p.max))) filterVals[i] = float(v);
        } else {
            ImGui::SliderFloat(p.label, &filterVals[i], p.min, p.max, "%.1f");
        }
        released |= ImGui::IsItemDeactivatedAfterEdit();
    }
    if (filter->customUi && filter->customUi()) filterCustomChanged = true;
    ImGui::Spacing();
    bool prevToggled = ImGui::Checkbox("Просмотр", &filterPreview);
    bool heavy = doc && size_t(doc->w) * doc->h > 4'000'000;
    bool stale = filterVals != filterShown || filterCustomChanged;
    bool dragging = ImGui::IsMouseDown(0);
    if (filterPreview && stale && (!heavy || released || filterShown.empty() || prevToggled || !dragging)) filterApplyPreview();
    if (!filterPreview && prevToggled) {
        doc->layer().img = filterBackup;
        filterShown.clear();
        invalidateAll();
    }
    ImGui::Spacing();
    float bw = 110;
    if (primaryButton("OK", ImVec2(bw, 0)) || ImGui::IsKeyPressed(ImGuiKey_Enter)) {
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

void Editor::drawNewDocument() {
    ImVec2 center = ImGui::GetMainViewport()->GetCenter();
    ImGui::SetNextWindowPos(center, ImGuiCond_Appearing, ImVec2(0.5f, 0.5f));
    ImGui::SetNextWindowSize(ImVec2(960, 600), ImGuiCond_Appearing);
    ImGui::PushStyleVar(ImGuiStyleVar_WindowPadding, ImVec2(20, 18));
    bool open = ImGui::BeginPopupModal("##newdoc", nullptr, ImGuiWindowFlags_NoTitleBar | ImGuiWindowFlags_NoResize);
    ImGui::PopStyleVar();
    if (!open) return;
    heading("Новый документ");
    ImGui::Spacing();
    const auto& cats = docCategories();
    // Category pills
    for (int i = 0; i < int(cats.size()); i++) {
        if (i) ImGui::SameLine(0, 6);
        bool on = newCategory == i;
        ImGui::PushStyleVar(ImGuiStyleVar_FrameRounding, 16);
        ImGui::PushStyleVar(ImGuiStyleVar_FramePadding, ImVec2(16, 6));
        if (on) ImGui::PushStyleColor(ImGuiCol_Button, IM_COL32(38, 128, 235, 255));
        if (ImGui::Button(cats[size_t(i)].name)) {
            newCategory = i;
            newPreset = -1;
        }
        if (on) ImGui::PopStyleColor();
        ImGui::PopStyleVar(2);
    }
    ImGui::Spacing();
    float rightW = 300;
    float bottomH = ImGui::GetFrameHeightWithSpacing() + 16;
    ImGui::BeginChild("##presets", ImVec2(-rightW - 16, -bottomH), ImGuiChildFlags_None);
    const auto& list = cats[size_t(newCategory)].presets;
    float avail = ImGui::GetContentRegionAvail().x;
    int cols = 3;
    float cw = (avail - (cols - 1) * 12) / cols, ch = 150;
    ImDrawList* dl = ImGui::GetWindowDrawList();
    for (int i = 0; i < int(list.size()); i++) {
        if (i % cols) ImGui::SameLine(0, 12);
        const DocPreset& p = list[size_t(i)];
        ImGui::PushID(i);
        ImVec2 a = ImGui::GetCursorScreenPos();
        bool clicked = ImGui::InvisibleButton("##card", ImVec2(cw, ch));
        bool dbl = ImGui::IsItemHovered() && ImGui::IsMouseDoubleClicked(0);
        bool hov = ImGui::IsItemHovered();
        ImGui::PopID();
        bool sel = newPreset == i;
        dl->AddRectFilled(a, ImVec2(a.x + cw, a.y + ch), sel ? IM_COL32(38, 128, 235, 50) : hov ? IM_COL32(38, 40, 50, 255) : IM_COL32(26, 27, 33, 255), 14);
        dl->AddRect(a, ImVec2(a.x + cw, a.y + ch), sel ? kAccent : hov ? IM_COL32(80, 82, 96, 255) : IM_COL32(40, 42, 52, 255), 14, 0, sel ? 2.f : 1.f);
        float k = std::min((cw - 60) / p.w, 70.f / p.h);
        float rw = std::max(6.f, p.w * k), rh = std::max(6.f, p.h * k);
        ImVec2 r0(a.x + (cw - rw) * 0.5f, a.y + 16 + (70 - rh) * 0.5f);
        dl->AddRectFilled(r0, ImVec2(r0.x + rw, r0.y + rh), IM_COL32(232, 232, 242, 255), 3);
        ImVec2 ts = ImGui::CalcTextSize(p.name);
        dl->AddText(ImVec2(a.x + (cw - ts.x) * 0.5f, a.y + 98), IM_COL32(235, 235, 245, 255), p.name);
        char buf[64];
        std::snprintf(buf, sizeof buf, "%d × %d px · %.0f ppi", p.w, p.h, p.dpi);
        ts = ImGui::CalcTextSize(buf);
        dl->AddText(ImVec2(a.x + (cw - ts.x) * 0.5f, a.y + 120), IM_COL32(128, 130, 146, 255), buf);
        if (clicked) {
            newPreset = i;
            newW = p.w;
            newH = p.h;
            newDpi = p.dpi;
            newName = p.name;
        }
        if (dbl) {
            newPreset = i;
            newW = p.w;
            newH = p.h;
            newDpi = p.dpi;
            newName = p.name;
            popupToOpen = "##createnow";
        }
    }
    ImGui::EndChild();
    ImGui::SameLine(0, 16);
    ImGui::PushStyleColor(ImGuiCol_ChildBg, IM_COL32(17, 18, 22, 255));
    ImGui::PushStyleVar(ImGuiStyleVar_WindowPadding, ImVec2(14, 14));
    ImGui::BeginChild("##details", ImVec2(rightW, -bottomH), ImGuiChildFlags_Borders | ImGuiChildFlags_AlwaysUseWindowPadding);
    ImGui::PopStyleVar();
    ImGui::PopStyleColor();
    subheading("Сведения о шаблоне");
    ImGui::Spacing();
    ImGui::SetNextItemWidth(-1);
    ImGui::InputText("##name", &newName);
    ImGui::Spacing();
    const char* units[] = {"Пиксели", "Сантиметры", "Миллиметры", "Дюймы"};
    ImGui::TextDisabled("Ширина");
    float f = unitFactor(newUnit, newDpi);
    float wv = newW / f, hv = newH / f;
    ImGui::SetNextItemWidth(130);
    if (ImGui::InputFloat("##w", &wv, 0, 0, newUnit ? "%.2f" : "%.0f")) newW = std::clamp(int(std::lround(wv * f)), 1, 16384);
    ImGui::SameLine();
    ImGui::SetNextItemWidth(-1);
    ImGui::Combo("##unit", &newUnit, units, 4);
    ImGui::TextDisabled("Высота");
    ImGui::SetNextItemWidth(130);
    if (ImGui::InputFloat("##h", &hv, 0, 0, newUnit ? "%.2f" : "%.0f")) newH = std::clamp(int(std::lround(hv * f)), 1, 16384);
    ImGui::SameLine();
    // orientation toggles
    float ob = ImGui::GetFrameHeight();
    for (int o = 0; o < 2; o++) {
        if (o) ImGui::SameLine(0, 4);
        bool portrait = o == 0;
        bool on = portrait ? newH >= newW : newW > newH;
        ImVec2 q = ImGui::GetCursorScreenPos();
        ImGui::PushID(o + 300);
        if (ImGui::InvisibleButton("##orient", ImVec2(ob, ob)) && !on) std::swap(newW, newH);
        ImGui::PopID();
        ImDrawList* d2 = ImGui::GetWindowDrawList();
        d2->AddRectFilled(q, ImVec2(q.x + ob, q.y + ob), on ? kAccent : IM_COL32(36, 38, 45, 255), 6);
        float rw = portrait ? ob * 0.4f : ob * 0.62f, rh = portrait ? ob * 0.62f : ob * 0.4f;
        d2->AddRect(ImVec2(q.x + (ob - rw) * 0.5f, q.y + (ob - rh) * 0.5f), ImVec2(q.x + (ob + rw) * 0.5f, q.y + (ob + rh) * 0.5f), IM_COL32_WHITE, 2, 0, 1.5f);
        ImGui::SetItemTooltip(portrait ? "Книжная" : "Альбомная");
    }
    ImGui::TextDisabled("Разрешение, пикс/дюйм");
    ImGui::SetNextItemWidth(-1);
    ImGui::InputFloat("##dpi", &newDpi, 0, 0, "%.0f");
    newDpi = std::clamp(newDpi, 1.f, 2400.f);
    ImGui::TextDisabled("Фон");
    const char* bgs[] = {"Белый", "Чёрный", "Прозрачный", "Фоновый цвет", "Другой…"};
    ImGui::SetNextItemWidth(newBg == 4 ? -ImGui::GetFrameHeight() - 6 : -1);
    ImGui::Combo("##bg", &newBg, bgs, 5);
    if (newBg == 4) {
        ImGui::SameLine();
        ImVec4 v = toVec4(newBgColor);
        if (ImGui::ColorEdit3("##bgc", &v.x, ImGuiColorEditFlags_NoInputs)) newBgColor = fromVec4(v);
    }
    ImGui::Spacing();
    ImGui::Separator();
    double mb = double(newW) * newH * 4 / (1024.0 * 1024.0);
    ImGui::TextDisabled("%d × %d px", newW, newH);
    ImGui::TextDisabled("%.1f × %.1f см при %.0f ppi", newW / newDpi * 2.54, newH / newDpi * 2.54, newDpi);
    ImGui::TextDisabled("Слой в памяти: %.1f МБ", mb);
    ImGui::EndChild();

    ImGui::Spacing();
    float bw = 130;
    ImGui::SetCursorPosX(ImGui::GetWindowWidth() - bw * 2 - 20 - 8);
    bool create = false;
    if (ImGui::Button("Закрыть", ImVec2(bw, 0)) || ImGui::IsKeyPressed(ImGuiKey_Escape)) ImGui::CloseCurrentPopup();
    ImGui::SameLine();
    if (primaryButton("Создать", ImVec2(bw, 0)) || ImGui::IsKeyPressed(ImGuiKey_Enter) || popupToOpen == "##createnow") create = true;
    if (create) {
        if (popupToOpen == "##createnow") popupToOpen.clear();
        RGBA bg = newBg == 0 ? RGBA{255, 255, 255, 255} : newBg == 1 ? RGBA{0, 0, 0, 255} : newBg == 2 ? RGBA{} : newBg == 3 ? secondary : newBgColor;
        auto d = std::make_unique<Document>(Document::blank(newW, newH, bg));
        d->title = newName.empty() ? "Без имени-" + std::to_string(docCounter) : newName;
        docCounter++;
        openTab(std::move(d));
        ImGui::CloseCurrentPopup();
    }
    ImGui::EndPopup();
}

void Editor::drawLayerStyle() {
    ImVec2 center = ImGui::GetMainViewport()->GetCenter();
    ImGui::SetNextWindowPos(ImVec2(center.x + 120, center.y), ImGuiCond_Appearing, ImVec2(0.5f, 0.5f));
    ImGui::SetNextWindowSize(ImVec2(780, 560), ImGuiCond_Appearing);
    ImGui::PushStyleVar(ImGuiStyleVar_WindowPadding, ImVec2(18, 16));
    bool open = ImGui::BeginPopupModal("##layerstyle", nullptr, ImGuiWindowFlags_NoTitleBar);
    ImGui::PopStyleVar();
    if (!open) return;
    if (!doc) {
        ImGui::CloseCurrentPopup();
        ImGui::EndPopup();
        return;
    }
    LayerFx& fx = doc->layer().fx;
    LayerFx before = fx;
    heading("Стиль слоя");
    ImGui::TextDisabled("Слой: %s", doc->layer().name.c_str());
    ImGui::Spacing();
    float bottomH = ImGui::GetFrameHeightWithSpacing() + 12;
    ImGui::PushStyleColor(ImGuiCol_ChildBg, IM_COL32(17, 18, 22, 255));
    ImGui::BeginChild("##fxlist", ImVec2(240, -bottomH), ImGuiChildFlags_Borders | ImGuiChildFlags_AlwaysUseWindowPadding);
    ImGui::PopStyleColor();
    subheading("Эффекты");
    struct Item { const char* name; bool* on; };
    Item items[] = {{"Тень", &fx.dropShadow.on},       {"Внешнее свечение", &fx.outerGlow.on}, {"Внутреннее свечение", &fx.innerGlow.on},
                    {"Тиснение", &fx.bevel.on},       {"Обводка", &fx.stroke.on},             {"Наложение цвета", &fx.colorOverlay.on},
                    {"Наложение градиента", &fx.gradientOverlay.on}};
    for (int i = 0; i < 7; i++) {
        ImGui::PushID(i);
        ImGui::Checkbox("##on", items[i].on);
        ImGui::SameLine();
        if (ImGui::Selectable(items[i].name, fxPage == i)) {
            fxPage = i;
            *items[i].on = true;
        }
        ImGui::PopID();
    }
    ImGui::Spacing();
    subheading("Быстрые стили");
    float bw = ImGui::GetContentRegionAvail().x;
    auto quick = [&](const char* name, auto&& fn) {
        if (ImGui::Button(name, ImVec2(bw, 0))) {
            fx = {};
            fn(fx);
        }
    };
    quick("Неон", [](LayerFx& f) {
        f.outerGlow.on = true; f.outerGlow.color = {0, 229, 255, 255}; f.outerGlow.size = 22; f.outerGlow.opacity = 0.9f; f.outerGlow.spread = 0.2f;
        f.innerGlow.on = true; f.innerGlow.color = {255, 255, 255, 255}; f.innerGlow.size = 6; f.innerGlow.opacity = 0.8f;
        f.colorOverlay.on = true; f.colorOverlay.color = {120, 240, 255, 255};
    });
    quick("Золото", [](LayerFx& f) {
        f.gradientOverlay.on = true;
        f.gradientOverlay.gradient = {"", {{0, {110, 74, 18, 255}}, {0.45f, {245, 205, 100, 255}}, {0.55f, {255, 240, 180, 255}}, {1, {150, 100, 25, 255}}}};
        f.bevel.on = true; f.bevel.size = 8;
        f.dropShadow.on = true; f.dropShadow.distance = 6; f.dropShadow.size = 10; f.dropShadow.opacity = 0.6f;
    });
    quick("Наклейка", [](LayerFx& f) {
        f.stroke.on = true; f.stroke.color = {255, 255, 255, 255}; f.stroke.size = 10;
        f.dropShadow.on = true; f.dropShadow.distance = 8; f.dropShadow.size = 16; f.dropShadow.opacity = 0.5f;
    });
    quick("Стекло", [](LayerFx& f) {
        f.bevel.on = true; f.bevel.size = 14; f.bevel.highlight = 0.9f; f.bevel.shadow = 0.4f;
        f.innerGlow.on = true; f.innerGlow.color = {255, 255, 255, 255}; f.innerGlow.size = 12; f.innerGlow.opacity = 0.5f;
        f.dropShadow.on = true; f.dropShadow.distance = 4; f.dropShadow.size = 12; f.dropShadow.opacity = 0.35f;
    });
    quick("Мягкая тень", [](LayerFx& f) {
        f.dropShadow.on = true; f.dropShadow.distance = 14; f.dropShadow.size = 30; f.dropShadow.opacity = 0.45f;
    });
    quick("Сбросить всё", [](LayerFx&) {});
    ImGui::EndChild();
    ImGui::SameLine(0, 14);
    ImGui::BeginChild("##fxpage", ImVec2(0, -bottomH));
    auto color = [](const char* label, RGBA& c) {
        ImVec4 v = toVec4(c);
        if (ImGui::ColorEdit3(label, &v.x)) c = fromVec4(v);
    };
    auto pct = [](const char* label, float& v) {
        float x = v * 100;
        if (ImGui::SliderFloat(label, &x, 0, 100, "%.0f%%")) v = x / 100;
    };
    ImGui::PushItemWidth(300);
    switch (fxPage) {
        case 0: {
            auto& s = fx.dropShadow;
            subheading("Тень");
            ImGui::Checkbox("Включить", &s.on);
            color("Цвет", s.color);
            pct("Непрозрачность", s.opacity);
            ImGui::SliderFloat("Угол", &s.angle, -180, 180, "%.0f°");
            ImGui::SliderFloat("Смещение", &s.distance, 0, 200, "%.0f px");
            pct("Размах", s.spread);
            ImGui::SliderFloat("Размер", &s.size, 0, 150, "%.0f px");
            break;
        }
        case 1:
        case 2: {
            auto& g = fxPage == 1 ? fx.outerGlow : fx.innerGlow;
            subheading(fxPage == 1 ? "Внешнее свечение" : "Внутреннее свечение");
            ImGui::Checkbox("Включить", &g.on);
            color("Цвет", g.color);
            pct("Непрозрачность", g.opacity);
            if (fxPage == 1) pct("Размах", g.spread);
            ImGui::SliderFloat("Размер", &g.size, 1, 150, "%.0f px");
            break;
        }
        case 3: {
            auto& b = fx.bevel;
            subheading("Тиснение");
            ImGui::Checkbox("Включить", &b.on);
            ImGui::SliderFloat("Размер", &b.size, 1, 100, "%.0f px");
            ImGui::SliderFloat("Глубина", &b.depth, 1, 500, "%.0f%%");
            ImGui::SliderFloat("Угол света", &b.angle, -180, 180, "%.0f°");
            ImGui::SliderFloat("Высота света", &b.altitude, 0, 90, "%.0f°");
            pct("Подсветка", b.highlight);
            pct("Тень", b.shadow);
            break;
        }
        case 4: {
            auto& s = fx.stroke;
            subheading("Обводка");
            ImGui::Checkbox("Включить", &s.on);
            ImGui::SliderFloat("Размер", &s.size, 1, 100, "%.0f px");
            const char* pos[] = {"Снаружи", "По центру", "Внутри"};
            ImGui::Combo("Положение", &s.position, pos, 3);
            color("Цвет", s.color);
            pct("Непрозрачность", s.opacity);
            break;
        }
        case 5:
            subheading("Наложение цвета");
            ImGui::Checkbox("Включить", &fx.colorOverlay.on);
            color("Цвет", fx.colorOverlay.color);
            pct("Непрозрачность", fx.colorOverlay.opacity);
            break;
        case 6: {
            auto& g = fx.gradientOverlay;
            subheading("Наложение градиента");
            ImGui::Checkbox("Включить", &g.on);
            ImGui::TextDisabled("Градиент");
            gradientCombo("##fxgrad", g.gradient, 300);
            int t = int(g.type);
            const char* types[] = {"Линейный", "Радиальный", "Угловой", "Зеркальный", "Ромбовидный"};
            if (ImGui::Combo("Стиль", &t, types, 5)) g.type = GradientType(t);
            ImGui::SliderFloat("Угол", &g.angle, -180, 180, "%.0f°");
            pct("Непрозрачность", g.opacity);
            break;
        }
    }
    ImGui::PopItemWidth();
    ImGui::Spacing();
    ImGui::TextDisabled("Стиль не меняет пиксели слоя.");
    ImGui::EndChild();

    // Live preview: re-render when anything changed.
    if (std::memcmp(&before.dropShadow, &fx.dropShadow, sizeof fx.dropShadow) != 0 ||
        std::memcmp(&before.outerGlow, &fx.outerGlow, sizeof fx.outerGlow) != 0 ||
        std::memcmp(&before.innerGlow, &fx.innerGlow, sizeof fx.innerGlow) != 0 ||
        std::memcmp(&before.bevel, &fx.bevel, sizeof fx.bevel) != 0 || std::memcmp(&before.stroke, &fx.stroke, sizeof fx.stroke) != 0 ||
        std::memcmp(&before.colorOverlay, &fx.colorOverlay, sizeof fx.colorOverlay) != 0 || before.gradientOverlay.on != fx.gradientOverlay.on ||
        before.gradientOverlay.type != fx.gradientOverlay.type || before.gradientOverlay.angle != fx.gradientOverlay.angle ||
        before.gradientOverlay.opacity != fx.gradientOverlay.opacity || before.gradientOverlay.gradient.stops.size() != fx.gradientOverlay.gradient.stops.size() ||
        !std::equal(before.gradientOverlay.gradient.stops.begin(), before.gradientOverlay.gradient.stops.end(), fx.gradientOverlay.gradient.stops.begin(),
                    [](const GradientStop& a, const GradientStop& b) { return a.pos == b.pos && a.color == b.color; })) {
        invalidateAll();
    }

    ImGui::Spacing();
    float bw2 = 120;
    ImGui::SetCursorPosX(ImGui::GetWindowWidth() - bw2 * 2 - 18 - 8);
    if (ImGui::Button("Отмена", ImVec2(bw2, 0)) || ImGui::IsKeyPressed(ImGuiKey_Escape)) {
        fx = fxBackup;
        doc->popLast();
        invalidateAll();
        fxOpen = false;
        ImGui::CloseCurrentPopup();
    }
    ImGui::SameLine();
    if (primaryButton("OK", ImVec2(bw2, 0))) {
        fxOpen = false;
        thumbsDirty = true;
        ImGui::CloseCurrentPopup();
    }
    ImGui::EndPopup();
}

void Editor::drawDialogs() {
    if (!popupToOpen.empty() && popupToOpen != "##createnow") {
        ImGui::OpenPopup(popupToOpen.c_str());
        popupToOpen.clear();
    }
    ImVec2 center = ImGui::GetMainViewport()->GetCenter();
    auto modal = [&](const char* name) {
        ImGui::SetNextWindowPos(center, ImGuiCond_Appearing, ImVec2(0.5f, 0.5f));
        return ImGui::BeginPopupModal(name, nullptr, ImGuiWindowFlags_AlwaysAutoResize);
    };
    float bw = 120;

    drawNewDocument();
    drawLayerStyle();
    drawFilterDialog();

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
        if (primaryButton("OK", ImVec2(bw, 0))) {
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
            if (i % 3) ImGui::SameLine(0, 3);
            ImGui::PushID(i);
            bool on = anchor == i;
            if (on) ImGui::PushStyleColor(ImGuiCol_Button, ImGui::GetStyleColorVec4(ImGuiCol_ButtonActive));
            if (ImGui::Button(on ? "●" : " ", ImVec2(30, 30))) anchor = i;
            if (on) ImGui::PopStyleColor();
            ImGui::PopID();
        }
        ImGui::Spacing();
        if (primaryButton("OK", ImVec2(bw, 0))) {
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
        if (primaryButton("OK", ImVec2(bw, 0))) {
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

    if (modal("Обводка")) {
        ImGui::TextDisabled("Обводит границу выделения основным цветом");
        ImGui::SetNextItemWidth(220);
        ImGui::SliderFloat("Толщина, px", &strokeWidth, 1, 100, "%.0f");
        if (primaryButton("OK", ImVec2(bw, 0))) {
            cmdStrokeSelection(strokeWidth);
            ImGui::CloseCurrentPopup();
        }
        ImGui::SameLine();
        if (ImGui::Button("Отмена", ImVec2(bw, 0)) || ImGui::IsKeyPressed(ImGuiKey_Escape)) ImGui::CloseCurrentPopup();
        ImGui::EndPopup();
    }

    if (modal("Сохранить изменения?")) {
        ImGui::Text("Сохранить изменения в «%s» перед закрытием?", doc ? doc->title.c_str() : "");
        ImGui::Spacing();
        if (primaryButton("Сохранить", ImVec2(bw, 0))) {
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
        if (primaryButton("OK", ImVec2(bw, 0)) || ImGui::IsKeyPressed(ImGuiKey_Enter) || ImGui::IsKeyPressed(ImGuiKey_Escape))
            ImGui::CloseCurrentPopup();
        ImGui::EndPopup();
    }

    if (showAbout) {
        ImGui::SetNextWindowPos(center, ImGuiCond_Appearing, ImVec2(0.5f, 0.5f));
        if (ImGui::Begin("О программе", &showAbout, ImGuiWindowFlags_AlwaysAutoResize | ImGuiWindowFlags_NoDocking | ImGuiWindowFlags_NoCollapse)) {
            if (splashTex) {
                float w = 480, h = w * splashH / std::max(1, splashW);
                ImGui::Image(ImTextureID(uintptr_t(splashTex)), ImVec2(w, h));
            }
            subheading("ArtGraf 2.0");
            ImGui::TextDisabled("Растровый графический редактор");
            ImGui::Separator();
            ImGui::TextUnformatted("Сделано на: SDL2, Dear ImGui, OpenGL, stb_image, stb_image_write,\n"
                                   "stb_image_resize2, stb_truetype, nlohmann/json, miniz,\n"
                                   "nativefiledialog-extended.");
        }
        ImGui::End();
    }

    if (showShortcuts) {
        ImGui::SetNextWindowPos(center, ImGuiCond_Appearing, ImVec2(0.5f, 0.5f));
        ImGui::SetNextWindowSize(ImVec2(620, 560), ImGuiCond_Appearing);
        if (ImGui::Begin("Горячие клавиши", &showShortcuts, ImGuiWindowFlags_NoDocking | ImGuiWindowFlags_NoCollapse)) {
            if (ImGui::BeginTable("##keys", 2, ImGuiTableFlags_RowBg | ImGuiTableFlags_BordersInnerV)) {
                auto row = [](const char* k, const char* v) {
                    ImGui::TableNextRow();
                    ImGui::TableNextColumn();
                    ImGui::TextUnformatted(k);
                    ImGui::TableNextColumn();
                    ImGui::TextUnformatted(v);
                };
                for (const auto& g : toolGroups()) {
                    std::string names;
                    for (Tool t : g) names += (names.empty() ? "" : " / ") + std::string(toolInfo(t).name);
                    char key[16];
                    std::snprintf(key, sizeof key, g.size() > 1 ? "%c, Shift+%c" : "%c", char(std::toupper(int(toolInfo(g[0]).key))),
                                  char(std::toupper(int(toolInfo(g[0]).key))));
                    row(key, names.c_str());
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
                row("Ctrl+M / Ctrl+L / Ctrl+U / Ctrl+B", "Кривые / уровни / тон-насыщенность / баланс");
                row("[ / ]", "Размер кисти");
                row("1 … 0", "Непрозрачность кисти 10 … 100%");
                row("F5", "Настройки кисти");
                row("X / D", "Поменять цвета / цвета по умолчанию");
                row("Пробел + мышь", "Двигать вид");
                row("Колесо мыши", "Масштаб");
                row("Ctrl+0 / Ctrl+1", "Целиком / 100%");
                row("Ctrl+Tab", "Следующий документ");
                row("Ctrl+S / Ctrl+Shift+E", "Сохранить проект / экспорт");
                ImGui::EndTable();
            }
        }
        ImGui::End();
    }
}

}  // namespace ag
