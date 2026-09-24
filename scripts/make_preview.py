"""Картинка-превью для ссылки (web/preview.png, 1200x630).

Ее показывают телеграм, директ и другие мессенджеры, когда в них
вставляют ссылку на страницу. Рисуется из HTML в Chromium:

    python3 scripts/make_preview.py

Подпись берется из web/content/site.json (имя автора и инстаграм), так что
после заполнения этого файла картинку стоит пересобрать.
"""
import asyncio
import json
import math
import os
from pathlib import Path

from playwright.async_api import async_playwright

ROOT = Path(__file__).resolve().parent.parent
WEB = ROOT / 'web'
SIGNS = '♈♉♊♋♌♍♎♏♐♑♒♓'
COLORS = ['#b5563a', '#6f7b3a', '#4f7a94', '#4a5f9c']


def ring():
    parts = []
    for i, glyph in enumerate(SIGNS):
        angle = math.pi + i * math.pi / 6 + math.pi / 12
        x = 250 + 205 * math.cos(angle)
        y = 250 - 205 * math.sin(angle)
        parts.append(f'<text x="{x:.1f}" y="{y:.1f}" fill="{COLORS[i % 4]}">{glyph}︎</text>')
        a2 = math.pi + i * math.pi / 6
        parts.append(f'<line x1="{250 + 180 * math.cos(a2):.1f}" y1="{250 - 180 * math.sin(a2):.1f}" '
                     f'x2="{250 + 232 * math.cos(a2):.1f}" y2="{250 - 232 * math.sin(a2):.1f}"/>')
    return '\n'.join(parts)


def page():
    site = json.loads((WEB / 'content' / 'site.json').read_text(encoding='utf-8'))
    author = site.get('author', {})
    by = ' · '.join(x for x in [author.get('name', ''),
                                 ('@' + author['instagram'].lstrip('@')) if author.get('instagram') else ''] if x)
    return f'''<!doctype html><html><head><meta charset="utf-8"><style>
    body {{ margin:0; width:1200px; height:630px; background:#fbf9f7; font-family:-apple-system,'Segoe UI',Roboto,sans-serif; color:#241f1b; display:flex; align-items:center; }}
    .text {{ padding-left:80px; width:600px; }}
    h1 {{ font-size:68px; line-height:1.05; margin:0 0 24px; letter-spacing:-.02em; }}
    p {{ font-size:30px; line-height:1.35; margin:0; color:#6d645b; }}
    .by {{ margin-top:36px; font-size:26px; color:#7c5a3a; font-weight:600; }}
    svg {{ width:500px; height:500px; margin-left:20px; }}
    svg text {{ font-size:38px; text-anchor:middle; dominant-baseline:central; font-family:'Noto Sans Symbols 2','Noto Sans Symbols','DejaVu Sans',sans-serif; }}
    svg line, svg circle {{ stroke:#e2dbd2; stroke-width:2; fill:none; }}
    </style></head><body>
    <div class="text"><h1>Натальная карта</h1>
    <p>Разбор по темам: характер, деньги, отношения, предназначение. И что из неба заденет именно тебя.</p>
    {f'<div class="by">{by}</div>' if by else ''}</div>
    <svg viewBox="0 0 500 500"><circle cx="250" cy="250" r="232"/><circle cx="250" cy="250" r="180"/>
    <circle cx="250" cy="250" r="110" style="stroke:#7c5a3a;stroke-width:3"/>{ring()}</svg>
    </body></html>'''


async def main():
    html = WEB / '_preview.html'
    html.write_text(page(), encoding='utf-8')
    try:
        async with async_playwright() as p:
            executable = os.environ.get('CHROMIUM')
            browser = await p.chromium.launch(executable_path=executable, args=['--no-sandbox']) \
                if executable else await p.chromium.launch()
            tab = await browser.new_page(viewport={'width': 1200, 'height': 630})
            await tab.goto(html.as_uri())
            await tab.screenshot(path=str(WEB / 'preview.png'))
            await browser.close()
    finally:
        html.unlink()


if __name__ == '__main__':
    asyncio.run(main())
