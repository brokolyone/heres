#pragma once
#include <functional>
#include <map>
#include <memory>
#include <string>
#include <vector>

#include <SDL.h>
#include <imgui.h>

#include "brush.h"
#include "document.h"
#include "file_dialog.h"
#include "gradient.h"
#include "raster.h"
#include "retouch.h"
#include "text.h"

namespace ag {

enum class Tool {
    Move, RectSelect, EllipseSelect, Lasso, PolyLasso, MagicWand, Crop, Eyedropper,
    SpotHeal, Clone, Brush, Pencil, Eraser, Gradient, Bucket,
    Blur, Sharpen, Smudge, Dodge, Burn, Sponge,
    Text, Shape, Hand, Zoom,
    Count
};

struct ToolInfo {
    const char* name;
    SDL_Keycode key;
    const char* hint;
};
const ToolInfo& toolInfo(Tool t);

// Toolbox slots; each slot holds tools that share a key (Shift+key cycles), like in big editors.
const std::vector<std::vector<Tool>>& toolGroups();

// Per-tool brush settings.
struct ToolBrush {
    BrushPreset preset;
    float opacity = 1.f;
    float strength = 0.5f;  // retouch tools
};

enum class ShapeKind { Rect, RoundRect, Ellipse, Line, Arrow, Polygon, Star, Heart };

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
    std::function<bool()> customUi;  // extra widgets (curves, colors...); returns true when changed
};

struct DocTab {
    std::unique_ptr<Document> doc;
    float zoom = 1.f;
    ImVec2 pan{0, 0};
    bool fitPending = true;
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

    // Splash screen (drawn by main while the app finishes loading)
    void drawSplash(float progress, const char* stage);
    void loadAssets();

    // ---- state shared by editor*.cpp ----
    SDL_Window* window;
    std::vector<DocTab> tabs;
    int current = -1;
    bool tabSelectRequest = false;
    Document* doc = nullptr;  // tabs[current].doc, or null on the home screen
    FileDialog files;

    Tool tool = Tool::Brush;
    std::map<int, Tool> groupTool;  // last used tool per toolbox slot
    std::map<Tool, ToolBrush> tb;
    std::vector<BrushPreset> userBrushes;
    std::vector<BrushTip> customTips;
    RGBA primary{0, 0, 0, 255}, secondary{255, 255, 255, 255};
    std::vector<RGBA> recentColors;
    int tolerance = 32;
    bool contiguous = true, sampleMerged = false;
    int selMode = 0;  // Selection::Op used when no modifier key is held
    float selFeather = 0.f;
    ShapeKind shapeKind = ShapeKind::Rect;
    bool shapeFilled = true, shapeNewLayer = true;
    float shapeStroke = 4.f, shapeRadius = 24.f;
    int shapeSides = 5;
    GradientType gradType = GradientType::Linear;
    Gradient gradient;
    bool gradReverse = false, gradDither = true;
    float gradOpacity = 1.f;
    int gradPreset = 0;
    float fontSize = 64.f;
    int fontIndex = 0;
    float smoothing = 0.f;  // stroke stabilizer 0..0.95
    int dodgeRange = 1;
    bool spongeSaturate = false;

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
    unsigned int logoTex = 0, splashTex = 0;
    int splashW = 0, splashH = 0;
    std::map<std::string, unsigned int> brushPreviewTex;

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
    Gradient liveGrad;
    BrushStamper stamper;
    Retoucher retoucher;
    bool retouching = false;
    Vec2 smoothPt;

    // Pointer interaction
    bool dragging = false, panning = false;
    Vec2 downPt, lastPt, curPt;
    ImVec2 panStartMouse, panStartPan;
    bool downShift = false, downAlt = false, downCtrl = false;
    Stroker stroker;
    float strokeDir = 0.f;
    std::vector<Vec2> lasso;
    bool polyActive = false;
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
    bool filterCustomChanged = false;
    Image filterBackup;
    bool filterPreview = true;
    std::string popupToOpen;
    std::string errorText;
    std::function<void()> pendingDiscard;
    bool quitNow = false;
    // new document
    int newCategory = 0, newPreset = -1;
    int newW = 1920, newH = 1080, newBg = 0, newUnit = 0;
    float newDpi = 72.f;
    RGBA newBgColor{255, 255, 255, 255};
    std::string newName = "Без имени-1";
    int docCounter = 1;
    // image size etc.
    int sizeW = 0, sizeH = 0, anchor = 4;
    bool keepRatio = true;
    float featherRadius = 5.f;
    // layer style dialog
    bool fxOpen = false;
    int fxPage = 0;
    LayerFx fxBackup;
    std::string renameBuf;
    int renaming = -1;
    bool layoutReset = true;
    std::string status;
    std::string iniPath, prefDir;
    std::vector<std::string> recentFiles;
    bool showShortcuts = false, showAbout = false;
    bool showBrushSettings = false;
    int colorTabFocus = 0;
    float strokeWidth = 4.f;

