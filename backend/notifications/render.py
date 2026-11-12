"""Turns an email written as plain text into a formatted email and its plain-text copy.

The text marks its own layout, so each email reads naturally where it is written:

    ## Heading            a section heading
    • item                a bullet (a run of them is one list)
    1. item               a numbered item
    [[Label|https://…]]   a button, on a line of its own
    [text](https://…)     a link inside a sentence
    **text**              bold

Paragraphs are separated by a blank line; a single line break stays a line break.
"""
import re
from html import escape

BRAND = "#1e5aa8"
INK = "#0f1b2d"
TEXT = "#334155"

BUTTON = re.compile(r"^\[\[(.+?)\|(.+?)\]\]$")
LINK = re.compile(r"\[([^\]]+)\]\(([^)\s]+)\)")
BOLD = re.compile(r"\*\*(.+?)\*\*")
NUMBERED = re.compile(r"^(\d+)\. (.*)$")


def _inline_html(text: str) -> str:
    out, last = [], 0
    for match in LINK.finditer(text):
        out.append(escape(text[last:match.start()]))
        out.append(f'<a href="{escape(match[2])}" style="color:{BRAND}">{escape(match[1])}</a>')
        last = match.end()
    out.append(escape(text[last:]))
    return BOLD.sub(r"<strong>\1</strong>", "".join(out))


def _inline_text(text: str) -> str:
    return BOLD.sub(r"\1", LINK.sub(lambda m: f"{m[1]} ({m[2]})", text))


def _html_block(lines: list) -> str:
    """One paragraph: headings, lists, buttons and plain lines, in the order written."""
    parts, plain, items, kind = [], [], [], None

    def flush():
        nonlocal plain, items, kind
        if plain:
            parts.append(f'<p style="margin:0 0 14px">{"<br>".join(plain)}</p>')
        if items:
            tag = "ol" if kind == "ol" else "ul"
            lis = "".join(f'<li style="margin:0 0 6px">{i}</li>' for i in items)
            parts.append(f'<{tag} style="margin:0 0 14px;padding-left:22px">{lis}</{tag}>')
        plain, items, kind = [], [], None

    for line in lines:
        button = BUTTON.match(line)
        numbered = NUMBERED.match(line)
        if line.startswith("## "):
            flush()
            parts.append(f'<h3 style="margin:22px 0 8px;font-size:16px;color:{INK}">{_inline_html(line[3:])}</h3>')
        elif button:
            flush()
            parts.append(
                f'<p style="margin:6px 0 18px"><a href="{escape(button[2])}" style="display:inline-block;'
                f'background:{BRAND};color:#ffffff;text-decoration:none;font-weight:bold;padding:11px 22px;'
                f'border-radius:6px">{escape(button[1])}</a></p>')
        elif line.startswith("• ") or numbered:
            this = "ol" if numbered else "ul"
            if plain or (items and kind != this):
                flush()
            kind = this
            items.append(_inline_html(numbered[2] if numbered else line[2:]))
        else:
            if items:
                flush()
            plain.append(_inline_html(line))
    flush()
    return "".join(parts)


def _text_line(line: str) -> str:
    button = BUTTON.match(line)
    if button:
        return f"{button[1]}: {button[2]}"
    if line.startswith("## "):
        return line[3:]
    return _inline_text(line)


def paragraphs(body: str) -> list:
    return [p.splitlines() for p in re.split(r"\n\s*\n", body.strip()) if p.strip()]


def render(body: str) -> tuple:
    """(plain text, HTML) for one email body."""
    blocks = paragraphs(body)
    text = "\n\n".join("\n".join(_text_line(line) for line in block) for block in blocks) + "\n"
    content = "".join(_html_block(block) for block in blocks)
    html = (
        '<!doctype html><html><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1"></head>'
        f'<body style="margin:0;padding:0;background:#f3f5f8">'
        '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#f3f5f8">'
        '<tr><td align="center" style="padding:24px 12px">'
        '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width:600px;'
        'background:#ffffff;border:1px solid #e2e8f0;border-radius:8px">'
        f'<tr><td style="padding:18px 28px;border-bottom:3px solid {BRAND};font-family:Arial,Helvetica,sans-serif;'
        f'font-size:14px;font-weight:bold;letter-spacing:2px;color:{INK}">UNITED GROUP</td></tr>'
        f'<tr><td style="padding:26px 28px 14px;font-family:Arial,Helvetica,sans-serif;font-size:15px;'
        f'line-height:1.6;color:{TEXT}">{content}</td></tr>'
        '</table></td></tr></table></body></html>'
    )
    return text, html
