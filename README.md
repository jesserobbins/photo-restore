# Photo Upscale & Enhance — Fidelity First

A reusable Agent Skills-compatible photo restoration workflow focused on **subject fidelity** rather than generative prettification.

- `SKILL.md`: skill metadata, non-negotiable fidelity constraints, restoration workflow, and validation rules.
- `references/prompt-templates.md`: prompts for normal images, same-person face references, archival scans, and group portraits.
- `references/qa-checklist.md`: acceptance criteria for faces, expressions, bodies, geometry, and visual quality.
- `scripts/compare.py`: optional side-by-side visual QA sheet; needs Pillow (`python -m pip install Pillow`).

## Use in an Agent Skills-compatible environment

Place the `photo-upscale-enhance` folder under the agent's supported skill directory (for example a Codex project's `.agents/skills/` directory), then invoke it by name or describe the task. Keep the folder name identical to the frontmatter `name`.

For a ChatGPT Project where direct skill installation is not supported, paste the content of `SKILL.md` into the Project's instructions/knowledge, or upload the package as project reference material. This zip by itself does **not** silently install the skill in the current chat.

The skill is a **tool-agnostic workflow**: it does not bundle an image upscaler, face model, or weights. It instructs any available image editing or non-generative image processing tools to produce fidelity-first results. It cannot recover information that was not recorded in the original photograph.

## Quick QA

```bash
python -m pip install Pillow
python scripts/compare.py original.jpg restored.png --out comparison.png
python scripts/compare.py original.jpg restored.png --out face-check.png --crop 120,100,300,330
```

The `--crop` coordinates refer to the original image (not the upscaled image). The comparison is for inspection, not a certified verification of identity.
