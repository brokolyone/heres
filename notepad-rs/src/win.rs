//! Окно Блокнота на чистом Win32: EDIT-контрол, меню, строка состояния,
//! стандартные диалоги (открыть/сохранить, шрифт, найти/заменить) и «Перейти».

use std::ffi::{c_void, OsString};
use std::os::windows::ffi::{OsStrExt, OsStringExt};
use std::path::{Path, PathBuf};
use std::ptr::{null, null_mut};

use windows_sys::core::{w, PCWSTR};
use windows_sys::Win32::Foundation::*;
use windows_sys::Win32::Globalization::*;
use windows_sys::Win32::Graphics::Gdi::*;
use windows_sys::Win32::System::DataExchange::IsClipboardFormatAvailable;
use windows_sys::Win32::System::LibraryLoader::{GetModuleFileNameW, GetModuleHandleW};
use windows_sys::Win32::System::Registry::*;
use windows_sys::Win32::System::SystemInformation::GetLocalTime;
use windows_sys::Win32::UI::Controls::Dialogs::*;
use windows_sys::Win32::UI::Controls::*;
use windows_sys::Win32::UI::HiDpi::GetDpiForWindow;
use windows_sys::Win32::UI::Input::KeyboardAndMouse::{GetKeyState, SetFocus, VK_CONTROL};
use windows_sys::Win32::UI::Shell::*;
use windows_sys::Win32::UI::WindowsAndMessaging::*;

use notepad_core::encoding::{self, Encoding, Eol};
use notepad_core::search;

const APP_NAME: &str = "Блокнот";
const UNTITLED: &str = "Безымянный";
const REG_KEY: PCWSTR = w!("Software\\notepad-rs");

// ---- идентификаторы команд ----
const IDM_NEW: u16 = 100;
const IDM_NEW_WINDOW: u16 = 101;
const IDM_OPEN: u16 = 102;
const IDM_SAVE: u16 = 103;
const IDM_SAVE_AS: u16 = 104;
const IDM_EXIT: u16 = 105;
const IDM_UNDO: u16 = 200;
const IDM_CUT: u16 = 201;
const IDM_COPY: u16 = 202;
const IDM_PASTE: u16 = 203;
const IDM_DELETE: u16 = 204;
const IDM_FIND: u16 = 205;
const IDM_FIND_NEXT: u16 = 206;
const IDM_FIND_PREV: u16 = 207;
const IDM_REPLACE: u16 = 208;
const IDM_GOTO: u16 = 209;
const IDM_SELECT_ALL: u16 = 210;
const IDM_TIME_DATE: u16 = 211;
const IDM_WORD_WRAP: u16 = 300;
const IDM_FONT: u16 = 301;
const IDM_ENC_FIRST: u16 = 310; // + индекс в Encoding::ALL
const IDM_EOL_CRLF: u16 = 320;
const IDM_EOL_LF: u16 = 321;
const IDM_EOL_CR: u16 = 322;
const IDM_ZOOM_IN: u16 = 400;
const IDM_ZOOM_OUT: u16 = 401;
const IDM_ZOOM_RESET: u16 = 402;
const IDM_STATUS_BAR: u16 = 403;
const IDM_ABOUT: u16 = 500;

const ID_EDIT: usize = 1;
const ID_STATUS: usize = 2;
const IDC_GOTO_LINE: i32 = 1001;

struct App {
    hinst: HINSTANCE,
    hwnd: HWND,
    edit: HWND,
    status: HWND,
    accel: HACCEL,
    path: Option<PathBuf>,
    encoding: Encoding,
    eol: Eol,
    wrap: bool,
    show_status: bool,
    face: [u16; 32],
    weight: i32,
    italic: bool,
    /// Размер шрифта в десятых долях пункта (110 = 11 pt).
    pt10: i32,
    zoom: i32,
    font: HFONT,
    shown_modified: Option<bool>,
    find_msg: u32,
    find_dlg: HWND,
    fr: FINDREPLACEW,
    find_buf: [u16; 256],
    repl_buf: [u16; 256],
}

static mut APP: *mut App = null_mut();

fn app() -> &'static mut App {
    // Всё GUI работает в одном потоке; состояние создаётся до первого сообщения.
    unsafe { &mut *APP }
}

// ---- мелкие помощники ----

fn wide(s: &str) -> Vec<u16> {
    s.encode_utf16().chain(Some(0)).collect()
}

fn from_wide_nul(buf: &[u16]) -> Vec<u16> {
    buf[..buf.iter().position(|&c| c == 0).unwrap_or(buf.len())].to_vec()
}

fn loword(v: usize) -> u16 {
    (v & 0xFFFF) as u16
}

fn hiword(v: usize) -> u16 {
    ((v >> 16) & 0xFFFF) as u16
}

unsafe fn send(h: HWND, msg: u32, w: usize, l: isize) -> isize {
    SendMessageW(h, msg, w, l)
}

fn message(text: &str, flags: u32) -> i32 {
    unsafe { MessageBoxW(app().hwnd, wide(text).as_ptr(), wide(APP_NAME).as_ptr(), flags) }
}

fn dpi() -> i32 {
    let a = app();
    let d = unsafe { GetDpiForWindow(a.hwnd) } as i32;
    if d > 0 { d } else { 96 }
}

fn mul_div(a: i32, b: i32, c: i32) -> i32 {
    ((a as i64 * b as i64 + c as i64 / 2) / c as i64) as i32
}

fn scale(px: i32) -> i32 {
    mul_div(px, dpi(), 96)
}

fn edit_text() -> Vec<u16> {
    unsafe {
        let e = app().edit;
        let len = GetWindowTextLengthW(e);
        let mut buf = vec![0u16; len as usize + 1];
        let n = GetWindowTextW(e, buf.as_mut_ptr(), len + 1);
        buf.truncate(n.max(0) as usize);
        buf
    }
}

fn set_edit_text(text: &[u16]) {
    let mut t = text.to_vec();
    t.push(0);
    unsafe { SetWindowTextW(app().edit, t.as_ptr()) };
}

fn selection() -> (usize, usize) {
    let (mut s, mut e) = (0u32, 0u32);
    unsafe { send(app().edit, EM_GETSEL, &mut s as *mut u32 as usize, &mut e as *mut u32 as isize) };
    (s as usize, e as usize)
}

