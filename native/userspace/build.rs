fn main() {
    println!("cargo:rerun-if-changed=build.rs");
    if std::env::var("TARGET").as_deref() == Ok("x86_64-unknown-none") {
        if std::env::var_os("CARGO_FEATURE_LAUNCH_SESSION").is_some() {
            println!(
                "cargo:rustc-link-arg-bin=PooleLaunchShell=--defsym=__poole_launch_candidate=1"
            );
        }
        println!("cargo:rustc-link-arg-bin=PooleWindowCapacity=--defsym=__poole_window_capacity=1");
        println!(
            "cargo:rustc-link-arg-bin=PooleWindowLifecycle=--defsym=__poole_window_capacity=1"
        );
        println!("cargo:rustc-link-arg-bin=PooleWindowInput=--defsym=__poole_window_capacity=1");
    }
}
