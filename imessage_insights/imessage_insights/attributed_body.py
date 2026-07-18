"""Decode the ``attributedBody`` column of the Messages database.

On modern macOS the plain-text ``text`` column of a message is often empty and
the real content lives in ``attributedBody`` — an ``NSAttributedString`` encoded
in Apple's legacy ``typedstream`` (NSArchiver) format. We don't need a full
typedstream parser; we only need the primary string, which sits right after the
``NSString`` class marker as a length-prefixed UTF-8 run.

The parser is deliberately defensive: on anything unexpected it returns ``None``
so callers can fall back to the plain ``text`` column.
"""

from __future__ import annotations

# The NSString value is emitted as: b"NSString" ... 0x2b <length> <utf-8 bytes>.
# 0x2b ('+') is the typedstream tag that introduces the encoded string bytes.
_NSSTRING = b"NSString"


def _read_varint(blob: bytes, i: int) -> tuple[int, int]:
    """Read a typedstream length starting at ``i``.

    Returns ``(value, next_index)``. Lengths < 0x80 are a single byte; 0x81
    signals a 2-byte little-endian short, 0x82 a 4-byte little-endian int.
    """
    first = blob[i]
    i += 1
    if first < 0x80:
        return first, i
    if first == 0x81:
        return int.from_bytes(blob[i : i + 2], "little"), i + 2
    if first == 0x82:
        return int.from_bytes(blob[i : i + 4], "little"), i + 4
    # Anything else we don't understand — treat the byte itself as the length.
    return first, i


def decode(blob: bytes | None) -> str | None:
    """Extract the message text from an ``attributedBody`` blob.

    Returns ``None`` if ``blob`` is empty or the string can't be located.
    """
    if not blob:
        return None

    start = blob.find(_NSSTRING)
    if start == -1:
        return None

    # Find the string-tag (0x2b) that follows the class name.
    plus = blob.find(b"\x2b", start + len(_NSSTRING))
    if plus == -1:
        return None

    try:
        length, i = _read_varint(blob, plus + 1)
        if length <= 0 or i + length > len(blob):
            return None
        text = blob[i : i + length].decode("utf-8", errors="replace")
    except (IndexError, ValueError):
        return None

    text = text.strip("\x00").strip()
    return text or None