fn select(s: usize, e: usize) {
    unsafe {
        send(app().edit, EM_SETSEL, s, e as isize);
        send(app().edit, EM_SCROLLCARET, 0, 0);
    }
}

fn replace_selection(text: &[u16]) {
    let mut t = text.to_vec();
    t.push(0);
    unsafe { send(app().edit, EM_REPLACESEL, 1, t.as_ptr() as isize) };
}

fn is_modified() -> bool {
    unsafe { send(app().edit, EM_GETMODIFY, 0, 0) != 0 }
}

fn set_modified(m: bool) {
    unsafe { send(app().edit, EM_SETMODIFY, m as usize, 0) };
    update_title();
}

fn file_name() -> String {
    match &app().path {
        Some(p) => p.file_name().map(|n| n.to_string_lossy().into_owned()).unwrap_or_default(),
        None => UNTITLED.to_string(),
    }
}

// ---- заголовок и строка состояния ----

fn update_title() {
    let m = is_modified();
    let a = app();
    if a.shown_modified == Some(m) {
        return;
    }
    a.shown_modified = Some(m);
    let title = format!("{}{} — {}", if m { "*" } else { "" }, file_name(), APP_NAME);
    unsafe { SetWindowTextW(a.hwnd, wide(&title).as_ptr()) };
}

fn status_parts() {
    let a = app();
    let mut rc: RECT = unsafe { std::mem::zeroed() };
    unsafe { GetClientRect(a.hwnd, &mut rc) };
    let r = rc.right;
    let widths = [scale(110), scale(130), scale(55), scale(150)]; // справа налево
    let mut edges = [0i32; 5];
    edges[4] = -1;
    edges[3] = r - widths[0];
    edges[2] = edges[3] - widths[1];
    edges[1] = edges[2] - widths[2];
    edges[0] = edges[1] - widths[3];
    unsafe { send(a.status, SB_SETPARTS, edges.len(), edges.as_ptr() as isize) };
}

fn set_status_text(part: usize, text: &str) {
    unsafe { send(app().status, SB_SETTEXTW, part, wide(text).as_ptr() as isize) };
}

fn update_status() {
    let a = app();
    if a.status.is_null() || !a.show_status {
        return;
    }
    let (_, end) = selection();
    let line = unsafe { send(a.edit, EM_LINEFROMCHAR, end, 0) } as usize;
    let start = unsafe { send(a.edit, EM_LINEINDEX, line, 0) } as usize;
    set_status_text(1, &format!("  Стр {}, стлб {}", line + 1, end.saturating_sub(start) + 1));
    set_status_text(2, &format!("  {}%", a.zoom));
    set_status_text(3, &format!("  {}", a.eol.label()));
    set_status_text(4, &format!("  {}", a.encoding.label()));
}

fn layout() {
    let a = app();
    let mut rc: RECT = unsafe { std::mem::zeroed() };
    unsafe {
        GetClientRect(a.hwnd, &mut rc);
        let mut sh = 0;
        if a.show_status {
            send(a.status, WM_SIZE, 0, 0);
            let mut src: RECT = std::mem::zeroed();
            GetWindowRect(a.status, &mut src);
            sh = src.bottom - src.top;
            status_parts();
        }
        MoveWindow(a.edit, 0, 0, rc.right, rc.bottom - sh, 1);
    }
    update_status();
}

// ---- шрифт и масштаб ----

fn apply_font() {
    let a = app();
    let mut lf: LOGFONTW = unsafe { std::mem::zeroed() };
    lf.lfHeight = -mul_div(a.pt10 * a.zoom, dpi(), 72 * 10 * 100);
    lf.lfWeight = a.weight;
    lf.lfItalic = a.italic as u8;
    lf.lfCharSet = DEFAULT_CHARSET as u8;
    lf.lfQuality = CLEARTYPE_QUALITY as u8;
    lf.lfFaceName = a.face;
    let font = unsafe { CreateFontIndirectW(&lf) };
    unsafe { send(a.edit, WM_SETFONT, font as usize, 1) };
    if !a.font.is_null() {
        unsafe { DeleteObject(a.font) };
    }
    a.font = font;
    update_status();
}

fn set_zoom(z: i32) {
    let a = app();
    let z = z.clamp(10, 500);
    if z != a.zoom {
        a.zoom = z;
        apply_font();
    }
}

fn choose_font() {
    let a = app();
    let mut lf: LOGFONTW = unsafe { std::mem::zeroed() };
    lf.lfHeight = -mul_div(a.pt10, dpi(), 720);
    lf.lfWeight = a.weight;
    lf.lfItalic = a.italic as u8;
    lf.lfCharSet = DEFAULT_CHARSET as u8;
    lf.lfFaceName = a.face;
    let mut cf: CHOOSEFONTW = unsafe { std::mem::zeroed() };
    cf.lStructSize = std::mem::size_of::<CHOOSEFONTW>() as u32;
    cf.hwndOwner = a.hwnd;
    cf.lpLogFont = &mut lf;
    cf.Flags = CF_SCREENFONTS | CF_INITTOLOGFONTSTRUCT;
    if unsafe { ChooseFontW(&mut cf) } != 0 {
        a.face = lf.lfFaceName;
        a.weight = lf.lfWeight;
        a.italic = lf.lfItalic != 0;
        a.pt10 = if cf.iPointSize > 0 { cf.iPointSize } else { a.pt10 };
        apply_font();
    }
}

// ---- EDIT-контрол ----

fn create_edit() -> HWND {
    let a = app();
    let mut style = WS_CHILD | WS_VISIBLE | WS_VSCROLL | (ES_MULTILINE | ES_AUTOVSCROLL | ES_NOHIDESEL) as u32;
    if !a.wrap {
        style |= WS_HSCROLL | ES_AUTOHSCROLL as u32;
    }
    unsafe {
        let edit = CreateWindowExW(
            0,
            w!("EDIT"),
            null(),
            style,
            0,
            0,
            0,
            0,
            a.hwnd,
            ID_EDIT as HMENU,
            a.hinst,
            null(),
        );
        send(edit, EM_SETLIMITTEXT, 0, 0); // без ограничения длины
        SetWindowSubclass(edit, Some(edit_proc), 1, 0);
        edit
    }
}

