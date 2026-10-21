#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""open-termbank 数据构建器：校验 data/*.csv → 生成/核对 data/index.json。

用法：
  python scripts/build_index.py [--version 2.0.0]   # 校验并（重新）生成 index.json
  python scripts/build_index.py --check             # 只校验（CI / 提交前门禁）

数据模式（v2.0.0 起，五列）：
  source,target,domain,definition,synonyms
    source     英文术语（小写，缩写/专名除外）
    target     规范中文译名
    domain     规范中文域标签（须在 domains.json 登记）
    definition 简明中文定义（自编，非空）
    synonyms   英文同义词/缩写，"; " 分隔，可为空

校验项（任一失败即退出码 1）：
  1. 表头必须精确为上述五列（UTF-8，无 BOM——BOM 会破坏机器读取）；
  2. 每行恰好 5 列、source/target/definition 非空、source≠target、domain 已登记；
  3. 字段内**禁止 ASCII 逗号 / 双引号 / 换行**（本库刻意保持「无引号纯文本」，
     让 split(",") 级别的朴素解析也安全；定义一律用中文标点）；
  4. 文件内无重复 source（大小写不敏感）；
  5. data/*.csv 与 domains.json 一一对应（无孤儿文件、无空注册）；
  6. index.json 的 sha256/count 与数据文件实际一致（--check 模式）。

index.json 是消费方的同步协议入口：版本号 + 每域文件 sha256 + 条数。
零第三方依赖（Python 3 标准库）。
"""
import argparse
import csv
import hashlib
import io
import json
import os
import sys
from datetime import datetime, timezone, timedelta

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")
HEADER = ["source", "target", "domain", "definition", "synonyms"]


def fail(msg):
    print("  ✗ " + msg)
    return 1


def sha256_of(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def load_domains():
    with io.open(os.path.join(DATA, "domains.json"), encoding="utf-8") as f:
        meta = json.load(f)
    by_slug = {}
    by_domain = {}
    for d in meta.get("domains", []):
        by_slug[d["slug"]] = d
        by_domain[d["domain"]] = d
    return by_slug, by_domain


def load_csv(path):
    """读数据文件（无 BOM、精确表头、五列）。返回 (rows, errors)，rows 为五元组。"""
    errors = []
    raw = open(path, "rb").read()
    if raw.startswith(b"\xef\xbb\xbf"):
        errors.append("文件带 UTF-8 BOM（应为无 BOM 的纯 UTF-8）")
    text = raw.decode("utf-8-sig")
    rows = list(csv.reader(io.StringIO(text)))
    if not rows:
        errors.append("空文件")
        return [], errors
    if rows[0] != HEADER:
        errors.append("表头应为 %s，实际 %r" % (HEADER, rows[0]))
        return [], errors
    seen = {}
    data_rows = []
    for i, row in enumerate(rows[1:], start=2):
        if not row or (len(row) == 1 and not row[0].strip()):
            continue  # 容忍末尾空行
        if len(row) != 5:
            errors.append("第 %d 行列数=%d（应为 5：检查是否有未转义 ASCII 逗号）" % (i, len(row)))
            continue
        s, t, d, df, sy = (x.strip() for x in row)
        if not s or not t:
            errors.append("第 %d 行 source/target 为空" % i)
            continue
        if s == t:
            errors.append("第 %d 行 source=target（无意义条目）" % i)
            continue
        if not d:
            errors.append("第 %d 行 domain 为空" % i)
            continue
        if not df:
            errors.append("第 %d 行 definition 为空（v2.0.0 起必填）" % i)
            continue
        bad = [f for f in (s, t, d, df, sy) if ("," in f or '"' in f or "\n" in f or "\r" in f)]
        if bad:
            errors.append("第 %d 行字段含 ASCII 逗号/引号/换行（请改用中文标点）" % i)
            continue
        key = s.lower()
        if key in seen:
            errors.append("重复 source（第 %d 行与第 %d 行，大小写不敏感）：%s" % (i, seen[key], s))
            continue
        seen[key] = i
        data_rows.append((s, t, d, df, sy))
    return data_rows, errors


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--version", default=None, help="写入 index.json 的版本号（默认沿用现有）")
    ap.add_argument("--check", action="store_true", help="只校验不重写 index.json")
    args = ap.parse_args()

    by_slug, by_domain = load_domains()
    problems = 0
    print("== open-termbank build ==")

    # 数据文件 ↔ domains.json 对应
    csv_files = sorted(f for f in os.listdir(DATA) if f.endswith(".csv"))
    slugs = [f[:-4] for f in csv_files]
    for slug in slugs:
        if slug not in by_slug:
            problems += fail("data/%s.csv 未在 domains.json 登记" % slug)
    for slug in by_slug:
        if slug not in slugs:
            problems += fail("domains.json 登记 %s 但无 data/%s.csv" % (slug, slug))

    domains_out = []
    total = 0
    for f in csv_files:
        slug = f[:-4]
        path = os.path.join(DATA, f)
        rows, errors = load_csv(path)
        for e in errors:
            problems += fail("data/%s：%s" % (f, e))
        registered = set()
        for (_, _, d, _, _) in rows:
            if d not in by_domain:
                problems += fail("data/%s：domain「%s」未在 domains.json 登记" % (f, d))
            else:
                registered.add(d)
        for d in registered:
            if by_domain[d]["slug"] != slug:
                problems += fail("data/%s：域「%s」应属于 %s.csv" % (f, d, by_domain[d]["slug"]))
        meta = by_slug.get(slug, {})
        count = len(rows)
        total += count
        entry = {
            "domain": meta.get("domain", rows[0][2] if rows else ""),
            "slug": slug,
            "en": meta.get("en", ""),
            "file": f,
            "count": count,
            "sha256": sha256_of(path),
        }
        domains_out.append(entry)
        print("  ✓ %-22s %4d 条" % (f, count))

    # 跨文件重复 source 警告（不同域允许同词，但值得知道）
    cross = {}
    for f, rows in [(os.path.basename(p), load_csv(p)[0]) for p in
                    (os.path.join(DATA, f) for f in csv_files)]:
        for (s, _, _, _, _) in rows:
            cross.setdefault(s.lower(), []).append(f)
    dups = {s: fs for s, fs in cross.items() if len(fs) > 1}
    if dups:
        print("  ⚠ 跨域同词（保留，供人工复核）：%s" %
              "; ".join("%s→%s" % (s, ",".join(fs)) for s, fs in list(dups.items())[:5]))

    if problems:
        print("== 校验失败：%d 个问题，未写 index.json ==" % problems)
        return 1

    index_path = os.path.join(DATA, "index.json")
    old = {}
    if os.path.exists(index_path):
        try:
            old = json.load(io.open(index_path, encoding="utf-8"))
        except Exception:
            old = {}
    version = args.version or old.get("version", "0.1.0")
    stamp = datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m-%dT%H:%M:%S+08:00")
    owner = os.environ.get("OTB_OWNER", old.get("owner", "yebuqiu"))
    index = {
        "name": "open-termbank",
        "description": "多学科领域中英术语对照数据库（按域取用 / CSV+TBX / CC BY 4.0）",
        "version": version,
        "updated": stamp,
        "owner": owner,
        "language_pair": "en → zh-CN",
        "schema": "source,target,domain,definition,synonyms",
        "license": {"data": "CC-BY-4.0", "code": "Apache-2.0"},
        "domains": domains_out,
        "total": total,
        "protocol": {
            "sync": "消费方轮询 index.json；对比每域 sha256 决定是否重新下载该域 CSV",
            "urls": {
                "raw": "https://raw.githubusercontent.com/%s/open-termbank/main/data/" % owner,
                "jsdelivr": "https://cdn.jsdelivr.net/gh/%s/open-termbank@main/data/" % owner,
            }
        },
    }

    if args.check:
        if not old:
            print("== --check：index.json 不存在 ==")
            return 1
        bad = 0
        for d in old.get("domains", []):
            cur = [x for x in domains_out if x["slug"] == d["slug"]]
            if not cur or cur[0]["sha256"] != d["sha256"] or cur[0]["count"] != d["count"]:
                bad += fail("index.json 与 data/ 不同步：%s（重跑 build_index.py）" % d.get("file"))
        if old.get("total") != total:
            bad += fail("index.json total=%s 实际=%s" % (old.get("total"), total))
        print("== --check：%s ==" % ("一致 ✓" if bad == 0 else "%d 处不同步" % bad))
        return 1 if bad else 0

    with io.open(index_path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(index, f, ensure_ascii=False, indent=2)
        f.write("\n")
    print("== index.json 已生成：v%s · %d 域 · 共 %d 条 ==" % (version, len(domains_out), total))
    return 0


if __name__ == "__main__":
    sys.exit(main())
