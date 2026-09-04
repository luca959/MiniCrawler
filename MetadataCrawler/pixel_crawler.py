#!/usr/bin/env python3
"""Query WeChat's current Mini Program search through an attached Android phone."""

from __future__ import annotations

import argparse
import ast
import csv
import html
import json
import re
import sqlite3
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = ROOT.parent
DEFAULT_FRIDA = PROJECT_ROOT / ".venv-frida" / "bin" / "frida"
DEFAULT_AGENT = ROOT / "frida_direct_query.js"
TAG_RE = re.compile(r"<[^>]+>")


def clean_text(value: Any) -> str:
    if value is None:
        return ""
    return html.unescape(TAG_RE.sub("", str(value))).strip()


def adb(*args: str) -> str:
    result = subprocess.run(
        ["adb", *args], check=True, text=True, capture_output=True
    )
    return result.stdout.strip()


def main_wechat_pid() -> int:
    output = adb("shell", "pidof", "com.tencent.mm")
    pids = [int(value) for value in output.split() if value.isdigit()]
    if not pids:
        raise RuntimeError("WeChat non risulta avviato sul telefono")
    return min(pids)


def decode_evaluate_value(value: str) -> dict[str, Any] | None:
    decoded: Any = value
    for _ in range(3):
        if not isinstance(decoded, str):
            break
        try:
            decoded = json.loads(decoded)
        except json.JSONDecodeError:
            return None
    return decoded if isinstance(decoded, dict) else None


def parse_frida_messages(stdout: str) -> list[dict[str, Any]]:
    messages: list[dict[str, Any]] = []
    for line in stdout.splitlines():
        if not line.startswith("message: "):
            continue
        raw = line[len("message: ") :]
        marker = " data: "
        if marker in raw:
            raw = raw.rsplit(marker, 1)[0]
        try:
            envelope = ast.literal_eval(raw)
        except (ValueError, SyntaxError):
            continue
        payload = envelope.get("payload", {}) if isinstance(envelope, dict) else {}
        if payload.get("kind") != "direct-query-result":
            continue
        decoded = decode_evaluate_value(payload.get("value", ""))
        if decoded is not None:
            messages.append(decoded)
    return messages


def query_phone(
    query: str,
    *,
    offset: int = 0,
    tag_info: dict[str, Any] | None = None,
    cookies: str = "",
    search_id: str = "",
    current_page: int = 1,
    pid: int | None = None,
    timeout: int = 14,
    frida: Path = DEFAULT_FRIDA,
    agent: Path = DEFAULT_AGENT,
) -> dict[str, Any]:
    if pid is None:
        pid = main_wechat_pid()
    parameters = {
        "query": query,
        "offset": offset,
        "tag_info": tag_info or {},
        "cookies": cookies,
        "search_id": search_id,
        "current_page": current_page,
        "wait_ms": 6500,
    }
    command = [
        str(frida),
        "-H",
        "127.0.0.1:27042",
        "-p",
        str(pid),
        "-q",
        "-t",
        str(timeout),
        "-e",
        "globalThis.__MC_OPTIONS = "
        + json.dumps(parameters, ensure_ascii=False, separators=(",", ":"))
        + ";",
        "-l",
        str(agent),
    ]
    result = subprocess.run(command, text=True, capture_output=True, timeout=timeout + 8)
    messages = parse_frida_messages(result.stdout)
    completed = [item for item in messages if item.get("phase") == "completed"]
    if completed:
        return completed[-1]
    detail = (result.stderr or result.stdout).strip()[-2000:]
    raise RuntimeError(f"Nessuna risposta completa da WeChat. {detail}")


def response_body(response: dict[str, Any]) -> dict[str, Any]:
    result = response.get("result")
    if not isinstance(result, dict):
        raise RuntimeError("WeChat non ha restituito un risultato di ricerca")
    raw = result.get("json")
    if isinstance(raw, str):
        body = json.loads(raw)
    elif isinstance(raw, dict):
        body = raw
    else:
        raise RuntimeError(f"Formato risposta WeChat inatteso: {result!r}")
    if body.get("ret") not in (None, 0):
        raise RuntimeError(f"Errore WeChat ret={body.get('ret')}: {body.get('errMsg', '')}")
    return body


def iter_items(body: dict[str, Any]):
    for box in body.get("data") or []:
        for sub_box in box.get("subBoxes") or []:
            for item in sub_box.get("items") or []:
                yield item