unsafe extern "system" fn edit_proc(h: HWND, msg: u32, wp: WPARAM, lp: LPARAM, _id: usize, _data: usize) -> LRESULT {
    if msg == WM_MOUSEWHEEL && GetKeyState(VK_CONTROL as i32) < 0 {
        let delta = hiword(wp) as i16;
        set_zoom(app().zoom + if delta > 0 { 10 } else { -10 });
        return 0;
    }
    let r = DefSubclassProc(h, msg, wp, lp);
    match msg {
        WM_KEYDOWN | WM_KEYUP | WM_CHAR | WM_LBUTTONDOWN | WM_LBUTTONUP | WM_MOUSEMOVE | WM_SETTEXT
        | EM_SETSEL | EM_REPLACESEL | WM_PASTE | WM_CUT | WM_CLEAR | WM_UNDO => {
            if msg != WM_MOUSEMOVE || wp & 0x0001usize /* MK_LBUTTON */ != 0 {
                update_status();
            }
        }
        _ => {}
    }
    r
}

fn toggle_wrap() {
    let a = app();
    let text = edit_text();
    let (s, e) = selection();
    let modified = is_modified();
    a.wrap = !a.wrap;
    let old = a.edit;
    a.edit = create_edit();
    unsafe {
        send(a.edit, WM_SETFONT, a.font as usize, 0);
        DestroyWindow(old);
    }
    set_edit_text(&text);
    a.shown_modified = None;
    set_modified(modified);
    select(s, e);
    layout();
    unsafe { SetFocus(a.edit) };
}

// ---- файлы ----

fn ansi_decode(bytes: &[u8]) -> Vec<u16> {
    if bytes.is_empty() {
        return Vec::new();
    }
    unsafe {
        let n = MultiByteToWideChar(CP_ACP, 0, bytes.as_ptr(), bytes.len() as i32, null_mut(), 0);
        let mut out = vec![0u16; n.max(0) as usize];
        MultiByteToWideChar(CP_ACP, 0, bytes.as_ptr(), bytes.len() as i32, out.as_mut_ptr(), n);
        out
    }
}

/// Возвращает байты и признак того, что часть символов потерялась.
fn ansi_encode_checked(units: &[u16]) -> (Vec<u8>, bool) {
    if units.is_empty() {
        return (Vec::new(), false);
    }
    unsafe {
        let n = WideCharToMultiByte(CP_ACP, 0, units.as_ptr(), units.len() as i32, null_mut(), 0, null(), null_mut());
        let mut out = vec![0u8; n.max(0) as usize];
        let mut lost: BOOL = 0;
        WideCharToMultiByte(CP_ACP, 0, units.as_ptr(), units.len() as i32, out.as_mut_ptr(), n, null(), &mut lost);
        (out, lost != 0)
    }
}

fn new_document() {
    let a = app();
    a.path = None;
    a.encoding = Encoding::Utf8;
    a.eol = Eol::CrLf;
    set_edit_text(&[]);
    a.shown_modified = None;
    set_modified(false);
    update_status();
}

fn load_file(path: PathBuf) {
    let bytes = match std::fs::read(&path) {
        Ok(b) => b,
        Err(e) => {
            message(&format!("{}\n\nНе удается открыть файл: {e}", path.display()), MB_ICONERROR);
            return;
        }
    };
    let d = encoding::decode(&bytes, ansi_decode);
    let a = app();
    a.path = Some(path);
    a.encoding = d.encoding;
    a.eol = d.eol;
    set_edit_text(&d.text);
    a.shown_modified = None;
    set_modified(false);
    select(0, 0);
    // Как в настоящем Блокноте: файл, начинающийся с «.LOG», получает отметку времени.
    if d.text.starts_with(&".LOG".encode_utf16().collect::<Vec<_>>()) {
        let end = d.text.len();
        select(end, end);
        let mut stamp: Vec<u16> = "\r\n".encode_utf16().collect();
        stamp.extend(time_date());
        stamp.extend("\r\n".encode_utf16());
        replace_selection(&stamp);
    }
    update_status();
}

fn write_file(path: &Path) -> bool {
    let a = app();
    let text = edit_text();
    let bytes = if a.encoding == Encoding::Ansi {
        let (bytes, lost) = ansi_encode_checked(&encoding::from_crlf(&text, a.eol));
        if lost
            && message(
                "Этот файл содержит символы Юникода, которые будут потеряны при сохранении в кодировке ANSI.\n\
                 Чтобы сохранить их, выберите в меню «Формат → Кодировка» вариант UTF-8.\n\nПродолжить?",
                MB_OKCANCEL | MB_ICONWARNING,
            ) != IDOK
        {
            return false;
        }
        bytes
    } else {
        encoding::encode(&text, a.encoding, a.eol, |u| ansi_encode_checked(u).0)
    };
    match std::fs::write(path, bytes) {
        Ok(()) => {
            a.path = Some(path.to_path_buf());
            a.shown_modified = None;
            set_modified(false);
            true
        }
        Err(e) => {
            message(&format!("{}\n\nНе удается сохранить файл: {e}", path.display()), MB_ICONERROR);
            false
        }
    }
}

const FILTER: &str = "Текстовые документы (*.txt)\0*.txt\0Все файлы (*.*)\0*.*\0\0";

fn file_dialog(save: bool) -> Option<PathBuf> {
    let a = app();
    let mut buf = vec![0u16; 32768];
    if save {
        let initial: Vec<u16> = match &a.path {
            Some(p) => p.file_name().map(|n| n.encode_wide().collect()).unwrap_or_default(),
            None => "*.txt".encode_utf16().collect(),
        };
        buf[..initial.len()].copy_from_slice(&initial);
    }
    let filter: Vec<u16> = FILTER.encode_utf16().collect();
    let mut ofn: OPENFILENAMEW = unsafe { std::mem::zeroed() };
    ofn.lStructSize = std::mem::size_of::<OPENFILENAMEW>() as u32;
    ofn.hwndOwner = a.hwnd;
    ofn.lpstrFilter = filter.as_ptr();
    ofn.lpstrFile = buf.as_mut_ptr();
    ofn.nMaxFile = buf.len() as u32;
    ofn.lpstrDefExt = w!("txt");
    ofn.Flags = OFN_EXPLORER
        | OFN_HIDEREADONLY
        | if save { OFN_OVERWRITEPROMPT | OFN_PATHMUSTEXIST } else { OFN_FILEMUSTEXIST | OFN_PATHMUSTEXIST };
    let ok = unsafe { if save { GetSaveFileNameW(&mut ofn) } else { GetOpenFileNameW(&mut ofn) } };
    (ok != 0).then(|| PathBuf::from(OsString::from_wide(&from_wide_nul(&buf))))
}

