// Minimal self-contained tests for the ArtGraf core (no GUI).
#include <cstdio>
#include <cstdlib>
#include <string>

#include "blend.h"
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

int main() {
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
