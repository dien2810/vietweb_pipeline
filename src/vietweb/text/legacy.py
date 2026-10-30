"""Convert Vietnamese text written in the legacy TCVN3 (ABC) and VNI-Windows encodings to Unicode.

Pages made with the .VnTime fonts (TCVN3) or the VNI fonts store Vietnamese letters as single bytes (TCVN3)
or as a base letter followed by a mark byte (VNI). Read as Windows-1252, which is what happens when such a
page declares no other charset, the letters become Latin-1 symbols: "Hµ Néi" (TCVN3) or "Haø Noäi" (VNI)
for "Hà Nội".

The tables below give, for every Vietnamese letter of each encoding, how it looks after Windows-1252
decoding and the Unicode letter it stands for. They were generated from the conversion tables of Unikey
(Pham Kim Long). TCVN3 has separate codes only for a few upper-case letters (Ă Â Ê Ô Ơ Ư Đ and the
unaccented ones): fonts such as .VnTimeH show the lower-case codes in upper case, so 60 upper-case letters
with tone marks come back in lower case.

convert_legacy() decides per document: it decodes the text both ways and keeps a decoded version only if
the share of Vietnamese stop words rises by a clear margin. Text that is already Unicode Vietnamese is
returned unchanged.
"""
from __future__ import annotations

import re
import unicodedata

from .tokenize import syllables

# TCVN3: the character after Windows-1252 decoding -> Unicode (same position in both strings)
_TCVN3_LEGACY = "¡¢£¤¥¦§¨©ª«¬­®µ¶·¸¹»¼½¾ÆÇÈÉÊËÌÎÏÐÑÒÓÔÕÖ×ØÜÝÞßáâãäåæçèéêëìíîïñòóôõö÷øùúûüýþ"
_TCVN3_UNICODE = "ĂÂÊÔƠƯĐăâêôơưđàảãáạằẳẵắặầẩẫấậèẻẽéẹềểễếệìỉĩíịòỏõóọồổỗốộờởỡớợùủũúụừửữứựỳỷỹýỵ"
TCVN3_TO_UNICODE = dict(zip(_TCVN3_LEGACY, _TCVN3_UNICODE))

# VNI-Windows: base letter + mark, or a single character, after Windows-1252 decoding -> Unicode
VNI_TO_UNICODE = {
    "AØ": "À", "aø": "à", "AÙ": "Á", "aù": "á", "AÂ": "Â", "aâ": "â", "AÕ": "Ã", "aõ": "ã",
    "EØ": "È", "eø": "è", "EÙ": "É", "eù": "é", "EÂ": "Ê", "eâ": "ê", "OØ": "Ò", "oø": "ò",
    "OÙ": "Ó", "où": "ó", "OÂ": "Ô", "oâ": "ô", "OÕ": "Õ", "oõ": "õ", "UØ": "Ù", "uø": "ù",
    "UÙ": "Ú", "uù": "ú", "YÙ": "Ý", "yù": "ý", "AÊ": "Ă", "aê": "ă", "Ñ": "Đ", "ñ": "đ",
    "Ó": "Ĩ", "ó": "ĩ", "UÕ": "Ũ", "uõ": "ũ", "Ô": "Ơ", "ô": "ơ", "Ö": "Ư", "ö": "ư",
    "AÏ": "Ạ", "aï": "ạ", "AÛ": "Ả", "aû": "ả", "AÁ": "Ấ", "aá": "ấ", "AÀ": "Ầ", "aà": "ầ",
    "AÅ": "Ẩ", "aå": "ẩ", "AÃ": "Ẫ", "aã": "ẫ", "AÄ": "Ậ", "aä": "ậ", "AÉ": "Ắ", "aé": "ắ",
    "AÈ": "Ằ", "aè": "ằ", "AÚ": "Ẳ", "aú": "ẳ", "AÜ": "Ẵ", "aü": "ẵ", "AË": "Ặ", "aë": "ặ",
    "EÏ": "Ẹ", "eï": "ẹ", "EÛ": "Ẻ", "eû": "ẻ", "EÕ": "Ẽ", "eõ": "ẽ", "EÁ": "Ế", "eá": "ế",
    "EÀ": "Ề", "eà": "ề", "EÅ": "Ể", "eå": "ể", "EÃ": "Ễ", "eã": "ễ", "EÄ": "Ệ", "eä": "ệ",
    "Æ": "Ỉ", "æ": "ỉ", "Ò": "Ị", "ò": "ị", "OÏ": "Ọ", "oï": "ọ", "OÛ": "Ỏ", "oû": "ỏ",
    "OÁ": "Ố", "oá": "ố", "OÀ": "Ồ", "oà": "ồ", "OÅ": "Ổ", "oå": "ổ", "OÃ": "Ỗ", "oã": "ỗ",
    "OÄ": "Ộ", "oä": "ộ", "ÔÙ": "Ớ", "ôù": "ớ", "ÔØ": "Ờ", "ôø": "ờ", "ÔÛ": "Ở", "ôû": "ở",
    "ÔÕ": "Ỡ", "ôõ": "ỡ", "ÔÏ": "Ợ", "ôï": "ợ", "UÏ": "Ụ", "uï": "ụ", "UÛ": "Ủ", "uû": "ủ",
    "ÖÙ": "Ứ", "öù": "ứ", "ÖØ": "Ừ", "öø": "ừ", "ÖÛ": "Ử", "öû": "ử", "ÖÕ": "Ữ", "öõ": "ữ",
    "ÖÏ": "Ự", "öï": "ự", "YØ": "Ỳ", "yø": "ỳ", "Î": "Ỵ", "î": "ỵ", "YÛ": "Ỷ", "yû": "ỷ",
    "YÕ": "Ỹ", "yõ": "ỹ",
}

