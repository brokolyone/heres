#include "editor.h"

#include <cmath>
#include <cstring>
#include <filesystem>

#include "gl.h"

#include "clipboard.h"
#include "effects.h"
#include "filters.h"
#include "io.h"
#include "parallel.h"

namespace ag {

const ToolInfo& toolInfo(Tool t) {
    static const ToolInfo k[] = {
        {"Перемещение", SDLK_v, "Перетащите слой или выделенную область. Стрелки сдвигают на 1 px, Shift — на 10"},
        {"Прямоугольная область", SDLK_m, "Shift — добавить, Alt — вычесть, Shift+Alt — пересечение"},
        {"Овальная область", SDLK_m, "Shift — добавить, Alt — вычесть, Shift+Alt — пересечение"},
        {"Лассо", SDLK_l, "Обведите область. Shift — добавить, Alt — вычесть"},
        {"Прямолинейное лассо", SDLK_l, "Клик — вершина, двойной клик или Enter — замкнуть, Esc — отмена"},
        {"Волшебная палочка", SDLK_w, "Выделяет похожие по цвету пиксели"},
        {"Кадрирование", SDLK_c, "Нарисуйте рамку, Enter — применить, Esc — отмена"},
        {"Пипетка", SDLK_i, "Клик — основной цвет, Alt+клик — фоновый"},
        {"Точечная восстанавливающая кисть", SDLK_j, "Закрасьте дефект — он заменится соседней текстурой"},
        {"Штамп", SDLK_s, "Alt+клик — точка-источник, затем рисуйте"},
        {"Кисть", SDLK_b, "[ и ] — размер, Shift+клик — прямая линия, Alt+клик — взять цвет"},
        {"Карандаш", SDLK_b, "Жёсткие пиксельные края. [ и ] — размер"},
        {"Ластик", SDLK_e, "Стирает до прозрачности. [ и ] — размер"},
        {"Градиент", SDLK_g, "Протяните линию. Shift — шаг 45°"},
        {"Заливка", SDLK_g, "Заливает похожие по цвету пиксели основным цветом"},
        {"Размытие", SDLK_r, "Смягчает участки, по которым проводите"},
        {"Резкость", SDLK_r, "Усиливает детали, по которым проводите"},
        {"Палец", SDLK_r, "Размазывает краску, как пальцем по мокрому"},
        {"Осветлитель", SDLK_o, "Высветляет участки. Диапазон — в панели параметров"},
        {"Затемнитель", SDLK_o, "Затемняет участки. Диапазон — в панели параметров"},
        {"Губка", SDLK_o, "Убирает или добавляет насыщенность"},
        {"Текст", SDLK_t, "Клик — начать ввод, Ctrl+Enter — применить, Esc — отмена"},
        {"Фигуры", SDLK_u, "Shift — квадрат, круг или шаг 45°"},
        {"Рука", SDLK_h, "Двигает вид. Также пробел или средняя кнопка мыши"},
        {"Масштаб", SDLK_z, "Клик — приблизить, Alt+клик — отдалить, колесо — масштаб"},
    };
    static_assert(sizeof(k) / sizeof(k[0]) == size_t(Tool::Count));
    return k[int(t)];
}

const std::vector<std::vector<Tool>>& toolGroups() {
    static const std::vector<std::vector<Tool>> g = {
        {Tool::Move},
        {Tool::RectSelect, Tool::EllipseSelect},
        {Tool::Lasso, Tool::PolyLasso},
        {Tool::MagicWand},
        {Tool::Crop},
        {Tool::Eyedropper},
        {Tool::SpotHeal, Tool::Clone},
        {Tool::Brush, Tool::Pencil},
        {Tool::Eraser},
        {Tool::Gradient, Tool::Bucket},
        {Tool::Blur, Tool::Sharpen, Tool::Smudge},
        {Tool::Dodge, Tool::Burn, Tool::Sponge},
        {Tool::Text},
        {Tool::Shape},
        {Tool::Hand},
        {Tool::Zoom},
    };
    return g;
}

bool Editor::isBrushTool(Tool t) {
    return t == Tool::Brush || t == Tool::Pencil || t == Tool::Eraser || t == Tool::Clone || t == Tool::SpotHeal ||
           isRetouchTool(t);
}

bool Editor::isRetouchTool(Tool t) {
    return t == Tool::Blur || t == Tool::Sharpen || t == Tool::Smudge || t == Tool::Dodge || t == Tool::Burn ||
           t == Tool::Sponge;
}

ImU32 toU32(RGBA c) { return IM_COL32(c.r, c.g, c.b, c.a); }
ImVec4 toVec4(RGBA c) { return ImVec4(c.r / 255.f, c.g / 255.f, c.b / 255.f, c.a / 255.f); }
RGBA fromVec4(const ImVec4& v) { return {clamp8(v.x * 255), clamp8(v.y * 255), clamp8(v.z * 255), clamp8(v.w * 255)}; }

Editor::Editor(SDL_Window* w) : window(w) {
    const auto& bb = builtinBrushes();
    tb[Tool::Brush].preset = bb[2];
    BrushPreset pencil;
    pencil.name = "Карандаш";
    pencil.hardness = 1;
    pencil.size = 2;
    pencil.spacing = 0.25f;
    pencil.aliased = true;
    tb[Tool::Pencil].preset = pencil;
    BrushPreset round;
    round.hardness = 0.6f;
    round.size = 40;
    tb[Tool::Eraser].preset = round;
    round.hardness = 0.5f;
    round.size = 50;
    tb[Tool::Clone].preset = round;
    round.hardness = 0.8f;
    round.size = 30;
    tb[Tool::SpotHeal].preset = round;
    for (Tool t : {Tool::Blur, Tool::Sharpen, Tool::Smudge, Tool::Dodge, Tool::Burn, Tool::Sponge}) {
        round.hardness = 0.3f;
        round.size = 50;
        tb[t].preset = round;
        tb[t].strength = 0.5f;
    }
    tb[Tool::Bucket].opacity = 1.f;
    for (size_t i = 0; i < toolGroups().size(); i++) groupTool[int(i)] = toolGroups()[i][0];
    groupTool[7] = Tool::Brush;
    gradient = gradientPresets(primary, secondary)[0];
}

Editor::~Editor() {
    if (tex) glDeleteTextures(1, &tex);
    if (!thumbs.empty()) glDeleteTextures(GLsizei(thumbs.size()), thumbs.data());
    if (logoTex) glDeleteTextures(1, &logoTex);
    if (splashTex) glDeleteTextures(1, &splashTex);
    for (auto& [k, t] : brushPreviewTex) glDeleteTextures(1, &t);
}

void Editor::touchGesture(float scale, float cx, float cy, float dx, float dy) {
    if (!doc) return;
    if (dragging) {  // a second finger turns a starting stroke into a gesture
        dragging = false;
        cancelLive();
        lasso.clear();
    }
    zoomAt(zoom * scale, ImVec2(cx, cy));
    pan.x += dx;
    pan.y += dy;
}

bool Editor::animating() const {
    return (doc && doc->sel.active()) || textEditing || dragging || cropActive || polyActive;
}

// ---------------------------------------------------------------- preferences

void Editor::loadPrefs() {
    std::vector<uint8_t> data;
    if (!readFile(prefDir + "recent.txt", data)) return;
    std::string s(data.begin(), data.end()), line;
    recentFiles.clear();
    for (char c : s) {
        if (c == '\n') {
            if (!line.empty()) recentFiles.push_back(line);
            line.clear();
        } else if (c != '\r') {
            line += c;
        }
    }
    if (!line.empty()) recentFiles.push_back(line);
}

void Editor::savePrefs() {
    std::string s;
    for (auto& r : recentFiles) s += r + "\n";
    writeFile(prefDir + "recent.txt", std::vector<uint8_t>(s.begin(), s.end()));
}

void Editor::addRecent(const std::string& path) {
    recentFiles.erase(std::remove(recentFiles.begin(), recentFiles.end(), path), recentFiles.end());
    recentFiles.insert(recentFiles.begin(), path);
    if (recentFiles.size() > 12) recentFiles.resize(12);
    savePrefs();
}

void Editor::pushRecentColor(RGBA c) {
    c.a = 255;
    recentColors.erase(std::remove(recentColors.begin(), recentColors.end(), c), recentColors.end());
    recentColors.insert(recentColors.begin(), c);
    if (recentColors.size() > 12) recentColors.resize(12);
}

// ---------------------------------------------------------------- tabs

void Editor::syncTabState() {
    if (current < 0 || current >= int(tabs.size())) return;
    tabs[size_t(current)].zoom = zoom;
    tabs[size_t(current)].pan = pan;
    tabs[size_t(current)].fitPending = fitPending;
}

void Editor::switchTab(int i) {
    if (i == current && doc) return;
    if (textEditing) commitText();
    cancelLive();
    syncTabState();
    cropActive = false;
    polyActive = false;
    lasso.clear();
    cloneHasSource = false;
    current = i;
    if (i < 0 || i >= int(tabs.size())) {
        current = -1;
        doc = nullptr;
        return;
    }
    DocTab& t = tabs[size_t(i)];
    doc = t.doc.get();
    zoom = t.zoom;
    pan = t.pan;
    fitPending = t.fitPending;
    texW = texH = 0;  // forces texture re-creation
    thumbsDirty = true;
    tabSelectRequest = true;
    selectionChanged();
    invalidateAll();
}

void Editor::openTab(std::unique_ptr<Document> d) {
    syncTabState();
    tabs.push_back({std::move(d), 1.f, {0, 0}, true});
    current = -2;  // force switch
    switchTab(int(tabs.size()) - 1);
}

void Editor::closeTabNow(int i) {
    if (i < 0 || i >= int(tabs.size())) return;
    if (i == current) {
        if (textEditing) cancelText();
        cancelLive();
    }
    syncTabState();
    tabs.erase(tabs.begin() + i);
    int next = tabs.empty() ? -1 : std::min(i, int(tabs.size()) - 1);
    current = -2;
    switchTab(next);
}

void Editor::closeTab(int i) {
    switchTab(i);
    guardUnsaved([this] { closeTabNow(current); });
}

void Editor::requestQuit() {
    for (int i = 0; i < int(tabs.size()); i++)
        if (tabs[size_t(i)].doc->dirty) {
            switchTab(i);
            guardUnsaved([this] {
                closeTabNow(current);
                requestQuit();
            });
            return;
        }
    quitNow = true;
}

// ---------------------------------------------------------------- document & view

void Editor::invalidate(Rect r) {
    if (!doc) return;
    doc->layer().touch();
    dirty = dirty.unite(r.intersect({0, 0, doc->w, doc->h}));
}

void Editor::invalidateAll() {
    if (!doc) return;
    doc->layer().touch();
    dirty = {0, 0, doc->w, doc->h};
}

void Editor::selectionChanged() { selOutlineDirty = true; }

void Editor::updateTexture() {
    if (!doc) return;
    if (doc->w != texW || doc->h != texH) {
        if (!tex) glGenTextures(1, &tex);
        glBindTexture(GL_TEXTURE_2D, tex);
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE);
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE);
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_NEAREST);
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR);
        texLinear = true;
        glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA, doc->w, doc->h, 0, GL_RGBA, GL_UNSIGNED_BYTE, nullptr);
        texW = doc->w;
        texH = doc->h;
        display = Image(texW, texH);
        dirty = {0, 0, texW, texH};
        selOutlineDirty = true;
    }
    bool wantLinear = zoom < 1.f;
    if (wantLinear != texLinear) {
        glBindTexture(GL_TEXTURE_2D, tex);
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, wantLinear ? GL_LINEAR : GL_NEAREST);
        texLinear = wantLinear;
    }
    if (dirty.empty()) return;
    Rect r = dirty;
    dirty = {};
    Image ov(r.w(), r.h());
    bool hasOv = previewActive(r, ov);
    doc->composite(r, display, hasOv ? &ov : nullptr, true);
    glBindTexture(GL_TEXTURE_2D, tex);
    glPixelStorei(GL_UNPACK_ALIGNMENT, 1);
    glPixelStorei(GL_UNPACK_ROW_LENGTH, display.w);
    glTexSubImage2D(GL_TEXTURE_2D, 0, r.x0, r.y0, r.w(), r.h(), GL_RGBA, GL_UNSIGNED_BYTE, display.at(r.x0, r.y0));
    glPixelStorei(GL_UNPACK_ROW_LENGTH, 0);
}

