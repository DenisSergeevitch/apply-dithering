---
name: apply-dithering
description: Implement, tune, or debug dithering in 3D scenes and real-time games, especially one-bit or limited-palette rendering, Obra Dinn-style effects, swimming patterns, flicker, and mapping aliasing. Use when choosing threshold patterns, mapping spaces, render order, or motion-stability tradeoffs.
license: MIT
---

# apply dithering

Apply dithering as a rendering decision involving tone, sampling, and motion. A convincing still frame is insufficient evidence that the effect works in a game.

This skill is based on Lucas Pope's [November 23, 2017 TIGSource post](https://forums.tigsource.com/index.php?topic=40832.msg1363742#msg1363742), available in his [author-hosted mirror](https://dukope.com/devlogs/obra-dinn/tig-32/). Read [sources.md](references/sources.md) for the source's findings and the boundary between those findings and this skill's additional implementation guidance.

## Establish the rendering contract

Inspect the project's renderer, engine version, materials, post-processing graph, color management, and target platform. Use the existing integration point and engine conventions. Establish these choices from the request and project before adding controls:

- **Output:** strictly two palette entries, several discrete levels, or deliberately softened output. Two colored entries can represent a binary mask without being literal black and white.
- **Purpose:** visible stylization, subtle banding reduction, or stochastic coverage such as transparency/LOD. These need different pass placement and temporal treatment.
- **Sampling grid:** internal logical resolution, presentation scale, and whether the pattern should stay aligned to that grid as resolution changes.
- **Motion:** camera rotation, camera translation, moving/deforming objects, and any temporal reconstruction already in use.
- **Cost:** target frame time and whether extra threshold samples are affordable.

Infer routine choices from existing visuals; ask only when an unresolved choice changes the requested result. Preserve the intended look when fixing a defect.

## Choose the mapping for the actual motion

The central tradeoff is between clean screen-pixel correspondence and correspondence with the moving scene. Use this table to choose a baseline, then inspect it in motion:

| Need | Starting approach | Limit to account for |
| --- | --- | --- |
| Crisp, fixed raster pattern | Integer screen-space thresholds | Geometry moves through the stationary pattern |
| Crisp raster with better response to looking around | Screen pattern offset by camera rotation | Approximate; translation, roll, perspective edges, and moving objects remain problems |
| Fullscreen comfort during camera rotation | Camera-centered, world-oriented directional sphere mapping; supersample threshold decisions | Does not follow translation or object motion; mapping distortion and aliasing remain |
| Pattern attached to moving surfaces | Object/UV/rest-pose coordinates with a deliberate scale and LOD strategy | Perspective minification, seams, deformation, and scale variation require work |
| Stochastic coverage with temporal filtering | Suitable blue-noise sequence integrated with the existing reconstruction | History rejection, motion vectors, and disocclusion determine behavior |

A camera-centered sphere is an angular reference, not a surface attachment. Do not promise stable translation from a direction-only mapping. World-position mapping also does not follow an independently moving object; choose object coordinates when that is the goal.

Use Bayer when its repeating ordered structure serves the style. Use a properly distributed blue-noise threshold field when a less ordered texture is preferable. Changing the pattern alone does not solve an unsuitable mapping.

## Implement the threshold path

Read [mapping-and-shaders.md](references/mapping-and-shaders.md) when writing shaders or modifying the render graph. It provides a Bayer baseline, multi-level quantization, rotation-offset guidance, and the directional/supersampling recipe.

Keep these invariants explicit:

1. **Quantize the intended signal.** Resolve scene lighting and tone mapping as appropriate before stylized final-image quantization. Keep lighting and light averages in linear color; choose and document the artistic tone/coverage domain. Subtle storage anti-banding instead belongs immediately before the actual storage quantizer, in its domain.
2. **Use thresholds with a known distribution.** Normalize rank `r` from a tile of `N` ranks as `(r + 0.5) / N`; compare the tone against the threshold. Preserve exact black/white endpoints. Random brightness added after quantization is not a replacement.
3. **Index the right pixels.** For a screen-aligned effect, index integer logical-render pixels, including viewport origin where needed. An upscale, dynamic resolution, TAA jitter, or stereo viewport must not silently redefine the grid.
4. **Treat threshold maps as data.** Disable sRGB decoding and lossy compression that changes ranks. Use nearest/integer fetches for the baseline. Ordinary bilinear filtering or averaged mipmaps alter the distribution; point sampling alone does not cure projected-pattern aliasing.
5. **Preserve the output contract through presentation.** Later bloom, blending, TAA, filtered scaling, and UI composition can introduce colors outside a strict palette. Place those operations before the final quantizer, quantize again deliberately, or document the intended exception.
6. **Keep temporal changes deliberate.** A static stylistic pattern needs stable phase. Animate noise only when the temporal filter and the intended appearance justify it. For history-based methods, reset/reject history on invalid samples and camera cuts.

For a strict raster look, start with the screen-grid path and consider the rotation offset if camera rotation causes swimming. For angular fullscreen stabilization, evaluate sphere mapping with threshold-then-downsample. If strict binary output is required, apply the final binary decision after that average and check the resulting artifacts. Do not silently soften a requested two-color image.

## Diagnose before adding complexity

| Observed defect | Investigate first |
| --- | --- |
| Stationary frame crawls or sparkles | Frame-random phase, jittered coordinates, unstable lighting/exposure, compression |
| Pattern looks like a screen door during a pan | Screen mapping versus scene motion; assess rotation offset or directional mapping |
| Pattern distorts near edges or poles | Projection, angular density, mapping seams, wide FOV |
| Moire grows with distance | Minification and resampling; use a controlled footprint/LOD or threshold supersampling |
| Dark/bright patches at reprojected boundaries | Depth discontinuities, invalid history, broken threshold neighborhoods |
| Tone ramp has incorrect mean brightness | Threshold distribution, color-space conversion, tone curve, downsample domain |
| Colors escape a strict palette | Operations performed after the final palette decision |

Do not bake a binary pattern into ordinary textures as a universal fix for swimming. It trades one motion problem for perspective sampling problems unless the material system handles them.

## Verify the result the player sees

Use the engine's normal shader/build checks. Inspect the final presentation at target resolution, scaling, and fullscreen size, with the actual post stack enabled. A small diagnostic scene should include a smooth tone ramp, flat patches, a curved object, a floor viewed at a grazing angle, a depth edge, and a moving object.

Record or observe a stationary camera, slow yaw/pitch, strafing, forward movement, and independent object motion. For the chosen method, also check camera cuts, FOV changes, resolution changes, mapping boundaries, and temporal-history resets. Compare the source tone, threshold field, and final output when a defect is ambiguous.

Confirm endpoint values and intended palette membership; inspect tone coverage over complete tiles for a screen baseline. Measure GPU cost at the target settings when increasing samples. Evaluate swimming, flicker, readability, and comfort in motion rather than claiming that a still image proves stability. If runtime access is unavailable, state which visual/performance checks remain unverified.

Deliver the implementation or concrete corrections, the selected mapping and render order, observed validation, and remaining compromises. Describe rotational stability, translational stability, and moving-object stability separately.
