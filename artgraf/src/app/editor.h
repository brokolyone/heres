#pragma once
#include <functional>
#include <map>
#include <memory>
#include <string>
#include <vector>

#include <SDL.h>
#include <imgui.h>

#include "document.h"
#include "file_dialog.h"
#include "raster.h"
#include "text.h"

namespace ag {

enum class Tool {
    Move, RectSelect, EllipseSelect, Lasso, MagicWand, Crop, Eyedropper,
    Brush, Pencil, Eraser, Clone, Gradient, Bucket, Text, Shape, Hand, Zoom,
    Count
};

struct ToolInfo {
    const char* name;
    SDL_Keycode key;
    const char* hint;
};
const ToolInfo& toolInfo(Tool t);

struct BrushOptions {
    float size = 20.f;
    float hardness = 0.8f;
    float opacity = 1.f;
};

enum class ShapeKind { Rect, Ellipse, Line };

// A filter or adjustment with numeric parameters and a live preview.
struct FilterSpec {
    struct Param {
        const char* label;
        float min, max, value;
        bool integer = false;
    };
    std::string title;
    std::vector<Param> params;
    std::function<void(Image&, const std::vector<float>&)> apply;
};

class Editor {
public:
    explicit Editor(SDL_Window* window);
    ~Editor();

    void beforeFrame();  // runs blocking native dialogs outside the ImGui frame
    void frame();
    void openPath(const std::string& path);
    void dropPath(const std::string& path);  // file dropped on the window
    void requestQuit();
    bool wantsQuit() const { return quitNow; }
    bool animating() const;

    // ---- state shared by editor*.cpp ----
    SDL_Window* window;
    std::unique_ptr<Document> doc;
    FileDialog files;

    Tool tool = Tool::Brush;
    std::map<Tool, BrushOptions> brushOpts;
    RGBA primary{0, 0, 0, 255}, secondary{255, 255, 255, 255};
    int tolerance = 32;
    bool contiguous = true, sampleMerged = false;
    int selMode = 0;  // Selection::Op used when no modifier key is held
    float selFeather = 0.f;
    ShapeKind shapeKind = ShapeKind::Rect;
    bool shapeFilled = true, shapeNewLayer = true;
    float shapeStroke = 4.f;
    bool gradRadial = false, gradToTransparent = false;
    float fontSize = 64.f;
    int fontIndex = 0;

    // View
    float zoom = 1.f;
    ImVec2 pan{0, 0};  // doc origin relative to the canvas area's top-left, in pixels
    ImVec2 canvasMin{0, 0}, canvasSize{0, 0};
    bool fitPending = true;
    bool showGrid = false;

    // Display texture
    unsigned int tex = 0;
    int texW = 0, texH = 0;
    Image display;
    Rect dirty;
    bool texLinear = false;
    std::vector<unsigned int> thumbs;
    bool thumbsDirty = true;

    // Live operation on the active layer
    enum class Live { None, Stroke, Move } live = Live::None;
    enum class Source { Solid, Erase, Clone, Gradient } source = Source::Solid;
    Coverage cov;
    RGBA liveColor{};
    float liveOpacity = 1.f;
    Image moveBase, moveFloat;
    Rect moveBounds;  // opaque area of moveFloat
    int moveDx = 0, moveDy = 0;
    Image cloneSnap;
    bool cloneHasSource = false, cloneAligned = false;
    Vec2 cloneSource;
    int cloneDx = 0, cloneDy = 0;
    Vec2 gradA, gradB;

    // Pointer interaction
    bool dragging = false, panning = false;
    Vec2 downPt, lastPt, curPt;
    ImVec2 panStartMouse, panStartPan;
    bool downShift = false, downAlt = false, downCtrl = false;
    Stroker stroker;
    std::vector<Vec2> lasso;
    bool cropActive = false, cropMoving = false;
    Rect cropRect;
    Vec2 cropGrab;

    // Selection outline (doc-space segments) and its marching ants
    std::vector<ImVec4> antSegments;
    bool selOutlineDirty = true;

    // Text tool
    bool textEditing = false;
    Vec2 textPos;
    std::string textBuf;
    bool textFocus = false;
    struct FontEntry { std::string name, path; };
    std::vector<FontEntry> fonts;
    std::map<std::string, Font> fontCache;
    const Font* currentFont();

