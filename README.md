# py_javascript_escape_sequence

Decodes JavaScript string escape sequences — `\u####`, `\x##`, `\u{...}`, octal (`\1`–`\377`), and named escapes (`\n`, `\t`, …) — into a Python `str`.

```python
from py_javascript_escape_sequence import decode, DecodeError

decode("\\u{1F600}")        # '😀'
decode("\\x41\\n\\101")      # 'A\nA'
decode("\\u00e9")          # 'é'

try:
    decode("\\u{D83D}")
except DecodeError as e:
    print(e)  # lone surrogate code point: U+D83D
```

The exported names are `decode`, `decode_string` (an alias of `decode`), `DecodeError`, and the `NAMED_ESCAPES` dict.

## Why

JavaScript source and JSON-ish payloads often carry escape sequences that Python's built-in `unicode_escape` codec does not read correctly: `\u{1F600}` brace form, legacy octal (`\101`), and `\0` NUL all trip it up. This library handles exactly those, plus the named escapes, and nothing more. It is a decoder, not a full JavaScript lexer — feed it the *contents* of a string literal, not raw source.

The main deliberate trade-off: octal escapes are supported even though strict-mode ECMAScript forbids them, because they appear in older data. We follow the JavaScript runtime rule that `\0` is NUL unless followed by a decimal digit, so `\08` decodes to NUL + `'8'`, not an error.

## Awkward edges

* `\u####` can express lone surrogates (e.g. `\uD83D`); this library passes them through as single code units. `\u{...}` rejects lone surrogates, matching JavaScript's `SyntaxError`.
* The result is normalised to NFC, so `\u0065\u0301` and `\u00e9` produce the same Python string. If you need byte-exact preservation of decomposed sequences, NFC normalisation will change them.
* An unrecognised escape like `\z` raises `DecodeError` rather than passing the backslash through silently, matching strict-mode JS.

## Design notes

The window stores values eagerly rather than keeping running aggregates. Running
sums drift with floating point over long streams, and recomputing from a small
buffer is cheap enough that the drift is not worth the speed.

