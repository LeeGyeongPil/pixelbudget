"""Q-10: error messages follow --lang.

Library exceptions keep their English text (API contract) and carry ``key``/``params``; the CLI
renders them in the chosen language. File system errors (missing file, folder in the way) are
translated by the CLI too. English CLI output and exit codes stay as they were.
"""

from __future__ import annotations

import json
import re
import string
from importlib import resources

import pytest

from pixelbudget import (
    InvalidBudgetError,
    InvalidOverlapError,
    PixelBudgetError,
    UnknownModelError,
    UnsupportedDetailError,
    estimate,
    fit_size,
    plan_slices,
)
from pixelbudget.cli import main


@pytest.fixture
def workdir(tmp_path, monkeypatch, make_image):
    """Run in tmp_path so paths in messages are short relative names."""
    monkeypatch.chdir(tmp_path)
    make_image("samples/hd.png", (1920, 1080))
    make_image("samples/tall.png", (1170, 9000))
    (tmp_path / "bad.png").write_text("notanimage")
    return tmp_path


# (argv, English text after "error: " — unchanged from before the fix, Korean text after "오류: ")
CASES = [
    (["estimate", "nope.png", "--model", "claude-standard"],
     "[Errno 2] No such file or directory: 'nope.png'",
     "파일이나 폴더가 없습니다: 'nope.png'"),
    (["estimate", "samples", "--model", "foo"],
     "Unknown model 'foo'. Run `pixelbudget models` to list supported models.",
     "알 수 없는 모델입니다: 'foo'. 지원 모델 목록은 `pixelbudget models` 로 확인하세요."),
    (["estimate", "samples", "--model", "claude-standrd"],
     "Unknown model 'claude-standrd'. Did you mean: claude-standard? Run `pixelbudget models` to list "
     "supported models.",
     "알 수 없는 모델입니다: 'claude-standrd'. 혹시 이 모델인가요: claude-standard? 지원 모델 목록은 "
     "`pixelbudget models` 로 확인하세요."),
    (["estimate", "samples", "--model", "gpt-4o", "--detail", "ultra"],
     "Model 'gpt-4o' does not support detail 'ultra' in the model table. Supported: auto, high, low.",
     "모델 표에서 'gpt-4o' 은(는) detail 'ultra' 을(를) 지원하지 않습니다. 사용 가능: auto, high, low."),
    (["report", "samples", "--model", "claude-standard", "--price", "gpt-4o=abc"],
     "--price value must be a number, got 'gpt-4o=abc'.",
     "--price 의 값은 숫자여야 합니다. 받은 값: 'gpt-4o=abc'."),
    (["report", "samples", "--model", "claude-standard", "--price", "gpt-4o"],
     "--price expects MODEL=USD_PER_MILLION_TOKENS, got 'gpt-4o'.",
     "--price 는 MODEL=백만 토큰당 USD 형식이어야 합니다. 받은 값: 'gpt-4o'."),
    (["report", "samples", "--model", "claude-standard", "--price", "x=1"],
     "Unknown model 'x'. Run `pixelbudget models` to list supported models.",
     "알 수 없는 모델입니다: 'x'. 지원 모델 목록은 `pixelbudget models` 로 확인하세요."),
    (["fit", "samples/hd.png", "--model", "claude-standard", "--budget", "0"],
     "budget must be a positive integer number of tokens, got 0.",
     "예산은 양의 정수(토큰 수)여야 합니다. 받은 값: 0."),
    (["fit", "samples/hd.png", "--model", "gpt-4o", "--budget", "10"],
     "budget 10 is below the minimum of 255 tokens for gpt-4o (a 1x1 image already costs that much). "
     "Use a larger budget.",
     "예산 10 이(가) gpt-4o 의 최소 비용 255 토큰보다 작습니다(1x1 이미지도 이만큼 듭니다). 더 큰 예산을 지정하세요."),
    (["fit", "nope.png", "--model", "claude-standard", "--budget", "800"],
     "[Errno 2] No such file or directory: 'nope.png'",
     "파일이나 폴더가 없습니다: 'nope.png'"),
    (["fit", "bad.png", "--model", "claude-standard", "--budget", "800"],
     "Cannot read 'bad.png' as an image: cannot identify image file 'bad.png'",
     "'bad.png' 을(를) 이미지로 읽을 수 없습니다(이미지 파일이 아니거나 손상됨)."),
    (["fit", "samples/hd.png", "--model", "claude-standard", "--budget", "100", "--max-pixels", "10"],
     "Image is 1920x1080 = 2073600 pixels, above the decode limit of 10. Pass max_pixels=<larger value> "
     "(CLI: --max-pixels) if you trust this image.",
     "이미지가 1920x1080 = 2073600 픽셀로 디코드 한도 10 을(를) 넘습니다. 믿을 수 있는 이미지라면 "
     "max_pixels=<더 큰 값> (CLI: --max-pixels) 을 지정하세요."),
    (["slice", "samples/tall.png", "--model", "claude-standard", "--overlap", "5000", "--dry-run"],
     "overlap 5000 must be smaller than the piece length 1036 for claude-standard. Use a smaller overlap.",
     "겹침 5000 은(는) claude-standard 의 조각 길이 1036 보다 작아야 합니다. 겹침을 줄이세요."),
    (["slice", "samples/tall.png", "--model", "claude-standard", "--overlap", "-1", "--dry-run"],
     "overlap must be a non-negative integer, got -1.",
     "겹침(overlap)은 0 이상의 정수여야 합니다. 받은 값: -1."),
]

