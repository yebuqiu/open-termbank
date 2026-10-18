#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""IATE 导入器：解析 IATE 导出的 TBX（ISO 30042），抽取 en + zh-CN 双语条目。

背景（为什么值得收）：
  IATE 的下载条款明确允许再分发与演绎，只需署名 "Download IATE, European Union, [年份]"。
  这是本库唯一建议**成规模收录**的外部官方源（微软术语集/搜狗衍生/UMLS 派生数据均禁止直收，
  见 README 贡献纪律）。

用法：
  1. 在 https://iate.europa.eu/download-iate 注册登录，选 English + Chinese + 目标领域，
     导出 TBX，得到压缩包里的 .tbx 文件；
  2. python scripts/import_iate.py iate-export.tbx --domain 医学
       （可选 --reliability 3 只收三星及以上；--limit 500 限量试跑）
  3. 按提示补 data/SOURCES.md 的署名行，跑 scripts/build_index.py。

映射规则：
  termEntry → 找 xml:lang="en" 与 xml:lang="zh-CN"（容 zh-Hans/zh（简体）别名）各取
  首个 <term>；descrip type="subjectField"（或 <subjectField>）取领域原文——IATE 域名是
  英文短语（如 "Health"），默认仅作记录：仅当 --domain 显式指定映射到本库某中文域时才写入。
  零依赖手写流式解析（TBX 是规整 XML，std 库足够；不求全解，只求这一种结构稳定可靠）。
"""
import argparse
import csv
import io
import json
import os
import re
import sys
import xml.etree.ElementTree as ET

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")
HEADER = ["source", "target", "domain"]

# IATE 语言码 → 本库语言
LANG_ALIAS = {
    "en": "en", "eng": "en",
    "zh-CN": "zh", "zh-cn": "zh", "zh": "zh", "zho": "zh", "zh-Hans": "zh", "cmn-Hans": "zh",
}
NS_TBX = "{urn:x-TBX:TBXcore}"


def _local(tag):
    return tag.split("}", 1)[-1] if "}" in tag else tag


def extract_entries(tbx_path, reliability_min=0, limit=0):
    """流式解析 TBX → [{en, zh, field, reliability}]。"""
    out = []
    # 去掉 DOCTYPE（ElementTree 不吃带参数的 DTD 声明）
    with io.open(tbx_path, encoding="utf-8", errors="replace") as f:
        text = f.read()
    text = re.sub(r"<!DOCTYPE[^>]*\[[^\]]*\]>", "", text, count=1)
    text = re.sub(r"<!DOCTYPE[^>]*>", "", text, count=1)
    root = ET.fromstring(text.encode("utf-8"))

    for entry in root.iter():
        if _local(entry.tag) != "termEntry":
            continue
        langs = {}
        field = ""
        reliability = 0
        for node in entry.iter():
            t = _local(node.tag)
            if t == "langSet":
                code = LANG_ALIAS.get(node.get("{http://www.w3.org/XML/1998/namespace}lang", "") or "")
                if code and code not in langs:
                    for tig in node.iter():
                        if _local(tig.tag) == "tig":
                            for tm in tig.iter():
                                if _local(tm.tag) == "term" and (tm.text or "").strip():
                                    langs.setdefault(code, tm.text.strip())
                                    break
                            # 可靠度挂在 tig/descripGrp/descrip type=reliability
                            for dp in tig.iter():
                                if _local(dp.tag) == "descrip" and (dp.get("type") or "") == "reliability":
                                    m = re.search(r"\d+", dp.text or "")
                                    if m:
                                        reliability = max(reliability, int(m.group()))
                            break
            elif t == "descrip" and (node.get("type") or "") == "subjectField":
                field = (node.text or "").strip()
            elif t == "subjectField":
                field = (node.text or "").strip()
        if "en" in langs and "zh" in langs and langs["en"] != langs["zh"]:
            if reliability >= reliability_min:
                out.append({"en": langs["en"], "zh": langs["zh"],
                            "field": field, "reliability": reliability})
                if limit and len(out) >= limit:
                    break
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("tbx", help="IATE 导出的 .tbx 文件路径")
    ap.add_argument("--domain", required=True, help="写入本库的中文域标签（须已登记）")
    ap.add_argument("--reliability", type=int, default=0, help="最低可靠度星数（1-4），默认 0 不限")
    ap.add_argument("--limit", type=int, default=0, help="最多导入条数（试跑用）")
    args = ap.parse_args()

    meta_path = os.path.join(DATA, "domains.json")
    meta = json.load(io.open(meta_path, encoding="utf-8"))
    if not any(d["domain"] == args.domain for d in meta["domains"]):
        print("域「%s」未在 domains.json 登记" % args.domain)
        return 1
    slug = [d for d in meta["domains"] if d["domain"] == args.domain][0]["slug"]
    target = os.path.join(DATA, slug + ".csv")

    entries = extract_entries(args.tbx, args.reliability, args.limit)
    if not entries:
        print("未抽取到 en+zh 双语条目（检查导出语言是否含 English 与 Chinese）")
        return 1

    existing = {}
    if os.path.exists(target):
        with io.open(target, encoding="utf-8") as f:
            for r in csv.reader(f):
                if r and r[0] != "source":
                    existing[r[0].lower()] = (r[0], r[1], r[2])
    added = skipped = 0
    for e in entries:
        key = e["en"].lower()
        if key in existing:
            skipped += 1
            continue
        existing[key] = (e["en"], e["zh"], args.domain)
        added += 1

    with io.open(target, "w", encoding="utf-8", newline="\n") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(HEADER)
        for row in existing.values():
            w.writerow(row)
    print("IATE → data/%s.csv：新增 %d、已存在跳过 %d（subjectField 分布见下）" % (slug, added, skipped))
    fields = {}
    for e in entries:
        fields[e["field"] or "(无)"] = fields.get(e["field"] or "(无)", 0) + 1
    for k, v in sorted(fields.items(), key=lambda x: -x[1])[:10]:
        print("   %-40s %d" % (k[:40], v))
    print("→ ⚠ 署名义务：在 data/SOURCES.md 记一行 "Download IATE, European Union, <年份>"")
    return 0


if __name__ == "__main__":
    sys.exit(main())
