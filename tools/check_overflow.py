#!/usr/bin/env python3
"""Report boxes that stick out past the A4 content area of the survey PDF.

Usage: python3 tools/check_overflow.py
Builds the same document build_pdf.py builds, lays it out, and walks the box
tree of every page looking for boxes whose right edge exceeds the page content
edge. Prints one line per offending page with the worst overflow in mm.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build_pdf  # noqa: E402  (same document, same CSS)

import weasyprint  # noqa: E402


def document():
    used = set()
    parts, toc = [], []
    for i, f in enumerate(build_pdf.chapter_files()):
        html, t = build_pdf.convert(f, used, first=(i == 0))
        parts.append(html)
        toc.extend(t)
    toc_html = '<div id="toc"><h1 class="first">目录</h1><ul>' + ''.join(
        f'<li class="lvl{l}"><a href="#{s}">{t}</a></li>' for l, t, s in toc) + '</ul></div>'
    body = build_pdf.cover_html() + toc_html + ''.join(parts)
    doc = f'<html><head><meta charset="utf-8"></head><body>{body}</body></html>'
    return weasyprint.HTML(string=doc, base_url=build_pdf.ROOT).render(
        stylesheets=[weasyprint.CSS(string=build_pdf.CSS)])


def walk(box):
    yield box
    for child in getattr(box, 'children', ()) or ():
        yield from walk(child)


def label(box):
    el = getattr(box, 'element_tag', None) or '?'
    txt = getattr(box, 'text', None)
    if txt:
        return f'{el}:{txt.strip()[:40]!r}'
    return el


def main():
    pages = document().pages
    PX_PER_MM = 96 / 25.4
    bad = 0
    for n, page in enumerate(pages, 1):
        pb = page._page_box
        right = pb.content_box_x() + pb.width
        worst, worst_box = 0.0, None
        for box in walk(pb):
            w = getattr(box, 'width', None)
            x = getattr(box, 'position_x', None)
            if not isinstance(w, (int, float)) or not isinstance(x, (int, float)):
                continue
            over = (x + w) - right
            if over > worst:
                worst, worst_box = over, box
        if worst > 0.5:  # ignore sub-half-pixel rounding
            bad += 1
            print(f'p{n:>3}  超出 {worst / PX_PER_MM:6.1f} mm  {label(worst_box)}')
    print(f'--- {len(pages)} 页，{bad} 页越界 ---')
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