def item_record(item: dict[str, Any], source_query: str) -> dict[str, str]:
    jump = item.get("jumpInfo") or {}
    source = item.get("source") or item.get("sourceName") or ""
    if isinstance(source, dict):
        source = source.get("title") or source.get("name") or ""
    appid = str(jump.get("appID") or item.get("appID") or "").strip()
    return {
        "appid": appid,
        "doc_id": str(item.get("docID") or ""),
        "name": clean_text(item.get("title")),
        "description": clean_text(item.get("desc")),
        "icon_url": str(item.get("imgUrl") or item.get("iconUrl") or ""),
        "username": str(jump.get("userName") or ""),
        "developer": clean_text(source),
        "app_version": str(jump.get("appVersion") or item.get("appVersion") or ""),
        "source_query": source_query,
        "verified_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }


def connect_db(path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(path)
    connection.execute("PRAGMA journal_mode=WAL")
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS miniapps (
            appid TEXT PRIMARY KEY,
            doc_id TEXT,
            name TEXT NOT NULL,
            description TEXT,
            icon_url TEXT,
            username TEXT,
            developer TEXT,
            app_version TEXT,
            source_query TEXT,
            verified_at TEXT NOT NULL
        )
        """
    )
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS searches (
            query TEXT NOT NULL,
            offset INTEGER NOT NULL,
            item_count INTEGER NOT NULL,
            continue_flag INTEGER NOT NULL,
            searched_at TEXT NOT NULL,
            PRIMARY KEY (query, offset)
        )
        """
    )
    return connection


def save_records(
    connection: sqlite3.Connection,
    records: list[dict[str, str]],
    query: str,
    offset: int,
    continue_flag: int,
) -> int:
    before = connection.total_changes
    for record in records:
        if not record["appid"] or not record["name"]:
            continue
        connection.execute(
            """
            INSERT INTO miniapps (
                appid, doc_id, name, description, icon_url, username,
                developer, app_version, source_query, verified_at
            ) VALUES (
                :appid, :doc_id, :name, :description, :icon_url, :username,
                :developer, :app_version, :source_query, :verified_at
            )
            ON CONFLICT(appid) DO UPDATE SET
                doc_id=excluded.doc_id,
                name=excluded.name,
                description=excluded.description,
                icon_url=excluded.icon_url,
                username=excluded.username,
                developer=excluded.developer,
                app_version=excluded.app_version,
                verified_at=excluded.verified_at
            """,
            record,
        )
    connection.execute(
        """
        INSERT OR REPLACE INTO searches
            (query, offset, item_count, continue_flag, searched_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        (query, offset, len(records), continue_flag, datetime.now(timezone.utc).isoformat(timespec="seconds")),
    )
    connection.commit()
    return connection.total_changes - before


def export_csv(
    connection: sqlite3.Connection,
    output: Path,
    detailed: Path,
    limit: int | None = None,
) -> int:
    sql = """
        SELECT appid, doc_id, name, description, icon_url, username,
               developer, app_version, source_query, verified_at
        FROM miniapps ORDER BY name COLLATE NOCASE, appid
        """
    parameters: tuple[int, ...] = ()
    if limit is not None:
        sql += " LIMIT ?"
        parameters = (limit,)
    rows = connection.execute(sql, parameters).fetchall()
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.writer(handle)
        writer.writerow(["id", "name", "category", "rating", "url", "description"])
        for row in rows:
            appid, _, name, description, *_ = row
            writer.writerow([appid, name, "Mini Program", "", "", description])
    with detailed.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "appid", "doc_id", "name", "description", "icon_url",
                "username", "developer", "app_version", "source_query", "verified_at",
            ]
        )
        writer.writerows(rows)
    return len(rows)


def crawl_query(
    connection: sqlite3.Connection,
    query: str,
    *,
    max_pages: int,
    delay: float,
    pid: int,
) -> tuple[int, int]:
    offset = 0
    tag_info: dict[str, Any] = {}
    cookies = ""
    search_id = ""
    seen_offsets: set[int] = set()
    found = 0
    pages = 0
    while pages < max_pages and offset not in seen_offsets:
        seen_offsets.add(offset)
        response = query_phone(
            query,
            offset=offset,
            tag_info=tag_info,
            cookies=cookies,
            search_id=search_id,
            current_page=pages + 1,
            pid=pid,
        )
        body = response_body(response)
        records = [item_record(item, query) for item in iter_items(body)]
        continue_flag = int(body.get("continueFlag") or 0)
        save_records(connection, records, query, offset, continue_flag)
        found += len(records)
        pages += 1
        next_offset = int(body.get("offset") or 0)
        print(
            f"{query!r}: pagina {pages}, offset {offset} -> {next_offset}, "
            f"{len(records)} risultati, continua={continue_flag}",
            flush=True,
        )
        if not continue_flag or not records or next_offset <= offset:
            break
        next_cookies = body.get("cookies")
        if isinstance(next_cookies, str):
            cookies = next_cookies
        elif isinstance(next_cookies, dict):
            cookies = json.dumps(next_cookies, ensure_ascii=False, separators=(",", ":"))
        search_id = str(body.get("searchID") or body.get("searchId") or search_id)
        offset = next_offset
        if delay:
            time.sleep(delay)
    return found, pages


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("queries", nargs="*", help="parole da cercare")
    parser.add_argument("--query-file", type=Path, help="una parola per riga")
    parser.add_argument("--max-pages", type=int, default=10)
    parser.add_argument("--delay", type=float, default=2.5)
    parser.add_argument("--database", type=Path, default=ROOT / "data.db")
    parser.add_argument("--output", type=Path, default=PROJECT_ROOT / "wechat_miniapps.csv")
    parser.add_argument(
        "--detailed-output",
        type=Path,
        default=PROJECT_ROOT / "wechat_miniapps_detailed.csv",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    queries = list(args.queries)
    if args.query_file:
        queries.extend(
            line.strip()
            for line in args.query_file.read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.lstrip().startswith("#")
        )
    queries = list(dict.fromkeys(queries))
    if not queries:
        print("Specifica almeno una query o --query-file", file=sys.stderr)
        return 2
    pid = main_wechat_pid()
    connection = connect_db(args.database)
    try:
        for query in queries:
            crawl_query(
                connection,
                query,
                max_pages=args.max_pages,
                delay=args.delay,
                pid=pid,
            )
            count = export_csv(connection, args.output, args.detailed_output)
            print(f"CSV aggiornati: {count} Mini Program unici", flush=True)
    finally:
        connection.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