# Words from the English messages that must never show up in Korean error output.
ENGLISH_WORDS = ("Unknown", "must", "Cannot", "cannot", "Errno", "does not support", "No such", "Did you mean",
                 "Supported", "Expected", "is below", "Use a", "got ", "File exists", "Is a directory",
                 "Image is", "unknown")


def _run(argv, capsys):
    code = main(argv)
    captured = capsys.readouterr()
    return code, captured.err.strip()


@pytest.mark.parametrize("argv, english, korean", CASES, ids=[" ".join(c[0][:2]) + f" #{i}" for i, c in enumerate(CASES)])
def test_error_is_korean_with_lang_ko(workdir, capsys, argv, english, korean):
    code, err = _run(["--lang", "ko", *argv], capsys)
    assert code == 2
    assert err == f"오류: {korean}"
    assert not [w for w in ENGLISH_WORDS if w in err], err


@pytest.mark.parametrize("argv, english, korean", CASES, ids=[" ".join(c[0][:2]) + f" #{i}" for i, c in enumerate(CASES)])
def test_english_error_text_and_exit_code_unchanged(workdir, capsys, argv, english, korean):
    code, err = _run(["--lang", "en", *argv], capsys)
    assert code == 2
    assert err == f"error: {english}"


def test_folder_given_to_fit_is_explained(workdir, capsys):
    code, err = _run(["--lang", "ko", "fit", "samples", "--model", "claude-standard", "--budget", "800"], capsys)
    assert code == 2 and err == "오류: 'samples' 은(는) 폴더입니다. 이미지 파일 하나를 지정하세요."
    code, err = _run(["--lang", "en", "fit", "samples", "--model", "claude-standard", "--budget", "800"], capsys)
    assert code == 2 and err.startswith("error: Cannot read 'samples' as an image: [Errno 21]")


def test_missing_path_without_image_extension(workdir, capsys):
    # report.py raises the standard errno form, so both spellings of a missing path read the same.
    assert _run(["--lang", "ko", "estimate", "nope", "--model", "claude-standard"], capsys) == (
        2, "오류: 파일이나 폴더가 없습니다: 'nope'")
    assert _run(["--lang", "en", "estimate", "nope", "--model", "claude-standard"], capsys) == (
        2, "error: [Errno 2] No such file or directory: 'nope'")


