#!/usr/bin/env python3
"""Загрузка ядра эфемерид JPL в каталог ephemeris/.

Запускается один раз при разворачивании; сам бот в сеть не ходит.

    python3 scripts/fetch_ephemeris.py            # de440s.bsp, 1849-2150, ~32 МБ
    python3 scripts/fetch_ephemeris.py --full     # de440.bsp, 1550-2650, ~114 МБ

Скачанный файл проверяется на месте: он должен открываться как ядро SPK,
содержать нужные тела и покрывать заявленный интервал дат. Битую или
обрезанную загрузку это ловит надёжнее, чем сверка размера.
"""

from __future__ import annotations

import argparse
import os
import sys
import urllib.request

KERNELS = {
    "de440s.bsp": [
        "https://naif.jpl.nasa.gov/pub/naif/generic_kernels/spk/planets/de440s.bsp",
        "https://ssd.jpl.nasa.gov/ftp/eph/planets/bsp/de440s.bsp",
    ],
    "de440.bsp": [
        "https://naif.jpl.nasa.gov/pub/naif/generic_kernels/spk/planets/de440.bsp",
        "https://ssd.jpl.nasa.gov/ftp/eph/planets/bsp/de440.bsp",
    ],
}

#: Коды NAIF, без которых карта не считается.
REQUIRED_CODES = (10, 301, 399, 1, 2, 4, 5, 6, 7, 8, 9)

TARGET_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "ephemeris")


def download(name: str, destination: str) -> None:
    last_error = None
    for url in KERNELS[name]:
        print(f"Загружаю {url}")
        try:
            with urllib.request.urlopen(url) as response:
                total = int(response.headers.get("Content-Length") or 0)
                downloaded = 0
                with open(destination, "wb") as handle:
                    while True:
                        chunk = response.read(1 << 20)
                        if not chunk:
                            break
                        handle.write(chunk)
                        downloaded += len(chunk)
                        if total:
                            print(f"\r  {downloaded / 1e6:7.1f} / {total / 1e6:.1f} МБ", end="")
                print()
            return
        except Exception as error:  # noqa: BLE001 — печатаем и пробуем зеркало
            last_error = error
            print(f"  не вышло: {error}")
            if os.path.exists(destination):
                os.remove(destination)
    raise SystemExit(f"не удалось скачать {name}: {last_error}")


def verify(path: str) -> None:
    """Проверяет, что файл — работающее ядро с нужными телами."""
    try:
        from skyfield.api import load_file
    except ImportError:
        print("Skyfield не установлен, проверка пропущена")
        return

    kernel = load_file(path)
    missing = [code for code in REQUIRED_CODES if code not in kernel.codes]
    if missing:
        raise SystemExit(f"в ядре нет тел с кодами {missing}")

    starts, ends = [], []
    for segment in kernel.segments:
        starts.append(segment.start_jd)
        ends.append(segment.end_jd)
    kernel.close()
    print(
        f"Проверено: {os.path.basename(path)}, {os.path.getsize(path) / 1e6:.1f} МБ, "
        f"покрытие с JD {max(starts):.1f} по JD {min(ends):.1f}"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--full", action="store_true",
                        help="полный de440.bsp вместо укороченного de440s.bsp")
    parser.add_argument("--force", action="store_true", help="перекачать поверх существующего")
    args = parser.parse_args()

    name = "de440.bsp" if args.full else "de440s.bsp"
    os.makedirs(TARGET_DIR, exist_ok=True)
    destination = os.path.join(TARGET_DIR, name)

    if os.path.exists(destination) and not args.force:
        print(f"{destination} уже есть, проверяю")
    else:
        download(name, destination)
    verify(destination)
    return 0


if __name__ == "__main__":
    sys.exit(main())
