"""Картинка-превью для ссылки (web/preview.png, 1200x630).

Ее показывают телеграм, директ и другие мессенджеры, когда в них
вставляют ссылку на страницу. Рисуется из HTML в Chromium:

    python3 scripts/make_preview.py

Подпись берется из web/content/site.json (имя автора и инстаграм), так что
после заполнения этого файла картинку стоит пересобрать.
"""
import asyncio
import json
import os
from pathlib import Path

from playwright.async_api import async_playwright

ROOT = Path(__file__).resolve().parent.parent
WEB = ROOT / 'web'


def page():
    site = json.loads((WEB / 'content' / 'site.json').read_text(encoding='utf-8'))
    author = site.get('author', {})
    nick = ('@' + author['instagram'].lstrip('@')) if author.get('instagram') else ''
    logo = (WEB / 'logo.svg').read_text(encoding='utf-8').replace('currentColor', '#a8875a')
    fonts = WEB.as_uri() + '/fonts/'
    return f'''<!doctype html><html><head><meta charset="utf-8"><style>
    @font-face {{ font-family: C; src: url('{fonts}CG-400.woff2'); }}
    @font-face {{ font-family: C; src: url('{fonts}CGi-400.woff2'); font-style: italic; }}
    body {{ margin:0; width:1200px; height:630px; background:#f5f1e8; color:#1f1a15;
           font-family: -apple-system, 'Segoe UI', Roboto, sans-serif; display:flex; align-items:center; }}
    .frame {{ position:absolute; inset:28px; border:1.5px solid #a8875a; }}
    .text {{ padding-left:96px; width:640px; position:relative; }}
    .brand {{ display:flex; align-items:center; gap:14px; font-weight:600; font-size:20px; letter-spacing:.42em; margin-bottom:44px; }}
    .brand svg {{ width:44px; height:44px; }}
    h1 {{ font: 400 92px/1 C, serif; margin:0 0 26px; }}
    h1 em {{ color:#8a6c43; }}
    p {{ font: italic 400 34px/1.3 C, serif; margin:0; color:#7a6f63; }}
    .by {{ margin-top:34px; font-size:22px; letter-spacing:.12em; color:#8a6c43; }}
    .wheel {{ position:relative; width:430px; height:430px; margin-left:10px; }}
    .wheel svg {{ width:100%; height:100%; }}
    .wheel svg g {{ stroke-width:1.1; }}
    </style></head><body><div class="frame"></div>
    <div class="text"><div class="brand">{logo}LUME</div>
    <h1>Натальная <em>карта</em></h1>
    <p>Характер, деньги, отношения, предназначение - и что из неба заденет именно тебя</p>
    {f'<div class="by">{nick}</div>' if nick else ''}</div>
    <div class="wheel">{logo}</div>
    </body></html>'''


async def main():
    html = WEB / '_preview.html'
    html.write_text(page(), encoding='utf-8')
    # шрифты грузятся по file://, им нужно чуть времени
    try:
        async with async_playwright() as p:
            executable = os.environ.get('CHROMIUM')
            browser = await p.chromium.launch(executable_path=executable, args=['--no-sandbox']) \
                if executable else await p.chromium.launch()
            tab = await browser.new_page(viewport={'width': 1200, 'height': 630})
            await tab.goto(html.as_uri())
            await tab.wait_for_timeout(500)
            await tab.screenshot(path=str(WEB / 'preview.png'))
            await browser.close()
    finally:
        html.unlink()


if __name__ == '__main__':
    asyncio.run(main())
