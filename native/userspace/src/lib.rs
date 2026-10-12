#![no_std]

pub mod console;
pub mod console_ipc;
pub mod protocol;
pub mod service;
pub mod startup;
pub mod supervisor;

#[cfg(all(target_arch = "x86_64", target_os = "none"))]
pub mod process;

#[cfg(test)]
extern crate std;
