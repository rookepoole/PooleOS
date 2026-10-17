fn main() {
    println!("cargo:rerun-if-changed=build.rs");
    if std::env::var("TARGET").as_deref() == Ok("x86_64-unknown-none") {
        println!("cargo:rustc-link-arg-bin=PooleWindowCapacity=--defsym=__poole_window_capacity=1");
        println!(
            "cargo:rustc-link-arg-bin=PooleWindowLifecycle=--defsym=__poole_window_capacity=1"
        );
    }
}
