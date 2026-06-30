"""Read / write fenced ``tags`` blocks inside TAGS.md.

Extracted from the Tkinter ``App`` so that any front-end (Flet, CLI,
tests) can round-trip tag blocks without importing tkinter.
"""

import re


def tag_block(text, header):
    m = re.search(r"##\s*" + header + r".*?```tags\n(.*?)```", text, re.S | re.I)
    return [l.rstrip() for l in (m.group(1).splitlines() if m else []) if l.strip()]


def replace_block(text, header, lines):
    pat = re.compile(r"(##\s*" + header + r".*?```tags\n)(.*?)(```)", re.S | re.I)
    body = "\n".join(x.rstrip() for x in lines if x.strip()) + "\n"
    return pat.sub(lambda m: m.group(1) + body + m.group(3), text, count=1)