fn save() -> bool {
    match app().path.clone() {
        Some(p) => write_file(&p),
        None => save_as(),
    }
}

fn save_as() -> bool {
    match file_dialog(true) {
        Some(p) => write_file(&p),
        None => false,
    }
}

/// Спрашивает про несохранённые изменения. `false` — пользователь передумал.
fn confirm_discard() -> bool {
    if !is_modified() {
        return true;
    }
    let q = format!("Вы хотите сохранить изменения в файле \"{}\"?", file_name());
    match message(&q, MB_YESNOCANCEL | MB_ICONWARNING) {
        IDYES => save(),
        IDNO => true,
        _ => false,
    }
}

fn open_from_command_line() {
    let Some(arg) = std::env::args_os().nth(1) else { return };
    let path = PathBuf::from(arg);
    if path.exists() {
        load_file(path);
    } else {
        let q = format!("Не удается найти файл {}.\n\nСоздать новый файл?", path.display());
        if message(&q, MB_YESNOCANCEL | MB_ICONWARNING) == IDYES {
            if std::fs::write(&path, b"").is_ok() {
                load_file(path);
            }
        }
    }
}

// ---- правка ----

fn time_date() -> Vec<u16> {
    unsafe {
        let mut st: SYSTEMTIME = std::mem::zeroed();
        GetLocalTime(&mut st);
        let mut t = [0u16; 64];
        let mut d = [0u16; 64];
        GetTimeFormatEx(null(), TIME_NOSECONDS, &st, null(), t.as_mut_ptr(), 64);
        GetDateFormatEx(null(), DATE_SHORTDATE, &st, null(), d.as_mut_ptr(), 64, null());
        let mut out = from_wide_nul(&t);
        out.push(b' ' as u16);
        out.extend(from_wide_nul(&d));
        out
    }
}

fn new_window() {
    let mut exe = [0u16; 1024];
    unsafe {
        GetModuleFileNameW(null_mut(), exe.as_mut_ptr(), exe.len() as u32);
        ShellExecuteW(app().hwnd, w!("open"), exe.as_ptr(), null(), null(), SW_SHOWNORMAL);
    }
}

// ---- найти / заменить ----

fn open_find(replace: bool) {
    let a = app();
    if !a.find_dlg.is_null() {
        unsafe { DestroyWindow(a.find_dlg) };
        a.find_dlg = null_mut();
    }
    // Однострочное выделение подставляется в поле «Что».
    let (s, e) = selection();
    if s != e {
        let text = edit_text();
        let sel = &text[s.min(text.len())..e.min(text.len())];
        if !sel.contains(&(b'\n' as u16)) && sel.len() < a.find_buf.len() {
            a.find_buf.fill(0);
            a.find_buf[..sel.len()].copy_from_slice(sel);
        }
    }
    a.fr.lStructSize = std::mem::size_of::<FINDREPLACEW>() as u32;
    a.fr.hwndOwner = a.hwnd;
    a.fr.Flags &= FR_DOWN | FR_MATCHCASE | FR_WHOLEWORD;
    a.fr.lpstrFindWhat = a.find_buf.as_mut_ptr();
    a.fr.wFindWhatLen = a.find_buf.len() as u16;
    a.fr.lpstrReplaceWith = a.repl_buf.as_mut_ptr();
    a.fr.wReplaceWithLen = a.repl_buf.len() as u16;
    a.find_dlg = unsafe { if replace { ReplaceTextW(&mut a.fr) } else { FindTextW(&mut a.fr) } };
}

fn search_options(up: bool) -> search::Options {
    let f = app().fr.Flags;
    search::Options { match_case: f & FR_MATCHCASE != 0, whole_word: f & FR_WHOLEWORD != 0, up, wrap: false }
}

fn needle() -> Vec<u16> {
    from_wide_nul(&app().find_buf)
}

fn find_next(up: bool) -> bool {
    let n = needle();
    if n.is_empty() {
        open_find(false);
        return false;
    }
    let text = edit_text();
    let (s, e) = selection();
    let from = if up { s } else { e };
    match search::find(&text, &n, from, &search_options(up)) {
        Some(pos) => {
            select(pos, pos + n.len());
            true
        }
        None => {
            let owner = if app().find_dlg.is_null() { app().hwnd } else { app().find_dlg };
            let t = format!("Не удается найти \"{}\"", String::from_utf16_lossy(&n));
            unsafe { MessageBoxW(owner, wide(&t).as_ptr(), wide(APP_NAME).as_ptr(), MB_ICONINFORMATION) };
            false
        }
    }
}

fn on_find_message(fr: &FINDREPLACEW) {
    let a = app();
    let f = fr.Flags;
    if f & FR_DIALOGTERM != 0 {
        a.find_dlg = null_mut();
        return;
    }
    let up = f & FR_DOWN == 0;
    if f & FR_FINDNEXT != 0 {
        find_next(up);
    } else if f & FR_REPLACE != 0 {
        let n = needle();
        let text = edit_text();
        let (s, e) = selection();
        let sel = &text[s.min(text.len())..e.min(text.len())];
        if !n.is_empty() && search::find(sel, &n, 0, &search_options(false)) == Some(0) && sel.len() == n.len() {
            replace_selection(&from_wide_nul(&a.repl_buf));
        }
        find_next(false);
    } else if f & FR_REPLACEALL != 0 {
        let n = needle();
        let (new, count) = search::replace_all(&edit_text(), &n, &from_wide_nul(&a.repl_buf), &search_options(false));
        if count > 0 {
            unsafe { send(a.edit, EM_SETSEL, 0, -1) };
            replace_selection(&new);
            select(0, 0);
        } else {
            find_next(false);
        }
    }
}

