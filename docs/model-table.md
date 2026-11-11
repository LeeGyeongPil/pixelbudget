# Model table

`src/pixelbudget/data/models.json` is the single source of truth. Every row has `source_url`,
`checked` (YYYY-MM-DD) and `confidence` (`documented` / `measured` / `approx`); the table is
validated when it is loaded. All rows were last checked on **2026-11-11**.

Run `pixelbudget models` (or `--format json`) to print it.

## Methods

| Method | Providers | Formula |
|---|---|---|
| `patch` (28 px) | Anthropic (`claude-standard`, `claude-high`) | tokens = `ceil(w/28) * ceil(h/28)` after the server resize. Standard tier: long edge <= 1568 px and <= 1568 tokens; high tier: 2576 px and 4784 tokens. |
| `patch` (32 px) | OpenAI (`gpt-5.5`, `gpt-5.4`, `gpt-5.2`, `gpt-4.1-mini`) | shrink to the detail's max edge, count 32 px patches, shrink again if over the patch budget, multiply (1.2 or 1.62) and round up. |
| `tile` | OpenAI (`gpt-5.1`, `gpt-5`, `gpt-4.1`, `gpt-4o`, `gpt-4o-mini`, `o1`, `o1-pro`, `o3`), Gemini 2 | OpenAI: fit in 2048 px, short side to 768 px, `base + tile_tokens * tiles(512 px)`; `detail=low` is the base cost only. Gemini 2: both edges <= 384 px is 258 tokens, otherwise 258 per 768 px tile. |
| `fixed` | Gemini 3 (alias `gemini-4`) | tokens depend only on `media_resolution`: low 280, medium 560, high 1120, ultra_high 2240. |

## Known documentation mismatches and approximations

These are surfaced as warning codes, never hidden.

1. **`docs_table_mismatch` - Claude standard, 2000x1500.** The docs table lists 1269x952, but the
   reference code printed on the same docs site returns 1270x952. Both give 1564 tokens.
   pixelbudget follows the reference code (1270x952) and attaches the warning when it sees this size.
2. **`approx_rounding` - OpenAI patch models over the patch budget.** The docs say the image is
   scaled down proportionally, rounded down and recomputed, but not the exact rounding. Any
   estimate that needed a shrink (for example 2048x2048 on `gpt-5.5` with `detail=high`, 4096 patches
   against a 2500-patch budget) is reported with `confidence="approx"`. Images within the budget
   (1920x1080 is 2040 patches) are `documented`.
3. **`approx_rule` - Gemini 2.** The AI Studio docs and the Vertex docs describe the rule differently,
   and forum reports show `count_tokens` and billed usage differing a lot. Treat it as a rough number.
4. **`fixed_per_image` - Gemini 3+.** Not a mismatch, but resizing does not reduce tokens and slicing
   multiplies them; `fit` and `slice` say so.

## Updating a row

1. Open the provider's docs, copy the numbers into `models.json`, set `source_url`, `checked` and `confidence`.
2. Add the example values from the docs to `tests/fixtures/doc_examples.json` (with their URL) so the next change is caught.
3. If the docs contradict their own examples, keep the reference code's value, add a `known_mismatches` entry and describe it here.
