#![no_std]
#![forbid(unsafe_code)]

// The demo replaces only the pure pixel function. Production boot logic is reused.
pub use pooleboot_base::*;

const EMBLEM: &[u8; 36_864] = include_bytes!("../assets/emblem.index8");
const PALETTE: &[u8; 768] = include_bytes!("../assets/emblem.rgb");
const TITLE: &[u8; 4_608] = include_bytes!("../assets/title.alpha4");
const CAPTION: &[u8; 2_240] = include_bytes!("../assets/caption.alpha4");
pub const BACKGROUND: Rgb = Rgb { red: 12, green: 15, blue: 20 };

fn blend(a: Rgb, b: Rgb, weight: u32) -> Rgb {
    let channel = |a: u8, b: u8| ((u32::from(a) * (256 - weight) + u32::from(b) * weight + 128) >> 8) as u8;
    Rgb { red: channel(a.red, b.red), green: channel(a.green, b.green), blue: channel(a.blue, b.blue) }
}

fn emblem(x: usize, y: usize) -> Rgb {
    let index = usize::from(EMBLEM[y * 192 + x]) * 3;
    Rgb { red: PALETTE[index], green: PALETTE[index + 1], blue: PALETTE[index + 2] }
}

fn texture(x: usize, y: usize, size: usize) -> Rgb {
    let fx = x * 191 * 256 / size.saturating_sub(1).max(1);
    let fy = y * 191 * 256 / size.saturating_sub(1).max(1);
    let ix = fx >> 8;
    let iy = fy >> 8;
    let right = (ix + 1).min(191);
    let below = (iy + 1).min(191);
    let top = blend(emblem(ix, iy), emblem(right, iy), (fx & 255) as u32);
    let bottom = blend(emblem(ix, below), emblem(right, below), (fx & 255) as u32);
    let pixel = blend(top, bottom, (fy & 255) as u32);
    // Fade only the empty outer margin into the opaque compositor background.
    let edge = x.min(y).min(size - 1 - x).min(size - 1 - y);
    blend(BACKGROUND, pixel, (edge * 256 / (size / 12).max(1)).min(256) as u32)
}

fn text_pixel(mask: &[u8], x: usize, y: usize, w: usize, color: Rgb) -> Rgb {
    let offset = y * w + x;
    let byte = mask[offset / 2];
    let alpha = if offset & 1 == 0 { byte >> 4 } else { byte & 15 };
    blend(BACKGROUND, color, u32::from(alpha) * 256 / 15)
}

pub fn identity_rgb(x: usize, y: usize, width: usize, height: usize) -> Rgb {
    if !(320..=16_384).contains(&width) || !(200..=16_384).contains(&height) || x >= width || y >= height {
        return BACKGROUND;
    }
    let large = width >= 800 && height >= 600;
    let (size, title_w, title_h, gap) = if large { (320, 256, 64, 12) } else { (96, 192, 48, 6) };
    let total = size + gap + title_h + gap + 20;
    let top = (height - total) / 2;
    let left = (width - size) / 2;
    if x >= left && x < left + size && y >= top && y < top + size {
        return texture(x - left, y - top, size);
    }
    let title_top = top + size + gap;
    let title_left = (width - title_w) / 2;
    if x >= title_left && x < title_left + title_w && y >= title_top && y < title_top + title_h {
        return text_pixel(TITLE, (x - title_left) * 192 / title_w, (y - title_top) * 48 / title_h, 192,
                          Rgb { red: 238, green: 242, blue: 245 });
    }
    let caption_top = title_top + title_h + gap;
    let caption_left = (width - 224) / 2;
    if x >= caption_left && x < caption_left + 224 && y >= caption_top && y < caption_top + 20 {
        return text_pixel(CAPTION, x - caption_left, y - caption_top, 224,
                          Rgb { red: 164, green: 177, blue: 189 });
    }
    BACKGROUND
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn bounds_fail_closed_without_overflow() {
        for (x, y, w, h) in [(0, 0, 0, 0), (0, 0, 319, 200), (320, 0, 320, 200),
                             (0, 200, 320, 200), (usize::MAX, usize::MAX, usize::MAX, usize::MAX)] {
            assert_eq!(identity_rgb(x, y, w, h), BACKGROUND);
        }
    }

    #[test]
    fn viewports_have_content_and_clear_margins() {
        for (w, h) in [(320, 200), (640, 480), (800, 600), (1280, 800), (1920, 1080), (3440, 1440)] {
            let mut visible = 0;
            for y in 0..h {
                for x in 0..w {
                    let pixel = identity_rgb(x, y, w, h);
                    if pixel != BACKGROUND { visible += 1; }
                    if x < 8 || y < 8 || x >= w - 8 || y >= h - 8 { assert_eq!(pixel, BACKGROUND); }
                }
            }
            assert!(visible > 3_000 && visible < w * h / 2);
        }
    }

    #[test]
    fn rgb_and_bgr_pack_equivalent_channels() {
        for y in 0..200 {
            for x in 0..320 {
                let color = identity_rgb(x, y, 320, 200);
                let rgb = pack_pixel(color, PixelFormat::Rgb);
                let bgr = pack_pixel(color, PixelFormat::Bgr);
                assert_eq!(rgb & 0xff00, bgr & 0xff00);
                assert_eq!(rgb & 255, (bgr >> 16) & 255);
                assert_eq!((rgb >> 16) & 255, bgr & 255);
                assert_eq!(rgb >> 24, 0);
            }
        }
    }

    #[test]
    fn texture_edge_is_opaque_background() {
        for i in 0..320 {
            assert_eq!(texture(i, 0, 320), BACKGROUND);
            assert_eq!(texture(319, i, 320), BACKGROUND);
        }
    }
}
