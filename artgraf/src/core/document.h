#pragma once
#include <string>
#include <vector>

#include "blend.h"
#include "image.h"

namespace ag {

struct Layer {
    std::string name;
    Image img;
    bool visible = true;
    float opacity = 1.f;
    BlendMode blend = BlendMode::Normal;
};

// Per-pixel selection weight 0..255. An empty mask means "nothing selected" (= everything editable).
struct Selection {
    int w = 0, h = 0;
    std::vector<uint8_t> mask;

    bool active() const { return !mask.empty(); }
    void clear() { mask.clear(); }
    void reset(int w_, int h_) { w = w_; h = h_; mask.clear(); }
    uint8_t at(int x, int y) const { return mask.empty() ? 255 : mask[size_t(y) * w + x]; }
    Rect bounds() const;

    enum class Op { Replace, Add, Subtract, Intersect };
    void combine(const std::vector<uint8_t>& shape, Op op);  // shape has w*h entries
    void selectAll();
    void invert();
    void feather(float radius);
    void translate(int dx, int dy);
};

class Document {
public:
    int w = 0, h = 0;
    std::vector<Layer> layers;  // index 0 = bottom
    int active = 0;
    Selection sel;
    std::string path;  // project file, empty until saved
    std::string title = "Без имени";
    bool dirty = false;

    static Document blank(int w, int h, RGBA background);
    static Document fromImage(Image img, const std::string& title);

    Layer& layer() { return layers[active]; }
    const Layer& layer() const { return layers[active]; }

    // Composite rect `r` into `out` (doc-sized). If `activeOverride` is given it replaces the
    // active layer's pixels inside r; it must have the size of r (before clipping to the document). With `checker` the result is
    // drawn over a transparency checkerboard (for display), otherwise left with real alpha.
    void composite(Rect r, Image& out, const Image* activeOverride = nullptr, bool checker = false) const;
    Image flatten() const;

    // Layers
    void addLayer(const std::string& name, Image img = {});
    void duplicateLayer();
    void deleteLayer();
    void moveLayer(int delta);
    void mergeDown();
    void flattenAll();
    std::string nextLayerName() const;

    // Whole-image operations (all layers)
    void resizeImage(int nw, int nh);
    void resizeCanvas(int nw, int nh, int offX, int offY);
    void crop(Rect r);
    void rotateCW();
    void rotateCCW();
    void rotate180();
    void flipH();
    void flipV();

    // History: call push(name) BEFORE changing the document.
    struct State {
        std::string name;
        int w, h, active;
        std::vector<Layer> layers;
    };
    std::vector<State> undoStack, redoStack;
    size_t historyLimit = 60;

    void push(const std::string& name);
    void popLast();  // drop the most recent push (cancelled action)
    bool undo();
    bool redo();
    bool canUndo() const { return !undoStack.empty(); }
    bool canRedo() const { return !redoStack.empty(); }

private:
    void compositeRows(Rect r, Rect req, int ya, int yb, Image& out, const Image* ov, bool checker) const;
    State capture(const std::string& name) const;
    void restore(State& s);
};

}  // namespace ag