# Reverse tables, used by the tests and by the synthetic evaluation (scripts/legacy_eval.py)
UNICODE_TO_TCVN3 = {"À": "µ", "Á": "¸", "Â": "¢", "Ã": "·", "È": "Ì", "É": "Ð", "Ê": "£", "Ì": "×", "Í": "Ý", "Ò": "ß", "Ó": "ã", "Ô": "¤", "Õ": "â", "Ù": "ï", "Ú": "ó", "Ý": "ý", "à": "µ", "á": "¸", "â": "©", "ã": "·", "è": "Ì", "é": "Ð", "ê": "ª", "ì": "×", "í": "Ý", "ò": "ß", "ó": "ã", "ô": "«", "õ": "â", "ù": "ï", "ú": "ó", "ý": "ý", "Ă": "¡", "ă": "¨", "Đ": "§", "đ": "®", "Ĩ": "Ü", "ĩ": "Ü", "Ũ": "ò", "ũ": "ò", "Ơ": "¥", "ơ": "¬", "Ư": "¦", "ư": "­", "Ạ": "¹", "ạ": "¹", "Ả": "¶", "ả": "¶", "Ấ": "Ê", "ấ": "Ê", "Ầ": "Ç", "ầ": "Ç", "Ẩ": "È", "ẩ": "È", "Ẫ": "É", "ẫ": "É", "Ậ": "Ë", "ậ": "Ë", "Ắ": "¾", "ắ": "¾", "Ằ": "»", "ằ": "»", "Ẳ": "¼", "ẳ": "¼", "Ẵ": "½", "ẵ": "½", "Ặ": "Æ", "ặ": "Æ", "Ẹ": "Ñ", "ẹ": "Ñ", "Ẻ": "Î", "ẻ": "Î", "Ẽ": "Ï", "ẽ": "Ï", "Ế": "Õ", "ế": "Õ", "Ề": "Ò", "ề": "Ò", "Ể": "Ó", "ể": "Ó", "Ễ": "Ô", "ễ": "Ô", "Ệ": "Ö", "ệ": "Ö", "Ỉ": "Ø", "ỉ": "Ø", "Ị": "Þ", "ị": "Þ", "Ọ": "ä", "ọ": "ä", "Ỏ": "á", "ỏ": "á", "Ố": "è", "ố": "è", "Ồ": "å", "ồ": "å", "Ổ": "æ", "ổ": "æ", "Ỗ": "ç", "ỗ": "ç", "Ộ": "é", "ộ": "é", "Ớ": "í", "ớ": "í", "Ờ": "ê", "ờ": "ê", "Ở": "ë", "ở": "ë", "Ỡ": "ì", "ỡ": "ì", "Ợ": "î", "ợ": "î", "Ụ": "ô", "ụ": "ô", "Ủ": "ñ", "ủ": "ñ", "Ứ": "ø", "ứ": "ø", "Ừ": "õ", "ừ": "õ", "Ử": "ö", "ử": "ö", "Ữ": "÷", "ữ": "÷", "Ự": "ù", "ự": "ù", "Ỳ": "ú", "ỳ": "ú", "Ỵ": "þ", "ỵ": "þ", "Ỷ": "û", "ỷ": "û", "Ỹ": "ü", "ỹ": "ü"}
UNICODE_TO_VNI = {**{u: s for s, u in VNI_TO_UNICODE.items()}, "Í": "Í", "í": "í", "Ì": "Ì", "ì": "ì"}

