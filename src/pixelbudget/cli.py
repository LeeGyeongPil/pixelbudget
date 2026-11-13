"""Command line interface (argparse). All user-facing text comes from ``locales/*.json``."""

from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from functools import partial
from pathlib import Path
from typing import Sequence

from PIL import Image

from . import __version__
from .errors import PixelBudgetError
from .fit import fit, fit_size
from .i18n import LANGS, resolve_lang, t
from .measure import measure
from .registry import get_model, list_models, set_models_file
from .report import build_report, size_rows
from .types import ReportResult
from .slicing import plan_slices, slice_image


def _width(text: str) -> int:
    """Terminal display width: East Asian wide/fullwidth characters (Hangul, CJK) take two columns."""
    return sum(2 if unicodedata.east_asian_width(c) in ("W", "F") else 1 for c in text)


def _pad(text: str, width: int) -> str:
    return text + " " * (width - _width(text))


def _table(headers: list[str], rows: list[list[str]]) -> str:
    widths = [max(_width(h), *(_width(r[i]) for r in rows)) if rows else _width(h) for i, h in enumerate(headers)]
    line = lambda cells: "  ".join(_pad(c, w) for c, w in zip(cells, widths)).rstrip()  # noqa: E731
    return "\n".join([line(headers), line(["-" * w for w in widths]), *(line(r) for r in rows)])


class _Parser(argparse.ArgumentParser):
    """ArgumentParser whose usage prefix, section titles and usage errors follow ``--lang``."""

    def __init__(self, *args, lang: str = "en", **kwargs):
        self._lang = lang
        super().__init__(*args, add_help=False, **kwargs)
        self._positionals.title = t(lang, "argparse.positional")
        self._optionals.title = t(lang, "argparse.options")
        self.add_argument("-h", "--help", action="help", help=t(lang, "help.help"))

    def _get_formatter(self, *args, **kwargs):
        formatter = super()._get_formatter(*args, **kwargs)
        original = formatter.add_usage
        prefix = t(self._lang, "argparse.usage")

        def add_usage(usage, actions, groups, prefix_arg=None):  # noqa: ARG001
            return original(usage, actions, groups, prefix)

        formatter.add_usage = add_usage
        return formatter

    def error(self, message: str):
        self.print_usage(sys.stderr)
        self.exit(2, f"{self.prog}: {t(self._lang, 'argparse.error')}: {_translate_argparse_error(self._lang, message)}\n")


_ERROR_PATTERNS = (
    (re.compile(r"the following arguments are required: (.*)$"), "argparse.err.required"),
    (re.compile(r"argument (.+?): invalid choice: (.+?) \(choose from (.*)\)$"), "argparse.err.choice"),
    (re.compile(r"argument (.+?): expected one argument$"), "argparse.err.one_arg"),
    (re.compile(r"argument (.+?): invalid (\w+) value: (.*)$"), "argparse.err.value"),
    (re.compile(r"unrecognized arguments: (.*)$"), "argparse.err.unrecognized"),
    (re.compile(r"ambiguous option: (.+?) could match (.*)$"), "argparse.err.ambiguous"),
)


def _translate_argparse_error(lang: str, message: str) -> str:
    if lang == "en":
        return message
    for pattern, key in _ERROR_PATTERNS:
        m = pattern.search(message)
        if m:
            return t(lang, key, **{f"a{i}": g for i, g in enumerate(m.groups(), 1)})
    return message


def _yn(lang: str, value: bool) -> str:
    return t(lang, "yes" if value else "no")


def _size(s: tuple[int, int]) -> str:
    return f"{s[0]}x{s[1]}"


def _print_warnings(lang: str, codes: Sequence[str], out) -> None:
    uniq = list(dict.fromkeys(codes))
    if uniq:
        print(t(lang, "warnings.title"), file=out)
        for code in uniq:
            print(f"  - [{code}] {t(lang, 'warn.' + code)}", file=out)