    // ---- editor.cpp: documents, view, commands ----
    void openTab(std::unique_ptr<Document> d);
    void switchTab(int i);
    void closeTab(int i);  // asks to save when dirty
    void closeTabNow(int i);
    void syncTabState();   // copies zoom/pan into the current tab
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
    void addRecent(const std::string& path);
    void loadPrefs();
    void savePrefs();
    void pushRecentColor(RGBA c);

    void cmdNew();
    void cmdOpen();
    void cmdPlace();
    void cmdImportLayers();
    void cmdBrushFromFile();
    void cmdBrushFromSelection();
    void cmdNewFromClipboard();
    void cmdSave(bool saveAs, std::function<void()> then = {});
    void cmdExport();
    void cmdUndo();
    void cmdRedo();
    void cmdCopy(bool merged);
    void cmdCut();
    void cmdPaste();
    void cmdFill(RGBA c, const char* name);
    void cmdClear();
    void cmdStrokeSelection(float width);
    void cmdSelectAll();
    void cmdDeselect();
    void cmdInvertSelection();
    void cmdCropToSelection();
    void cmdTrim();
    void cmdLayerViaCopy();
    void cmdFlipLayer(bool horizontal);
    void cmdOpenLayerStyle();
    void layerAction(const char* name, const std::function<void(Document&)>& f);
    void imageAction(const char* name, const std::function<void(Document&)>& f);
    void instantFilter(const char* name, const std::function<void(Image&)>& f);
    void openFilter(FilterSpec spec);
    void filterApplyPreview();
    void filterFinish(bool ok);
    void cmdTransform();
    void placeImage(const std::string& path);
    Image loadImageOrError(const std::string& path, bool& ok);

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
    void retouchDab(Vec2 p);
    float spacingPx() const;
    void applyCrop();
    void finishPolyLasso();
    void commitText();
    void cancelText();
    void textPreview();
    void drawShapeCoverage(Vec2 a, Vec2 b);
    void drawOverlays(ImDrawList* dl);
    void rebuildAnts();
    Selection::Op selOpFromMods() const;
    void combineSelection(std::vector<uint8_t> shape, Selection::Op op);
    RGBA gradientAt(int x, int y) const;
    ToolBrush& brush() { return tb[tool]; }
    const BrushTip& tipOf(const BrushPreset& p);
    static bool isBrushTool(Tool t);
    static bool isRetouchTool(Tool t);

    // ---- editor_ui.cpp: main windows, menus, panels ----
    void setupStyle(float scale);
    void loadFonts(float scale);
    void drawMenuBar();
    void drawOptionsBar();
    void drawStatusBar();
    void drawDockspace();
    void drawToolbox();
    void drawCanvas();
    void drawTabs();
    void drawColors();
    void drawBrushes();
    void drawLayers();
    void drawHistory();
    void drawNavigator();
    void drawHomeScreen();
    void handleShortcuts();
    void scanFonts();
    bool brushPresetButton(const BrushPreset& p, bool selected, float w);
    bool gradientCombo(const char* id, Gradient& g, float width);

    // ---- editor_dialogs.cpp: modal dialogs ----
    void drawDialogs();
    void drawNewDocument();
    void drawLayerStyle();
    void drawFilterDialog();
    void openCurves();
    void openGradientMap();
    void openPhotoFilter();
    void openClouds();
    void openLensFlare();
};

extern ImFont* gTitleFont;  // large bold font for headings (may be null)
extern ImFont* gMediumFont;

ImU32 toU32(RGBA c);
ImVec4 toVec4(RGBA c);
RGBA fromVec4(const ImVec4& v);

void drawGradientStrip(ImDrawList* dl, ImVec2 a, ImVec2 b, const Gradient& g, float rounding = 4.f);

// Small line icons for UI buttons (not tools).
enum class UiIcon { Eye, EyeOff, Plus, Duplicate, Trash, Up, Down, Merge, Fx, Folder, File, Close, Brush };
void drawUiIcon(ImDrawList* dl, UiIcon icon, ImVec2 center, float size, ImU32 color);
bool iconButton(const char* id, UiIcon icon, const char* tooltip, bool enabled = true, float size = 0);

}  // namespace ag
