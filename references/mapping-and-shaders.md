# Mapping and shader implementation

Read the sections relevant to the chosen rendering path. These are original implementation examples and integration guidance, not recovered Obra Dinn source code. The reference article's exact spherical rings shader is not published in that post.

## 1. Screen-grid baseline

Start with a scalar tone/coverage value `v` in `[0,1]` and a threshold `t` strictly between 0 and 1. For binary output, use `v > t`. Apply the resulting mask to the dark/light palette entries. Both threshold data and `v` must use the intended numeric domain; do not let texture import conversions silently change either.

The following functions use GLSL ES 3.00 / GLSL 330 integer operations and can be adapted to HLSL or an engine shader graph. They are helpers, not a complete engine shader. Supply an integer pixel coordinate from the actual logical target.

```glsl
// Integer Bayer ranks for an 8x8 tile. Negative coordinates wrap too.
float bayer8Threshold(ivec2 pixel) {
    ivec2 p = ivec2((pixel.x % 8 + 8) % 8,
                   (pixel.y % 8 + 8) % 8);
    int rank = 0;
    for (int bit = 0; bit < 3; ++bit) {
        int x = (p.x >> bit) & 1;
        int y = (p.y >> bit) & 1;
        int digit = ((x ^ y) << 1) | y; // 2x2 order: 0,2 / 3,1
        rank |= digit << (2 * (2 - bit));
    }
    return (float(rank) + 0.5) / 64.0;
}

float binaryDither(float v, float t) {
    return clamp(v, 0.0, 1.0) > t ? 1.0 : 0.0;
}

// Require levels >= 2; this is an evenly spaced scalar ramp.
float quantizeDither(float v, float t, int levels) {
    float intervals = float(levels - 1);
    float x = clamp(v, 0.0, 1.0) * intervals;
    float upper = fract(x) > t ? 1.0 : 0.0;
    return (floor(x) + upper) / intervals;
}

// Example inside a fragment shader rendering at logical resolution:
// ivec2 pixel = ivec2(floor(gl_FragCoord.xy)) - viewportOrigin;
// float mask = binaryDither(tone, bayer8Threshold(pixel + phasePixels));
// vec3 result = mix(darkPalette, lightPalette, mask);
```

`phasePixels` is an integer offset. Choose a fixed coordinate origin and orientation; a mirrored Bayer tile is still a valid rank distribution. For a full 8x8 tile of constant input, expected light-pixel count is approximately `64*v`, rounded by the threshold decisions. `v=0` gives none and `v=1` gives all. Keep `levels` integral and at least 2. Arbitrary palettes need their own neighboring-color selection; per-channel RGB quantization can create unintended hues and colors outside that palette.

For a threshold texture, use integer fetches or sample its texel centers with point filtering and explicit wrapping. Import as linear scalar data with rank-preserving storage. A normalized byte channel containing ranks `0..255` is fetched as `r/255`; converting it to centered rank thresholds requires `(sample*255 + 0.5)/256`. Do not apply that conversion blindly to an asset already authored as normalized thresholds. Inspect its encoding and histogram first.

White noise and blue noise can share a histogram while distributing spatial error differently. A hash is not automatically blue noise. Preserve the supplied blue-noise asset's distribution and use a proven generator when producing one.

## 2. Tone and color management

Separate physical lighting, artistic tone shaping, and quantizer storage:

- Decode color inputs and perform lighting in linear light. For linear sRGB/Rec.709 primaries, luminance is `dot(rgb, vec3(0.2126, 0.7152, 0.0722))`. Other working primaries, such as ACEScg, need their matching coefficients or a color-space conversion first.
- If the target mean luminance is `Y`, and palette endpoints have linear luminances `Ydark < Ylight`, physical area coverage is `v = clamp((Y-Ydark)/(Ylight-Ydark), 0, 1)`. An artistic tone curve can intentionally choose a different coverage; make that choice visible in the implementation.
- After tone mapping, choose whether the effect's ramp is artistic display-referred tone or linear-light coverage. Never call these equivalent or apply an arbitrary gamma correction twice.
- Average light/color in linear light when downsampling. Averaging a binary scalar coverage mask also has a clear interpretation. Encode final color for the destination once; account for automatic sRGB render-target conversion.
- Subtle anti-banding for an 8-bit storage step differs from visible one-bit rendering. Its noise amplitude is tied to that quantizer's step (typically a fraction of one LSB) and its numeric domain; full-strength ordered posterization is inappropriate.

A linear half-coverage of black and white has a linear mean of 0.5. Encoding that mean to sRGB yields about 0.735. Averaging encoded black/white to 0.5 and then decoding yields only about 0.214 linear light. This distinction matters when deciding whether to downsample a mask or already encoded color.

## 3. Screen mapping offset by camera rotation

Pope's inexpensive approximation shifts the threshold grid by roughly one screen extent for one FOV of camera rotation:

```text
continuousOffset.x = logicalWidth  * unwrappedYaw   / horizontalFov
continuousOffset.y = logicalHeight * unwrappedPitch / verticalFov
phasePixels        = round(continuousOffset) modulo patternSize
```