_TCVN3_RE = re.compile("[" + re.escape(_TCVN3_LEGACY) + "]")
_VNI_RE = re.compile("|".join(sorted(map(re.escape, VNI_TO_UNICODE), key=len, reverse=True)))


def decode_tcvn3(text: str) -> str:
    return _TCVN3_RE.sub(lambda m: TCVN3_TO_UNICODE[m.group()], text)


def decode_vni(text: str) -> str:
    return _VNI_RE.sub(lambda m: VNI_TO_UNICODE[m.group()], text)


def encode_tcvn3(text: str) -> str:
    """Unicode -> how TCVN3 text looks when read as Windows-1252 (for tests and evaluation)."""
    return "".join(UNICODE_TO_TCVN3.get(ch, ch) for ch in unicodedata.normalize("NFC", text))


def encode_vni(text: str) -> str:
    return "".join(UNICODE_TO_VNI.get(ch, ch) for ch in unicodedata.normalize("NFC", text))


# Lower-case Vietnamese letters with a diacritic or tone mark
_VN_MARKED = {ch.lower() for ch in UNICODE_TO_VNI}
_VN_ALL = set(UNICODE_TO_VNI)
# Codes of each encoding that never occur in Unicode Vietnamese text ("µ", "¸" in TCVN3; "ø", "ï", "ñ" in VNI)
FOREIGN = {
    "tcvn3": frozenset(ch for ch in TCVN3_TO_UNICODE if ch not in _VN_ALL),
    "vni": frozenset(ch for key in VNI_TO_UNICODE for ch in key if not ch.isascii() and ch not in _VN_ALL),
}


_FOREIGN_RE = {enc: re.compile("[" + re.escape("".join(sorted(chars))) + "]") for enc, chars in FOREIGN.items()}
_SPACE_RE = re.compile(r"\s")


def foreign_share(text: str, enc: str) -> float:
    """Share of the non-space characters that are codes of `enc` foreign to Unicode Vietnamese."""
    nonspace = len(text) - len(_SPACE_RE.findall(text))
    return len(_FOREIGN_RE[enc].findall(text)) / max(nonspace, 1)


def _shares(text: str, stopwords: frozenset | set) -> tuple[float, float]:
    """(share of stop words, share of syllables with a Vietnamese diacritic) among the syllables of a text."""
    toks = syllables(text)
    if not toks:
        return 0.0, 0.0
    stop = sum(tok in stopwords for tok in toks) / len(toks)
    marked = sum(any(ch in _VN_MARKED for ch in tok) for tok in toks) / len(toks)
    return stop, marked


def convert_legacy(text: str, stopwords: frozenset | set, min_gain: float = 0.04, min_marked: float = 0.3,
                   min_foreign: float = 0.02) -> tuple[str, str | None]:
    """Return (text, encoding): the decoded text and "tcvn3" or "vni", or the input and None.

    Most Vietnamese stop words carry diacritics ("của", "và", "là", "được"), so in legacy text they are
    unrecognizable and their share is near 0; in Vietnamese prose it is usually 10-20%. A decoded version is
    kept when (1) at least min_foreign of the input's non-space characters are codes of that encoding that
    Unicode Vietnamese never uses, (2) its stop-word share is at least min_gain above that of the input, and
    (3) at least min_marked of its syllables carry a Vietnamese diacritic. Without (1), product lists in
    Unicode Vietnamese with few stop words were "decoded" as VNI ("bò" -> "bị", "Công" -> "Cơng").
    (The share of marked syllables alone does not work: VNI text keeps Latin-1 letters such as "ô", "ó".)
    """
    candidates = [(enc, decode) for enc, decode in (("tcvn3", decode_tcvn3), ("vni", decode_vni))
                  if foreign_share(text, enc) >= min_foreign]
    if not candidates:                           # almost every document stops here
        return text, None
    stop, marked = _shares(text, stopwords)
    if stop >= 0.10 and marked >= min_marked:    # already reads as Vietnamese
        return text, None
    best_text, best_enc, best_stop, best_marked = text, None, stop, marked
    for enc, decode in candidates:
        cand = decode(text)
        if cand != text:
            s, m = _shares(cand, stopwords)
            if s > best_stop:
                best_text, best_enc, best_stop, best_marked = cand, enc, s, m
    if best_enc is not None and best_stop - stop >= min_gain and best_marked >= min_marked:
        return unicodedata.normalize("NFC", best_text), best_enc
    return text, None
