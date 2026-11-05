fn main() {
    // Иконка, манифест (визуальные стили, DPI) и сведения о версии — только для Windows-сборки.
    if std::env::var("CARGO_CFG_TARGET_OS").as_deref() == Ok("windows") {
        println!("cargo:rerun-if-changed=res");
        embed_resource::compile("res/notepad.rc", embed_resource::NONE);
    }
}