void Editor::updateThumbs() {
    if (!doc || !thumbsDirty) return;
    thumbsDirty = false;
    size_t n = doc->layers.size();
    while (thumbs.size() < n) {
        GLuint t;
        glGenTextures(1, &t);
        glBindTexture(GL_TEXTURE_2D, t);
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR);
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR);
        thumbs.push_back(t);
    }
    const int TW = 56, TH = 42;
    float k = std::min(float(TW) / doc->w, float(TH) / doc->h);
    int tw = std::max(1, int(doc->w * k)), th = std::max(1, int(doc->h * k));
    Image t(tw, th);
    for (size_t i = 0; i < n; i++) {
        const Image& src = doc->layers[i].img;
        for (int y = 0; y < th; y++)
            for (int x = 0; x < tw; x++) {
                uint8_t c = (((x >> 2) + (y >> 2)) & 1) ? 150 : 200;
                RGBA s = src.get(std::min(src.w - 1, int((x + 0.5f) / k)), std::min(src.h - 1, int((y + 0.5f) / k)));
                t.set(x, y, over({c, c, c, 255}, s));
            }
        glBindTexture(GL_TEXTURE_2D, thumbs[i]);
        glPixelStorei(GL_UNPACK_ALIGNMENT, 1);
        glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA, tw, th, 0, GL_RGBA, GL_UNSIGNED_BYTE, t.px.data());
    }
}

