"""python -m sim [сценарий ...] [--days N] [--scale N]"""

import argparse
import time

from sim.scenarios import format_report, run, scenarios


def main():
    ap = argparse.ArgumentParser(description="Экономическая симуляция IronVein")
    ap.add_argument("names", nargs="*")
    ap.add_argument("--days", type=int, default=3)
    ap.add_argument("--scale", type=int, default=100)
    args = ap.parse_args()
    sc = scenarios(args.scale, args.days)
    failed = False
    for name in args.names or list(sc):
        t0 = time.time()
        r = run(name, sc[name])
        print(format_report(r), f"\n({time.time() - t0:.1f} с)\n")
        failed |= not all(r["checks"].values())
    raise SystemExit(1 if failed else 0)


if __name__ == "__main__":
    main()
