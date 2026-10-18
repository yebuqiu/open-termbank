#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""通用导入器：把外部 CSV / TSV / JSON /「原文 = 译文」行式文本合并进指定域的数据文件。

用法：
  python scripts/import_csv.py input.csv --domain 计算机
  python scripts/import_csv.py input.tsv --domain 计算机 --new-domain 化学 --slug chemistry --en Chemistry
  python scripts/import_csv.py input.json --domain 医学

识别形态（与 PaperPilot 插件的 parseGlossaryImport 同一套判定思路）：
  1. JSON 数组：[{"s":"..","t":"..","d":".."}] 或 [["s","t"(,"d")]]；
  2. 带表头 CSV/TSV：source,target(,domain) / 原文,译文(,领域) / en,zh_CN…（多余列忽略）；
  3. 裸两三列 CSV/TSV；
  4. 行式：`原文 = 译文` / `=>` / TAB（本库与 PaperPilot 的原生格式）。

合并语义 = 行级 upsert：同 source（大小写不敏感）新译覆盖，其余追加；表头保持规范。
导入后自动跑一遍 build_index.py --check 提醒同步 index.json。
⚠️ 贡献纪律（见 README）：只导入你有权再分发的数据；来源与许可记录进 data/SOURCES.md。
"""
import argparse
import csv
import io
import json
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")
HEADER = ["source", "target", "domain"]

HDR_S = re.compile(r"^(source|src|en[a-z_-]*|english|term|原文|词语|源语)$", re.I)
HDR_T = re.compile(r"^(target|tgt|dst|zh[a-z_-]*|chinese|translation|译文|译语|目标语)$", re.I)
HDR_D = re.compile(r"^(domain|field|subject|tag|领域|学科|标签)$", re.I)


def parse_text(text):
    """任意形态 → [(s, t, d)]（d 可为空，由调用方填充/校验）。"""
    src = text.lstrip("\ufeff").strip()
    if not src:
        return []
    out = []
    if src.startswith("["):
        try:
            for it in json.loads(src):
                s = it.get("s") if isinstance(it, dict) else it[0]
                t = it.get("t") if isinstance(it, dict) else it[1]
                d = (it.get("d") if isinstance(it, dict) else (it[2] if len(it) > 2 else "")) or ""
                if s and t and s != t:
                    out.append((str(s).strip(), str(t).strip(), str(d).strip()))
            return out
        except Exception:
            pass
    lines = [l for l in src.splitlines() if l.strip()]
    if not lines:
        return []
    sep = "\t" if ("\t" in lines[0] and "," not in lines[0]) else ","
    first = [c.strip() for c in next(csv.reader(io.StringIO(lines[0])))]
    if len(first) >= 2 and HDR_S.match(first[0]) and HDR_T.match(first[1]):
        di = 2 if (len(first) >= 3 and HDR_D.match(first[2])) else -1
        for line in lines[1:]:
            cols = [c.strip() for c in next(csv.reader(io.StringIO(line)))]
            if len(cols) >= 2 and cols[0] and cols[1] and cols[0] != cols[1]:
                out.append((cols[0], cols[1], (cols[di] if di >= 2 else "") or
                            (cols[2] if len(cols) > 2 else "")))
        return out
    # 行式（含 = / => / TAB）
    if sum(1 for l in lines if re.search(r"\s(=>|=)\s|\t", l)) >= len(lines) / 2.0:
        for line in lines:
            m = re.match(r"^(.+?)\s*(?:=>|=)\s*(.+)$", line.replace("\t", " => ").strip())
            if m and m.group(1).strip() != m.group(2).strip():
                out.append((m.group(1).strip(), m.group(2).strip(), ""))
        return out
    # 裸 CSV/TSV
    for line in lines:
        cols = [c.strip() for c in next(csv.reader(io.StringIO(line), delimiter=sep))]
        if 2 <= len(cols) <= 3 and cols[0] and cols[1] and cols[0] != cols[1]:
            out.append((cols[0], cols[1], cols[2] if len(cols) > 2 else ""))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("input", help="输入文件（CSV/TSV/JSON/行式文本）")
    ap.add_argument("--domain", help="目标域标签（中文，须已在 domains.json 登记）")
    ap.add_argument("--new-domain", help="顺带登记新域（与 --slug/--en 配套）")
    ap.add_argument("--slug", help="新域的文件名标识，如 chemistry")
    ap.add_argument("--en", help="新域英文名，如 Chemistry")
    args = ap.parse_args()

    if not os.path.exists(args.input):
        print("输入文件不存在：%s" % args.input)
        return 1
    with io.open(args.input, encoding="utf-8-sig") as f:
        items = parse_text(f.read())
    if not items:
        print("未识别到任何术语（支持 JSON / 带表头 CSV-TSV / 裸两三列 / 行式）")
        return 1

    if args.new_domain:
        if not (args.slug and args.en and args.domain == args.new_domain):
            print("登记新域需同时给 --new-domain/--slug/--en，且 --domain 与新域一致")
            return 1
        dpath = os.path.join(DATA, "domains.json")
        meta = json.load(io.open(dpath, encoding="utf-8"))
        if any(d["slug"] == args.slug for d in meta["domains"]):
            print("slug 已存在：%s" % args.slug)
            return 1
        meta["domains"].append({
            "domain": args.new_domain, "slug": args.slug, "en": args.en,
            "source_note": "外部导入（%s）；来源与许可见 SOURCES.md" % args.input,
        })
        with io.open(dpath, "w", encoding="utf-8", newline="\n") as f:
            json.dump(meta, f, ensure_ascii=False, indent=2)
            f.write("\n")
        with io.open(os.path.join(DATA, args.slug + ".csv"), "w", encoding="utf-8", newline="\n") as f:
            f.write(",".join(HEADER) + "\n")
        print("已登记新域 %s（%s / %s）" % (args.new_domain, args.slug, args.en))

    domain = args.domain
    meta = json.load(io.open(os.path.join(DATA, "domains.json"), encoding="utf-8"))
    match = [d for d in meta["domains"] if d["domain"] == domain]
    if not match:
        print("域「%s」未在 domains.json 登记（用 --new-domain 登记）" % domain)
        return 1
    slug = match[0]["slug"]
    target = os.path.join(DATA, slug + ".csv")

    existing = {}
    if os.path.exists(target):
        with io.open(target, encoding="utf-8") as f:
            for r in csv.reader(f):
                if r and r[0] != "source":
                    existing[r[0].lower()] = (r[0], r[1], r[2])
    added = updated = skipped = 0
    for (s, t, d) in items:
        if d and d != domain:
            skipped += 1  # 行内自带域与目标域不一致 → 不动，避免静默串域
            continue
        key = s.lower()
        if key in existing:
            if existing[key][1] != t:
                existing[key] = (s, t, domain)
                updated += 1
            else:
                skipped += 1
        else:
            existing[key] = (s, t, domain)
            added += 1

    with io.open(target, "w", encoding="utf-8", newline="\n") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(HEADER)
        for (s, t, d) in existing.values():
            w.writerow([s, t, d])
    print("data/%s.csv：新增 %d、更新 %d、跳过 %d（同译或域不符）" % (slug, added, updated, skipped))
    print("→ 记得把来源与许可写进 data/SOURCES.md，然后跑 scripts/build_index.py 同步 index.json")
    r = subprocess.call([sys.executable, os.path.join(ROOT, "scripts", "build_index.py"), "--check"])
    return 0 if r == 0 else 0  # check 失败不算导入失败，只提醒


if __name__ == "__main__":
    sys.exit(main())