void Editor::fitView() {
    if (!doc || canvasSize.x < 10) return;
    float z = std::min((canvasSize.x - 60) / doc->w, (canvasSize.y - 60) / doc->h);
    zoom = std::clamp(z, 0.01f, 64.f);
    pan = ImVec2((canvasSize.x - doc->w * zoom) * 0.5f, (canvasSize.y - doc->h * zoom) * 0.5f);
}

void Editor::zoomAt(float z, ImVec2 s) {
    z = std::clamp(z, 0.01f, 64.f);
    Vec2 d = toDoc(s);
    zoom = z;
    pan = ImVec2(s.x - canvasMin.x - d.x * zoom, s.y - canvasMin.y - d.y * zoom);
}

ImVec2 Editor::toScreen(Vec2 p) const { return ImVec2(canvasMin.x + pan.x + p.x * zoom, canvasMin.y + pan.y + p.y * zoom); }
Vec2 Editor::toDoc(ImVec2 s) const { return {(s.x - canvasMin.x - pan.x) / zoom, (s.y - canvasMin.y - pan.y) / zoom}; }

RGBA Editor::mergedPixel(int x, int y) const {
    RGBA acc{};
    for (auto& l : doc->layers)
        if (l.visible) acc = blendPixel(acc, l.styled().get(x, y), l.blend, l.opacity);
    return acc;
}

