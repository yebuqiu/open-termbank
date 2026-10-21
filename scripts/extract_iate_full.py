#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""IATE 全量 dump 流式抽取器：IATE_download.zip 里的 TBX → en+zh 候选 TSV。

⚠️ 2026-10-21 实测结论（重要）：IATE 官方全量 dump（IATE_export_26022019.tbx，
93.5 万 termEntry / 1.86GB）**不含任何中文语言集**——IATE 仅覆盖 24 种欧盟官方语言
+ 拉丁语，全文件 grep 'xml:lang="zh' 零匹配。en+zh 方向不能指望 IATE。
本脚本保留价值：① 若未来 IATE 加入中文可直接复用；② 其它语言对（en↔fr/de/…）可抽；
③ 域名映射与可靠度过滤管线已在 select_iate.py 备好。

与 import_iate.py 的分工：
  - import_iate.py   面向「官网下载页按域导出的小 TBX」（整读内存）；
  - 本脚本           面向官方全量 dump（~1GB XML），ET.iterparse 流式逐 termEntry
                     解析、即时丢弃，内存占用与条目数无关。

用法：
  python scripts/extract_iate_full.py .work-iate/IATE_download.tbx --out .work-iate/iate-en-zh.tsv

输出 TSV 列：en <TAB> zh <TAB> subjectField <TAB> reliability（同 en 多义取最高可靠度）。
过滤：en 2~60 字符、zh 1~30 字符、en≠zh、字段内无 TAB/换行/ASCII 逗号/双引号
（本库 CSV「无引号纯文本」纪律的源头保障——带逗号的 IATE 词条如 "acid, fatty" 直接弃）。

许可：IATE 数据 © European Union，再分发署名 "Download IATE, European Union, <年份>"——
本脚本只抽取不改写；入选条目进库时在 data/SOURCES.md 登记署名行。
"""
import argparse
import io
import os
import re
import sys
import xml.etree.ElementTree as ET

LANG_ALIAS = {
    "en": "en", "eng": "en",
    "zh-CN": "zh", "zh-cn": "zh", "zh": "zh", "zho": "zh",
    "zh-Hans": "zh", "cmn-Hans": "zh",
}
BAD_CHARS = re.compile(r"[,\t\r\n\"]")


def _local(tag):
    return tag.split("}", 1)[-1] if "}" in tag else tag


def _iter_entries(path):
    """流式产出 termEntry 元素（处理完即清理，内存恒定）。"""
    context = ET.iterparse(path, events=("end",))
    for _, elem in context:
        if _local(elem.tag) == "termEntry":
            yield elem
            elem.clear()


def _entry_to_pair(elem):
    """termEntry → (en, zh, field, reliability)；不合要求返回 None。"""
    langs = {}
    field = ""
    reliability = 0
    for node in elem.iter():
        t = _local(node.tag)
        if t == "langSet":
            code = LANG_ALIAS.get(node.get("{http://www.w3.org/XML/1998/namespace}lang", "") or "")
            if not code or code in langs:
                continue
            for tig in node.iter():
                if _local(tig.tag) != "tig":
                    continue
                for tm in tig.iter():
                    if _local(tm.tag) == "term" and (tm.text or "").strip():
                        langs.setdefault(code, tm.text.strip())
                        break
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
    en = langs.get("en", "")
    zh = langs.get("zh", "")
    if not en or not zh or en == zh:
        return None
    if not (2 <= len(en) <= 60) or not (1 <= len(zh) <= 30):
        return None
    if BAD_CHARS.search(en) or BAD_CHARS.search(zh):
        return None
    return en, zh, field, reliability


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("tbx", help="全量 dump 解压后的 .tbx 路径")
    ap.add_argument("--out", required=True, help="输出 TSV 路径")
    args = ap.parse_args()

    if not os.path.exists(args.tbx):
        print("找不到 TBX：%s" % args.tbx)
        return 1

    best = {}  # en.lower() → (en, zh, field, reliability)
    scanned = kept = 0
    for elem in _iter_entries(args.tbx):
        scanned += 1
        if scanned % 100000 == 0:
            print("  …已扫描 %d 个 termEntry，保留 %d" % (scanned, len(best)))
        pair = _entry_to_pair(elem)
        if not pair:
            continue
        en, zh, field, rel = pair
        key = en.lower()
        if key not in best or rel > best[key][3]:
            best[key] = (en, zh, field, rel)
        kept += 1

    with io.open(args.out, "w", encoding="utf-8", newline="\n") as f:
        f.write("en\tzh\tsubjectField\treliability\n")
        for (en, zh, field, rel) in sorted(best.values(), key=lambda x: x[0].lower()):
            f.write("%s\t%s\t%s\t%d\n" % (en, zh, field, rel))

    fields = {}
    for (_, _, field, _) in best.values():
        fields[field or "(无)"] = fields.get(field or "(无)", 0) + 1
    print("== 抽取完成：扫描 %d 个 termEntry，en+zh 双语 %d 条（去重后） ==" % (scanned, len(best)))
    print("subjectField 分布（前 20）：")
    for k, v in sorted(fields.items(), key=lambda x: -x[1])[:20]:
        print("   %-46s %d" % (k[:46], v))
    return 0


if __name__ == "__main__":
    sys.exit(main())
