#include "editor.h"

#include <cmath>
#include <cstring>

#include <SDL_opengl.h>

#include "clipboard.h"
#include "filters.h"
#include "io.h"
#include "parallel.h"

namespace ag {

const ToolInfo& toolInfo(Tool t) {
    static const ToolInfo k[] = {
        {"Перемещение", SDLK_v, "Перетащите слой или выделенную область. Стрелки сдвигают на 1 px"},
        {"Прямоугольная область", SDLK_m, "Shift — добавить, Alt — вычесть, Shift+Alt — пересечение"},
        {"Овальная область", SDLK_o, "Shift — добавить, Alt — вычесть, Shift+Alt — пересечение"},
        {"Лассо", SDLK_l, "Обведите область. Shift — добавить, Alt — вычесть"},
        {"Волшебная палочка", SDLK_w, "Выделяет похожие по цвету пиксели"},
        {"Кадрирование", SDLK_c, "Нарисуйте рамку, Enter — применить, Esc — отмена"},
        {"Пипетка", SDLK_i, "Клик — основной цвет, Alt+клик — фоновый"},
        {"Кисть", SDLK_b, "[ и ] — размер, Shift+клик — прямая линия, Alt+клик — взять цвет"},
        {"Карандаш", SDLK_n, "Жёсткие пиксельные края. [ и ] — размер"},
        {"Ластик", SDLK_e, "Стирает до прозрачности. [ и ] — размер"},
        {"Штамп", SDLK_s, "Alt+клик — точка-источник, затем рисуйте"},
        {"Градиент", SDLK_g, "Протяните линию. Shift — шаг 45°"},
        {"Заливка", SDLK_k, "Заливает похожие по цвету пиксели основным цветом"},
        {"Текст", SDLK_t, "Клик — начать ввод, Ctrl+Enter — применить, Esc — отмена"},
        {"Фигуры", SDLK_u, "Shift — квадрат, круг или шаг 45°"},
        {"Рука", SDLK_h, "Двигает вид. Также пробел или средняя кнопка мыши"},
        {"Масштаб", SDLK_z, "Клик — приблизить, Alt+клик — отдалить, колесо — масштаб"},
    };
    static_assert(sizeof(k) / sizeof(k[0]) == size_t(Tool::Count));
    return k[int(t)];
}

ImU32 toU32(RGBA c) { return IM_COL32(c.r, c.g, c.b, c.a); }
ImVec4 toVec4(RGBA c) { return ImVec4(c.r / 255.f, c.g / 255.f, c.b / 255.f, c.a / 255.f); }
RGBA fromVec4(const ImVec4& v) { return {clamp8(v.x * 255), clamp8(v.y * 255), clamp8(v.z * 255), clamp8(v.w * 255)}; }

Editor::Editor(SDL_Window* w) : window(w) {
    brushOpts[Tool::Brush] = {20.f, 0.8f, 1.f};
    brushOpts[Tool::Pencil] = {3.f, 1.f, 1.f};
    brushOpts[Tool::Eraser] = {40.f, 0.6f, 1.f};
    brushOpts[Tool::Clone] = {40.f, 0.5f, 1.f};
    scanFonts();
}

Editor::~Editor() {
    if (tex) glDeleteTextures(1, &tex);
    if (!thumbs.empty()) glDeleteTextures(GLsizei(thumbs.size()), thumbs.data());
}

bool Editor::animating() const {
    return (doc && doc->sel.active()) || textEditing || dragging || cropActive;
}

// ---------------------------------------------------------------- document & view

void Editor::setDocument(std::unique_ptr<Document> d) {
    cancelLive();
    cancelText();
    cropActive = false;
    cloneHasSource = false;
    doc = std::move(d);
    texW = texH = 0;  // forces texture re-creation
    fitPending = true;
    thumbsDirty = true;
    selectionChanged();
    if (doc) invalidateAll();
}

void Editor::invalidate(Rect r) {
    if (!doc) return;
    dirty = dirty.unite(r.intersect({0, 0, doc->w, doc->h}));
}

void Editor::invalidateAll() {
    if (doc) dirty = {0, 0, doc->w, doc->h};
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
    // Smooth when zoomed out, crisp pixels when zoomed in.
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
                uint8_t c = (((x >> 2) + (y >> 2)) & 1) ? 190 : 245;
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
    float z = std::min((canvasSize.x - 40) / doc->w, (canvasSize.y - 40) / doc->h);
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
        if (l.visible) acc = blendPixel(acc, l.img.get(x, y), l.blend, l.opacity);
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

void Editor::requestQuit() {
    guardUnsaved([this] { quitNow = true; });
}

// ---------------------------------------------------------------- files

static const std::vector<FileDialog::Filter> kOpenFilters = {
    {"Изображения и проекты", "agf,png,jpg,jpeg,bmp,tga,gif,psd,hdr,pic,pnm,ppm,pgm"},
    {"Проект ArtGraf", "agf"},
    {"Изображения", "png,jpg,jpeg,bmp,tga,gif,psd"},
};

void Editor::openPath(const std::string& path) {
    std::string err;
    if (lowerExt(path) == "agf") {
        auto d = std::make_unique<Document>();
        if (!loadProject(path, *d, err)) return showError(err);
        setDocument(std::move(d));
        return;
    }
    Image img;
    if (!loadImage(path, img, err)) return showError(err);
    setDocument(std::make_unique<Document>(Document::fromImage(std::move(img), fileStem(path))));
}

void Editor::dropPath(const std::string& path) {
    if (!doc || lowerExt(path) == "agf") return guardUnsaved([this, path] { openPath(path); });
    placeImage(path);
}

void Editor::placeImage(const std::string& path) {
    Image img;
    std::string err;
    if (!loadImage(path, img, err)) return showError(err);
    // Scale down to fit the canvas, like "Place" in other editors.
    float k = std::min(1.f, std::min(float(doc->w) / img.w, float(doc->h) / img.h));
    if (k < 1.f) img = img.resized(std::max(1, int(img.w * k)), std::max(1, int(img.h * k)));
    Image layer(doc->w, doc->h);
    layer.blit(img, (doc->w - img.w) / 2, (doc->h - img.h) / 2);
    layerAction("Поместить", [&](Document& d) { d.addLayer(fileStem(path), std::move(layer)); });
}

void Editor::cmdNew() {
    guardUnsaved([this] {
        newW = doc ? doc->w : newW;
        newH = doc ? doc->h : newH;
        popupToOpen = "Новый документ";
    });
}

void Editor::cmdOpen() {
    guardUnsaved([this] {
        files.request(FileDialog::Mode::Open, "Открыть", kOpenFilters, "", [this](const std::string& p) { openPath(p); });
    });
}

void Editor::cmdPlace() {
    if (!doc) return;
    files.request(FileDialog::Mode::Open, "Поместить как слой", {kOpenFilters[2]}, "",
                  [this](const std::string& p) { placeImage(p); });
}

void Editor::cmdSave(bool saveAs, std::function<void()> then) {
    if (!doc) return;
    auto saveTo = [this, then](const std::string& path) {
        std::string err;
        if (!saveProject(path, *doc, err)) return showError(err);
        doc->path = path;
        doc->title = fileStem(path);
        doc->dirty = false;
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
    Image src = merged ? doc->flatten() : doc->layer().img;
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
    // Our own copy comes back from the system clipboard without its position: prefer the internal one.
    bool internal = clip.valid() && (!fromSys || (sys.w == clip.w && sys.h == clip.h));
    Image img = internal ? clip : sys;
    if (!img.valid()) {
        status = "В буфере обмена нет изображения";
        return;
    }
    if (!doc) {
        setDocument(std::make_unique<Document>(Document::fromImage(img, "Вставка")));
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
    doc->sel.combine(doc->sel.mask, Selection::Op::Replace);  // drops the mask if it became empty
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
void transformImage(Image& img, float sx, float sy, float angleDeg, float dx, float dy) {
    Image src = img;
    float a = angleDeg * 3.14159265f / 180.f;
    float ca = std::cos(a), sa = std::sin(a);
    float cx = img.w * 0.5f, cy = img.h * 0.5f;
    sx = std::max(sx, 0.001f);
    sy = std::max(sy, 0.001f);
    parallelRows(0, img.h, [&](int y0, int y1) {
        for (int y = y0; y < y1; y++)
            for (int x = 0; x < img.w; x++) {
                // inverse map: destination -> source
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
                }});
}

}  // namespace ag
