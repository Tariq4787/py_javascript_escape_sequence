"""py_javascript_escape_sequence

A focused decoder for JavaScript string escape sequences.
"""

from .core import decode, decode_string, DecodeError, NAMED_ESCAPES

__all__ = ["decode", "decode_string", "DecodeError", "NAMED_ESCAPES"]