    // Clipboard (internal fallback when the system clipboard has no image)
    Image clip;
    int clipX = 0, clipY = 0;

    // Dialogs
    std::unique_ptr<FilterSpec> filter;
    std::vector<float> filterVals, filterShown;
    Image filterBackup;
    bool filterPreview = true;
    std::string popupToOpen;
    std::string errorText;
    std::function<void()> afterSave;  // continuation for "save changes?"
    std::function<void()> pendingDiscard;
    bool quitNow = false;
    int newW = 1920, newH = 1080, newBg = 0;
    int sizeW = 0, sizeH = 0, anchor = 4;
    bool keepRatio = true;
    float featherRadius = 5.f;
    std::string renameBuf;
    int renaming = -1;
    bool layoutReset = true;
    std::string status;
    std::string iniPath;
    bool showShortcuts = false, showAbout = false;

    // ---- editor.cpp: document, view, commands ----
    void setDocument(std::unique_ptr<Document> d);
    void invalidate(Rect r);
    void invalidateAll();
    void selectionChanged();
    void updateTexture();
    void updateThumbs();
    void fitView();
    void zoomAt(float newZoom, ImVec2 screenPt);
    ImVec2 toScreen(Vec2 p) const;
    Vec2 toDoc(ImVec2 s) const;
    RGBA mergedPixel(int x, int y) const;
    void updateTitle();
    void showError(const std::string& msg);
    void guardUnsaved(std::function<void()> action);

    void cmdNew();
    void cmdOpen();
    void cmdPlace();
    void cmdSave(bool saveAs, std::function<void()> then = {});
    void cmdExport();
    void cmdUndo();
    void cmdRedo();
    void cmdCopy(bool merged);
    void cmdCut();
    void cmdPaste();
    void cmdFill(RGBA c, const char* name);
    void cmdClear();
    void cmdSelectAll();
    void cmdDeselect();
    void cmdInvertSelection();
    void cmdCropToSelection();
    void cmdTrim();
    void cmdLayerViaCopy();
    void cmdFlipLayer(bool horizontal);
    void layerAction(const char* name, const std::function<void(Document&)>& f);
    void imageAction(const char* name, const std::function<void(Document&)>& f);
    void instantFilter(const char* name, const std::function<void(Image&)>& f);
    void openFilter(FilterSpec spec);
    void filterApplyPreview();
    void filterFinish(bool ok);
    void cmdTransform();
    void placeImage(const std::string& path);

    // ---- editor_tools.cpp: canvas input and live preview ----
    void setTool(Tool t);
    void nudge(int dx, int dy);
    void canvasInput(bool hovered, bool active);
    void toolDown(Vec2 p);
    void toolDrag(Vec2 p);
    void toolUp(Vec2 p);
    void cancelLive();
    void beginStroke(Source src, RGBA color, float opacity);
    void commitStroke(const char* name, bool toNewLayer = false, const std::string& layerName = {});
    RGBA livePixel(RGBA dst, int x, int y) const;
    bool previewActive(Rect r, Image& out) const;
    void brushDab(Vec2 p);
    void applyCrop();
    void commitText();
    void cancelText();
    void textPreview();
    void drawOverlays(ImDrawList* dl);
    void rebuildAnts();
    Selection::Op selOpFromMods() const;
    void combineSelection(std::vector<uint8_t> shape, Selection::Op op);
    RGBA gradientAt(int x, int y) const;
    BrushOptions& brush() { return brushOpts[tool]; }
    bool isBrushTool(Tool t) const { return t == Tool::Brush || t == Tool::Pencil || t == Tool::Eraser || t == Tool::Clone; }

    // ---- editor_ui.cpp: windows, menus, panels, dialogs ----
    void setupStyle(float scale);
    void loadFonts(float scale);
    void drawMenuBar();
    void drawOptionsBar();
    void drawStatusBar();
    void drawDockspace();
    void drawToolbox();
    void drawCanvas();
    void drawColors();
    void drawLayers();
    void drawHistory();
    void drawNavigator();
    void drawDialogs();
    void drawStartScreen();
    void handleShortcuts();
    void scanFonts();
};

ImU32 toU32(RGBA c);
ImVec4 toVec4(RGBA c);
RGBA fromVec4(const ImVec4& v);

}  // namespace ag
