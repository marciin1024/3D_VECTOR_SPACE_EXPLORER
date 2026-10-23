"""Fail (exit code 1) if graph_data.json still contains e-mail addresses or
sender/routing header lines in any string value.

Usage:  python check_pii.py [path/to/graph_data.json]
Run it after validate_json.py and before every commit of the data file.
"""
import json
import re
import sys
from pathlib import Path

EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
HEADER = re.compile(
    r"(?im)^[ \t>]*(from|to|cc|bcc|sender|reply-to|nntp-posting-host)[ \t]*:(?!\s*\[redacted\]).*$"
)


def strings(obj, path=""):
    if isinstance(obj, str):
        yield path, obj
    elif isinstance(obj, dict):
        for k, v in obj.items():
            yield from strings(v, f"{path}.{k}" if path else str(k))
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            yield from strings(v, f"{path}[{i}]")


def main() -> int:
    default = Path(__file__).resolve().parent.parent / "web" / "data" / "graph_data.json"
    p = Path(sys.argv[1]) if len(sys.argv) > 1 else default
    data = json.loads(p.read_text(encoding="utf-8"))
    bad = 0
    for path, s in strings(data):
        for rx, label in ((EMAIL, "email"), (HEADER, "header line")):
            m = rx.search(s)
            if m:
                bad += 1
                if bad <= 10:
                    print(f"  {label} at {path}: {m.group(0)[:70]!r}")
    if bad:
        print(f"PII CHECK FAILED: {bad} hit(s)")
        return 1
    print("PII CHECK GREEN: no e-mail addresses or sender lines in", p.name)
    return 0


if __name__ == "__main__":
    sys.exit(main())
