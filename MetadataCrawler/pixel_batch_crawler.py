#!/usr/bin/env python3
"""Resumable high-volume Mini Program crawler for an attached Pixel/WeChat."""

from __future__ import annotations

import argparse
import ast
import json
import re
import sqlite3
import subprocess
import time
from pathlib import Path
from typing import Any

from pixel_crawler import (
    DEFAULT_FRIDA,
    PROJECT_ROOT,
    ROOT,
    adb,
    connect_db,
    export_csv,
    item_record,
    iter_items,
    main_wechat_pid,
    response_body,
    save_records,
)


AGENT = ROOT / "frida_batch_crawl.js"
CJK_RUN = re.compile(r"[\u3400-\u9fff]{2,}")
SEED_TERMS = """
小程序 服务 工具 生活 购物 商城 电商 外卖 美食 餐饮 菜谱 咖啡 茶 饮品
旅游 酒店 民宿 机票 火车 交通 地图 导航 出行 打车 公交 地铁 汽车 停车
天气 新闻 阅读 小说 视频 音乐 直播 图片 摄影 相机 游戏 娱乐 电影 票务
教育 学习 课程 学校 大学 考试 英语 数学 编程 科技 AI 人工智能 办公
健康 医疗 医院 挂号 药店 运动 健身 跑步 瑜伽 睡眠 心理 母婴 儿童
金融 银行 保险 股票 基金 证券 支付 记账 发票 税务 法律 政务 公积金
招聘 求职 企业 管理 客户 CRM 营销 广告 设计 装修 房产 租房 家居
快递 物流 查询 翻译 日历 时间 计算器 扫描 文件 表格 证件 预约 社区
宠物 花卉 农业 公益 环保 二手 团购 优惠 会员 积分 抽奖 婚礼 交友
北京 上海 广州 深圳 成都 杭州 重庆 天津 南京 武汉 西安 苏州 青岛
weather travel hotel food shop game music video health education finance tools
""".split()
COMMON_CHARS = (
    "的一是在不了有和人这中大为上个国我以要他时来用们生到作地于出就分对"
    "成会可主发年动同工也能下过子说产种面而方后多定行学法所民得经十三之"
    "进着等部度家电力里如水化高自二理起小物现实加量都两体制机当使点从业"
    "本去把性好应开它合还因由其些然前外天政四日那社义事平形相全表间样与"
    "关各重新线内数正心反你明看原又么利比或但质气第向道命此变条只没结解"
    "问意建月公无系军很情者最立代想已通并提直题党程展五果料象员革位入常"
    "文总次品式活设及管特件长求老头基资边流路级少图山统接知较将组见计别"
    "她手角期根论运农指几九区强放决西被干做必战先回则任取据处理世车市持"
    "场该吃住衣游医教金商店网云智安乐美新爱家宝优快易通达信微好学健康"
)


class BatchUnavailable(RuntimeError):
    pass