@pytest.mark.parametrize("lang, expected", [
    ("en", "error: Cannot save 'x.xyz': unknown image file extension '.xyz'. Use .png, .jpg or .webp."),
    ("ko", "오류: 'x.xyz' 로 저장할 수 없습니다: 알 수 없는 이미지 확장자 '.xyz'. .png, .jpg, .webp 를 쓰세요."),
])
def test_unknown_output_extension_is_an_error_not_a_traceback(workdir, capsys, lang, expected):
    argv = ["--lang", lang, "fit", "samples/hd.png", "--model", "claude-standard", "--budget", "100", "--out", "x.xyz"]
    assert _run(argv, capsys) == (2, expected)
    assert not (workdir / "x.xyz").exists()


@pytest.mark.parametrize("lang, expected", [
    ("en", "error: [Errno 17] File exists: 'samples/hd.png'"),
    ("ko", "오류: 같은 이름의 파일이 이미 있어 폴더를 만들 수 없습니다: 'samples/hd.png'"),
])
@pytest.mark.parametrize("argv", [
    ["fit", "samples/hd.png", "--model", "claude-standard", "--budget", "100", "--out", "samples/hd.png/x.png"],
    ["slice", "samples/tall.png", "--model", "claude-standard", "--out-dir", "samples/hd.png"],
    ["demo", "--out", "samples/hd.png"],
])
def test_output_folder_blocked_by_a_file_is_an_error_not_a_traceback(workdir, capsys, lang, expected, argv):
    code = main(["--lang", lang, *argv])
    assert code == 2
    assert capsys.readouterr().err.strip() == expected


def test_korean_ambiguous_option_is_translated(workdir, capsys):
    with pytest.raises(SystemExit) as exc:
        main(["--lang", "ko", "report", "samples", "--m", "gpt-4o"])  # --model or --max-tokens?
    assert exc.value.code == 2
    err = capsys.readouterr().err
    assert "여러 옵션과 겹칩니다" in err and "ambiguous" not in err


# --- library side: English text stays the API contract, code/key/params are structured ----------

def test_library_exceptions_keep_english_text_and_carry_params():
    with pytest.raises(UnknownModelError) as exc:
        estimate((100, 100), "foo")
    assert str(exc.value) == "Unknown model 'foo'. Run `pixelbudget models` to list supported models."
    assert exc.value.code == "unknown_model" and exc.value.params == {"name": "foo"}

    with pytest.raises(UnsupportedDetailError) as exc:
        estimate((100, 100), "gpt-4o", detail="ultra")
    assert exc.value.params == {"model": "gpt-4o", "detail": "ultra", "supported": "auto, high, low"}

    with pytest.raises(InvalidBudgetError) as exc:
        fit_size((1000, 1000), "gpt-4o", budget=10)
    assert exc.value.code == "invalid_budget" and exc.value.key == "budget_below_minimum"
    assert exc.value.params == {"budget": 10, "minimum": 255, "model": "gpt-4o"}

    with pytest.raises(InvalidOverlapError) as exc:
        plan_slices((1170, 9000), "claude-standard", overlap=5000)
    assert exc.value.render("ko").startswith("겹침 5000")
    assert exc.value.render() == str(exc.value)


def test_hand_written_error_message_is_kept_in_every_language():
    err = UnknownModelError("custom text from user code")
    assert str(err) == err.render("ko") == "custom text from user code"
    assert PixelBudgetError("plain").render("ko") == "plain"


def _table(lang):
    return json.loads(resources.files("pixelbudget").joinpath(f"locales/{lang}.json").read_text("utf-8"))


def _fields(template):
    return {name for _, name, _, _ in string.Formatter().parse(template) if name}


ERROR_KEYS = sorted(k for k in _table("en") if k.startswith(("error.", "os.")) and k != "error.prefix")


@pytest.mark.parametrize("key", ERROR_KEYS)
def test_every_error_template_is_translated_with_the_same_fields(key):
    en, ko = _table("en")[key], _table("ko")[key]
    assert _fields(ko) <= _fields(en), f"{key}: Korean uses a field the English message does not pass"
    sample = {name: "VALUE" for name in _fields(en)}
    en.format(**sample), ko.format(**sample)  # both render with the same params
    assert ko != en and re.search(r"[가-힣]", ko), f"{key} is not translated"
