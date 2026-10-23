"""Redaction of personal data from the text shown in the app.

Applied at JSON export time only, to the display fields ("name", "text").
Embeddings, clusters, neighbours and TF-IDF labels are computed from the
original cleaned text, so every number in the report stays unchanged.
"""
import re

# Sender / routing lines that survive inside forwarded or quoted posts,
# e.g.  From: "Name" <name@host>   or   >> From: name@host
_HEADER_LINE = re.compile(
    r"(?im)^(?P<prefix>[ \t>]*)(?P<key>from|to|cc|bcc|sender|reply-to|"
    r"nntp-posting-host)[ \t]*:.*$"
)
_REDACTED_HEADER = re.compile(
    r"(?i)^[ \t>]*(from|to|cc|bcc|sender|reply-to|nntp-posting-host)"
    r"[ \t]*:[ \t]*\[redacted\][ \t]*$"
)
_EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")


def redact(text: str) -> str:
    """Replace sender/routing lines and e-mail addresses."""
    text = _HEADER_LINE.sub(
        lambda m: f"{m.group('prefix')}{m.group('key')}: [redacted]", text)
    return _EMAIL.sub("[email]", text)


def display_title(text: str, max_chars: int) -> str:
    """First non-empty line of the redacted text that is not a redacted
    sender line (same rule as the original title, minus the personal data)."""
    for line in redact(text).splitlines():
        s = line.strip().lstrip(">").strip()
        if s and not _REDACTED_HEADER.match(line):
            return s[:max_chars]
    return "untitled"
