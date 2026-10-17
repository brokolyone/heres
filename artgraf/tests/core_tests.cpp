// Minimal self-contained tests for the ArtGraf core (no GUI).
#include <cstdio>
#include <cstdlib>
#include <string>

#include "blend.h"
#include "brush.h"
#include "effects.h"
#include "gradient.h"
#include "retouch.h"
#include "document.h"
#include "filters.h"
#include "io.h"
#include "raster.h"
#include "text.h"

using namespace ag;

static int failures = 0;
#define CHECK(cond)                                                          \
    do {                                                                     \
        if (!(cond)) {                                                       \
            std::printf("FAIL %s:%d: %s\n", __FILE__, __LINE__, #cond);      \
            failures++;                                                      \
        }                                                                    \
    } while (0)

static bool near(int a, int b, int tol = 2) { return std::abs(a - b) <= tol; }

static void testBlend() {
    RGBA red{255, 0, 0, 255}, blue{0, 0, 255, 255}, half{0, 0, 255, 128};
    CHECK(over(red, blue) == blue);
    RGBA h = over(red, half);
    CHECK(near(h.r, 127) && near(h.b, 128) && h.a == 255);
    RGBA m = blendPixel({200, 100, 50, 255}, {128, 128, 128, 255}, BlendMode::Multiply, 1.f);
    CHECK(near(m.r, 100) && near(m.g, 50) && near(m.b, 25));
    RGBA s = blendPixel({0, 0, 0, 255}, {100, 150, 200, 255}, BlendMode::Screen, 1.f);
    CHECK(near(s.r, 100) && near(s.b, 200));
    // Blending onto transparent shows the source as is in every mode.
    RGBA t = blendPixel({}, {10, 20, 30, 255}, BlendMode::Difference, 1.f);
    CHECK(t == (RGBA{10, 20, 30, 255}));
    CHECK(blendFromId(blendId(BlendMode::SoftLight)) == BlendMode::SoftLight);
}

static void testHistory() {
    Document d = Document::blank(8, 8, {255, 255, 255, 255});
    d.push("Заливка");
    d.layer().img.fill({255, 0, 0, 255});
    d.push("Новый слой");
    d.addLayer("Слой 2");
    CHECK(d.layers.size() == 2 && d.active == 1);
    CHECK(d.undo());
    CHECK(d.layers.size() == 1 && d.layer().img.get(3, 3) == (RGBA{255, 0, 0, 255}));
    CHECK(d.undo());
    CHECK(d.layer().img.get(3, 3) == (RGBA{255, 255, 255, 255}));
    CHECK(!d.undo());
    CHECK(d.redo() && d.redo());
    CHECK(d.layers.size() == 2);
    CHECK(d.undoStack.size() == 2 && d.undoStack[1].name == "Новый слой");
}

static void testLayersAndComposite() {
    Document d = Document::blank(4, 4, {0, 0, 0, 255});
    d.addLayer("top", Image(4, 4, {255, 255, 255, 255}));
    d.layers[1].opacity = 0.5f;
    Image out = d.flatten();
    CHECK(near(out.get(1, 1).r, 128));
    d.layers[1].blend = BlendMode::Multiply;
    CHECK(d.flatten().get(0, 0).r == 0);
    d.layers[1].blend = BlendMode::Normal;
    d.mergeDown();
    CHECK(d.layers.size() == 1 && near(d.layer().img.get(2, 2).r, 128));
}

static void testGeometry() {
    Document d = Document::blank(4, 2, {});
    d.layer().img.set(0, 0, {255, 0, 0, 255});
    d.rotateCW();
    CHECK(d.w == 2 && d.h == 4 && d.layer().img.get(1, 0).r == 255);
    d.flipH();
    CHECK(d.layer().img.get(0, 0).r == 255);
    d.resizeCanvas(4, 6, 1, 1);
    CHECK(d.w == 4 && d.layer().img.get(1, 1).r == 255);
    d.crop({1, 1, 3, 3});
    CHECK(d.w == 2 && d.h == 2 && d.layer().img.get(0, 0).r == 255);
    d.resizeImage(10, 10);
    CHECK(d.layer().img.w == 10);
}

static void testSelection() {
    Selection s;
    s.reset(10, 10);
    CHECK(!s.active() && s.at(5, 5) == 255);
    Coverage c;
    c.reset(10, 10);
    c.rect(2, 2, 6, 6, true, 0);
    s.combine(c.v, Selection::Op::Replace);
    CHECK(s.active() && s.at(3, 3) == 255 && s.at(8, 8) == 0);
    Rect b = s.bounds();
    CHECK(b.x0 == 2 && b.y0 == 2 && b.x1 == 6 && b.y1 == 6);
    s.invert();
    CHECK(s.at(3, 3) == 0 && s.at(8, 8) == 255);
    s.invert();
    s.translate(2, 0);
    CHECK(s.at(7, 3) == 255 && s.at(2, 3) == 0);
    s.combine(c.v, Selection::Op::Subtract);
    CHECK(s.at(7, 3) == 255 && s.at(5, 3) == 0);

    // A shape that covers no pixel must not leave an "everything locked" selection behind.
    Selection e;
    e.reset(10, 10);
    e.combine(std::vector<uint8_t>(100, 0), Selection::Op::Replace);
    CHECK(!e.active() && e.at(1, 1) == 255);
}

static void testRaster() {
    Coverage c;
    c.reset(32, 32);
    c.dab(16, 16, 5, 1.f, true);
    CHECK(c.at(16, 16) == 255 && c.at(16, 25) == 0);
    c.clear();
    CHECK(c.at(16, 16) == 0);
    c.line(2, 2, 30, 2, 3);
    CHECK(c.at(15, 2) == 255 && c.at(15, 10) == 0);
    c.clear();
    c.ellipse(0, 0, 32, 32, false, 2);
    CHECK(c.at(16, 16) == 0 && c.at(0, 16) > 100);
    c.clear();
    c.polygon({{0, 0}, {20, 0}, {0, 20}});
    CHECK(c.at(2, 2) == 255 && c.at(18, 18) == 0);

    Stroker st;
    int dabs = 0;
    st.begin({0, 0}, [&](Vec2) { dabs++; });
    st.to({10, 0}, 2.f, [&](Vec2) { dabs++; });
    st.to({11, 0}, 2.f, [&](Vec2) { dabs++; });
    CHECK(dabs == 6);  // at 0,2,4,6,8,10 — the extra 1px is carried

    Image img(10, 10, {255, 255, 255, 255});
    for (int y = 0; y < 10; y++) img.set(5, y, {0, 0, 0, 255});
    auto m = floodMask(img, 1, 1, 10, true);
    CHECK(m[1 * 10 + 4] == 255 && m[1 * 10 + 5] == 0 && m[1 * 10 + 7] == 0);
    auto g = floodMask(img, 1, 1, 10, false);
    CHECK(g[1 * 10 + 7] == 255);
}

static void testFilters() {
    Image img(16, 16, {100, 150, 200, 255});
    Image a = img;
    invert(a);
    CHECK(a.get(0, 0) == (RGBA{155, 105, 55, 255}));
    a = img;
    desaturate(a);
    CHECK(a.get(0, 0).r == a.get(0, 0).g);
    a = img;
    hueSaturation(a, 0, -100, 0);
    CHECK(near(a.get(0, 0).r, a.get(0, 0).b));
    a = img;
    gaussianBlur(a, 3);
    CHECK(near(a.get(8, 8).r, 100));  // uniform image stays uniform
    a = Image(16, 16);
    a.set(8, 8, {255, 0, 0, 255});
    gaussianBlur(a, 2);
    CHECK(a.get(8, 8).a < 255 && a.get(9, 8).a > 0 && a.get(9, 8).r == 255);  // no dark halo
    a = img;
    posterize(a, 2);
    CHECK(a.get(0, 0).r == 0 && a.get(0, 0).b == 255);
    a = img;
    brightnessContrast(a, 20, 0);
    CHECK(near(a.get(0, 0).r, 151));
    a = img;
    levels(a, 100, 200, 1.f, 0, 255);
    CHECK(a.get(0, 0).r == 0 && near(a.get(0, 0).g, 128) && a.get(0, 0).b == 255);
    a = img;
    pixelate(a, 4);
    CHECK(a.get(0, 0) == img.get(0, 0));

    Image f = img;
    invert(f);
    Image base = img;
    std::vector<uint8_t> mask(16 * 16, 0);
    mask[0] = 255;
    applyMasked(base, f, mask);
    CHECK(base.get(0, 0) == f.get(0, 0) && base.get(1, 0) == img.get(1, 0));
}

static void testIo() {
    Document d = Document::blank(6, 5, {10, 20, 30, 255});
    d.addLayer("Верх «тест»", Image(6, 5, {200, 0, 0, 128}));
    d.layers[1].blend = BlendMode::Screen;
    d.layers[1].opacity = 0.25f;
    d.layers[1].visible = false;
    std::string err;
    const std::string path = "artgraf_test_project.agf";
    CHECK(saveProject(path, d, err));
    Document e;
    CHECK(loadProject(path, e, err));
    CHECK(e.w == 6 && e.h == 5 && e.layers.size() == 2 && e.active == 1);
    CHECK(e.layers[1].name == "Верх «тест»" && e.layers[1].blend == BlendMode::Screen);
    CHECK(!e.layers[1].visible && near(int(e.layers[1].opacity * 100), 25, 0));
    CHECK(e.layers[1].img.get(3, 3) == (RGBA{200, 0, 0, 128}));
    std::remove(path.c_str());

    Image img(3, 3, {1, 2, 3, 255});
    CHECK(saveImage("artgraf_test.png", img, 90, err));
    Image back;
    CHECK(loadImage("artgraf_test.png", back, err) && back.get(2, 2) == img.get(2, 2));
    std::remove("artgraf_test.png");
    CHECK(!saveImage("x.webp", img, 90, err));
    CHECK(lowerExt("C:/a/B.JPG") == "jpg" && fileStem("C:\\dir\\pic.v2.png") == "pic.v2");
}

static void testText() {
    CHECK(decodeUtf8("Яa€").size() == 3 && decodeUtf8("Я")[0] == 0x42F);
    const char* candidates[] = {"/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "C:/Windows/Fonts/arial.ttf"};
    for (const char* p : candidates) {
        Font f;
        if (!f.load(p)) continue;
        Coverage c;
        c.reset(200, 60);
        Rect r = f.draw(&c, "Привет", 5, 5, 32);
        CHECK(!r.empty() && r.w() > 60);
        int lit = 0;
        for (uint8_t v : c.v) lit += v > 128;
        CHECK(lit > 100);
        return;
    }
    std::printf("note: no system font found, text rendering not tested\n");
}

static void testBrushesAndGradients() {
    CHECK(builtinBrushes().size() >= 15);
    Coverage c;
    c.reset(100, 100);
    BrushStamper st;
    for (const BrushPreset& p : builtinBrushes()) {
        c.clear();
        BrushPreset q = p;
        q.size = 40;
        q.scatter = 0;
        st.dab(c, q, tipFor(q.shape, q.hardness), 50, 50, 0);
        int lit = 0;
        for (uint8_t v : c.v) lit += v > 0;
        if (lit == 0) std::printf("brush '%s' paints nothing\n", p.name.c_str());
        CHECK(lit > 0);
    }
    // Airbrush accumulates, normal brushes don't.
    BrushPreset air = builtinBrushes()[3];
    CHECK(air.buildup);
    c.clear();
    st.dab(c, air, tipFor(air.shape, air.hardness), 50, 50, 0);
    uint8_t once = c.at(50, 50);
    st.dab(c, air, tipFor(air.shape, air.hardness), 50, 50, 0);
    CHECK(c.at(50, 50) > once);

    Gradient g{"", {{0, {0, 0, 0, 255}}, {1, {255, 255, 255, 255}}}};
    CHECK(near(g.sample(0.5f).r, 128));
    CHECK(g.reversed().sample(0.f).r == 255);
    CHECK(near(int(gradientT(GradientType::Linear, 0, 0, 10, 0, 5, 3) * 100), 50));
    CHECK(gradientT(GradientType::Reflected, 0, 0, 10, 0, -5, 0) > 0.4f);
    Gradient fade{"", {{0, {255, 0, 0, 255}}, {1, {255, 0, 0, 0}}}};
    RGBA m = fade.sample(0.5f);
    CHECK(m.r == 255 && near(m.a, 128));
    CHECK(gradientPresets({1, 2, 3, 255}, {4, 5, 6, 255}).size() > 10);
}

static void testEffects() {
    std::vector<uint8_t> in(20 * 10, 0);
    in[5 * 20 + 5] = 1;
    auto d = distanceTransform(in, 20, 10);
    CHECK(d[5 * 20 + 5] == 0.f && near(int(d[5 * 20 + 9] * 10), 40, 1) && near(int(d[8 * 20 + 9] * 10), 50, 1));

    Image img(40, 40);
    for (int y = 15; y < 25; y++)
        for (int x = 15; x < 25; x++) img.set(x, y, {255, 0, 0, 255});
    LayerFx fx;
    fx.stroke.on = true;
    fx.stroke.size = 3;
    fx.stroke.color = {0, 0, 255, 255};
    Image out = renderLayerFx(img, fx);
    CHECK(out.get(13, 20).b == 255 && out.get(20, 20).r == 255 && out.get(5, 5).a == 0);
    fx = {};
    fx.dropShadow.on = true;
    fx.dropShadow.distance = 6;
    fx.dropShadow.angle = 90;  // light from above: shadow below
    out = renderLayerFx(img, fx);
    CHECK(out.get(20, 28).a > out.get(20, 12).a + 60);
    fx = {};
    fx.colorOverlay.on = true;
    fx.colorOverlay.color = {0, 255, 0, 255};
    CHECK(renderLayerFx(img, fx).get(20, 20).g == 255);

    Document doc = Document::blank(40, 40, {255, 255, 255, 255});
    doc.addLayer("fx", img);
    doc.layers[1].fx.stroke = LayerFx().stroke;
    doc.layers[1].fx.stroke.on = true;
    CHECK(doc.flatten().get(13, 20).r == 0);  // black stroke shows up in the composite
    std::string err;
    CHECK(saveProject("fx_test.agf", doc, err));
    Document back;
    CHECK(loadProject("fx_test.agf", back, err) && back.layers[1].fx.stroke.on);
    std::remove("fx_test.agf");
}

static void testRetouch() {
    Image img(60, 60, {200, 200, 200, 255});
    for (int y = 25; y < 35; y++)
        for (int x = 25; x < 35; x++) img.set(x, y, {0, 0, 0, 255});
    Coverage hole;
    hole.reset(60, 60);
    hole.dab(30, 30, 9, 1.f, true);
    healRegion(img, hole, {});
    CHECK(img.get(30, 30).r > 150);  // the dark spot is gone

    Image b(30, 30, {255, 255, 255, 255});
    for (int y = 0; y < 30; y++) b.set(15, y, {0, 0, 0, 255});
    Retoucher r;
    RetouchParams p;
    p.mode = RetouchMode::Blur;
    p.radius = 6;
    p.strength = 1;
    r.dab(b, 15, 15, p, {});
    CHECK(b.get(15, 15).r > 0 && b.get(14, 15).r < 255);
    p.mode = RetouchMode::Burn;
    Image gray(10, 10, {128, 128, 128, 255});
    r.dab(gray, 5, 5, p, {});
    CHECK(gray.get(5, 5).r < 128);
}

static void testNewFilters() {
    Image img(32, 32);
    for (int y = 0; y < 32; y++)
        for (int x = 0; x < 32; x++) img.set(x, y, {uint8_t(x * 8), uint8_t(y * 8), 100, 255});
    uint8_t lutTable[256];
    curveLut({{0, 0}, {255, 255}}, lutTable);
    CHECK(lutTable[100] == 100);
    curveLut({{0, 255}, {255, 0}}, lutTable);
    CHECK(lutTable[0] == 255 && lutTable[255] == 0);
    auto run = [&](void (*f)(Image&)) { Image c = img; f(c); return c; };
    (void)run;
    Image c = img; twirl(c, 90); CHECK(c.w == 32);
    c = img; spherize(c, 50);
    c = img; zoomBlur(c, 50);
    c = img; spinBlur(c, 20);
    c = img; wave(c, 3, 10);
    c = img; ripple(c, 3, 8);
    c = img; polarCoordinates(c, true);
    c = img; halftone(c, 6);
    c = img; glitch(c, 6, 4, 1);
    c = img; renderClouds(c, {0, 0, 0, 255}, {255, 255, 255, 255}, 8, 3); CHECK(c.get(3, 3).a == 255);
    c = img; lensFlare(c, 10, 10, 100); CHECK(c.get(10, 10).r == 255);
    c = img; median(c, 1);
    c = img; crystallize(c, 6, 2);
    c = img; sketch(c, 100);
    c = img; vibrance(c, 50, 0);
    c = img; exposure(c, 1, 0, 1); CHECK(c.get(10, 10).r > img.get(10, 10).r);
    c = img; blackWhite(c, 40, 60, 40, 60, 20, 80); CHECK(c.get(5, 5).r == c.get(5, 5).g);
    c = img; gradientMap(c, Gradient{"", {{0, {255, 0, 0, 255}}, {1, {0, 0, 255, 255}}}});
    CHECK(c.get(0, 0).r > c.get(0, 0).b);
}

int main() {
    testBrushesAndGradients();
    testEffects();
    testRetouch();
    testNewFilters();
    testBlend();
    testHistory();
    testLayersAndComposite();
    testGeometry();
    testSelection();
    testRaster();
    testFilters();
    testIo();
    testText();
    if (failures) {
        std::printf("%d check(s) failed\n", failures);
        return 1;
    }
    std::printf("all core tests passed\n");
    return 0;
}
