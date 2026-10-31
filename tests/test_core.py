"""Tests for py_javascript_escape_sequence.core.

Run with:
    PYTHONPATH=src python -m unittest discover -s tests
"""

import unittest

from py_javascript_escape_sequence.core import (
    decode,
    decode_string,
    DecodeError,
    NAMED_ESCAPES,
)


class TestNamedEscapes(unittest.TestCase):
    def test_newline(self):
        self.assertEqual(decode("a\\nb"), "a\nb")

    def test_tab(self):
        self.assertEqual(decode("\\t"), "\t")

    def test_carriage_return(self):
        self.assertEqual(decode("\\r"), "\r")

    def test_backspace(self):
        self.assertEqual(decode("\\b"), "\b")

    def test_formfeed(self):
        self.assertEqual(decode("\\f"), "\f")

    def test_vertical_tab(self):
        self.assertEqual(decode("\\v"), "\x0b")

    def test_quote_variants(self):
        self.assertEqual(decode("\\\\"), "\\")
        self.assertEqual(decode("\\'"), "'")
        self.assertEqual(decode('\\"'), '"')
        self.assertEqual(decode("\\/"), "/")
        self.assertEqual(decode("\\`"), "`")

    def test_named_table_keys(self):
        # Confirm the exported mapping has the documented keys.
        for k in ["n", "t", "r", "b", "f", "v", "'", '"', "\\", "/", "`"]:
            self.assertIn(k, NAMED_ESCAPES)


class TestUnicodeEscapes(unittest.TestCase):
    def test_u_four_digits_basic(self):
        self.assertEqual(decode("\\u0041"), "A")

    def test_u_four_digits_lowercase(self):
        self.assertEqual(decode("\\u00e9"), "é")

    def test_u_four_digits_uppercase(self):
        self.assertEqual(decode("\\u00E9"), "é")

    def test_u_brace_single_ascii(self):
        self.assertEqual(decode("\\u{41}"), "A")

    def test_u_brace_emoji(self):
        self.assertEqual(decode("\\u{1F600}"), "😀")

    def test_u_brace_leading_zeros(self):
        self.assertEqual(decode("\\u{000041}"), "A")

    def test_u_brace_max_code_point(self):
        self.assertEqual(decode("\\u{10FFFF}"), "\U0010FFFF")

    def test_u_four_digits_surrogate_high(self):
        # \uD83D is a high surrogate; we pass it through as a lone code unit.
        self.assertEqual(decode("\\uD83D"), "\ud83d")

    def test_u_brace_rejects_lone_surrogate(self):
        with self.assertRaises(DecodeError):
            decode("\\u{D83D}")

    def test_u_brace_rejects_out_of_range(self):
        with self.assertRaises(DecodeError):
            decode("\\u{110000}")

    def test_u_brace_empty(self):
        with self.assertRaises(DecodeError):
            decode("\\u{}")

    def test_u_brace_unterminated(self):
        with self.assertRaises(DecodeError):
            decode("\\u{41")

    def test_u_brace_non_hex(self):
        with self.assertRaises(DecodeError):
            decode("\\u{ZZ}")

    def test_u_four_short(self):
        with self.assertRaises(DecodeError):
            decode("\\u41")

    def test_u_four_non_hex(self):
        with self.assertRaises(DecodeError):
            decode("\\u00ZZ")


class TestHexEscapes(unittest.TestCase):
    def test_x_basic(self):
        self.assertEqual(decode("\\x41"), "A")

    def test_x_lowercase(self):
        self.assertEqual(decode("\\x61"), "a")

    def test_x_uppercase(self):
        self.assertEqual(decode("\\xFF"), "ÿ")

    def test_x_short(self):
        with self.assertRaises(DecodeError):
            decode("\\x4")

    def test_x_non_hex(self):
        with self.assertRaises(DecodeError):
            decode("\\xZZ")


class TestOctalEscapes(unittest.TestCase):
    def test_nul_plain(self):
        self.assertEqual(decode("\\0"), "\x00")

    def test_nul_followed_by_letter(self):
        self.assertEqual(decode("\\0a"), "\x00a")

    def test_nul_followed_by_decimal_eight(self):
        # \08 is NUL then literal '8', not an octal escape.
        self.assertEqual(decode("\\08"), "\x008")

    def test_nul_followed_by_decimal_nine(self):
        self.assertEqual(decode("\\09"), "\x009")

    def test_single_digit_octal(self):
        self.assertEqual(decode("\\1"), "\x01")

    def test_two_digit_octal(self):
        self.assertEqual(decode("\\12"), "\x0a")

    def test_three_digit_octal(self):
        self.assertEqual(decode("\\123"), "\x53")  # octal 123 == 0x53 == 'S'

    def test_three_digit_max(self):
        self.assertEqual(decode("\\377"), "\xff")

    def test_octal_then_text(self):
        self.assertEqual(decode("\\101BC"), "ABC")

    def test_octal_stops_at_non_octal(self):
        # \101 is octal, '8' is not octal so it is left literal.
        self.assertEqual(decode("\\1018"), "A8")


class TestPlainAndMixed(unittest.TestCase):
    def test_plain_string_unchanged(self):
        self.assertEqual(decode("hello world"), "hello world")

    def test_empty_string(self):
        self.assertEqual(decode(""), "")

    def test_mixed(self):
        self.assertEqual(decode("\\u0048\\x65\\154\\154\\u006F"), "Hello")

    def test_emoji_in_sentence(self):
        self.assertEqual(decode("Hi \\u{1F600}!"), "Hi 😀!")

    def test_decode_alias_same_function(self):
        self.assertIs(decode, decode_string)


class TestErrorCases(unittest.TestCase):
    def test_dangling_backslash(self):
        with self.assertRaises(DecodeError):
            decode("abc\\")

    def test_unknown_escape(self):
        with self.assertRaises(DecodeError):
            decode("\\z")

    def test_unknown_escape_letter(self):
        with self.assertRaises(DecodeError):
            decode("\\q")


class TestNormalization(unittest.TestCase):
    def test_decomposed_normalised_to_nfc(self):
        # \u0065 (e) + \u0301 (combining acute) should compose to é under NFC.
        self.assertEqual(decode("\\u0065\\u0301"), "é")

    def test_precomposed_stays(self):
        self.assertEqual(decode("\\u00e9"), "é")


if __name__ == "__main__":
    unittest.main()