void Editor::updateTitle() {
    static std::string last;
    std::string t = doc ? doc->title + (doc->dirty ? " *" : "") + " — ArtGraf" : "ArtGraf";
    if (t != last) {
        SDL_SetWindowTitle(window, t.c_str());
        last = t;
    }
}

void Editor::showError(const std::string& msg) {
    errorText = msg;
    popupToOpen = "Ошибка";
}

void Editor::guardUnsaved(std::function<void()> action) {
    if (doc && doc->dirty) {
        pendingDiscard = std::move(action);
        popupToOpen = "Сохранить изменения?";
    } else {
        action();
    }
}

// ---------------------------------------------------------------- files

static const std::vector<FileDialog::Filter> kOpenFilters = {
    {"Изображения и проекты", "agf,png,jpg,jpeg,bmp,tga,gif,psd,hdr,pic,pnm,ppm,pgm"},
    {"Проект ArtGraf", "agf"},
    {"Изображения", "png,jpg,jpeg,bmp,tga,gif,psd"},
};

Image Editor::loadImageOrError(const std::string& path, bool& ok) {
    Image img;
    std::string err;
    ok = loadImage(path, img, err);
    if (!ok) showError(err);
    return img;
}

void Editor::openPath(const std::string& path) {
    for (int i = 0; i < int(tabs.size()); i++)
        if (!tabs[size_t(i)].doc->path.empty() && tabs[size_t(i)].doc->path == path) return switchTab(i);
    std::string err;
    if (lowerExt(path) == "agf") {
        auto d = std::make_unique<Document>();
        if (!loadProject(path, *d, err)) return showError(err);
        openTab(std::move(d));
        addRecent(path);
        return;
    }
    bool ok;
    Image img = loadImageOrError(path, ok);
    if (!ok) return;
    openTab(std::make_unique<Document>(Document::fromImage(std::move(img), fileStem(path))));
    addRecent(path);
}

