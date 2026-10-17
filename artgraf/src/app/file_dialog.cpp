#include "file_dialog.h"

#include <algorithm>

#include <imgui.h>
#include <imgui_stdlib.h>

#include "io.h"

#ifdef ARTGRAF_NFD
#include <nfd.h>
#endif

namespace fs = std::filesystem;

namespace ag {

namespace {
std::string u8(const fs::path& p) {
    auto s = p.u8string();
    return std::string(s.begin(), s.end());
}
fs::path fromU8(const std::string& s) {
#if defined(__cpp_char8_t)
    return fs::path(std::u8string(s.begin(), s.end()));
#else
    return fs::u8path(s);
#endif
}
}  // namespace

FileDialog::FileDialog() {
#ifdef ARTGRAF_NFD
    NFD_Init();
#endif
    std::error_code ec;
    dir = fs::current_path(ec);
}

FileDialog::~FileDialog() {
#ifdef ARTGRAF_NFD
    NFD_Quit();
#endif
}

void FileDialog::request(Mode m, const std::string& t, std::vector<Filter> f, const std::string& def, Callback c) {
#ifdef ARTGRAF_NFD
    multi = false;
#endif
    mode = m;
    title = t;
    filters = std::move(f);
    defaultName = def;
    cb = std::move(c);
    pending = true;
}

void FileDialog::requestMulti(const std::string& t, std::vector<Filter> f, MultiCallback c) {
    multiCb = std::move(c);
    request(Mode::Open, t, std::move(f), "", [this](const std::string& p) {
        if (multiCb) multiCb({p});
    });
#ifdef ARTGRAF_NFD
    multi = true;
#endif
}

void FileDialog::runPending() {
#ifdef ARTGRAF_NFD
    if (!pending) return;
    pending = false;
    std::vector<nfdu8filteritem_t> items;
    for (auto& f : filters) items.push_back({f.name.c_str(), f.exts.c_str()});
    if (multi) {
        multi = false;
        const nfdpathset_t* set = nullptr;
        if (NFD_OpenDialogMultipleU8(&set, items.data(), nfdfiltersize_t(items.size()), nullptr) == NFD_OKAY && set) {
            std::vector<std::string> paths;
            nfdpathsetsize_t n = 0;
            NFD_PathSet_GetCount(set, &n);
            for (nfdpathsetsize_t i = 0; i < n; i++) {
                nfdu8char_t* p = nullptr;
                if (NFD_PathSet_GetPathU8(set, i, &p) == NFD_OKAY && p) {
                    paths.push_back(p);
                    NFD_PathSet_FreePathU8(p);
                }
            }
            NFD_PathSet_Free(set);
            if (multiCb) multiCb(paths);
        }
        return;
    }
    nfdu8char_t* out = nullptr;
    nfdresult_t r;
    if (mode == Mode::Open)
        r = NFD_OpenDialogU8(&out, items.data(), nfdfiltersize_t(items.size()), nullptr);
    else
        r = NFD_SaveDialogU8(&out, items.data(), nfdfiltersize_t(items.size()), nullptr, defaultName.c_str());
    if (r == NFD_OKAY && out) {
        std::string path = out;
        NFD_FreePathU8(out);
        // The Windows save dialog does not always append the extension of the chosen filter.
        if (mode == Mode::Save && lowerExt(path).empty() && !filters.empty())
            path += "." + filters[0].exts.substr(0, filters[0].exts.find(','));
        if (cb) cb(path);
    }
#endif
}

bool FileDialog::matches(const std::string& name) const {
    if (filters.empty()) return true;
    std::string ext = lowerExt(name);
    const std::string& list = filters[size_t(filterIdx)].exts;
    size_t start = 0;
    while (start <= list.size()) {
        size_t end = list.find(',', start);
        if (end == std::string::npos) end = list.size();
        if (list.compare(start, end - start, ext) == 0) return true;
        start = end + 1;
    }
    return false;
}

void FileDialog::refresh() {
    entries.clear();
    std::error_code ec;
    for (auto it = fs::directory_iterator(dir, fs::directory_options::skip_permission_denied, ec);
         !ec && it != fs::directory_iterator(); it.increment(ec)) {
        std::string name = u8(it->path().filename());
        if (name.empty() || name[0] == '.') continue;
        bool isDir = it->is_directory(ec);
        if (isDir || matches(name)) entries.push_back({name, isDir});
    }
    std::sort(entries.begin(), entries.end(), [](const Entry& a, const Entry& b) {
        if (a.dir != b.dir) return a.dir;
        return a.name < b.name;
    });
}

void FileDialog::draw() {
#ifdef ARTGRAF_NFD
    return;  // native dialogs run from runPending() between frames
#endif
    if (pending) {  // built-in browser: the popup has to be opened inside the frame
        pending = false;
        browserOpen = true;
        nameBuf = defaultName;
        filterIdx = 0;
        dirBuf = u8(dir);
        refresh();
        ImGui::OpenPopup("##filebrowser");
    }
    if (!browserOpen) return;
    ImGui::SetNextWindowSize(ImVec2(620, 460), ImGuiCond_Appearing);
    if (!ImGui::BeginPopupModal("##filebrowser", &browserOpen)) return;
    ImGui::TextUnformatted(title.c_str());
    ImGui::Separator();
    if (ImGui::Button("Вверх")) {
        dir = dir.parent_path();
        dirBuf = u8(dir);
        refresh();
    }
    ImGui::SameLine();
    ImGui::SetNextItemWidth(-1);
    if (ImGui::InputText("##dir", &dirBuf, ImGuiInputTextFlags_EnterReturnsTrue)) {
        std::error_code ec;
        if (fs::is_directory(fromU8(dirBuf), ec)) dir = fromU8(dirBuf);
        refresh();
    }
    std::string accept;
    ImGui::BeginChild("##list", ImVec2(0, -ImGui::GetFrameHeightWithSpacing() * 2), ImGuiChildFlags_Borders);
    for (auto& e : entries) {
        std::string label = (e.dir ? "[папка] " : "") + e.name;
        if (ImGui::Selectable(label.c_str(), !e.dir && e.name == nameBuf, ImGuiSelectableFlags_AllowDoubleClick)) {
            if (e.dir) {
                if (ImGui::IsMouseDoubleClicked(0)) {
                    dir /= fromU8(e.name);
                    dirBuf = u8(dir);
                    refresh();
                    break;
                }
            } else {
                nameBuf = e.name;
                if (ImGui::IsMouseDoubleClicked(0)) accept = nameBuf;
            }
        }
    }
    ImGui::EndChild();
    ImGui::SetNextItemWidth(ImGui::GetContentRegionAvail().x * 0.6f);
    if (ImGui::InputText("Имя", &nameBuf, ImGuiInputTextFlags_EnterReturnsTrue)) accept = nameBuf;
    if (!filters.empty()) {
        ImGui::SameLine();
        ImGui::SetNextItemWidth(-1);
        if (ImGui::BeginCombo("##filter", filters[size_t(filterIdx)].name.c_str())) {
            for (int i = 0; i < int(filters.size()); i++)
                if (ImGui::Selectable(filters[size_t(i)].name.c_str(), i == filterIdx)) {
                    filterIdx = i;
                    refresh();
                }
            ImGui::EndCombo();
        }
    }
    if (ImGui::Button(mode == Mode::Open ? "Открыть" : "Сохранить", ImVec2(120, 0)) && !nameBuf.empty()) accept = nameBuf;
    ImGui::SameLine();
    if (ImGui::Button("Отмена", ImVec2(120, 0))) {
        browserOpen = false;
        ImGui::CloseCurrentPopup();
    }
    if (!accept.empty()) {
        std::string path = u8(dir / fromU8(accept));
        if (mode == Mode::Save && lowerExt(path).empty() && !filters.empty()) {
            const std::string& ex = filters[size_t(filterIdx)].exts;
            path += "." + ex.substr(0, ex.find(','));
        }
        browserOpen = false;
        ImGui::CloseCurrentPopup();
        if (cb) cb(path);
    }
    ImGui::EndPopup();
}

}  // namespace ag
