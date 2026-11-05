#![cfg_attr(windows, windows_subsystem = "windows")]

#[cfg(windows)]
mod win;

#[cfg(windows)]
fn main() {
    win::run();
}

#[cfg(not(windows))]
fn main() {
    eprintln!("Это Блокнот для Windows. Соберите его так:");
    eprintln!("  cargo build --release --target x86_64-pc-windows-gnu");
    std::process::exit(1);
}