def ensure_queue(connection: sqlite3.Connection) -> None:
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS query_queue (
            query TEXT PRIMARY KEY,
            status TEXT NOT NULL DEFAULT 'pending',
            attempts INTEGER NOT NULL DEFAULT 0,
            discovered_from TEXT,
            last_error TEXT,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    connection.commit()


def enqueue(connection: sqlite3.Connection, queries, source: str) -> int:
    before = connection.total_changes
    connection.executemany(
        "INSERT OR IGNORE INTO query_queue(query, discovered_from) VALUES (?, ?)",
        ((query.strip(), source) for query in queries if 1 <= len(query.strip()) <= 32),
    )
    connection.commit()
    return connection.total_changes - before


def discovered_queries(records: list[dict[str, str]]):
    for record in records:
        name = record["name"]
        if 2 <= len(name) <= 24:
            yield name
        for run in CJK_RUN.findall(name):
            for width in (2, 3, 4):
                for index in range(max(0, len(run) - width + 1)):
                    yield run[index : index + width]


def decode_value(value: str) -> dict[str, Any] | None:
    decoded: Any = value
    for _ in range(3):
        if not isinstance(decoded, str):
            break
        try:
            decoded = json.loads(decoded)
        except json.JSONDecodeError:
            return None
    return decoded if isinstance(decoded, dict) else None


def message_payload(line: str) -> dict[str, Any] | None:
    if not line.startswith("message: "):
        return None
    raw = line[len("message: ") :]
    if " data: " in raw:
        raw = raw.rsplit(" data: ", 1)[0]
    try:
        envelope = ast.literal_eval(raw)
    except (SyntaxError, ValueError):
        return None
    if not isinstance(envelope, dict):
        return None
    payload = envelope.get("payload")
    return payload if isinstance(payload, dict) else None


def crawl_batch(
    connection: sqlite3.Connection,
    queries: list[str],
    *,
    pid: int,
    delay_ms: int,
    max_pages: int,
) -> int:
    options = {"queries": queries, "delay_ms": delay_ms, "max_pages": max_pages}
    expression = "globalThis.__MC_OPTIONS = " + json.dumps(
        options, ensure_ascii=False, separators=(",", ":")
    ) + ";"
    command = [
        str(DEFAULT_FRIDA), "-H", "127.0.0.1:27042", "-p", str(pid),
        "-q", "-t", "inf", "-e", expression, "-l", str(AGENT),
    ]
    process = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )
    completed = False
    seen_queries: set[str] = set()
    failed_queries: set[str] = set()
    consecutive_failures = 0
    received = 0
    try:
        assert process.stdout is not None
        for line in process.stdout:
            payload = message_payload(line.rstrip("\n"))
            if not payload:
                continue
            if payload.get("kind") == "batch-fatal":
                raise RuntimeError(str(payload.get("error")))
            if payload.get("kind") != "batch-poll":
                continue
            chunk = decode_value(str(payload.get("value", "")))
            if not chunk:
                continue
            for entry in chunk.get("results", []):
                query = str(entry.get("query") or "")
                seen_queries.add(query)
                response = {"result": entry.get("result")}
                try:
                    body = response_body(response)
                    if body.get("data") is None:
                        raise RuntimeError("WeChat ha restituito data=null (probabile throttling)")
                    records = [item_record(item, query) for item in iter_items(body)]
                    save_records(
                        connection,
                        records,
                        query,
                        int(entry.get("offset") or 0),
                        int(body.get("continueFlag") or 0),
                    )
                    enqueue(connection, discovered_queries(records), query)
                    received += len(records)
                    consecutive_failures = 0
                    print(
                        f"{query!r} p{entry.get('page')}: {len(records)} risultati; "
                        f"ricevuti batch={received}",
                        flush=True,
                    )
                except Exception as exc:
                    failed_queries.add(query)
                    consecutive_failures += 1
                    connection.execute(
                        "UPDATE query_queue SET last_error=?, attempts=attempts+1, updated_at=CURRENT_TIMESTAMP WHERE query=?",
                        (str(exc)[:500], query),
                    )
                    connection.commit()
                    if consecutive_failures >= 3:
                        raise BatchUnavailable("tre risposte consecutive mancanti o non valide")
            if chunk.get("done"):
                completed = True
                break
    finally:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
        if not completed:
            subprocess.run(
                [
                    str(DEFAULT_FRIDA), "-H", "127.0.0.1:27042", "-p", str(pid),
                    "-q", "-t", "6", "-l", str(ROOT / "frida_stop_batch.js"),
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=12,
                check=False,
            )
    if completed:
        connection.executemany(
            "UPDATE query_queue SET status='done', attempts=attempts+1, updated_at=CURRENT_TIMESTAMP WHERE query=?",
            ((query,) for query in queries if query not in failed_queries),
        )
        connection.executemany(
            "UPDATE query_queue SET status='pending', updated_at=CURRENT_TIMESTAMP WHERE query=?",
            ((query,) for query in failed_queries),
        )
    else:
        connection.executemany(
            "UPDATE query_queue SET status='pending', last_error='batch interrotto', updated_at=CURRENT_TIMESTAMP WHERE query=?",
            ((query,) for query in queries),
        )
    connection.commit()
    return received


def count_apps(connection: sqlite3.Connection) -> int:
    return int(connection.execute("SELECT count(*) FROM miniapps").fetchone()[0])


def export_keyword_list(connection: sqlite3.Connection, output: Path) -> int:
    rows = connection.execute("SELECT query FROM query_queue ORDER BY rowid").fetchall()
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_name(output.name + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="\n") as handle:
        for (query,) in rows:
            handle.write(query.replace("\n", " ").strip() + "\n")
    temporary.replace(output)
    return len(rows)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", type=int, default=200_000)
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument("--batch-pause", type=float, default=5.0)
    parser.add_argument("--delay-ms", type=int, default=1400)
    parser.add_argument("--max-pages", type=int, default=5)
    parser.add_argument("--database", type=Path, default=ROOT / "data.db")
    parser.add_argument("--output", type=Path, default=PROJECT_ROOT / "wechat_miniapps_200k.csv")
    parser.add_argument(
        "--keywords-output",
        type=Path,
        default=PROJECT_ROOT / "wechat_miniapps_keywords.txt",
    )
    parser.add_argument(
        "--detailed-output",
        type=Path,
        default=PROJECT_ROOT / "wechat_miniapps_200k_detailed.csv",
    )
    parser.add_argument("--max-batches", type=int, default=0, help="0 = nessun limite")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    pid = main_wechat_pid()
    connection = connect_db(args.database)
    ensure_queue(connection)
    enqueue(connection, SEED_TERMS, "seed")
    enqueue(connection, COMMON_CHARS, "common-char")
    export_keyword_list(connection, args.keywords_output)
    connection.execute("UPDATE query_queue SET status='pending' WHERE status='running'")
    connection.execute(
        """
        UPDATE query_queue SET status='done'
        WHERE query IN (
            SELECT query FROM searches
            GROUP BY query
            HAVING count(*) >= ? OR min(continue_flag) = 0
        )
        """,
        (args.max_pages,),
    )
    connection.commit()
    batches = 0
    safety_backoff = 900
    try:
        while count_apps(connection) < args.target:
            adb("shell", "input", "keyevent", "KEYCODE_WAKEUP")
            adb("shell", "wm", "dismiss-keyguard")
            rows = connection.execute(
                "SELECT query FROM query_queue WHERE status='pending' ORDER BY attempts, rowid LIMIT ?",
                (args.batch_size,),
            ).fetchall()
            queries = [row[0] for row in rows]
            if not queries:
                raise RuntimeError("Coda query esaurita prima del raggiungimento del target")
            connection.executemany(
                "UPDATE query_queue SET status='running', updated_at=CURRENT_TIMESTAMP WHERE query=?",
                ((query,) for query in queries),
            )
            connection.commit()
            try:
                crawl_batch(
                    connection,
                    queries,
                    pid=pid,
                    delay_ms=args.delay_ms,
                    max_pages=args.max_pages,
                )
            except BatchUnavailable as exc:
                connection.execute(
                    "UPDATE query_queue SET status='pending' WHERE status='running'"
                )
                connection.commit()
                total = count_apps(connection)
                export_csv(connection, args.output, args.detailed_output, limit=args.target)
                print(
                    f"PAUSA DI SICUREZZA: {exc}; {total}/{args.target}. "
                    f"Riprovo tra {safety_backoff} secondi.",
                    flush=True,
                )
                time.sleep(safety_backoff)
                safety_backoff = min(safety_backoff * 2, 3600)
                continue
            safety_backoff = 900
            batches += 1
            total = count_apps(connection)
            if batches == 1 or batches % 10 == 0 or total >= args.target:
                export_csv(connection, args.output, args.detailed_output, limit=args.target)
            pending = connection.execute(
                "SELECT count(*) FROM query_queue WHERE status='pending'"
            ).fetchone()[0]
            keyword_count = export_keyword_list(connection, args.keywords_output)
            print(f"PROGRESSO: {total}/{args.target}; query in coda={pending}", flush=True)
            print(f"KEYWORD TXT: {keyword_count} keyword", flush=True)
            if args.max_batches and batches >= args.max_batches:
                break
            time.sleep(args.batch_pause)
    finally:
        export_csv(connection, args.output, args.detailed_output, limit=args.target)
        export_keyword_list(connection, args.keywords_output)
        connection.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
