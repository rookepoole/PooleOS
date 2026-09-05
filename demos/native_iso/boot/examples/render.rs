use std::io::{self, Write};

fn main() {
    let args: Vec<_> = std::env::args().collect();
    assert_eq!(args.len(), 3, "render WIDTH HEIGHT > frame.ppm");
    let width: usize = args[1].parse().unwrap();
    let height: usize = args[2].parse().unwrap();
    assert!((320..=3840).contains(&width) && (200..=2160).contains(&height));
    let mut out = io::BufWriter::new(io::stdout().lock());
    write!(out, "P6\n{width} {height}\n255\n").unwrap();
    for y in 0..height {
        for x in 0..width {
            let p = pooleboot::identity_rgb(x, y, width, height);
            out.write_all(&[p.red, p.green, p.blue]).unwrap();
        }
    }
}