void Editor::dropPath(const std::string& path) {
    if (!doc || lowerExt(path) == "agf") return openPath(path);
    placeImage(path);
}

void Editor::placeImage(const std::string& path) {
    bool ok;
    Image img = loadImageOrError(path, ok);
    if (!ok || !doc) return;
    float k = std::min(1.f, std::min(float(doc->w) / img.w, float(doc->h) / img.h));
    if (k < 1.f) img = img.resized(std::max(1, int(img.w * k)), std::max(1, int(img.h * k)));
    Image layer(doc->w, doc->h);
    layer.blit(img, (doc->w - img.w) / 2, (doc->h - img.h) / 2);
    layerAction("Поместить", [&](Document& d) { d.addLayer(fileStem(path), std::move(layer)); });
}

void Editor::cmdNew() {
    newName = "Без имени-" + std::to_string(docCounter);
    popupToOpen = "##newdoc";
}

void Editor::cmdOpen() {
    files.request(FileDialog::Mode::Open, "Открыть", kOpenFilters, "", [this](const std::string& p) { openPath(p); });
}

void Editor::cmdPlace() {
    if (!doc) return;
    files.request(FileDialog::Mode::Open, "Поместить как слой", {kOpenFilters[2]}, "",
                  [this](const std::string& p) { placeImage(p); });
}

void Editor::cmdImportLayers() {
    files.requestMulti("Импорт изображений как слоёв", {kOpenFilters[2]}, [this](const std::vector<std::string>& paths) {
        if (paths.empty()) return;
        std::vector<std::pair<std::string, Image>> imgs;
        for (auto& p : paths) {
            bool ok;
            Image img = loadImageOrError(p, ok);
            if (ok) imgs.push_back({fileStem(p), std::move(img)});
        }
        if (imgs.empty()) return;
        if (!doc) {
            auto& first = imgs.front();
            openTab(std::make_unique<Document>(Document::fromImage(first.second, first.first)));
            imgs.erase(imgs.begin());
        }
        layerAction("Импорт слоёв", [&](Document& d) {
            for (auto& [name, img] : imgs) {
                Image layer(d.w, d.h);
                layer.blit(img, (d.w - img.w) / 2, (d.h - img.h) / 2);
                d.addLayer(name, std::move(layer));
            }
        });
    });
}

static void addCustomBrush(Editor& e, BrushTip tip, const std::string& name) {
    if (!tip.valid()) return;
    e.customTips.push_back(std::move(tip));
    BrushPreset p;
    p.name = name;
    p.shape = TipShape::Custom;
    p.customId = int(e.customTips.size()) - 1;
    p.size = float(std::min(300, e.customTips.back().size));
    p.spacing = 0.25f;
    e.userBrushes.push_back(p);
    e.tb[Tool::Brush].preset = p;
    e.setTool(Tool::Brush);
    e.status = "Новая кисть: " + name;
}

void Editor::cmdBrushFromFile() {
    files.request(FileDialog::Mode::Open, "Кисть из изображения", {kOpenFilters[2]}, "", [this](const std::string& p) {
        bool ok;
        Image img = loadImageOrError(p, ok);
        if (ok) addCustomBrush(*this, tipFromImage(img), fileStem(p));
    });
}