// ---- «Перейти к строке»: диалог собирается в памяти ----

fn push_str(v: &mut Vec<u16>, s: &str) {
    v.extend(s.encode_utf16());
    v.push(0);
}

fn align4(v: &mut Vec<u16>) {
    if v.len() % 2 == 1 {
        v.push(0);
    }
}

#[allow(clippy::too_many_arguments)]
fn push_item(v: &mut Vec<u16>, style: u32, x: i16, y: i16, cx: i16, cy: i16, id: u16, class: u16, text: &str) {
    align4(v);
    let style = style | WS_CHILD | WS_VISIBLE;
    v.extend([style as u16, (style >> 16) as u16, 0, 0]);
    v.extend([x as u16, y as u16, cx as u16, cy as u16, id, 0xFFFF, class]);
    push_str(v, text);
    v.push(0);
}

fn goto_template() -> Vec<u32> {
    let mut v: Vec<u16> = Vec::new();
    let style = DS_MODALFRAME as u32 | DS_SETFONT as u32 | DS_CENTER as u32 | WS_POPUP | WS_CAPTION | WS_SYSMENU;
    v.extend([style as u16, (style >> 16) as u16, 0, 0, 4, 0, 0, 180, 62, 0, 0]);
    push_str(&mut v, "Переход на строку");
    v.push(9);
    push_str(&mut v, "Segoe UI");
    push_item(&mut v, 0, 7, 7, 166, 9, 0xFFFF, 0x0082, "&Номер строки:");
    push_item(&mut v, (ES_NUMBER | ES_AUTOHSCROLL) as u32 | WS_BORDER | WS_TABSTOP, 7, 18, 166, 13, IDC_GOTO_LINE as u16, 0x0081, "");
    push_item(&mut v, BS_DEFPUSHBUTTON as u32 | WS_TABSTOP, 69, 40, 50, 15, IDOK as u16, 0x0080, "Перейти");
    push_item(&mut v, BS_PUSHBUTTON as u32 | WS_TABSTOP, 123, 40, 50, 15, IDCANCEL as u16, 0x0080, "Отмена");
    align4(&mut v);
    v.chunks(2).map(|c| c[0] as u32 | (c[1] as u32) << 16).collect()
}

unsafe extern "system" fn goto_proc(dlg: HWND, msg: u32, wp: WPARAM, _lp: LPARAM) -> isize {
    match msg {
        WM_INITDIALOG => {
            let (_, e) = selection();
            let line = send(app().edit, EM_LINEFROMCHAR, e, 0) as u32 + 1;
            SetDlgItemInt(dlg, IDC_GOTO_LINE, line, 0);
            let field = GetDlgItem(dlg, IDC_GOTO_LINE);
            send(field, EM_SETSEL, 0, -1);
            SetFocus(field);
            0
        }
        WM_COMMAND => match loword(wp) as i32 {
            IDOK => {
                let mut ok: BOOL = 0;
                let n = GetDlgItemInt(dlg, IDC_GOTO_LINE, &mut ok, 0) as usize;
                let count = send(app().edit, EM_GETLINECOUNT, 0, 0) as usize;
                if ok != 0 && n >= 1 && n <= count {
                    EndDialog(dlg, n as isize);
                } else {
                    MessageBoxW(
                        dlg,
                        w!("Номер строки выходит за пределы общего числа строк"),
                        w!("Блокнот — переход на строку"),
                        MB_ICONWARNING,
                    );
                }
                1
            }
            IDCANCEL => {
                EndDialog(dlg, 0);
                1
            }
            _ => 0,
        },
        _ => 0,
    }
}

fn goto_line() {
    let a = app();
    let tpl = goto_template();
    let n = unsafe { DialogBoxIndirectParamW(a.hinst, tpl.as_ptr() as *const DLGTEMPLATE, a.hwnd, Some(goto_proc), 0) };
    if n > 0 {
        let idx = unsafe { send(a.edit, EM_LINEINDEX, n as usize - 1, 0) } as usize;
        select(idx, idx);
    }
}

// ---- меню ----

fn build_menu() -> HMENU {
    unsafe {
        let item = |m: HMENU, id: u16, text: &str| {
            AppendMenuW(m, MF_STRING, id as usize, wide(text).as_ptr());
        };
        let sep = |m: HMENU| {
            AppendMenuW(m, MF_SEPARATOR, 0, null());
        };
        let bar = CreateMenu();

        let file = CreatePopupMenu();
        item(file, IDM_NEW, "&Создать\tCtrl+N");
        item(file, IDM_NEW_WINDOW, "&Новое окно\tCtrl+Shift+N");
        item(file, IDM_OPEN, "&Открыть...\tCtrl+O");
        item(file, IDM_SAVE, "Со&хранить\tCtrl+S");
        item(file, IDM_SAVE_AS, "Сохранить &как...\tCtrl+Shift+S");
        sep(file);
        item(file, IDM_EXIT, "В&ыход");
        AppendMenuW(bar, MF_POPUP, file as usize, w!("&Файл"));

        let edit = CreatePopupMenu();
        item(edit, IDM_UNDO, "&Отменить\tCtrl+Z");
        sep(edit);
        item(edit, IDM_CUT, "Вы&резать\tCtrl+X");
        item(edit, IDM_COPY, "&Копировать\tCtrl+C");
        item(edit, IDM_PASTE, "Вст&авить\tCtrl+V");
        item(edit, IDM_DELETE, "&Удалить\tDel");
        sep(edit);
        item(edit, IDM_FIND, "&Найти...\tCtrl+F");
        item(edit, IDM_FIND_NEXT, "Найти &далее\tF3");
        item(edit, IDM_FIND_PREV, "Найти ра&нее\tShift+F3");
        item(edit, IDM_REPLACE, "&Заменить...\tCtrl+H");
        item(edit, IDM_GOTO, "&Перейти...\tCtrl+G");
        sep(edit);
        item(edit, IDM_SELECT_ALL, "Выделить &все\tCtrl+A");
        item(edit, IDM_TIME_DATE, "Вре&мя и дата\tF5");
        AppendMenuW(bar, MF_POPUP, edit as usize, w!("&Правка"));

        let format = CreatePopupMenu();
        item(format, IDM_WORD_WRAP, "&Перенос по словам");
        item(format, IDM_FONT, "&Шрифт...");
        sep(format);
        let enc = CreatePopupMenu();
        for (i, e) in Encoding::ALL.iter().enumerate() {
            item(enc, IDM_ENC_FIRST + i as u16, e.label());
        }
        AppendMenuW(format, MF_POPUP, enc as usize, w!("&Кодировка"));
        let eol = CreatePopupMenu();
        item(eol, IDM_EOL_CRLF, Eol::CrLf.label());
        item(eol, IDM_EOL_LF, Eol::Lf.label());
        item(eol, IDM_EOL_CR, Eol::Cr.label());
        AppendMenuW(format, MF_POPUP, eol as usize, w!("Конец &строки"));
        AppendMenuW(bar, MF_POPUP, format as usize, w!("Фор&мат"));

        let view = CreatePopupMenu();
        let zoom = CreatePopupMenu();
        item(zoom, IDM_ZOOM_IN, "&Увеличить\tCtrl+Плюс");
        item(zoom, IDM_ZOOM_OUT, "У&меньшить\tCtrl+Минус");
        item(zoom, IDM_ZOOM_RESET, "&Восстановить масштаб по умолчанию\tCtrl+0");
        AppendMenuW(view, MF_POPUP, zoom as usize, w!("&Масштаб"));
        item(view, IDM_STATUS_BAR, "&Строка состояния");
        AppendMenuW(bar, MF_POPUP, view as usize, w!("&Вид"));

        let help = CreatePopupMenu();
        item(help, IDM_ABOUT, "&О программе");
        AppendMenuW(bar, MF_POPUP, help as usize, w!("&Справка"));
        bar
    }
}

