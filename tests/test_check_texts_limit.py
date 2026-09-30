"""Проверка под рилс не просит у сервера больше текстов, чем он отдает.

Сервер (server/texts.js) отдает не больше LIMITS.checks текстов проверки за
запрос, лишние ключи молча отбрасывает. Страница просит только варианты,
которые выпадут карте, и это число обязано влезать в предел.
"""
import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent

SCRIPT = """
import fs from 'node:fs';
import { pathToFileURL } from 'node:url';
const m = await import(pathToFileURL(process.argv[2]).href);
const full = JSON.parse(fs.readFileSync(process.argv[3], 'utf8'));
const BODIES = ['sun', 'moon', 'mercury', 'venus', 'mars', 'jupiter', 'saturn', 'uranus', 'neptune', 'pluto'];
const chart = (exactTime, house, sign) => ({
  exactTime,
  houseSystem: 'placidus',
  houses: new Map([['placidus', { cusps: Array.from({ length: 12 }, (_, i) => (i * 30 + sign * 30) % 360) }]]),
  angles: { asc: sign * 30, mc: (sign * 30 + 270) % 360 },
  aspects: [],
  // Все точки в одном градусе: у ретроградной планеты это худший случай -
  // в зоне разворота сразу все личные точки.
  positions: new Map(BODIES.map((b) => [b, { house, sign: { index: sign }, longitude: sign * 30 + 5, body: { name: b } }])),
});
const out = {};
for (const check of m.stripCheckTexts(full)) {
  let most = 0;
  for (let house = 1; house <= 12; house += 1) {
    for (const exact of [true, false]) {
      most = Math.max(most, m.neededCheckTexts(check, chart(exact, house, house - 1)).length);
    }
  }
  out[check.key] = most;
}
console.log(JSON.stringify(out));
"""


@pytest.mark.skipif(shutil.which("node") is None, reason="нужен node")
def test_check_requests_fit_server_limit(tmp_path):
    limit = int(re.search(r"checks:\s*(\d+)", (ROOT / "server/texts.js").read_text()).group(1))
    script = tmp_path / "count.mjs"
    script.write_text(SCRIPT)
    result = subprocess.run(
        ["node", str(script), str(ROOT / "web/checks.js"), str(ROOT / "web/content/checks.json")],
        capture_output=True, text=True, check=True,
    )
    counts = json.loads(result.stdout)
    assert counts
    too_many = {key: count for key, count in counts.items() if count > limit}
    assert not too_many, f"проверки просят больше {limit} текстов: {too_many}"
