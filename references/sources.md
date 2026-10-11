# Sources and attribution

## Requested article

**Lucas Pope (dukope), “Fullscreen, Round 3,” November 23, 2017, Return of the Obra Dinn development log, TIGSource post #767.**

- [Original post, message 1363742](https://forums.tigsource.com/index.php?topic=40832.msg1363742#msg1363742)
- [Author-hosted mirror, November 2017](https://dukope.com/devlogs/obra-dinn/tig-32/)

The mirror includes the post and subsequent replies. Its quoted link to Pope's post points to the exact requested message. Use Pope's post as the primary evidence; suggestions in replies are not his tested conclusions.

### Findings used from the article

Pope compares grayscale output against tiled thresholds, using 8x8 Bayer and 128x128 blue noise. Screen mapping is clean but swims during motion. Texture attachment improves correspondence while introducing perspective aliasing. Motion warping breaks threshold neighborhoods. A camera-rotation screen offset is an inexpensive approximation. World-oriented cube/sphere mapping centered on the camera stabilizes rotation, not translation. His tuned spherical rings still need alias control: threshold at twice the resolution per axis, then box-downsample. The average introduces intermediate values; a final half-value threshold can restore binary output. He describes separate crisp and softened presentation modes.

### Implementation boundary

The post does not supply its exact spherical rings shader. This skill's Bayer helper, normalized rank convention, multi-level formula, color-space guidance, engine integration, and validation workflow are additional engineering guidance. They are not claims about Obra Dinn's undisclosed implementation. Its camera and scene assumptions must be re-evaluated for other games.

No forum text, screenshots, GIFs, threshold assets, or original game code are bundled. The repository's MIT license covers its original skill material and examples; the linked article and third-party material retain their respective ownership and licenses.

## Supplementary primary sources

Read these when the corresponding implementation needs more depth:

- **NVIDIA, [Rendering in Real Time with Spatiotemporal Blue Noise Textures, Part 1](https://developer.nvidia.com/blog/rendering-in-real-time-with-spatiotemporal-blue-noise-textures-part-1/), and [research publication](https://research.nvidia.com/publication/2022-07_spatiotemporal-blue-noise-masks).** Relevant to stochastic samples reconstructed over time, nearest-neighbor tiled sampling, and the limitations introduced by motion. This is later research, not a technique specified by Pope's 2017 post.
- **Larry Gritz and Eugene d'Eon, [GPU Gems 3, Chapter 24: The Importance of Being Linear](https://developer.nvidia.com/gpugems/gpugems3/part-iv-image-effects/chapter-24-importance-being-linear).** Relevant to decoding color, linear-light operations, filtering, and correct output encoding.
- **Unity, [TextureImporter.sRGBTexture](https://docs.unity.com/en-us/engine/6000.0/script-reference/unityeditor/textureimporter/srgbtexture).** Documents disabling sRGB conversion for non-color texture data; apply the equivalent option in the project's actual engine/version.
- **Rune Skovbo Johansen, [Dither3D](https://github.com/runevision/Dither3D).** An optional later implementation for surface-stable, adaptive-density dithering. It is separate from Pope's method. Its MPL-2.0 code is not included here; check the upstream license before reuse.
