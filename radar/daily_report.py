#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""娜娜技术雷达 · 日报生成器（纯数据版，零 LLM 依赖）
直接从 SQLite 读取 24h 采集数据，按来源+热度排序输出 Markdown.
"""

import json
import sqlite3
import time
from pathlib import Path
from datetime import datetime, timezone, timedelta

# ── 路径 ──────────────────────
DB_PATH = Path.home() / ".local" / "share" / "intel-radar" / "radar.db"
OUT_DIR = Path(__file__).resolve().parent.parent / "output"
OUT_DIR.mkdir(parents=True, exist_ok=True)

# ── 来源别名 ──────────────────
SOURCE_LABEL = {
    "bili": "📺 B站",
    "bili_hot": "🔥 B站热门",
    "github": "🐙 GitHub",
    "hf": "🤗 HuggingFace",
    "hn": "💬 Hacker News",
    "aihot": "📰 AI 资讯",
    "qbitai": "📰 量子位",
    "producthunt": "🚀 Product Hunt",
    "youtube": "🎬 YouTube",
    "douyin": "📱 抖音",
    "xhs": "📕 小红书",
    "x": "𝕏 Twitter",
    "tiktok": "🎵 TikTok",
}

def today_str() -> str:
    return datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m-%d")

def metric_score(row: dict) -> float:
    """从 metrics JSON 提取热度分"""
    try:
        m = json.loads(row["metrics"]) if row["metrics"] else {}
    except Exception:
        return 0.0
    return float(
        m.get("score", 0) or m.get("stars", 0) or m.get("points", 0)
        or m.get("play", 0) or m.get("views", 0) or m.get("like_count", 0) or 0
    )

def build_report(day: str) -> str:
    db = sqlite3.connect(str(DB_PATH))
    db.row_factory = sqlite3.Row
    tz = timezone(timedelta(hours=8))
    day_start = datetime.strptime(day, "%Y-%m-%d").replace(tzinfo=tz).timestamp()
    day_end = day_start + 86400

    rows = db.execute(
        "SELECT * FROM items WHERE first_seen >= ? AND first_seen < ? ORDER BY first_seen",
        (day_start, day_end),
    ).fetchall()
    db.close()

    if not rows:
        return f"# 🛰️ 娜娜技术雷达 · {day}\n\n> ⚠️ 今日无数据。\n"

    # 按来源分组，每组按热度排序取 top N
    groups: dict[str, list[dict]] = {}
    for r in rows:
        src = r["source"]
        groups.setdefault(src, []).append(dict(r))

    TOP_PER_SOURCE = {"bili": 15, "bili_hot": 10, "github": 10, "hn": 8,
                       "hf": 5, "aihot": 5, "qbitai": 5, "producthunt": 5,
                       "youtube": 5, "douyin": 5, "xhs": 5, "x": 5, "tiktok": 5}

    lines = [
        f"# 🛰️ 娜娜技术雷达 · {day}",
        "",
        f"> 采集 {len(rows)} 条 · {len(groups)} 个信源 · 纯数据版",
        "",
        "---",
        "",
    ]

    for src in sorted(groups, key=lambda s: -len(groups[s])):
        items = groups[src]
        items.sort(key=metric_score, reverse=True)
        top_n = TOP_PER_SOURCE.get(src, 5)
        lines.append(f"## {SOURCE_LABEL.get(src, src)}（{len(items)} 条，展示 Top {top_n}）")
        lines.append("")
        for item in items[:top_n]:
            title = (item.get("title") or item.get("text") or "-").strip()
            url = item.get("url") or ""
            author = item.get("author") or ""
            kind = item.get("kind", "")
            score = metric_score(item)
            line = f"- "
            if score > 0:
                line += f"`{score:.0f}` "
            if author:
                line += f"**{author}** · "
            if url:
                line += f"[{title[:100]}]({url})"
            else:
                line += title[:100]
            if kind and kind != "video":
                line += f" `[{kind}]`"
            lines.append(line)
        lines.append("")

    lines.append("---")
    lines.append(f"*由娜娜技术雷达于 {day} 自动生成 · 纯数据版，不含 AI 摘要*")
    return "\n".join(lines)

def main():
    day = today_str()
    report = build_report(day)
    out_path = OUT_DIR / f"nana-daily-{day}.md"
    out_path.write_text(report, encoding="utf-8")
    html_path = OUT_DIR / f"nana-daily-{day}.html"
    html = f"<html><head><meta charset='utf-8'><title>娜娜技术雷达 {day}</title>"
    html += "<style>body{font-family:system-ui;max-width:900px;margin:0 auto;padding:2em;background:#0d1117;color:#c9d1d9}"
    html += "a{color:#58a6ff}h1{color:#f0f6fc}h2{color:#f0f6fc;border-bottom:1px solid #30363d}"
    html += "li{margin:0.4em 0}</style></head><body>"
    html += report.replace("\n", "<br>").replace("`", "<code>").replace("</code><br><code>", "</code> <code>")
    html += "</body></html>"
    html_path.write_text(html, encoding="utf-8")
    print(f"✅ 日报已生成: {out_path} ({len(report)} 字)")
    print(f"✅ HTML 已生成: {html_path}")
    print(report[:2000])

if __name__ == "__main__":
    main()