#!/usr/bin/env python3
"""Keep a text export of the crawler's used and pending keyword queue."""

from __future__ import annotations

import argparse
import os
import sqlite3
import time
from pathlib import Path

from pixel_batch_crawler import export_keyword_list


def process_exists(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--crawler-pid", type=int, required=True)
    parser.add_argument("--interval", type=float, default=30.0)
    args = parser.parse_args()

    last_count = -1
    while True:
        connection = sqlite3.connect(args.database)
        try:
            count = export_keyword_list(connection, args.output)
        finally:
            connection.close()
        if count != last_count:
            print(f"Keyword esportate: {count}", flush=True)
            last_count = count
        if not process_exists(args.crawler_pid):
            break
        time.sleep(args.interval)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
