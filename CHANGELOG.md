# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/).

## [0.1.0] - 2026-11-11

### Added
- `estimate`, `fit_size`, `fit`, `plan_slices`, `slice_image`, `report` and `measure` for offline image-token work.
- Model table (`data/models.json`) with Anthropic 28 px patches (standard/high), OpenAI 32 px patches and 512 px tiles, Gemini 2 tiles and Gemini 3 fixed `media_resolution` levels; every row carries `source_url`, `checked` and `confidence`.
- CLI: `models`, `estimate`, `fit`, `slice`, `report` (CI exit code with `--max-tokens`), `demo`.
- `report`/`estimate --strict`: exit 1 when a file could not be read as an image. Without it, skipped files are listed and the exit code stays 0.
- `--format json` for machine-readable output, and `--price MODEL=USD` (price per million tokens is your input; no prices are bundled) for a cost column.
- `build_report`: one row per image and model, and also lists skipped files (`ReportResult`). `report()`/`build_report()` accept a single path or model string as well as lists.
- English and Korean CLI output (`--lang`, `PIXELBUDGET_LANG`, locale variables), including error messages. Library exceptions keep their English text and carry `code`, `key` and `params`.
- Examples `examples/make_samples.py` and `examples/fit_and_slice.py` used by the README walkthrough.