Yaw/pitch here are relative to a chosen anchor, and FOV and angle use the same units. Derive signs from the renderer's handedness and texture origin: track a feature near screen center during a small turn and make the pattern move in the same direction. A guessed sign can double the apparent swimming.

Avoid Euler wrap jumps by maintaining continuous angles or accumulating shortest signed deltas. Recompute from the anchor when resolution or FOV changes rather than mixing old pixel-scale offsets with new ones. Keep integer phase for one-threshold-texel-per-logical-pixel correspondence. This will produce discrete phase steps; evaluate them in motion.

The formula is heuristic, not the exact perspective projection. It does not solve parallax, roll, wide-angle edge distortion, or object motion. Horizontal and vertical FOV differ for non-square targets. A more precise center derivative such as `width/(2*tan(horizontalFov/2))` may be useful for a particular camera, but it still cannot match the entire image with one global offset. Treat such tuning as an extension to the article.

## 4. Directional sphere mapping

This method uses world **direction**, excluding camera position:

1. Reconstruct a view ray for each output/subsample position using the engine's inverse projection. Respect its clip range, Y orientation, stereo eye, and reversed-Z conventions. For a stable angular reference, use an unjittered ray or compensate known temporal jitter explicitly.
2. Transform the ray by the camera-to-world **rotation**, then normalize. Do not rotate the pattern with the camera or add camera translation to the direction.
3. Map the world direction to a threshold field on a world-oriented sphere. The sphere conceptually follows the camera position, so this is rotational stabilization, not positional surface tracking.
4. Keep threshold neighborhoods and approximate angular dot size coherent across the sphere. Inspect poles, seams, horizon, and wide FOV. A cube representation additionally needs face-boundary/corner checks.

A generic longitude/latitude UV can prototype the idea, but it clusters samples near poles and is **not** Pope's tuned rings mapping. A custom ring construction can vary longitudinal sample count with latitude to improve density; transitions and seams still require design and measurement. The article provides qualitative constraints and images, not a portable exact mapping formula. Do not label an arbitrary equirectangular shader as an exact reproduction.

Choose angular dot density for the intended FOV and logical resolution; a single angular mapping cannot remain exactly one screen pixel everywhere. Changing FOV changes the projected size. Moving/deforming objects or translating past surfaces still change which scene samples meet which thresholds. For actual material attachment, use surface/object coordinates or a purpose-built surface-stable method with its own sampling strategy.

### Supersample the decisions, then resolve

For each logical output pixel, evaluate four subpixel positions in a 2x2 layout. Each sample needs both its corresponding scene tone and the threshold at its own reconstructed direction:

```text
for each of four subpixel centers:
    tone_i = scene tone at this subpixel
    t_i    = threshold mapped from its world direction
    bit_i  = (tone_i > t_i) ? 1 : 0
coverage = (bit_0 + bit_1 + bit_2 + bit_3) / 4
```

This is 2x per axis, or four threshold samples per logical pixel. It is not merely repeating the same threshold four times. Average **after** each threshold decision; filtering the threshold texture first is a different operation and does not preserve the same result. A full 2W-by-2H threshold target followed by a box resolve is another implementation. If scene tone comes from a lower-resolution target, acknowledge that interpolation does not recover missing scene detail; measure whether higher-resolution scene rendering is also needed.

- **Softened output:** apply `coverage` between palette endpoints in the chosen linear/coverage domain. Intermediate colors are intentional.
- **Strict two-color output:** convert the resolved coverage back to a binary mask, for example `coverage >= 0.5`. Specify the tie rule; this example chooses light at exactly one half. A dark-on-tie rule is also possible and changes coverage bias. Evaluate the loss of intermediate coverage and resulting aliasing.

Downsampling creates additional levels; it cannot simultaneously be described as softened and strictly binary. Subsequent bilinear upscaling or post-processing can break strict palette membership again. Four threshold samples add work; rendering the whole scene at four times the pixel count costs more than supersampling a cheap final pass. Measure the actual implementation.

## 5. Surface mapping and temporal alternatives

UV/object-space attachment can be appropriate for an intentionally printed texture or moving character. Use consistent texel density, a chosen deformation/rest-pose policy, and a footprint-aware treatment when dots become subpixel. Ordinary mipmaps average thresholds toward a constant and destroy their ordered distribution. Do not present point sampling as a complete minification solution.

Reprojection requires valid motion information, depth/normal checks as appropriate, disocclusion handling, and reset behavior. Independently moving/deforming objects need their own motion vectors. Reprojecting unrelated threshold pixels can break local pattern neighborhoods and create seams even when individual samples follow motion.

Spatiotemporal blue noise is an optional modern approach for stochastic estimators accumulated over time; see [sources.md](sources.md). It is not a universal substitute for a stable visible pattern. Validate stationary accumulation, motion, disocclusion, and camera cuts. If the requested image must stay binary, a temporal average must precede its last binary/palette decision or be an explicitly accepted output compromise.
