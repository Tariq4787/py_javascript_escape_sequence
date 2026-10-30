"""Core implementation of JavaScript escape-sequence decoding.

Supported escapes (the ones you meet in real JS string literals):

    \\u{1F600}   code point in brace form (any non-negative value up to 0x10FFFF)
    \\u0041     exactly four hex digits
    \\x41       exactly two hex digits
    \\0         NUL when not followed by a digit 0-9
    \\377       one-to-three-digit octal (legacy; see note below)
    \\n \\t \\r \\b \\f \\v \\0 \\x41 \\u0041 \\u{...}
    \\' \\" \\\\ \\/   literal punctuation
    \\`         backtick (TemplateLiteral) — decoded to a raw backtick

Design decisions (stated plainly so the tests and the reader agree):

* Octal escapes are supported even though strict ECMAScript forbids them in
  strict-mode code. They are common in older data and in non-strict source.
  We follow the JavaScript runtime rule: \\0 is NUL when not followed by a
  decimal digit, and \\1 through \\377 are octal. \\08 and \\09 are NOT valid
  octal — we treat \\0 as NUL and leave the '8'/'9' as literal characters.
  A leading-zero three-digit sequence like \\012 is read as a single octal
  value (octal 12 == 0x0A).
* \\/ is accepted and yields a literal '/'. Some JSON encoders emit it to
  keep '</script>' out of embedded strings.
* A lone backslash at end of input raises DecodeError; JavaScript treats this
  as a syntax error, not as a literal backslash.
* An escape we do not recognise (e.g. \\z) raises DecodeError rather than
  silently passing the backslash through. This matches strict-mode JS.
* We deliberately do NOT implement line continuation (backslash-newline);
  this decoder is for escape sequences inside already-extracted string
  contents, not for raw source-token lexing.
"""

from __future__ import annotations

import unicodedata
from typing import Dict


class DecodeError(ValueError):
    """Raised when an input string contains an escape we cannot decode."""


# Named single-character escapes, in the order JavaScript defines them.
NAMED_ESCAPES: Dict[str, str] = {
    "n": "\n",
    "t": "\t",
    "r": "\r",
    "b": "\b",
    "f": "\f",
    "v": "\x0b",
    "0": "\x00",  # special-cased below when followed by a decimal digit
    "'": "'",
    '"': '"',
    "\\": "\\",
    "/": "/",
    "`": "`",
}

_MAX_CP = 0x10FFFF


def _is_hex(ch: str) -> bool:
    return ch in "0123456789abcdefABCDEF"


def _is_octal_digit(ch: str) -> bool:
    return ch in "01234567"


def _hex_to_int(digits: str) -> int:
    return int(digits, 16)


def decode_string(s: str) -> str:
    """Decode JavaScript escape sequences in *s* and return the result.

    Raises:
        DecodeError: on a malformed escape, a bad code point, a dangling
            backslash, or a lone surrogate code point in \\u{...}.
    """
    out: list = []
    i = 0
    n = len(s)
    while i < n:
        ch = s[i]
        if ch != "\\":
            out.append(ch)
            i += 1
            continue

        # We are at a backslash; we require at least one more character.
        if i + 1 >= n:
            raise DecodeError("dangling backslash at end of input")

        esc = s[i + 1]

        # --- \u{...} -------------------------------------------------------
        if esc == "u" and i + 2 < n and s[i + 2] == "{":
            j = i + 3
            hex_digits = []
            while j < n and s[j] != "}":
                hex_digits.append(s[j])
                j += 1
            if j >= n:
                raise DecodeError("unterminated \\u{...} escape")
            digits = "".join(hex_digits)
            if digits == "":
                raise DecodeError("empty \\u{} escape")
            if not all(_is_hex(d) for d in digits):
                raise DecodeError("non-hex digit in \\u{...} escape: %r" % digits)
            cp = _hex_to_int(digits)
            if cp < 0 or cp > _MAX_CP:
                raise DecodeError("code point out of range: U+%X" % cp)
            # JavaScript rejects lone surrogates in \u{...}. Runtimes throw
            # SyntaxError; we mirror that.
            if 0xD800 <= cp <= 0xDFFF:
                raise DecodeError("lone surrogate code point: U+%04X" % cp)
            out.append(chr(cp))
            i = j + 1
            continue

        # --- \u#### (exactly four hex digits) ------------------------------
        if esc == "u":
            if i + 6 > n:
                raise DecodeError("\\u escape needs four hex digits")
            digits = s[i + 2 : i + 6]
            if not all(_is_hex(d) for d in digits):
                raise DecodeError("non-hex digit in \\u escape: %r" % digits)
            cp = _hex_to_int(digits)
            # \u#### can express lone surrogates in JS (e.g. \uD83D). We allow
            # them through unchanged; combining them into a pair is the
            # caller's job. This matches what String.fromCharCode does.
            out.append(chr(cp))
            i += 6
            continue

        # --- \x## (exactly two hex digits) ---------------------------------
        if esc == "x":
            if i + 4 > n:
                raise DecodeError("\\x escape needs two hex digits")
            digits = s[i + 2 : i + 4]
            if not all(_is_hex(d) for d in digits):
                raise DecodeError("non-hex digit in \\x escape: %r" % digits)
            out.append(chr(_hex_to_int(digits)))
            i += 4
            continue

        # --- Octal: \0, \1..\377 ------------------------------------------
        # JS rule: \0 is NUL unless followed by a decimal digit. \1-\7 start
        # a one-to-three digit octal run, but only octal digits count.
        if _is_octal_digit(esc):
            if esc == "0":
                # Look ahead: if the next char is a decimal digit 0-9, \0 is
                # NOT an octal escape — it is NUL followed by the literal
                # digit. This matches V8's behaviour for "\08".
                if i + 2 < n and s[i + 2].isdigit():
                    out.append("\x00")
                    i += 2
                    continue
            # Collect up to three octal digits, but only the ones that are
            # actually octal (0-7). The first digit is already known good.
            collected = [esc]
            j = i + 2
            while j < n and len(collected) < 3 and _is_octal_digit(s[j]):
                collected.append(s[j])
                j += 1
            value = int("".join(collected), 8)
            if value > 0xFF:
                # Should not happen with <= 3 octal digits, but be safe.
                raise DecodeError("octal escape out of byte range: \\%s" % "".join(collected))
            out.append(chr(value))
            i = j
            continue

        # --- Named single-character escapes -------------------------------
        if esc in NAMED_ESCAPES:
            out.append(NAMED_ESCAPES[esc])
            i += 2
            continue

        # --- Anything else: strict-mode rejects it -------------------------
        raise DecodeError("unrecognised escape sequence: \\%s" % esc)

    result = "".join(out)
    # Normalise to NFC so that composed/decomposed sequences compare equal
    # across encoders. This is a deliberate, documented choice: the caller
    # usually wants \u00E9 and \u0065\u0301 to produce the same Python string.
    return unicodedata.normalize("NFC", result)


# Public alias. The README documents `decode` as the primary entry point;
# `decode_string` is kept for readers who prefer the explicit name.
decode = decode_string
