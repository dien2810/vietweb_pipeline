"""Stage 3: Vietnamese text normalization.

- Repair common encoding errors (ftfy) and convert to Unicode NFC.
- Normalize tone-mark placement in the open rhymes oa, oe, uy (e.g. "hoà" <-> "hòa").
- Detect text written in the legacy VNI / TCVN3 encodings that was decoded incorrectly.
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
    alts = "|".join(sorted(map(re.escape, mapping), key=len, reverse=True))
    # Apply only when the rhyme ends the syllable (no final consonant) and does not follow 'q'
    # ("quý", "quỳ" are spelled the same in both styles)
    return re.compile(rf"(?<![qQ])({alts})(?![{_VN_LETTERS}])")


_RE_NEW = _tone_regex(_NEW_TO_OLD)
_RE_OLD = _tone_regex(_OLD_TO_NEW)


def normalize_tone_marks(text: str, style: str = "old") -> str:
    """style='old': new-style -> old-style placement; style='new': the reverse; 'none': unchanged."""
    if style == "old":
        return _RE_NEW.sub(lambda m: _NEW_TO_OLD[m.group(1)], text)
    if style == "new":
        return _RE_OLD.sub(lambda m: _OLD_TO_NEW[m.group(1)], text)
    return text


# Control characters, zero-width characters, and the byte-order mark
_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f\u200b-\u200f\ufeff]")
# Tabs, no-break space, and other Unicode spaces
_SPACES = re.compile(r"[ \t\u00a0\u2000-\u200a\u3000]+")
_BLANK_LINES = re.compile(r"\n{3,}")


def normalize_text(text: str, fix_mojibake: bool = True, form: str = "NFC", tone_style: str = "old") -> str:
    if fix_mojibake and ftfy is not None:
        text = ftfy.fix_text(text, normalization=form)
    text = unicodedata.normalize(form, text)
    text = _CONTROL.sub("", text)
    text = "\n".join(_SPACES.sub(" ", line).strip() for line in text.split("\n"))
    text = _BLANK_LINES.sub("\n\n", text).strip()
    return normalize_tone_marks(text, tone_style)


# Characters that appear when TCVN3 (ABC) or VNI text is misread as Latin-1 / Windows-1252.
# This is a simple detector; validate it in weeks 8-10 on clean text that is deliberately corrupted.
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


def convert_legacy(text: str) -> str:
    """TODO (weeks 8-10): convert TCVN3/VNI text to Unicode with a complete conversion table."""
    raise NotImplementedError("TCVN3/VNI -> Unicode conversion table is not implemented yet")