def _build_parser(lang: str) -> argparse.ArgumentParser:
    p = _Parser(prog="pixelbudget", description=t(lang, "app.description"), lang=lang)
    p.add_argument("--lang", choices=LANGS, help=t(lang, "help.lang"))
    p.add_argument("--models-file", metavar="PATH", help=t(lang, "help.models_file"))
    p.add_argument("--version", action="version", version=f"pixelbudget {__version__}", help=t(lang, "help.version"))
    sub = p.add_subparsers(dest="command", required=True, metavar="{models,estimate,fit,slice,report,demo}",
                           parser_class=partial(_Parser, lang=lang))

    def add(name: str) -> argparse.ArgumentParser:
        return sub.add_parser(name, help=t(lang, f"help.{name}"), description=t(lang, f"help.{name}"))

    m = add("models")
    m.add_argument("--format", choices=("table", "json"), default="table", help=t(lang, "help.format"))

    def multi(sp: argparse.ArgumentParser) -> None:
        sp.add_argument("paths", nargs="+", metavar="PATH", help=t(lang, "help.paths_size" if sp.prog.endswith("estimate") else "help.paths"))
        sp.add_argument("--model", action="append", help=t(lang, "help.model"))
        sp.add_argument("--detail", help=t(lang, "help.detail"))
        sp.add_argument("--format", choices=("table", "json"), default="table", help=t(lang, "help.format"))
        sp.add_argument("--strict", action="store_true", help=t(lang, "help.strict"))

    e = add("estimate")
    multi(e)
    r = add("report")
    multi(r)
    r.add_argument("--max-tokens", type=int, help=t(lang, "help.max_tokens"))
    r.add_argument("--price", action="append", metavar="MODEL=USD", help=t(lang, "help.price"))

    f = add("fit")
    f.add_argument("path", metavar="PATH", help=t(lang, "help.path"))
    f.add_argument("--model", required=True, help=t(lang, "help.model_one"))
    f.add_argument("--budget", type=int, help=t(lang, "help.budget"))
    f.add_argument("--detail", help=t(lang, "help.detail"))
    f.add_argument("--out", help=t(lang, "help.out"))
    f.add_argument("--max-pixels", type=int, help=t(lang, "help.max_pixels"))

    s = add("slice")
    s.add_argument("path", metavar="PATH", help=t(lang, "help.path"))
    s.add_argument("--model", required=True, help=t(lang, "help.model_one"))
    s.add_argument("--overlap", type=int, default=64, help=t(lang, "help.overlap"))
    s.add_argument("--detail", help=t(lang, "help.detail"))
    s.add_argument("--out-dir", help=t(lang, "help.out_dir"))
    s.add_argument("--dry-run", action="store_true", help=t(lang, "help.dry_run"))
    s.add_argument("--max-pixels", type=int, help=t(lang, "help.max_pixels"))

    d = add("demo")
    d.add_argument("--out", default="pixelbudget-demo", help=t(lang, "help.demo_out"))
    d.add_argument("--model", default="claude-standard", help=t(lang, "help.model_one"))
    return p


def _parse_prices(items: list[str] | None) -> dict[str, float]:
    prices: dict[str, float] = {}
    for item in items or []:
        name, sep, value = item.partition("=")
        if not sep:
            raise PixelBudgetError(key="price_format", item=item)
        try:
            prices[name] = float(value)
        except ValueError:
            raise PixelBudgetError(key="price_number", item=item) from None
    return prices


def _check_save_path(path: Path) -> None:
    """Fail before decoding when Pillow cannot pick a format from the output extension."""
    ext = path.suffix.lower()
    if ext not in Image.registered_extensions():
        raise PixelBudgetError(key="unknown_extension", path=path.as_posix(), ext=path.suffix)


# OSError 종류별 메시지 키. 영어 템플릿은 파이썬 기본 형식("[Errno 2] ...")과 같아 영어 출력은 그대로다.
_OS_ERROR_KEYS = (
    (FileNotFoundError, "os.not_found"),
    (IsADirectoryError, "os.is_directory"),
    (NotADirectoryError, "os.not_directory"),
    (FileExistsError, "os.exists"),
    (PermissionError, "os.permission"),
)


def _error_text(lang: str, exc: Exception) -> str:
    """User-facing text of an error in ``lang`` (library errors and file system errors)."""
    if isinstance(exc, PixelBudgetError):
        return exc.render(lang)  # 코드+인자로 언어별 템플릿을 채운다
    if isinstance(exc, OSError) and exc.errno is not None and exc.filename is not None:
        key = next((k for cls, k in _OS_ERROR_KEYS if isinstance(exc, cls)), "os.other")
        return t(lang, key, errno=exc.errno, reason=exc.strerror, path=exc.filename)
    return str(exc)  # 형식을 알 수 없는 오류는 원문 그대로(영어일 수 있음)


def _cmd_models(args, lang, out) -> int:
    specs = list_models()
    if args.format == "json":
        json.dump([s.as_dict() for s in specs], out, indent=2, ensure_ascii=False)
        print(file=out)
        return 0
    headers = [t(lang, k) for k in ("col.model", "col.provider", "col.method", "col.confidence", "col.checked", "col.source", "col.origin")]
    rows = [[s.name, s.provider, s.method, s.confidence, s.checked, s.source_url, s.origin] for s in specs]
    print(_table(headers, rows), file=out)
    return 0


