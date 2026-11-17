"""User-interface translations.

The Traditional Chinese texts in the source code are the message keys. Every other language has a module
here (``en.py``) whose ``MESSAGES`` dict maps those keys to its own text; a missing entry falls back to the
key, so the program never shows an empty label.

    tr("已加入 {n} 個檔案", n=3)        # named placeholders, str.format syntax
    "已加入 {n} 個檔案": ("Added {n} file", "Added {n} files")   # en.py: (singular, plural), picked by n
    tr("關閉", context="ocr")          # same source text, different meaning: en.py key "ocr|關閉"

The language is chosen once at start-up (QSettings "language": "system" or a code from LANGUAGES) and a
change takes effect after a restart. Qt-free on purpose: the engine, legal.py and the build scripts use it.
"""

from __future__ import annotations

import locale
import sys
from typing import Union

SOURCE = "zh_TW"  # the language the keys are written in
# Language code -> name in that language (shown untranslated in the language menu).
LANGUAGES = {"zh_TW": "繁體中文", "en": "English"}
SYSTEM = "system"
SETTING_KEY = "language"

Message = Union[str, tuple[str, str]]

_current = SOURCE
_messages: dict[str, Message] = {}


def _catalog(code: str) -> dict[str, Message]:
    # Static imports, so PyInstaller bundles every catalog.
    if code == "en":
        from .en import MESSAGES
        return MESSAGES
    return {}


def set_language(code: str) -> str:
    """Activate a language for every later tr() call; returns the code actually used."""
    global _current, _messages
    code = code if code in LANGUAGES else SOURCE
    _messages = _catalog(code)
    _current = code
    return code


def current() -> str:
    return _current


def tr(text: str, n: int | None = None, *, context: str | None = None, **values) -> str:
    """Translate ``text`` and fill its named placeholders. ``n`` picks the plural form and is also ``{n}``;
    ``context`` tells apart identical source texts that need different translations."""
    message = _messages.get(f"{context}|{text}") if context else None
    if message is None:
        message = _messages.get(text, text)
    if isinstance(message, tuple):
        message = message[0] if n == 1 else message[1]
    if n is not None:
        values["n"] = n
    return message.format(**values) if values else message


def sep() -> str:
    """Separator between items on one line ("A · B")."""
    return tr("　·　")


# --------------------------------------------------------------------------- choosing the language

def system_languages() -> list[str]:
    """The user's preferred UI languages, best first (BCP-47 style, e.g. "zh-Hant-TW", "en-US")."""
    try:
        from PySide6.QtCore import QLocale

        langs = [s for s in QLocale.system().uiLanguages() if s]
        if langs:
            return langs
    except Exception:  # pragma: no cover - Qt missing (build scripts)
        pass
    if sys.platform == "win32":
        try:
            import ctypes

            return [locale.windows_locale.get(ctypes.windll.kernel32.GetUserDefaultUILanguage(), "")]
        except Exception:  # pragma: no cover
            pass
    return [locale.getlocale()[0] or ""]


def match_language(tags: list[str]) -> str:
    """First supported language in ``tags``; English when none of them is supported.

    Every Chinese variant maps to Traditional Chinese, the closest available language for those readers.
    """
    for tag in tags:
        t = tag.replace("_", "-").lower()
        if t.startswith("zh"):
            return "zh_TW"
        if t.startswith("en"):
            return "en"
    return "en"


def resolve(preference: object) -> str:
    """The language to use for a stored preference ("system" or a language code)."""
    pref = str(preference or SYSTEM)
    return pref if pref in LANGUAGES else match_language(system_languages())


def qt_locale_name(code: str | None = None) -> str:
    """Qt locale name for a language code (used for QLocale and Qt's own translation files)."""
    return {"zh_TW": "zh_TW", "en": "en_US"}.get(code or _current, "en_US")
