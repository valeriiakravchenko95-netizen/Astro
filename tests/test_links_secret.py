"""Ссылки на темы и события не угадать по соседней.

Каждая ссылка под рилс - слово темы и хвост из шести случайных символов
(venera-epjreq): по одной ссылке нельзя добраться до другой. Старые простые
ссылки, которые уже разосланы, живут только в aliases и в списке ниже.
"""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SECRET = re.compile(r"^[a-z]+(-[a-z]+)*-[a-z0-9]{6}$")
# Ссылки на события, разосланные до правила. Новые сюда не добавлять.
OLD_EVENT_LINKS = {"polnolunie"}


def test_check_links_have_secret_tail():
    checks = json.loads((ROOT / "web/content/checks.json").read_text())["checks"]
    bad = [c["key"] for c in checks if not SECRET.match(c.get("slug", ""))]
    bad += [slug for c in checks for slug in c.get("brand_slugs", {}) if not SECRET.match(slug)]
    assert not bad, f"ссылка без случайного хвоста у проверок: {bad}"


def test_check_links_are_unique():
    checks = json.loads((ROOT / "web/content/checks.json").read_text())["checks"]
    paths = [c["slug"] for c in checks] + [a for c in checks for a in c.get("aliases", [])]
    paths += [b for c in checks for b in c.get("brand_slugs", {})]
    assert len(paths) == len(set(paths))


def test_event_links_have_secret_tail():
    links = json.loads((ROOT / "web/content/transits.json").read_text()).get("links", {})
    bad = [slug for slug in links if slug not in OLD_EVENT_LINKS and not SECRET.match(slug)]
    assert not bad, f"ссылка без случайного хвоста у событий: {bad}"