fn build_accel() -> HACCEL {
    let c = (FVIRTKEY | FCONTROL) as u8;
    let cs = (FVIRTKEY | FCONTROL | FSHIFT) as u8;
    let v = FVIRTKEY as u8;
    let s = (FVIRTKEY | FSHIFT) as u8;
    let k = |ch: u8| ch as u16;
    let table = [
        (c, k(b'N'), IDM_NEW),
        (cs, k(b'N'), IDM_NEW_WINDOW),
        (c, k(b'O'), IDM_OPEN),
        (c, k(b'S'), IDM_SAVE),
        (cs, k(b'S'), IDM_SAVE_AS),
        (c, k(b'F'), IDM_FIND),
        (v, VK_F3, IDM_FIND_NEXT),
        (s, VK_F3, IDM_FIND_PREV),
        (c, k(b'H'), IDM_REPLACE),
        (c, k(b'G'), IDM_GOTO),
        (c, k(b'A'), IDM_SELECT_ALL),
        (v, VK_F5, IDM_TIME_DATE),
        (c, VK_OEM_PLUS, IDM_ZOOM_IN),
        (cs, VK_OEM_PLUS, IDM_ZOOM_IN),
        (c, VK_ADD, IDM_ZOOM_IN),
        (c, VK_OEM_MINUS, IDM_ZOOM_OUT),
        (c, VK_SUBTRACT, IDM_ZOOM_OUT),
        (c, k(b'0'), IDM_ZOOM_RESET),
        (c, VK_NUMPAD0, IDM_ZOOM_RESET),
    ];
    let accels: Vec<ACCEL> = table.iter().map(|&(f, key, cmd)| ACCEL { fVirt: f, key, cmd }).collect();
    unsafe { CreateAcceleratorTableW(accels.as_ptr(), accels.len() as i32) }
}

use windows_sys::Win32::UI::Input::KeyboardAndMouse::{
    VK_ADD, VK_F3, VK_F5, VK_NUMPAD0, VK_OEM_MINUS, VK_OEM_PLUS, VK_SUBTRACT,
};

fn init_menu_popup(menu: HMENU) {
    let a = app();
    let (s, e) = selection();
    let has_sel = s != e;
    let flag = |on: bool| if on { MF_ENABLED } else { MF_GRAYED };
    unsafe {
        EnableMenuItem(menu, IDM_UNDO as u32, flag(send(a.edit, EM_CANUNDO, 0, 0) != 0));
        EnableMenuItem(menu, IDM_CUT as u32, flag(has_sel));
        EnableMenuItem(menu, IDM_COPY as u32, flag(has_sel));
        EnableMenuItem(menu, IDM_DELETE as u32, flag(has_sel));
        EnableMenuItem(menu, IDM_PASTE as u32, flag(IsClipboardFormatAvailable(13 /* CF_UNICODETEXT */) != 0));
        let has_text = GetWindowTextLengthW(a.edit) > 0;
        for id in [IDM_FIND, IDM_FIND_NEXT, IDM_FIND_PREV] {
            EnableMenuItem(menu, id as u32, flag(has_text));
        }
        CheckMenuItem(menu, IDM_WORD_WRAP as u32, if a.wrap { MF_CHECKED } else { MF_UNCHECKED });
        CheckMenuItem(menu, IDM_STATUS_BAR as u32, if a.show_status { MF_CHECKED } else { MF_UNCHECKED });
        let enc_idx = Encoding::ALL.iter().position(|&x| x == a.encoding).unwrap_or(0) as u32;
        let last = IDM_ENC_FIRST as u32 + Encoding::ALL.len() as u32 - 1;
        CheckMenuRadioItem(menu, IDM_ENC_FIRST as u32, last, IDM_ENC_FIRST as u32 + enc_idx, MF_BYCOMMAND);
        let eol = match a.eol {
            Eol::CrLf => IDM_EOL_CRLF,
            Eol::Lf => IDM_EOL_LF,
            Eol::Cr => IDM_EOL_CR,
        };
        CheckMenuRadioItem(menu, IDM_EOL_CRLF as u32, IDM_EOL_CR as u32, eol as u32, MF_BYCOMMAND);
    }
}

