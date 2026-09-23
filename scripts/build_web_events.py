#!/usr/bin/env python3
"""Считает календарь событий неба для страницы.

Станции, точные аспекты между планетами, входы в знаки, новолуния и
полнолуния с затмениями. Считается заранее и складывается в файл: в
браузере искать их численно долго, а меняться они не могут.

    python3 scripts/build_web_events.py
    python3 scripts/build_web_events.py --from 2024 --to 2032
"""

from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from astro import sky  # noqa: E402
from astro.ephemeris import load_ephemeris  # noqa: E402
from astro.zodiac import to_sign  # noqa: E402

OUTPUT = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "web", "data", "events.json",
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--from", dest="start_year", type=int, default=2025)
    parser.add_argument("--to", dest="end_year", type=int, default=2031)
    parser.add_argument("--out", default=OUTPUT)
    args = parser.parse_args()

    eph = load_ephemeris()
    jd_start = eph.ts.utc(args.start_year, 1, 1).tt
    jd_end = eph.ts.utc(args.end_year, 1, 1).tt

    print(f"считаю события {args.start_year}–{args.end_year}…")
    events = sky.collect(eph, jd_start, jd_end)

    rows = []
    for event in events:
        moment = eph.ts.tt_jd(event.jd)
        position = to_sign(event.longitude)
        rows.append({
            "key": event.key(),
            "kind": event.kind,
            "title": event.title,
            "date": moment.utc_strftime("%Y-%m-%d"),
            "time": moment.utc_strftime("%H:%M"),
            "jd": round(event.jd, 6),
            "bodies": list(event.bodies),
            "longitude": round(event.longitude, 6),
            "sign": position.sign_index,
            "degree": round(position.degree_in_sign, 4),
            "detail": {
                key: (round(value, 6) if isinstance(value, float) else value)
                for key, value in event.detail.items()
            },
        })

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as handle:
        json.dump({"from": args.start_year, "to": args.end_year, "events": rows},
                  handle, ensure_ascii=False, separators=(",", ":"))

    counts = {}
    for row in rows:
        counts[row["kind"]] = counts.get(row["kind"], 0) + 1
    print(f"{args.out}: {os.path.getsize(args.out) / 1024:.0f} КБ, {len(rows)} событий")
    for kind, count in sorted(counts.items()):
        print(f"  {kind}: {count}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
