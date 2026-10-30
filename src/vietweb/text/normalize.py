"""Stage 3: Vietnamese text normalization.

- Repair common encoding errors (ftfy) and convert to Unicode NFC.
- Normalize tone-mark placement in the open rhymes oa, oe, uy (e.g. "hoà" <-> "hòa").
- Detect text written in the legacy VNI / TCVN3 encodings that was decoded incorrectly
  (conversion to Unicode: text/legacy.py).
"""
from __future__ import annotations

import re
import unicodedata

try:
    import ftfy
except ImportError:  # ftfy is optional for minimal test runs
    ftfy = None

# Tone variants of each vowel: (no tone, grave, acute, hook above, tilde, dot below)
_TONES = {
    "a": "aàáảãạ", "e": "eèéẻẽẹ", "o": "oòóỏõọ", "u": "uùúủũụ", "y": "yỳýỷỹỵ",
}
# Latin letters plus all Vietnamese letters (lower and upper case)
_VN_LETTERS = "a-zA-Zàáảãạăằắẳẵặâầấẩẫậèéẻẽẹêềếểễệìíỉĩịòóỏõọôồốổỗộơờớởỡợùúủũụưừứửữựỳýỷỹỵđ" \
              "ÀÁẢÃẠĂẰẮẲẴẶÂẦẤẨẪẬÈÉẺẼẸÊỀẾỂỄỆÌÍỈĨỊÒÓỎÕỌÔỒỐỔỖỘƠỜỚỞỠỢÙÚỦŨỤƯỪỨỬỮỰỲÝỶỸỴĐ"


def _build_tone_maps() -> tuple[dict[str, str], dict[str, str]]:
    """Map new-style -> old-style placement and back, for the open rhymes oa, oe, uy (all letter cases)."""
    new_to_old, old_to_new = {}, {}
    for first, second in (("o", "a"), ("o", "e"), ("u", "y")):
        for t in range(1, 6):
            new = first + _TONES[second][t]          # new style: tone mark on the second vowel
            old = _TONES[first][t] + second          # old style: tone mark on the first vowel
            for n, o in ((new, old), (new.capitalize(), old.capitalize()), (new.upper(), old.upper())):
                new_to_old[n] = o
                old_to_new[o] = n
    return new_to_old, old_to_new


_NEW_TO_OLD, _OLD_TO_NEW = _build_tone_maps()


def _tone_regex(mapping: dict[str, str]) -> re.Pattern:
    # One character class per position instead of an alternation of every rhyme (about 5 times faster);
    # pairs that are not in the mapping are returned unchanged by normalize_tone_marks.
    firsts = "".join(sorted({k[0] for k in mapping}))
    seconds = "".join(sorted({k[1] for k in mapping}))
    # Apply only when the rhyme ends the syllable (no final consonant) and does not follow 'q'
    # ("quý", "quỳ" are spelled the same in both styles)
    return re.compile(rf"(?<![qQ])([{firsts}][{seconds}])(?![{_VN_LETTERS}])")


_RE_NEW = _tone_regex(_NEW_TO_OLD)
_RE_OLD = _tone_regex(_OLD_TO_NEW)


def normalize_tone_marks(text: str, style: str = "old") -> str:
    """style='old': new-style -> old-style placement; style='new': the reverse; 'none': unchanged."""
    if style == "old":
        return _RE_NEW.sub(lambda m: _NEW_TO_OLD.get(m.group(1), m.group(1)), text)
    if style == "new":
        return _RE_OLD.sub(lambda m: _OLD_TO_NEW.get(m.group(1), m.group(1)), text)
    return text


# Control characters, zero-width characters, and the byte-order mark
_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f\u200b-\u200f\ufeff]")
# Tabs, no-break space, and other Unicode spaces
_SPACES = re.compile(r"[ \t\u00a0\u2000-\u200a\u3000]+")
_BLANK_LINES = re.compile(r"\n{3,}")


# ftfy only needs to see a line that contains a character it could change. A line is left as it is when it
# holds only printable ASCII other than "&" (HTML entities) and Vietnamese letters, except the upper-case
# letters U+00C0-U+00DF: those are also lead bytes of 2-byte UTF-8 mojibake ("Ã " for "à" when the A0 byte
# became a space). On the 48,815 documents of the 200-file run the output equals ftfy on the whole text,
# and stage 3 is about 3 times faster (most of its time was ftfy).
_PLAIN_CHARS = ("".join(chr(c) for c in range(0x20, 0x7F) if chr(c) != "&")
                + "".join(ch for ch in _VN_LETTERS[6:] if not "\u00c0" <= ch <= "\u00df"))
_NOT_PLAIN = re.compile("[^" + re.escape(_PLAIN_CHARS) + "]")


def fix_text_lines(text: str, form: str = "NFC") -> str:
    """Same result as ftfy.fix_text(text, normalization=form), running ftfy only on lines it could change."""
    if ftfy is None or not _NOT_PLAIN.search(text.replace("\n", "")):
        return text
    parts = text.split("\n")
    out, seen_lt = [], False
    for i, line in enumerate(parts):
        seg = line + ("\n" if i < len(parts) - 1 else "")
        # As in ftfy.fix_text: once a line contains "<", HTML entities are not unescaped in that line or later ones
        seen_lt = seen_lt or "<" in line
        if _NOT_PLAIN.search(line):
            seg = ftfy.fix_text(seg, normalization=form, unescape_html=False if seen_lt else "auto")
        out.append(seg)
    return "".join(out)


def normalize_text(text: str, fix_mojibake: bool = True, form: str = "NFC", tone_style: str = "old") -> str:
    if fix_mojibake and ftfy is not None:
        text = fix_text_lines(text, form)
    text = unicodedata.normalize(form, text)
    text = _CONTROL.sub("", text)
    text = "\n".join(_SPACES.sub(" ", line).strip() for line in text.split("\n"))
    text = _BLANK_LINES.sub("\n\n", text).strip()
    return normalize_tone_marks(text, tone_style)


# Characters that appear when TCVN3 (ABC) or VNI text is misread as Latin-1 / Windows-1252.
# This score only flags pages; the decision to convert is made in text/legacy.py by decoding the text and
# checking that it then reads as Vietnamese (the score also flags Turkish and Kurdish pages).
# Only characters that are NOT part of the Vietnamese alphabet are used, and symbols common in normal
# text (copyright sign, registered sign, guillemets, middle dot, pound sign) are excluded to limit false positives.
_TCVN3_MARKERS = set("\u00b8\u00b5\u00b6\u00b9\u00a8\u00aa\u00ac\u00a6\u00a7\u00a1\u00a2\u00a4\u00a5"
                     "\u00bc\u00bd\u00be\u00c6\u00c7\u00ce\u00cf\u00d1\u00d7\u00d8\u00dc\u00de\u00df"
                     "\u00e6\u00e7\u00ee\u00ef\u00f1\u00f7\u00f8\u00fc\u00fe")
_VNI_PATTERN = re.compile(r"[aeiouyAEIOUY][\u00f8\u00ef\u00fb\u00f6\u00e4\u00eb\u00fc]")


def legacy_encoding_score(text: str) -> float:
    """Share of characters typical of misdecoded TCVN3/VNI text. Proper Unicode text scores close to 0."""
    if not text:
        return 0.0
    tcvn = sum(ch in _TCVN3_MARKERS for ch in text)
    vni = len(_VNI_PATTERN.findall(text))
    return (tcvn + vni) / max(len(text), 1)

