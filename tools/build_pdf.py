#!/usr/bin/env python3
"""Build a printable A4 PDF of the survey from README.md and chapters 01–16.

Usage: python3 tools/build_pdf.py [output.pdf]
Requires: python-markdown, weasyprint, and the "Noto Sans CJK SC" font installed.
"""
import re
import sys
import glob
import os
import datetime

import markdown
import weasyprint

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, 'nga-survey.pdf')

CSS = """
@page {
  size: A4;
  margin: 16mm 14mm 18mm 14mm;
  @bottom-center { content: counter(page) " / " counter(pages); font-size: 8pt; color: #666; }
  @top-right { content: "Jev 类快思考模型与快/慢协同框架调研"; font-size: 7.5pt; color: #888; }
}
@page :first { @top-right { content: none; } }
body { font-family: "Noto Sans CJK SC", "Noto Sans", sans-serif; font-size: 9.2pt; line-height: 1.42; color: #111; }
h1 { font-size: 17pt; margin: 0 0 6pt 0; page-break-before: always; border-bottom: 1.5pt solid #333; padding-bottom: 3pt; }
h1.first { page-break-before: avoid; }
h2 { font-size: 12.5pt; margin: 12pt 0 4pt 0; border-bottom: 0.6pt solid #999; padding-bottom: 2pt; }
h3 { font-size: 10.5pt; margin: 9pt 0 3pt 0; }
p { margin: 3pt 0 5pt 0; text-align: justify; }
ul, ol { margin: 2pt 0 5pt 0; padding-left: 16pt; }
li { margin: 1.5pt 0; }
blockquote { margin: 4pt 0 6pt 0; padding: 3pt 8pt; border-left: 2.5pt solid #999; background: #f4f4f4; color: #333; }
code { font-family: "DejaVu Sans Mono", monospace; font-size: 7.8pt; background: #f0f0f0; padding: 0 2px; }
pre { font-family: "DejaVu Sans Mono", monospace; font-size: 7.6pt; background: #f4f4f4; padding: 5pt; white-space: pre-wrap; word-break: break-all; }
table { border-collapse: collapse; width: 100%; margin: 4pt 0 7pt 0; font-size: 7.6pt; line-height: 1.3; page-break-inside: auto; }
tr { page-break-inside: avoid; }
th, td { border: 0.5pt solid #888; padding: 2pt 3pt; vertical-align: top; word-break: break-word; }
th { background: #e8e8e8; font-weight: bold; }
a { color: #0b4d8c; text-decoration: none; }
strong { font-weight: bold; }
hr { border: 0; border-top: 0.6pt solid #aaa; margin: 8pt 0; }
#toc { page-break-before: always; }
#toc ul { list-style: none; padding-left: 0; }
#toc li { margin: 2pt 0; }
#toc li.lvl2 { padding-left: 14pt; font-size: 8.6pt; }
#toc a::after { content: leader(". ") target-counter(attr(href), page); }
.cover { text-align: center; margin-top: 70mm; }
.cover h1 { border: 0; font-size: 22pt; page-break-before: avoid; }
.cover p { text-align: center; color: #444; }
"""


def slug(text, used):
    s = re.sub(r'[^\w一-鿿]+', '-', text).strip('-').lower() or 'sec'
    base, n = s, 1
    while s in used:
        n += 1
        s = f'{base}-{n}'
    used.add(s)
    return s


def chapter_files():
    files = [os.path.join(ROOT, 'README.md')]
    files += sorted(glob.glob(os.path.join(ROOT, '[0-9][0-9]-*.md')))
    return files


def convert(path, used, first):
    md = open(path, encoding='utf-8').read()
    # Internal links between chapter files -> anchors to the chapter heading.
    md = re.sub(r'\]\(((?:\d\d-[\w-]+|README)\.md)(#[^)]*)?\)', lambda m: f'](#file-{m.group(1).replace(".", "-")})', md)
    md = md.replace('](nga-survey.pdf)', '](#file-README-md)')
    html = markdown.markdown(md, extensions=['tables', 'fenced_code', 'sane_lists'])
    toc = []
    file_anchor = 'file-' + os.path.basename(path).replace('.', '-')

    def heading(m):
        level, text = m.group(1), m.group(2)
        plain = re.sub(r'<[^>]+>', '', text)
        sid = slug(plain, used)
        cls = ' class="first"' if (first and level == '1') else ''
        extra = f'<a id="{file_anchor}"></a>' if level == '1' else ''
        if level in ('1', '2'):
            toc.append((level, plain, sid))
        return f'{extra}<h{level} id="{sid}"{cls}>{text}</h{level}>'

    html = re.sub(r'<h([12])>(.*?)</h\1>', heading, html, flags=re.S)
    return html, toc


def main():
    used = set()
    parts, toc = [], []
    for i, f in enumerate(chapter_files()):
        html, t = convert(f, used, first=(i == 0))
        parts.append(html)
        toc.extend(t)
    today = datetime.date.today().isoformat()
    cover = (f'<div class="cover"><h1>下一代 Agent 技术路线调研</h1>'
             f'<p>Jev 类快思考模型（System One）与快 / 慢协同框架</p>'
             f'<p>调研报告 · 仅分析与调研，不含训练方案</p>'
             f'<p>生成日期：{today}</p></div>')
    toc_html = '<div id="toc"><h1 class="first">目录</h1><ul>' + ''.join(
        f'<li class="lvl{l}"><a href="#{s}">{t}</a></li>' for l, t, s in toc) + '</ul></div>'
    body = cover + toc_html + ''.join(parts)
    doc = f'<html><head><meta charset="utf-8"><title>Jev 类快思考模型调研报告</title></head><body>{body}</body></html>'
    weasyprint.HTML(string=doc, base_url=ROOT).write_pdf(OUT, stylesheets=[weasyprint.CSS(string=CSS)])
    print(OUT, os.path.getsize(OUT) // 1024, 'KB')


if __name__ == '__main__':
    main()