# estimate 전용: 같은 이름의 파일·폴더가 없고 WxH 모양이면 이미지 없이 크기로 계산한다(파일 우선).
_SIZE_RE = re.compile(r"^\d+[xX]\d+$")


def _is_size_arg(arg: str) -> bool:
    return bool(_SIZE_RE.match(arg)) and not Path(arg).exists()


def _estimate_mixed(args, models: list[str]) -> ReportResult:
    """Handle estimate inputs one by one, in order: real paths via build_report, WxH via size_rows."""
    rows: list = []
    skipped: list[str] = []
    for arg in args.paths:
        if _is_size_arg(arg):
            w, h = (int(n) for n in arg.lower().split("x"))
            rows.extend(size_rows(arg, (w, h), models, detail=args.detail))
        else:
            part = build_report([arg], models, detail=args.detail)
            rows.extend(part.rows)
            skipped.extend(part.skipped)
    return ReportResult(rows=tuple(rows), skipped=tuple(skipped))


def _cmd_report(args, lang, out, with_budget: bool) -> int:
    models = args.model or ["claude-standard"]
    max_tokens = getattr(args, "max_tokens", None) if with_budget else None
    prices = _parse_prices(getattr(args, "price", None)) if with_budget else {}
    if with_budget or not any(_is_size_arg(a) for a in args.paths):
        result = build_report(args.paths, models, detail=args.detail, max_tokens=max_tokens, prices=prices)
    else:
        result = _estimate_mixed(args, models)
    over = sum(1 for r in result.rows if r.over_budget)
    failed = bool(over or (args.strict and result.skipped))  # --strict: unreadable files fail the run too
    if args.format == "json":
        payload = {"rows": [r.as_dict() for r in result.rows], "skipped": list(result.skipped),
                   "summary": {"rows": len(result.rows), "over_budget": over, "skipped": len(result.skipped)}}
        json.dump(payload, out, indent=2, ensure_ascii=False)
        print(file=out)
        return 1 if failed else 0
    headers = [t(lang, k) for k in ("col.path", "col.model", "col.original", "col.sent", "col.tokens", "col.downscaled", "col.wasted")]
    if with_budget and max_tokens is not None:
        headers.append(t(lang, "col.over"))
    if prices:
        headers.append(t(lang, "col.cost"))
    rows = []
    for r in result.rows:
        row = [r.path, r.model, _size(r.original_size), _size(r.sent_size), str(r.tokens),
               _yn(lang, r.server_downscaled), str(r.wasted_pixels)]
        if with_budget and max_tokens is not None:
            row.append(_yn(lang, r.over_budget))
        if prices:
            row.append("-" if r.cost_usd is None else f"{r.cost_usd:.6f}")
        rows.append(row)
    if not rows:
        print(t(lang, "report.skipped_only" if result.skipped else "report.no_images"), file=out)
    else:
        print(_table(headers, rows), file=out)
    _print_warnings(lang, [c for r in result.rows for c in r.warnings], out)
    if result.skipped:
        print(t(lang, "report.skipped", paths=", ".join(result.skipped)), file=out)
    print(t(lang, "report.summary_one" if len(result.rows) == 1 else "report.summary", rows=len(result.rows), over=over, skipped=len(result.skipped)), file=out)
    return 1 if failed else 0


def _save(img: Image.Image, path: Path) -> None:
    if path.suffix.lower() in (".jpg", ".jpeg") and img.mode not in ("RGB", "L"):
        img = img.convert("RGB")
    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(path)


def _cmd_fit(args, lang, out) -> int:
    size = measure(args.path)
    plan = fit_size(size, args.model, budget=args.budget, detail=args.detail)
    spec = get_model(args.model)
    if plan.reason == "fixed_per_image":
        print(t(lang, "fit.fixed_per_image", model=spec.name, tokens=plan.tokens), file=out)
        if plan.suggest:
            print(t(lang, "fit.suggest", budget=args.budget, detail=plan.suggest[0], tokens=plan.suggest[1]), file=out)
        elif args.budget is not None and plan.tokens > args.budget:
            print(t(lang, "fit.suggest_none", budget=args.budget), file=out)
        return 0
    if not plan.changed:
        print(t(lang, "fit.unchanged", w=size[0], h=size[1], tokens=plan.tokens), file=out)
        return 0
    src = Path(args.path)
    dest = Path(args.out) if args.out else src.with_name(f"{src.stem}.fit{src.suffix}")
    _check_save_path(dest)  # 디코드 전에 저장 형식부터 확인(트레이스백 대신 알기 쉬운 오류)
    result = fit(args.path, args.model, budget=args.budget, detail=args.detail, max_pixels=args.max_pixels)
    _save(result.image, dest)
    print(t(lang, "fit.written", path=dest.as_posix(), w=plan.size[0], h=plan.size[1],
            tokens=plan.tokens, scale=plan.scale), file=out)
    return 0


