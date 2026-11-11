"""Exception hierarchy.

Every error carries a stable ``code`` (the kind of error) plus structured ``key``/``params``.
The English exception text that library users see is rendered from ``locales/en.json`` with
those params, and the CLI renders the same key in the user's language (``render("ko")``).
"""

from __future__ import annotations

from .i18n import messages, t


class PixelBudgetError(Exception):
    """Base class for all errors raised by pixelbudget.

    ``key`` picks the message template ``error.<key>`` (defaults to ``code``); ``params`` fill it.
    Passing ``message`` keeps a hand-written English text (for errors raised by user code).
    """

    code = "error"

    def __init__(self, message: str | None = None, *, key: str | None = None, **params: object) -> None:
        self.key = key or self.code
        self.params = params
        self._custom = message is not None  # hand-written text has no template to translate
        # 메시지를 직접 주지 않으면 영어 표(en.json)에서 만든다 — 라이브러리 예외 문구의 원본은 한 곳.
        super().__init__(message if message is not None else self.render("en"))

    def render(self, lang: str = "en") -> str:
        """Message in ``lang``; falls back to the English exception text when there is no template."""
        template_key = f"error.{self.key}"
        if self._custom or template_key not in messages("en"):
            return str(self)
        try:
            return t(lang, template_key, **self.params)
        except (KeyError, IndexError, ValueError):  # params do not match the template (custom raise)
            return str(self)


class UnknownModelError(PixelBudgetError):
    code = "unknown_model"


class UnsupportedDetailError(PixelBudgetError):
    code = "unsupported_detail"


class InvalidBudgetError(PixelBudgetError):
    code = "invalid_budget"


class InvalidOverlapError(PixelBudgetError):
    code = "invalid_overlap"


class InvalidSizeError(PixelBudgetError):
    code = "invalid_size"


class UnreadableImageError(PixelBudgetError):
    code = "unreadable_image"


class ImageTooLargeError(PixelBudgetError):
    """Decoding needed (fit/slice) but the pixel count exceeds the guard."""

    code = "image_too_large"


class ModelTableError(PixelBudgetError):
    code = "model_table"
