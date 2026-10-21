"""Markdown post-processing: turn raw extractor output into clean, readable Markdown."""

from __future__ import annotations

import re

_FENCE = re.compile(r"^\s*(```|~~~)")
_HEADING = re.compile(r"^(#{1,6})\s+(.*)$")
_LIST_ITEM = re.compile(r"^(\s*)([-*+•]|\d{1,3}[.)])\s+(.*)$")
# Bullet glyphs as they come out of PDFs and OCR (which often reads "•" as "・" or "·").
_GLYPH_BULLET = re.compile(r"^(\s*)[•・●▪◦·‧]\s*(?=\S)")
# OCR can put two bullet lines on one: "- first ・second". A space before "・" keeps
# names such as 約翰・史密斯 intact.
_INLINE_BULLET = re.compile(r"\s+・\s*(?=\S)")
_HR = re.compile(r"^\s*([-*_])(\s*\1){2,}\s*$")
_BOLD_PAIR = re.compile(r"\*\*(.+?)\*\*")
_SPACE_BEFORE_PUNCT = re.compile(r"(\*\*|__|(?<!\w)_|`) +([,.;:!?，。；：！？、）)])")
_CJK_CHAR = r"⺀-鿿가-힯豈-﫿＀-￯　-〿"
_CJK = re.compile(f"[{_CJK_CHAR}]")
_WORD = re.compile(r"[A-Za-z0-9]+(?:['’.-][A-Za-z0-9]+)*")
_DATA_URI = re.compile(r"\(data:[^)]*\)|\(<[^>]*>\)")
_MD_NOISE = re.compile(r"[#*_`>|\-\[\]()!]")

# Block kinds that may sit next to each other without a blank line in between.
_TIGHT = {("list", "list"), ("table", "table"), ("quote", "quote")}


def tidy_markdown(md: str) -> str:
    """Clean up extractor artifacts while leaving code blocks untouched.

    * joins code blocks that were split line by line
    * removes redundant bold inside headings and stray spaces before punctuation
    * re-flows hard-wrapped paragraphs and list items (CJK-aware, de-hyphenates)
    * normalises list indentation and makes lists tight
    * guarantees exactly one blank line between different blocks
    """
    lines = [line.rstrip() for line in md.replace("\r\n", "\n").replace("\r", "\n").split("\n")]
    lines = _merge_adjacent_code_blocks(lines)
    blocks = _to_blocks(lines)
    blocks = _normalise_lists(blocks)

    out: list[str] = []
    prev_kind = None
    for kind, text in blocks:
        if prev_kind is not None and (prev_kind, kind) not in _TIGHT:
            out.append("")
        out.append(text)
        prev_kind = kind
    return "\n".join(out).strip("\n") + "\n"


def _merge_adjacent_code_blocks(lines: list[str]) -> list[str]:
    """Join code blocks that the extractor split line by line (```a``` ```b``` → one block)."""
    out: list[str] = []
    in_code = False
    i = 0
    while i < len(lines):
        line = lines[i]
        if line.strip() == "```" and in_code:
            j = i + 1
            while j < len(lines) and lines[j].strip() == "":
                j += 1
            if j < len(lines) and lines[j].strip() == "```":
                i = j + 1  # skip closing fence, blank lines and the next bare opening fence
                continue
            in_code = False
            out.append(line)
        elif _FENCE.match(line):
            in_code = not in_code
            out.append(line)
        else:
            out.append(line)
        i += 1
    return out


def _classify(line: str) -> str:
    stripped = line.lstrip()
    if _HEADING.match(line):
        return "heading"
    if _HR.match(line):
        return "hr"
    if _LIST_ITEM.match(line):
        return "list"
    if stripped.startswith("|"):
        return "table"
    if stripped.startswith(">"):
        return "quote"
    if stripped.startswith("<"):
        return "html"
    if stripped.startswith("!["):
        return "image"
    return "text"


def _join(a: str, b: str) -> str:
    """Join two wrapped lines: no space between CJK text, undo end-of-line hyphenation."""
    b = b.strip()
    if not b:
        return a
    if re.search(r"[A-Za-z]-$", a) and b[:1].islower():
        return a[:-1] + b
    if _CJK.match(a[-1:]) or _CJK.match(b[:1]):
        return a + b
    return a + " " + b


def _to_blocks(lines: list[str]) -> list[tuple[str, str]]:
    blocks: list[tuple[str, str]] = []
    code: list[str] | None = None
    joinable = False  # may the next text line be appended to the last block?
    for line in lines:
        if code is not None:
            code.append(line)
            if _FENCE.match(line):
                blocks.append(("code", "\n".join(code)))
                code = None
            continue
        if _FENCE.match(line):
            code = [line.strip()]
            joinable = False
            continue
        if not line.strip():
            joinable = False
            continue

        glyph = _GLYPH_BULLET.match(line)
        if glyph:
            indent = glyph.group(1)
            if blocks and blocks[-1][0] == "list":  # a sibling of the item above
                indent = _LIST_ITEM.match(blocks[-1][1]).group(1)
            line = f"{indent}- {line[glyph.end():]}"
        kind = _classify(line)
        if kind == "heading":
            m = _HEADING.match(line)
            # Extractors often wrap heading text in **bold**; the heading already is bold.
            text = re.sub(r"\s{2,}", " ", _BOLD_PAIR.sub(r"\1", m.group(2))).strip()
            if text:
                blocks.append(("heading", f"{m.group(1)} {text}"))
            joinable = False
            continue
        if kind in ("text", "list"):
            line = _SPACE_BEFORE_PUNCT.sub(r"\1\2", line)
        if kind == "text" and joinable and blocks and blocks[-1][0] in ("text", "list"):
            last_kind, last_text = blocks[-1]
            blocks[-1] = (last_kind, _join(last_text, line))
            continue
        blocks.append((kind, line))
        joinable = kind in ("text", "list")

    if code is not None:  # unterminated fence: close it
        code.append("```")
        blocks.append(("code", "\n".join(code)))
    return blocks


def _normalise_lists(blocks: list[tuple[str, str]]) -> list[tuple[str, str]]:
    """Map noisy indentation (2 vs 3 spaces for siblings) onto clean 4-space nesting levels."""
    out: list[tuple[str, str]] = []
    i = 0
    while i < len(blocks):
        if blocks[i][0] != "list":
            out.append(blocks[i])
            i += 1
            continue
        j = i
        while j < len(blocks) and blocks[j][0] == "list":
            j += 1
        items = [_LIST_ITEM.match(text) for _, text in blocks[i:j]]
        indents = sorted({len(m.group(1).expandtabs(4)) for m in items})
        levels: dict[int, int] = {}
        level, anchor = 0, indents[0]
        for ind in indents:
            if ind - anchor >= 2:  # a real step, not jitter
                level, anchor = level + 1, ind
            levels[ind] = min(level, 5)
        for m in items:
            marker = m.group(2)
            if marker == "•":
                marker = "-"
            depth = levels[len(m.group(1).expandtabs(4))]
            parts = _INLINE_BULLET.split(m.group(3)) if marker in "-*+" else [m.group(3)]
            for part in parts:
                out.append(("list", f"{'    ' * depth}{marker} {part.strip()}"))
        i = j
    return out


def count_words(md: str) -> int:
    """Rough reading length: each CJK character counts as one word, plus Latin words."""
    text = _DATA_URI.sub(" ", md)
    text = _MD_NOISE.sub(" ", text)
    return len(_CJK.findall(text)) + len(_WORD.findall(text))