def _cmd_slice(args, lang, out) -> int:
    plan = plan_slices(measure(args.path), args.model, overlap=args.overlap, detail=args.detail)
    print(t(lang, "slice.summary_one" if len(plan.pieces) == 1 else "slice.summary", n=len(plan.pieces), length=plan.piece_length, axis=t(lang, "axis." + plan.axis),
            overlap=plan.overlap, total=plan.total_tokens, whole=plan.whole_tokens), file=out)
    headers = [t(lang, k) for k in ("col.piece", "col.box", "col.size", "col.tokens", "col.scale", "col.downscaled")]
    rows = [[str(p.index + 1), ",".join(map(str, p.box)), _size(p.size), str(p.tokens), f"{p.scale:.3f}",
             _yn(lang, p.server_downscaled)] for p in plan.pieces]
    print(_table(headers, rows), file=out)
    _print_warnings(lang, plan.warnings, out)
    if len(plan.pieces) == 1:
        print(t(lang, "slice.single"), file=out)
        return 0
    if args.dry_run:
        return 0
    src = Path(args.path)
    folder = Path(args.out_dir) if args.out_dir else src.with_name(f"{src.stem}-slices")
    _check_save_path(folder / f"{src.stem}-01{src.suffix}")
    result = slice_image(args.path, args.model, overlap=args.overlap, detail=args.detail, max_pixels=args.max_pixels)
    for i, img in enumerate(result.images, 1):
        _save(img, folder / f"{src.stem}-{i:02d}{src.suffix}")
    print(t(lang, "slice.written", n=len(result.images), folder=folder.as_posix()), file=out)
    return 0


def _cmd_demo(args, lang, out) -> int:
    from .demo import run_demo

    size, fitted, sliced = run_demo(args.out, args.model)
    p0 = sliced.plan.pieces[0]
    print(t(lang, "demo.title"), file=out)
    print(t(lang, "demo.model", model=get_model(args.model).name), file=out)
    print(t(lang, "demo.image", w=size[0], h=size[1]), file=out)
    print(t(lang, "demo.fit", w=fitted.plan.size[0], h=fitted.plan.size[1], tokens=fitted.plan.tokens,
            scale=fitted.plan.scale), file=out)
    print(t(lang, "demo.slice", n=len(sliced.plan.pieces), pw=p0.size[0], ph=p0.size[1],
            total=sliced.plan.total_tokens), file=out)
    print(t(lang, "demo.tradeoff"), file=out)
    print(t(lang, "demo.files", folder=Path(args.out).as_posix()), file=out)
    _print_warnings(lang, sliced.plan.warnings, out)
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    """Entry point for ``pixelbudget`` and ``python -m pixelbudget``. Returns the exit code."""
    argv = list(sys.argv[1:] if argv is None else argv)
    pre = argparse.ArgumentParser(add_help=False)
    pre.add_argument("--lang")
    known, _ = pre.parse_known_args(argv)
    lang = resolve_lang(known.lang)
    parser = _build_parser(lang)
    args = parser.parse_args(argv)
    out = sys.stdout
    set_models_file(args.models_file)  # --models-file 은 환경변수보다 우선한다
    try:
        if args.command == "models":
            return _cmd_models(args, lang, out)
        if args.command == "estimate":
            return _cmd_report(args, lang, out, with_budget=False)
        if args.command == "report":
            return _cmd_report(args, lang, out, with_budget=True)
        if args.command == "fit":
            return _cmd_fit(args, lang, out)
        if args.command == "slice":
            return _cmd_slice(args, lang, out)
        return _cmd_demo(args, lang, out)
    except (PixelBudgetError, OSError) as exc:
        # 라이브러리 예외는 영어 문구를 유지하고, 화면에는 고른 언어로 다시 렌더링해 보여 준다.
        print(f"{t(lang, 'error.prefix')}: {_error_text(lang, exc)}", file=sys.stderr)
        return 2
    finally:
        set_models_file(None)


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
