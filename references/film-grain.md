# Film grain: asking, preserving, and the one place it is allowed to be invented

Grain is where "era-appropriate" and "invent nothing" pull against each other. This
reference draws the line and gives the questions that put the decision in the
owner's hands instead of the model's.

## Where grain comes from

Grain is in the negative: silver halide crystals in the emulsion, which in
C-41 colour negative become dye clouds after development, clustered in the shape
the crystals left. A print shows that same grain because the negative is
projected onto the paper. Nothing new is created. The print enlarges the grain by its
magnification.

A 35mm frame is 24×36mm. A 4×6 print is roughly 100×150mm, so the grain lands
about 4× larger on paper than it sat on the negative. A 645 negative at the same
print size is enlarged less, which is why medium format looks finer. Same grain,
different magnification.

What a print genuinely adds is separate from grain:

| Added | Character |
| --- | --- |
| Paper surface | High frequency and regular. RC paper has a pebble surface, and fibre paper has a tooth |
| Paper emulsion grain | Real but minor. Dominates only in contact prints |
| Print/process noise | Dust, handling, the optical printer's own variation |

So paper texture and grain live at different frequencies. A 2× upscale that
amplifies both makes paper look like noise. Keep them apart.

This matters for the skill because the era predicts grain size well enough to
check the file, which is the honest use of "era-appropriate." It is a
diagnostic, not a licence.

## Ask before restoring

Ask these when the source is film or plausibly film. Skip what the file already
answers.

1. What era, and do you know the stock or ISO? A stock name settles the
   expected grain character. A year narrows it.
2. Film or digital capture? If digital, no grain is added unless explicitly
   requested. Do not default to grain on a digital photo.
3. Is this a scan of a print, a scan of the negative, or a photo of a photo?
   Print scans carry paper texture. Re-photographed prints add a second
   generation and the copying camera's noise.
4. Is grain visible in the file, or was it removed? Look before asking. If it
   is plainly visible, say so and ask only about intent.
5. What do you want done with it? Preserve exactly / recover what is
   attenuated / reconstruct to the stock's character / clean up.
6. Was this retouched? Studio portraits were spotted and skin-softened in
   1997 as now. Retouched areas legitimately have no grain, and adding grain
   back over them is wrong.

Question 4 is the one that decides the job. Do not skip it in favour of question 1.

## The boundary

| Situation | Allowed | Recorded as |
| --- | --- | --- |
| Grain visible and intact | Preserve. Denoise gently, before the upscale. | `grain: preserved` |
| Grain attenuated but still present in flat areas | Recover from the source's own flat regions. Sample what is there. | `grain: recovered` |
| Grain absent everywhere | Only on explicit request, matched to the stock's character, and disclosed. | `grain: reconstructed` |
| Digital capture, no grain | Leave it alone. | `grain: none` |

Synthesizing grain into a grainless file is invention. It invents texture rather than
of faces. It is permitted only when asked for, only matched to what the stock
actually did, and only when the delivery says so. Recovering grain that is
merely attenuated stays on the evidence side of the line. That distinction is the
whole difference between restoring and decorating.

The finalize step enforces the disclosure: `--grain reconstructed` puts the fact
into the provenance sentence automatically, so it cannot be quietly omitted.

## Stock character, for recognition

Use this to recognise what you are looking at and to detect absence. Do not use
it as a synthesis recipe for a file whose grain is gone without saying so.

| Stock | Character |
| --- | --- |
| Kodak Tri-X 400 | Coarse, prominent, classic clumping. Chunky when pushed. |
| Ilford HP5 400 | Coarse, slightly softer than Tri-X. |
| Kodak T-Max 400 | Finer than Tri-X. Tabular grain, smoother clumps. |
| Plus-X 125 / FP4 125 / T-Max 100 | Moderate to very fine. |
| Kodachrome 25/64 | Extremely fine, high contrast, distinctive dye structure. |
| Ektachrome 100 / Provia 100F | Fine. |
| Velvia 50 | Very fine, saturated, high contrast. |
| Kodak Gold 100/200/400 | Soft warm clumping. The 400 shows moderate chroma grain. |
| Kodak Royal Gold | Finer than Gold. |
| Kodak Vericolor III / VPS (portrait) | Smooth, low contrast, fine-moderate. |
| Fujicolor Superia 200/400/800 | Visible grain with green/magenta chroma noise. Punchier. |
| Fuji NPS/NPH (portrait) | Fine, neutral. |
| Reala 100 | Fine, four-layer colour. |

Era caveat: grain got finer over the decades. Tabular-grain stocks arrived in the
late 1980s, and several names above date from the late 1990s, so a given year can
predate a stock. When the stock is unknown, infer from the grain visible in the
file rather than from the year alone.

## Grain scale is pixel-relative

This is the part that gets missed.

A faithful 2× upscale doubles grain size in pixels, and that result is correct. The
same grain now covers more pixels. What usually happens instead is the
super-resolution pass averages grain into blotches in flat areas and leaves
crunchy artefacts at edges. So "grain preserved" and "upscaled 2×" quietly
conflict, and the claim needs checking rather than assuming.

Measure a flat region before and after. Use the sky, a wall, or an out-of-focus background:

| Observation | Conclusion |
| --- | --- |
| Clump diameter approximately `source × scale` | Preserved. Good. |
| Flat, smooth, no texture | Grain was destroyed. Report it. |
| Uniform tiny texture, identical everywhere | Synthetic texture was substituted by the upscaler. |
| Crunchy noise concentrated at edges | Over-sharpening, not grain. |

When flat regions have lost texture but the source still shows grain in its own
flat areas, re-inject grain sampled from the source at the output's scale.
That keeps it evidence-based and avoids borrowing a stranger's grain.

## Ordering rules

1. Denoise before upscaling, never after. Denoising an upscaled image removes
   the amplified grain and leaves the invented detail, which is backwards.
2. Never sharpen grain. Sharpening amplifies clumps into crunchy artefacts
   that read as digital noise and are the single most common "enhanced" tell.
3. Chroma first. Colour negative grain is predominantly chroma, because it is
   dye clouds. Heavy chroma denoise removes grain while luminance texture looks
   untouched. A file whose colour is suspiciously smooth but whose
   luminance is intact has had a chroma pass, and the grain is partially gone.
4. Keep paper texture separate on a print scan. Different frequency,
   different fix.
5. Retouched areas have no grain by design. Do not even them out.

## Worked example: a 1997 high school graduation photo

Two likely origins, with different grain:

- Family snapshot. Consumer colour negative, Kodak Gold 400 or Fuji Superia
  400. Moderate, soft, slightly chromatic clumping.
- Studio portrait package. Usually 645 on Vericolor/VPS or Fuji NPS. Finer
  grain, flatter contrast, and visible retouching. The studio removed spots and
  softened.

What follows:

- Coarse monochrome grain would be wrong here. Nobody shot 1997 graduations on
  Tri-X unless the yearbook staff was being artsy.
- A file that is uniformly smooth is not evidence of a fine-grain stock.
  consumer film in 1997 was not that clean. It is evidence of a denoise pass or
  a heavy scan, and the year is what makes that inference safe.
- If grain looks mechanically regular rather than randomly clumped,
  photofinishing was already going hybrid by then and this can be a digital
  print showing printer dither, not optical grain. Different texture, different
  fix.

The check is the same in every case: look at a flat region at 100%, decide
whether texture is present, and let that decide the branch. Do not decide from the year.