void Editor::cmdBrushFromSelection() {
    if (!doc) return;
    Rect b = doc->sel.active() ? doc->sel.bounds() : doc->flatten().opaqueBounds();
    if (b.empty()) return;
    Image src = doc->flatten().crop(b);
    // Flatten on white so "dark = paint" works for opaque pictures too.
    Image tipImg(src.w, src.h, {255, 255, 255, 255});
    for (int y = 0; y < src.h; y++)
        for (int x = 0; x < src.w; x++) {
            RGBA c = src.get(x, y);
            c.a = uint8_t(c.a * doc->sel.at(b.x0 + x, b.y0 + y) / 255);
            tipImg.set(x, y, over({255, 255, 255, 255}, c));
        }
    addCustomBrush(*this, tipFromImage(tipImg), "Кисть " + std::to_string(customTips.size() + 1));
}

void Editor::cmdNewFromClipboard() {
    Image img;
    if (!clipboardGetImage(img)) img = clip;
    if (!img.valid()) {
        status = "В буфере обмена нет изображения";
        return;
    }
    openTab(std::make_unique<Document>(Document::fromImage(img, "Из буфера")));
}

void Editor::cmdSave(bool saveAs, std::function<void()> then) {
    if (!doc) return;
    Document* target = doc;
    auto saveTo = [this, then, target](const std::string& path) {
        std::string err;
        if (!saveProject(path, *target, err)) return showError(err);
        target->path = path;
        target->title = fileStem(path);
        target->dirty = false;
        addRecent(path);
        status = "Сохранено: " + path;
        if (then) then();
    };
    if (!saveAs && !doc->path.empty()) return saveTo(doc->path);
    files.request(FileDialog::Mode::Save, "Сохранить проект", {{"Проект ArtGraf", "agf"}}, doc->title + ".agf", saveTo);
}

void Editor::cmdExport() {
    if (!doc) return;
    files.request(FileDialog::Mode::Save, "Экспорт изображения",
                  {{"PNG", "png"}, {"JPEG", "jpg,jpeg"}, {"BMP", "bmp"}, {"TGA", "tga"}}, doc->title + ".png",
                  [this](const std::string& path) {
                      std::string err;
                      if (!saveImage(path, doc->flatten(), 92, err)) return showError(err);
                      status = "Экспортировано: " + path;
                  });
}

// ---------------------------------------------------------------- edit

void Editor::cmdUndo() {
    if (!doc) return;
    if (textEditing) return cancelText();
    if (polyActive) {
        polyActive = false;
        lasso.clear();
        return;
    }
    cancelLive();
    if (doc->undo()) {
        invalidateAll();
        thumbsDirty = true;
        selectionChanged();
    }
}

void Editor::cmdRedo() {
    if (!doc) return;
    cancelLive();
    if (doc->redo()) {
        invalidateAll();
        thumbsDirty = true;
        selectionChanged();
    }
}

void Editor::cmdCopy(bool merged) {
    if (!doc) return;
    Image src = merged ? doc->flatten() : doc->layer().styled();
    Rect b = doc->sel.active() ? doc->sel.bounds() : Rect{0, 0, doc->w, doc->h};
    if (b.empty()) return;
    clip = src.crop(b);
    if (doc->sel.active())
        for (int y = 0; y < clip.h; y++)
            for (int x = 0; x < clip.w; x++) {
                uint8_t* p = clip.at(x, y);
                p[3] = uint8_t(p[3] * doc->sel.at(b.x0 + x, b.y0 + y) / 255);
            }
    clipX = b.x0;
    clipY = b.y0;
    clipboardSetImage(clip);
    status = "Скопировано " + std::to_string(clip.w) + "×" + std::to_string(clip.h);
}

void Editor::cmdCut() {
    if (!doc) return;
    cmdCopy(false);
    beginStroke(Source::Erase, {}, 1.f);
    cov.fillAll();
    commitStroke("Вырезать");
}

void Editor::cmdPaste() {
    Image sys;
    bool fromSys = clipboardGetImage(sys);
    bool internal = clip.valid() && (!fromSys || (sys.w == clip.w && sys.h == clip.h));
    Image img = internal ? clip : sys;
    if (!img.valid()) {
        status = "В буфере обмена нет изображения";
        return;
    }
    if (!doc) {
        openTab(std::make_unique<Document>(Document::fromImage(img, "Вставка")));
        return;
    }
    int x = (doc->w - img.w) / 2, y = (doc->h - img.h) / 2;
    if (internal && clipX + img.w <= doc->w && clipY + img.h <= doc->h) {
        x = clipX;
        y = clipY;
    }
    Image layer(doc->w, doc->h);
    layer.blit(img, x, y);
    layerAction("Вставить", [&](Document& d) { d.addLayer("Вставленный слой", std::move(layer)); });
    doc->sel.clear();
    selectionChanged();
}

