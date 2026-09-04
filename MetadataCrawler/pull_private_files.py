#!/usr/bin/env python3
"""Read files in WeChat's private directory through an attached Frida process."""

from __future__ import annotations

import argparse
from pathlib import Path, PurePosixPath

import frida


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("remote", nargs="+")
    parser.add_argument("--pid", type=int, required=True)
    parser.add_argument("--host", default="127.0.0.1:27042")
    parser.add_argument("--output-dir", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    source = Path(__file__).with_name("frida_read_files.js").read_text(encoding="utf-8")
    device = frida.get_device_manager().add_remote_device(args.host)
    session = device.attach(args.pid)
    script = session.create_script(source)
    active_stream = None

    def on_message(message: dict, data: bytes | None) -> None:
        nonlocal active_stream
        if message.get("type") == "error":
            raise RuntimeError(message.get("stack", message.get("description", message)))
        payload = message.get("payload", {})
        if payload.get("type") == "file-chunk" and active_stream is not None and data is not None:
            active_stream.write(data)

    script.on("message", on_message)
    script.load()
    try:
        for remote in args.remote:
            output = args.output_dir / PurePosixPath(remote).name
            with output.open("wb") as stream:
                active_stream = stream
                size = script.exports_sync.readfile(remote)
            active_stream = None
            print(f"pulled {remote} -> {output} ({size} bytes)")
    finally:
        session.detach()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
