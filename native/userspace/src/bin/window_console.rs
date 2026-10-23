#![no_std]
#![no_main]
#[path = "../window_main.rs"]
mod window_main;
poole_userspace::entry!(window_main::main);
