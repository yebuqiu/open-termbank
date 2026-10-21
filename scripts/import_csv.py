#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""通用导入器：把外部 CSV / TSV / JSON /「原文 = 译文」行式文本合并进指定域的数据文件。

用法：
  python scripts/import_csv.py input.csv --domain 计算机
  python scripts/import_csv.py input.tsv --domain 化学 --new-domain 化学 --slug chemistry --en Chemistry
  python scripts/import_csv.py input.json --domain 医学

识别形态（与 PaperPilot 插件的 parseGlossaryImport 同一套判定思路）：
  1. JSON 数组：[{"s","t","d"(,"df","sy")}] 或 [["s","t"(,"d","df","sy")]]；
  2. 带表头 CSV/TSV：source,target(,domain,definition,synonyms) / 原文,译文…
     ——domain/definition/synonyms 列按表头名识别（位置不限），多余列忽略；
  3. 裸二至五列 CSV/TSV；
  4. 行式：`原文 = 译文` / `=>` / TAB（本库与 PaperPilot 的原生格式）。

合并语义 = 行级 upsert：同 source（大小写不敏感）新译覆盖，其余追加；表头保持
规范五列。**注意**：v2.0.0 起 definition 为必填校验项——外部导入若无定义列，
请补写 definition 后再跑 build_index.py（门禁会拦下空定义）。
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
HEADER = ["source", "target", "domain", "definition", "synonyms"]

HDR_S = re.compile(r"^(source|src|en[a-z_-]*|english|term|原文|词语|源语)$", re.I)
HDR_T = re.compile(r"^(target|tgt|dst|zh[a-z_-]*|chinese|translation|译文|译语|目标语)$", re.I)
HDR_D = re.compile(r"^(domain|field|subject|tag|领域|学科|标签)$", re.I)
HDR_DF = re.compile(r"^(definition|def|gloss|定义|释义)$", re.I)
HDR_SY = re.compile(r"^(synonyms?|abbr|同义词|缩写)$", re.I)


def parse_text(text):
    """任意形态 → [(s, t, d, df, sy)]（d/df/sy 可为空，由调用方填充/校验）。"""
    src = text.lstrip("﻿").strip()
    if not src:
        return []
    out = []
    if src.startswith("["):
        try:
            for it in json.loads(src):
                if isinstance(it, dict):
                    s, t = it.get("s"), it.get("t")
                    d = it.get("d") or ""
                    df = it.get("df") or it.get("definition") or ""
                    sy = it.get("sy") or it.get("synonyms") or ""
                else:
                    s, t = it[0], it[1]
                    d = it[2] if len(it) > 2 else ""
                    df = it[3] if len(it) > 3 else ""
                    sy = it[4] if len(it) > 4 else ""
                if s and t and s != t:
                    out.append((str(s).strip(), str(t).strip(), str(d).strip(),
                                str(df).strip(), str(sy).strip()))
            return out
        except Exception:
            pass
    lines = [l for l in src.splitlines() if l.strip()]
    if not lines:
        return []
    sep = "\t" if ("\t" in lines[0] and "," not in lines[0]) else ","
    first = [c.strip() for c in next(csv.reader(io.StringIO(lines[0])))]
    if len(first) >= 2 and HDR_S.match(first[0]) and HDR_T.match(first[1]):
        # 列定位：domain/definition/synonyms 按表头名识别（位置不限，多余列忽略）
        di = dfi = syi = -1
        for i, h in enumerate(first):
            if di < 0 and HDR_D.match(h):
                di = i
            elif dfi < 0 and HDR_DF.match(h):
                dfi = i
            elif syi < 0 and HDR_SY.match(h):
                syi = i
        for line in lines[1:]:
            cols = [c.strip() for c in next(csv.reader(io.StringIO(line)))]
            if len(cols) >= 2 and cols[0] and cols[1] and cols[0] != cols[1]:
                def col(i):
                    return cols[i] if 0 <= i < len(cols) else ""
                out.append((cols[0], cols[1], col(di), col(dfi), col(syi)))
        return out
    # 行式（含 = / => / TAB）
    if sum(1 for l in lines if re.search(r"\s(=>|=)\s|\t", l)) >= len(lines) / 2.0:
        for line in lines:
            m = re.match(r"^(.+?)\s*(?:=>|=)\s*(.+)$", line.replace("\t", " => ").strip())
            if m and m.group(1).strip() != m.group(2).strip():
                out.append((m.group(1).strip(), m.group(2).strip(), "", "", ""))
        return out
    # 裸 CSV/TSV（二至五列）
    for line in lines:
        cols = [c.strip() for c in next(csv.reader(io.StringIO(line), delimiter=sep))]
        if 2 <= len(cols) <= 5 and cols[0] and cols[1] and cols[0] != cols[1]:
            cols += [""] * (5 - len(cols))
            out.append((cols[0], cols[1], cols[2], cols[3], cols[4]))
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
        print("未识别到任何术语（支持 JSON / 带表头 CSV-TSV / 裸二至五列 / 行式）")
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
                if r and r[0] != "source" and len(r) >= 3:
                    r += [""] * (5 - len(r))
                    existing[r[0].lower()] = (r[0], r[1], r[2], r[3], r[4])
    added = updated = skipped = 0
    for (s, t, d, df, sy) in items:
        if d and d != domain:
            skipped += 1  # 行内自带域与目标域不一致 → 不动，避免静默串域
            continue
        key = s.lower()
        if key in existing:
            # 新译/新定义/新同义词任一变化 → 覆盖；定义/同义词新值为空时保留旧值
            olds, oldt, oldd, olddf, oldsy = existing[key]
            newdf = df if df else olddf
            newsy = sy if sy else oldsy
            if oldt != t or olddf != newdf or oldsy != newsy:
                existing[key] = (s, t, domain, newdf, newsy)
                updated += 1
            else:
                skipped += 1
        else:
            existing[key] = (s, t, domain, df, sy)
            added += 1

    with io.open(target, "w", encoding="utf-8", newline="\n") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(HEADER)
        for row in existing.values():
            w.writerow(list(row))
    print("data/%s.csv：新增 %d、更新 %d、跳过 %d（同译或域不符）" % (slug, added, updated, skipped))
    print("→ 记得把来源与许可写进 data/SOURCES.md，然后跑 scripts/build_index.py 同步 index.json")
    print("→ 注意：v2.0.0 起 definition 必填；无定义的行请先补写定义再通过门禁")
    r = subprocess.call([sys.executable, os.path.join(ROOT, "scripts", "build_index.py"), "--check"])
    return 0 if r == 0 else 0  # check 失败不算导入失败，只提醒


if __name__ == "__main__":
    sys.exit(main())