void Editor::cmdFill(RGBA c, const char* name) {
    if (!doc) return;
    beginStroke(Source::Solid, c, 1.f);
    cov.fillAll();
    commitStroke(name);
}

void Editor::cmdClear() {
    if (!doc) return;
    beginStroke(Source::Erase, {}, 1.f);
    cov.fillAll();
    commitStroke("Очистить");
}

void Editor::cmdStrokeSelection(float width) {
    if (!doc || !doc->sel.active()) return;
    size_t n = size_t(doc->w) * doc->h;
    std::vector<uint8_t> in(n), out(n);
    for (size_t i = 0; i < n; i++) {
        in[i] = doc->sel.mask[i] >= 128;
        out[i] = !in[i];
    }
    auto dOut = distanceTransform(in, doc->w, doc->h), dIn = distanceTransform(out, doc->w, doc->h);
    Selection keep = doc->sel;
    doc->sel.clear();  // the stroke straddles the edge, so it is not clipped by the selection
    beginStroke(Source::Solid, primary, 1.f);
    for (int y = 0; y < doc->h; y++)
        for (int x = 0; x < doc->w; x++) {
            size_t i = size_t(y) * doc->w + x;
            float d = in[i] ? dIn[i] : dOut[i];
            float c = std::clamp(width * 0.5f - d + 0.5f, 0.f, 1.f);
            if (c > 0) cov.v[i] = clamp8(c * 255);
        }
    cov.touched = {0, 0, doc->w, doc->h};
    commitStroke("Обводка");
    doc->sel = std::move(keep);
}

void Editor::cmdSelectAll() {
    if (!doc) return;
    doc->sel.selectAll();
    selectionChanged();
}

void Editor::cmdDeselect() {
    if (!doc) return;
    doc->sel.clear();
    selectionChanged();
}

void Editor::cmdInvertSelection() {
    if (!doc || !doc->sel.active()) return;
    doc->sel.invert();
    doc->sel.combine(doc->sel.mask, Selection::Op::Replace);
    selectionChanged();
}

void Editor::cmdCropToSelection() {
    if (!doc || !doc->sel.active()) return;
    Rect b = doc->sel.bounds();
    imageAction("Кадрировать", [b](Document& d) { d.crop(b); });
}

void Editor::cmdTrim() {
    if (!doc) return;
    Rect b = doc->flatten().opaqueBounds();
    if (b.empty() || (b.w() == doc->w && b.h() == doc->h)) return;
    imageAction("Обрезать прозрачное", [b](Document& d) { d.crop(b); });
}

void Editor::cmdLayerViaCopy() {
    if (!doc) return;
    if (!doc->sel.active()) return layerAction("Дублировать слой", [](Document& d) { d.duplicateLayer(); });
    Image img = doc->layer().img;
    for (int y = 0; y < img.h; y++)
        for (int x = 0; x < img.w; x++) {
            uint8_t* p = img.at(x, y);
            p[3] = uint8_t(p[3] * doc->sel.at(x, y) / 255);
        }
    layerAction("Скопировать на новый слой", [&](Document& d) { d.addLayer(d.nextLayerName(), std::move(img)); });
}

void Editor::cmdFlipLayer(bool horizontal) {
    layerAction(horizontal ? "Отразить слой по горизонтали" : "Отразить слой по вертикали", [horizontal](Document& d) {
        if (horizontal) d.layer().img.flipH();
        else d.layer().img.flipV();
    });
}

void Editor::cmdOpenLayerStyle() {
    if (!doc) return;
    cancelLive();
    fxBackup = doc->layer().fx;
    doc->push("Стиль слоя");
    fxOpen = true;
    popupToOpen = "##layerstyle";
}

void Editor::layerAction(const char* name, const std::function<void(Document&)>& f) {
    if (!doc) return;
    cancelLive();
    doc->push(name);
    f(*doc);
    invalidateAll();
    thumbsDirty = true;
}

