#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""IATE 候选条目遴选：extract_iate_full.py 的 TSV → 按域候选文件（待补定义）。

管线位置：
  extract_iate_full.py（流式抽取 en+zh 全量子集）
    → 本脚本（域映射 + 可靠度过滤 + 去重既有库 + 每域限额）
    → 定义撰写（人工/辅助）补齐 definition/synonyms 两列
    → import_csv.py 合并入 data/<slug>.csv
    → build_index.py

用法：
  python scripts/select_iate.py .work-iate/iate-en-zh.tsv \
      --reliability 3 --per-domain 100 --out .work-iate/candidates

域映射：IATE subjectField（EuroVoc 式顶层域）→ 本库中文域标签，见 FIELD_MAP；
未映射的 field 一律跳过（宁缺毋滥）。同一 IATE 域可拆进多个本库域时用
--review-fields 先看分布再调 FIELD_MAP。
"""
import argparse
import csv
import io
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")

# IATE subjectField（大写规范化后）→ 本库中文域标签。
# IATE 顶层域是 EuroVoc 风格大类；只收映射关系明确的，模糊域（如 SCIENCE 太宽）不收。
FIELD_MAP = {
    "FINANCE": ["金融"],
    "ECONOMICS": ["金融"],
    "TRADE": ["金融", "管理"],
    "BUSINESS AND COMPETITION": ["管理"],
    "LAW": ["法律"],
    "INTERNATIONAL ORGANISATIONS": ["法律"],
    "INTERNATIONAL RELATIONS": ["法律"],
    "AGRICULTURE, FORESTRY AND FISHERIES": ["农业"],
    "AGRI-FOODSTUFFS": ["农业"],
    "ENERGY": ["能源"],
    "ENVIRONMENT": ["环境"],
    "INDUSTRY": ["工程", "材料"],
    "PRODUCTION, TECHNOLOGY AND RESEARCH": ["工程"],
    "TRANSPORT": ["工程"],
    "EDUCATION AND COMMUNICATIONS": ["教育", "传播"],
    "SCIENCE": ["物理", "化学", "生物", "数学"],
    "SOCIAL QUESTIONS": ["心理学", "教育"],
    "HEALTH": ["医学"],
    "INFORMATION TECHNOLOGY AND DATA PROCESSING": ["计算机"],
    "EUROPEAN COMMUNITIES": [],   # 欧盟行政专名不收
    "POLITICS": [],               # 政治类与本库 20 域不对口
    "GEOGRAPHY": [],              # 地名类不收
    "EMPLOYMENT AND WORKING CONDITIONS": ["管理"],
}


def load_existing():
    """既有库全部 source（小写）→ 不重复收录。"""
    seen = set()
    for f in os.listdir(DATA):
        if not f.endswith(".csv"):
            continue
        with io.open(os.path.join(DATA, f), encoding="utf-8") as fh:
            for r in csv.reader(fh):
                if r and r[0] != "source":
                    seen.add(r[0].strip().lower())
    return seen


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("tsv", help="extract_iate_full.py 产出的 TSV")
    ap.add_argument("--reliability", type=int, default=3, help="最低可靠度（默认 3）")
    ap.add_argument("--per-domain", type=int, default=100, help="每域入选上限（默认 100）")
    ap.add_argument("--out", default=".work-iate/candidates", help="候选输出目录")
    ap.add_argument("--review-fields", action="store_true", help="只看 field 分布不产出")
    args = ap.parse_args()

    meta = json.load(io.open(os.path.join(DATA, "domains.json"), encoding="utf-8"))
    domain_slug = {d["domain"]: d["slug"] for d in meta["domains"]}

    with io.open(args.tsv, encoding="utf-8") as f:
        rows = [line.rstrip("\n").split("\t") for line in f][1:]
    rows = [r for r in rows if len(r) == 4]

    if args.review_fields:
        stat = {}
        for (_, _, field, _) in rows:
            stat[field] = stat.get(field, 0) + 1
        for k, v in sorted(stat.items(), key=lambda x: -x[1]):
            mark = "→" + "/".join(FIELD_MAP.get(k.upper(), ["(跳过)"])) or "(跳过)"
            print("%6d  %-46s %s" % (v, k[:46], mark))
        return 0

    existing = load_existing()
    picked = {}  # slug → list of (en, zh, domain, reliability)
    skipped_dup = skipped_field = skipped_rel = 0
    for (en, zh, field, rel) in rows:
        rel = int(rel)
        if rel < args.reliability:
            skipped_rel += 1
            continue
        targets = FIELD_MAP.get((field or "").upper(), [])
        if not targets:
            skipped_field += 1
            continue
        key = en.strip().lower()
        if key in existing:
            skipped_dup += 1
            continue
        # 多目标域：进第一个未饱和的域（顺序即 FIELD_MAP 内优先级）
        for d in targets:
            slug = domain_slug.get(d)
            if not slug:
                continue
            bucket = picked.setdefault(slug, [])
            if len(bucket) < args.per_domain and all(b[0].lower() != key for b in bucket):
                bucket.append((en, zh, d, rel))
                existing.add(key)  # 防同词跨域重复入选
                break

    os.makedirs(args.out, exist_ok=True)
    total = 0
    for slug, bucket in sorted(picked.items()):
        bucket.sort(key=lambda x: (-x[3], x[0].lower()))
        path = os.path.join(args.out, slug + ".csv")
        with io.open(path, "w", encoding="utf-8", newline="\n") as f:
            w = csv.writer(f, lineterminator="\n")
            w.writerow(["source", "target", "domain", "definition", "synonyms"])
            for (en, zh, d, _rel) in bucket:
                w.writerow([en, zh, d, "", ""])
        total += len(bucket)
        print("  %-22s %4d 条候选" % (slug + ".csv", len(bucket)))
    print("== 候选合计 %d 条（去重既有 %d / 域未映射 %d / 可靠度不足 %d）=="
          % (total, skipped_dup, skipped_field, skipped_rel))
    print("→ 下一步：补齐每个候选文件的 definition/synonyms 列后，用 import_csv.py 合并")
    return 0


if __name__ == "__main__":
    sys.exit(main())
