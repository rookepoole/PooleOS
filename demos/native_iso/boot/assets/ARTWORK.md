# PooleGlass Boot Artwork

Built-in image-generation tool, one initial generation and one refinement.
The selected image is `pooleglass-emblem.png`; the discarded chrome-heavy first
draft is not a boot asset. No third-party logo or award badge is included.
This is original project artwork, subject to owner visual and branding review.

Final refinement prompt:

> Refine this PooleOS emblem into truly transparent optical LIQUID GLASS, not metallic chrome. Keep the single central capital P and a fine circular rim, front-on centered balanced identity. Change the P to a simple modern rounded geometric sans-serif P with no serifs, no ornamental foot. Material: beautifully clear thick optical glass, visible graphite background through the broad interior of the P, softly rounded transparent bevels, only thin near-white highlights at the edges, restrained aqua refraction and a tiny blush reflection. The body must be translucent not dark metallic opaque. Reduce multiple ridges to one smooth liquid-glass surface. The rim should also be smooth clear glass without concentric chrome rings. High-end restrained OS industrial design. Make the image OPAQUE on one perfectly flat graphite background RGB 12,15,20, NOT transparent and NOT pure black; no texture, no gradients or particle artifacts outside the mark. Full logo fits with 12 percent empty margin on all sides. No typography, cards, progress bar, extra orbs, watermark or award badges. Square image.

The source image is retained unchanged. Host encoding reduces it to a 192x192
indexed texture with a 256-entry RGB palette. Runtime bilinear sampling and an
outer-margin blend avoid a rectangular boundary on the opaque boot background.
This is raster artwork, not a live refraction shader. The original high-resolution
image is not included on the ISO; the compact arrays are compiled into demo EFI.

The two typography masks contain only the fixed strings `PooleOS` and
`Native engineering preview`, rasterized from Bitstream Vera. `FONT-LICENSE.txt`
is included in the ISO license notice. No complete font is embedded in firmware.
`encoding.json` records the font input hash, Pillow version, source artwork hash,
and all compact payload identities. Encoding is a host build operation; the
UEFI loader contains no PNG parser, font parser, heap allocator, or external asset
file loading path for these assets.
