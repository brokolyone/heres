#pragma once
#include <filesystem>
#include <functional>
#include <string>
#include <vector>

namespace ag {

// Open/save dialogs. With nativefiledialog-extended the system dialog is shown (blocking, between
// frames); otherwise a small ImGui file browser is drawn as a modal popup.
class FileDialog {
public:
    enum class Mode { Open, Save };
    struct Filter {
        std::string name;
        std::string exts;  // comma separated, no dots: "png,jpg"
    };
    using Callback = std::function<void(const std::string& path)>;

    FileDialog();
    ~FileDialog();

    void request(Mode mode, const std::string& title, std::vector<Filter> filters, const std::string& defaultName,
                 Callback cb);
    void runPending();
    void draw();

private:
    struct Entry { std::string name; bool dir; };
    void refresh();
    bool matches(const std::string& name) const;

    bool pending = false, browserOpen = false;
    Mode mode = Mode::Open;
    std::string title, defaultName;
    std::vector<Filter> filters;
    Callback cb;

    std::filesystem::path dir;
    std::vector<Entry> entries;
    std::string nameBuf, dirBuf;
    int filterIdx = 0;
};

}  // namespace ag
