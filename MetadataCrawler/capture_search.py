#!/usr/bin/env python3
"""Capture only WeChat mini-program search traffic from a rooted USB device."""

from __future__ import annotations

import argparse
import json
import signal
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import frida


PACKAGE_PREFIX = "com.tencent.mm"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1:27042")
    parser.add_argument("--script", type=Path, default=Path(__file__).with_name("frida_capture.bundle.js"))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--duration", type=int, default=180)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not args.script.exists():
        raise SystemExit(f"compiled Frida agent not found: {args.script}")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    source = args.script.read_text(encoding="utf-8")
    device = frida.get_device_manager().add_remote_device(args.host)
    sessions: dict[int, tuple[frida.core.Session, frida.core.Script]] = {}
    stopping = False

    def stop(*_: object) -> None:
        nonlocal stopping
        stopping = True

    signal.signal(signal.SIGINT, stop)
    signal.signal(signal.SIGTERM, stop)

    with args.output.open("a", encoding="utf-8") as stream:
        def record(pid: int, process_name: str, message: dict, data: bytes | None) -> None:
            row = {
                "captured_at": datetime.now(timezone.utc).isoformat(),
                "pid": pid,
                "process": process_name,
                "message": message,
            }
            if data is not None:
                row["data_length"] = len(data)
            stream.write(json.dumps(row, ensure_ascii=False) + "\n")
            stream.flush()
            payload = message.get("payload", {})
            if payload.get("kind") != "hooked":
                print(json.dumps(row, ensure_ascii=False), flush=True)

        deadline = time.monotonic() + args.duration
        while not stopping and time.monotonic() < deadline:
            current = {
                process.pid: process.name
                for process in device.enumerate_processes()
                if process.name == "WeChat" or process.name.startswith(PACKAGE_PREFIX)
            }
            for pid, name in current.items():
                if pid in sessions:
                    continue
                try:
                    session = device.attach(pid)
                    script = session.create_script(source)
                    script.on("message", lambda message, data, p=pid, n=name: record(p, n, message, data))
                    script.load()
                    sessions[pid] = (session, script)
                    print(f"attached pid={pid} process={name}", flush=True)
                except frida.ProcessNotFoundError:
                    continue
            time.sleep(1)

    for session, _script in sessions.values():
        try:
            session.detach()
        except frida.InvalidOperationError:
            pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
