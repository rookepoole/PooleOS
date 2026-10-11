#![no_std]

pub mod console;
pub mod protocol;
pub mod service;
pub mod startup;

#[cfg(all(target_arch = "x86_64", target_os = "none"))]
pub mod process;

#[cfg(test)]
extern crate std;
