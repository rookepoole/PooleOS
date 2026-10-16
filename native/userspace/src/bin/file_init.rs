#![no_std]
#![no_main]
use poole_userspace::{
    files::{self, Frame, rpc::Client},
    process, startup,
};
poole_userspace::entry!(main);
extern "C" fn main(address: u64, bytes: u64, version: u64) -> ! {
    // SAFETY: the owned PSTART1 launcher supplies this live startup stack block.
    let block =
        unsafe { process::file_block(address, bytes) }.unwrap_or_else(|_| process::exit(193));
    let (endpoint, peer) =
        startup::file_init(block, version).unwrap_or_else(|_| process::exit(193));
    let mut client = Client::new(endpoint, peer, process::ConsoleCalls);
    let mut request = Frame::empty(files::READ, 1, 0);
    request.len = 12;
    request.data[..12].copy_from_slice(b"/version.txt");
    loop {
        while !client
            .start(&request)
            .unwrap_or_else(|_| process::exit(194))
        {}
        let reply = loop {
            if let Some(reply) = client.finish().unwrap_or_else(|_| process::exit(194)) {
                break reply;
            }
        };
        if reply.status != files::OK
            || reply.total != files::VERSION.len() as u32
            || !reply
                .payload()
                .is_some_and(|data| files::same_bytes(data, files::VERSION))
        {
            process::exit(195);
        }
        request.sequence = request
            .sequence
            .checked_add(1)
            .filter(|&n| n < u64::MAX)
            .unwrap_or_else(|| process::exit(195));
    }
}
#[panic_handler]
fn panic(_: &core::panic::PanicInfo<'_>) -> ! {
    process::exit(196)
}