fn command(id: u16) {
    let a = app();
    unsafe {
        match id {
            IDM_NEW => {
                if confirm_discard() {
                    new_document();
                }
            }
            IDM_NEW_WINDOW => new_window(),
            IDM_OPEN => {
                if confirm_discard() {
                    if let Some(p) = file_dialog(false) {
                        load_file(p);
                    }
                }
            }
            IDM_SAVE => {
                save();
            }
            IDM_SAVE_AS => {
                save_as();
            }
            IDM_EXIT => {
                PostMessageW(a.hwnd, WM_CLOSE, 0, 0);
            }
            IDM_UNDO => {
                send(a.edit, WM_UNDO, 0, 0);
            }
            IDM_CUT => {
                send(a.edit, WM_CUT, 0, 0);
            }
            IDM_COPY => {
                send(a.edit, WM_COPY, 0, 0);
            }
            IDM_PASTE => {
                send(a.edit, WM_PASTE, 0, 0);
            }
            IDM_DELETE => {
                send(a.edit, WM_CLEAR, 0, 0);
            }
            IDM_FIND => open_find(false),
            IDM_REPLACE => open_find(true),
            IDM_FIND_NEXT => {
                find_next(false);
            }
            IDM_FIND_PREV => {
                find_next(true);
            }
            IDM_GOTO => goto_line(),
            IDM_SELECT_ALL => {
                send(a.edit, EM_SETSEL, 0, -1);
                update_status();
            }
            IDM_TIME_DATE => replace_selection(&time_date()),
            IDM_WORD_WRAP => toggle_wrap(),
            IDM_FONT => choose_font(),
            IDM_EOL_CRLF | IDM_EOL_LF | IDM_EOL_CR => {
                let eol = [Eol::CrLf, Eol::Lf, Eol::Cr][(id - IDM_EOL_CRLF) as usize];
                if eol != a.eol {
                    a.eol = eol;
                    set_modified(true);
                    update_status();
                }
            }
            id if (IDM_ENC_FIRST..IDM_ENC_FIRST + Encoding::ALL.len() as u16).contains(&id) => {
                let enc = Encoding::ALL[(id - IDM_ENC_FIRST) as usize];
                if enc != a.encoding {
                    a.encoding = enc;
                    set_modified(true);
                    update_status();
                }
            }
            IDM_ZOOM_IN => set_zoom(a.zoom + 10),
            IDM_ZOOM_OUT => set_zoom(a.zoom - 10),
            IDM_ZOOM_RESET => set_zoom(100),
            IDM_STATUS_BAR => {
                a.show_status = !a.show_status;
                ShowWindow(a.status, if a.show_status { SW_SHOW } else { SW_HIDE });
                layout();
            }
            IDM_ABOUT => {
                let icon = LoadIconW(a.hinst, 1 as PCWSTR);
                ShellAboutW(
                    a.hwnd,
                    wide("Блокнот на Rust#Блокнот на Rust").as_ptr(),
                    wide("Блокнот Windows, пересобранный на Rust. Чистый Win32, без рантайма. Версия 0.1.0").as_ptr(),
                    icon,
                );
            }
            _ => {}
        }
    }
}

// ---- настройки в реестре ----

fn reg_get_dword(name: &str) -> Option<u32> {
    let mut v = 0u32;
    let mut size = 4u32;
    let r = unsafe {
        RegGetValueW(HKEY_CURRENT_USER, REG_KEY, wide(name).as_ptr(), RRF_RT_REG_DWORD, null_mut(), &mut v as *mut u32 as *mut c_void, &mut size)
    };
    (r == ERROR_SUCCESS).then_some(v)
}

fn reg_set_dword(name: &str, v: u32) {
    unsafe { RegSetKeyValueW(HKEY_CURRENT_USER, REG_KEY, wide(name).as_ptr(), REG_DWORD, &v as *const u32 as *const c_void, 4) };
}

fn reg_get_face() -> Option<[u16; 32]> {
    let mut buf = [0u16; 32];
    let mut size = 64u32;
    let r = unsafe {
        RegGetValueW(HKEY_CURRENT_USER, REG_KEY, w!("FaceName"), RRF_RT_REG_SZ, null_mut(), buf.as_mut_ptr() as *mut c_void, &mut size)
    };
    (r == ERROR_SUCCESS && buf[0] != 0).then_some(buf)
}

fn load_settings(a: &mut App) -> Option<RECT> {
    if let Some(f) = reg_get_face() {
        a.face = f;
    }
    a.pt10 = reg_get_dword("PointSize").map(|v| v as i32).filter(|v| (40..=7200).contains(v)).unwrap_or(a.pt10);
    a.weight = reg_get_dword("Weight").map(|v| v as i32).unwrap_or(a.weight);
    a.italic = reg_get_dword("Italic").map(|v| v != 0).unwrap_or(a.italic);
    a.wrap = reg_get_dword("WordWrap").map(|v| v != 0).unwrap_or(a.wrap);
    a.show_status = reg_get_dword("StatusBar").map(|v| v != 0).unwrap_or(a.show_status);
    let get = |n| reg_get_dword(n).map(|v| v as i32);
    match (get("WindowX"), get("WindowY"), get("WindowW"), get("WindowH")) {
        (Some(x), Some(y), Some(w), Some(h)) if w > 100 && h > 100 => Some(RECT { left: x, top: y, right: x + w, bottom: y + h }),
        _ => None,
    }
}

fn save_settings() {
    let a = app();
    unsafe {
        let len = a.face.iter().position(|&c| c == 0).unwrap_or(31) + 1;
        RegSetKeyValueW(HKEY_CURRENT_USER, REG_KEY, w!("FaceName"), REG_SZ, a.face.as_ptr() as *const c_void, (len * 2) as u32);
        let mut wp: WINDOWPLACEMENT = std::mem::zeroed();
        wp.length = std::mem::size_of::<WINDOWPLACEMENT>() as u32;
        if GetWindowPlacement(a.hwnd, &mut wp) != 0 {
            let r = wp.rcNormalPosition;
            reg_set_dword("WindowX", r.left as u32);
            reg_set_dword("WindowY", r.top as u32);
            reg_set_dword("WindowW", (r.right - r.left) as u32);
            reg_set_dword("WindowH", (r.bottom - r.top) as u32);
        }
    }
    reg_set_dword("PointSize", a.pt10 as u32);
    reg_set_dword("Weight", a.weight as u32);
    reg_set_dword("Italic", a.italic as u32);
    reg_set_dword("WordWrap", a.wrap as u32);
    reg_set_dword("StatusBar", a.show_status as u32);
}