void Editor::imageAction(const char* name, const std::function<void(Document&)>& f) {
    if (!doc) return;
    int w = doc->w, h = doc->h;
    layerAction(name, f);
    doc->touchAll();
    if (doc->w != w || doc->h != h) fitPending = true;
    cloneHasSource = false;
    selectionChanged();
}

void Editor::instantFilter(const char* name, const std::function<void(Image&)>& f) {
    if (!doc) return;
    cancelLive();
    doc->push(name);
    Image copy = doc->layer().img;
    f(copy);
    applyMasked(doc->layer().img, copy, doc->sel.mask);
    invalidateAll();
    thumbsDirty = true;
}

void Editor::openFilter(FilterSpec spec) {
    if (!doc) return;
    cancelLive();
    filter = std::make_unique<FilterSpec>(std::move(spec));
    filterVals.clear();
    for (auto& p : filter->params) filterVals.push_back(p.value);
    filterShown.clear();
    filterCustomChanged = true;
    filterBackup = doc->layer().img;
    popupToOpen = "##filter";
}

void Editor::filterApplyPreview() {
    Image f = filterBackup;
    filter->apply(f, filterVals);
    Image l = filterBackup;
    applyMasked(l, f, doc->sel.mask);
    doc->layer().img = std::move(l);
    filterShown = filterVals;
    filterCustomChanged = false;
    invalidateAll();
}

void Editor::filterFinish(bool ok) {
    if (!filter) return;
    doc->layer().img = filterBackup;
    if (ok) {
        doc->push(filter->title);
        filterApplyPreview();
    }
    invalidateAll();
    filter.reset();
    filterBackup = {};
    thumbsDirty = true;
}

// Scale/rotate/offset a layer around the canvas center, bilinear resampling.
static void transformImage(Image& img, float sx, float sy, float angleDeg, float dx, float dy) {
    Image src = img;
    float a = angleDeg * 3.14159265f / 180.f;
    float ca = std::cos(a), sa = std::sin(a);
    float cx = img.w * 0.5f, cy = img.h * 0.5f;
    sx = std::max(sx, 0.001f);
    sy = std::max(sy, 0.001f);
    parallelRows(0, img.h, [&](int y0, int y1) {
        for (int y = y0; y < y1; y++)
            for (int x = 0; x < img.w; x++) {
                float px = x + 0.5f - cx - dx, py = y + 0.5f - cy - dy;
                float rx = (px * ca + py * sa) / sx, ry = (-px * sa + py * ca) / sy;
                float u = rx + cx - 0.5f, v = ry + cy - 0.5f;
                int x0 = int(std::floor(u)), y0i = int(std::floor(v));
                float fu = u - x0, fv = v - y0i;
                float acc[4] = {};
                for (int j = 0; j < 2; j++)
                    for (int i = 0; i < 2; i++) {
                        int qx = x0 + i, qy = y0i + j;
                        if (qx < 0 || qy < 0 || qx >= src.w || qy >= src.h) continue;
                        float wgt = (i ? fu : 1 - fu) * (j ? fv : 1 - fv);
                        const uint8_t* p = src.at(qx, qy);
                        float al = p[3] * wgt;
                        acc[0] += p[0] * al; acc[1] += p[1] * al; acc[2] += p[2] * al; acc[3] += al;
                    }
                uint8_t* d = img.at(x, y);
                if (acc[3] > 0) {
                    d[0] = clamp8(acc[0] / acc[3]); d[1] = clamp8(acc[1] / acc[3]); d[2] = clamp8(acc[2] / acc[3]);
                }
                d[3] = clamp8(acc[3]);
            }
    });
}

void Editor::cmdTransform() {
    openFilter({"Трансформирование слоя",
                {{"Масштаб X, %", 1, 400, 100}, {"Масштаб Y, %", 1, 400, 100}, {"Поворот, °", -180, 180, 0},
                 {"Сдвиг X, px", -2000, 2000, 0, true}, {"Сдвиг Y, px", -2000, 2000, 0, true}},
                [](Image& img, const std::vector<float>& v) {
                    transformImage(img, v[0] / 100.f, v[1] / 100.f, v[2], v[3], v[4]);
                },
                {}});
}

}  // namespace ag