// ---- главное окно ----

unsafe extern "system" fn wnd_proc(hwnd: HWND, msg: u32, wp: WPARAM, lp: LPARAM) -> LRESULT {
    if APP.is_null() {
        return DefWindowProcW(hwnd, msg, wp, lp);
    }
    let a = app();
    if msg == a.find_msg && a.find_msg != 0 {
        on_find_message(&*(lp as *const FINDREPLACEW));
        return 0;
    }
    match msg {
        WM_CREATE => {
            a.hwnd = hwnd;
            a.edit = create_edit();
            a.status = CreateWindowExW(
                0,
                STATUSCLASSNAMEW,
                null(),
                WS_CHILD | SBARS_SIZEGRIP | if a.show_status { WS_VISIBLE } else { 0 },
                0,
                0,
                0,
                0,
                hwnd,
                ID_STATUS as HMENU,
                a.hinst,
                null(),
            );
            apply_font();
            DragAcceptFiles(hwnd, 1);
            0
        }
        WM_SIZE => {
            layout();
            0
        }
        WM_SETFOCUS => {
            SetFocus(a.edit);
            0
        }
        WM_COMMAND => {
            if lp as HWND == a.edit {
                if hiword(wp) as u32 == EN_CHANGE {
                    update_title();
                }
            } else {
                command(loword(wp));
            }
            0
        }
        WM_INITMENUPOPUP => {
            init_menu_popup(wp as HMENU);
            0
        }
        WM_DROPFILES => {
            let drop = wp as HDROP;
            let mut buf = vec![0u16; 32768];
            let n = DragQueryFileW(drop, 0, buf.as_mut_ptr(), buf.len() as u32);
            DragFinish(drop);
            if n > 0 && confirm_discard() {
                load_file(PathBuf::from(OsString::from_wide(&buf[..n as usize])));
            }
            0
        }
        WM_DPICHANGED => {
            let r = &*(lp as *const RECT);
            SetWindowPos(hwnd, null_mut(), r.left, r.top, r.right - r.left, r.bottom - r.top, SWP_NOZORDER | SWP_NOACTIVATE);
            apply_font();
            layout();
            0
        }
        WM_CLOSE => {
            if confirm_discard() {
                DestroyWindow(hwnd);
            }
            0
        }
        WM_QUERYENDSESSION => confirm_discard() as LRESULT,
        WM_DESTROY => {
            save_settings();
            PostQuitMessage(0);
            0
        }
        _ => DefWindowProcW(hwnd, msg, wp, lp),
    }
}

pub fn run() {
    unsafe {
        let hinst = GetModuleHandleW(null());
        let icc = INITCOMMONCONTROLSEX {
            dwSize: std::mem::size_of::<INITCOMMONCONTROLSEX>() as u32,
            dwICC: ICC_BAR_CLASSES | ICC_STANDARD_CLASSES,
        };
        InitCommonControlsEx(&icc);

        let mut face = [0u16; 32];
        let consolas: Vec<u16> = "Consolas".encode_utf16().collect();
        face[..consolas.len()].copy_from_slice(&consolas);
        let mut state = Box::new(App {
            hinst,
            hwnd: null_mut(),
            edit: null_mut(),
            status: null_mut(),
            accel: null_mut(),
            path: None,
            encoding: Encoding::Utf8,
            eol: Eol::CrLf,
            wrap: false,
            show_status: true,
            face,
            weight: FW_NORMAL as i32,
            italic: false,
            pt10: 110,
            zoom: 100,
            font: null_mut(),
            shown_modified: None,
            find_msg: RegisterWindowMessageW(FINDMSGSTRINGW),
            find_dlg: null_mut(),
            fr: std::mem::zeroed(),
            find_buf: [0; 256],
            repl_buf: [0; 256],
        });
        state.fr.Flags = FR_DOWN;
        let placement = load_settings(&mut state);
        APP = Box::into_raw(state);
        let a = app();

        let icon = LoadIconW(hinst, 1 as PCWSTR);
        let class = WNDCLASSEXW {
            cbSize: std::mem::size_of::<WNDCLASSEXW>() as u32,
            style: CS_HREDRAW | CS_VREDRAW,
            lpfnWndProc: Some(wnd_proc),
            cbClsExtra: 0,
            cbWndExtra: 0,
            hInstance: hinst,
            hIcon: icon,
            hCursor: LoadCursorW(null_mut(), IDC_ARROW),
            hbrBackground: (COLOR_WINDOW + 1) as usize as HBRUSH,
            lpszMenuName: null(),
            lpszClassName: w!("NotepadRs"),
            hIconSm: icon,
        };
        RegisterClassExW(&class);

        let (x, y, w, h) = match placement {
            Some(r) => (r.left, r.top, r.right - r.left, r.bottom - r.top),
            None => (CW_USEDEFAULT, CW_USEDEFAULT, CW_USEDEFAULT, CW_USEDEFAULT),
        };
        let hwnd = CreateWindowExW(
            WS_EX_ACCEPTFILES,
            w!("NotepadRs"),
            w!("Блокнот"),
            WS_OVERLAPPEDWINDOW,
            x,
            y,
            w,
            h,
            null_mut(),
            build_menu(),
            hinst,
            null(),
        );
        a.accel = build_accel();
        new_document();
        open_from_command_line();
        ShowWindow(hwnd, SW_SHOWDEFAULT);
        UpdateWindow(hwnd);
        SetFocus(a.edit);

        let mut msg: MSG = std::mem::zeroed();
        while GetMessageW(&mut msg, null_mut(), 0, 0) > 0 {
            let a = app();
            if !a.find_dlg.is_null() && IsDialogMessageW(a.find_dlg, &msg) != 0 {
                continue;
            }
            if TranslateAcceleratorW(a.hwnd, a.accel, &msg) != 0 {
                continue;
            }
            TranslateMessage(&msg);
            DispatchMessageW(&msg);
        }
    }
}
