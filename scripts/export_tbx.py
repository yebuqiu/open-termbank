#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""open-termbank TBX 导出器：data/*.csv → tbx/open-termbank.tbx（TBX-Min 方言）。

TBX（ISO 30042 / TermBase eXchange）是术语交换的行业标准，CAT 工具
（OmegaT / memoQ / Trados / cafe.trique…）基本都能导入。这里生成最简的
TBX-Min 骨架：每条术语一个 termEntry，两个 langSet（en / zh-CN），
领域写进 descrip type="subjectField"（TBX 的标准数据类目）。

用法：
  python scripts/export_tbx.py               # 全部领域 → tbx/open-termbank.tbx
  python scripts/export_tbx.py --domain 医学  # 单域 → tbx/open-termbank-medicine.tbx

零第三方依赖；XML 转义手工处理（仅 & < > 需要转义出现在术语文本里的情况）。
"""
import argparse
import csv
import io
import os
import sys
from xml.sax.saxutils import escape

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")
OUT = os.path.join(ROOT, "tbx")


def read_all():
    """读全部数据文件。兼容三列（v1.x）与五列（v2.x）行，统一返回五元组。"""
    rows = []
    for f in sorted(x for x in os.listdir(DATA) if x.endswith(".csv")):
        with io.open(os.path.join(DATA, f), encoding="utf-8") as fh:
            for r in csv.reader(fh):
                if r and r[0] != "source" and len(r) >= 3:
                    s, t, d = r[0].strip(), r[1].strip(), r[2].strip()
                    df = r[3].strip() if len(r) > 3 else ""
                    sy = r[4].strip() if len(r) > 4 else ""
                    rows.append((s, t, d, df, sy))
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--domain", default=None, help="只导出该域（按域标签过滤）")
    args = ap.parse_args()

    rows = read_all()
    if args.domain:
        rows = [r for r in rows if r[2] == args.domain]
    if not rows:
        print("没有可导出的条目")
        return 1

    os.makedirs(OUT, exist_ok=True)
    name = "open-termbank" + (("-" + args.domain) if args.domain else "") + ".tbx"
    path = os.path.join(OUT, name)

    parts = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<martif type="TBX-Min" xml:lang="en">',
        '  <martifHeader>',
        '    <fileDesc>',
        '      <titleStmt><title>open-termbank</title></titleStmt>',
        '      <sourceDesc><p>Multi-domain English-Chinese termbase '
        '(data: CC BY 4.0, https://github.com/yebuqiu/open-termbank)</p></sourceDesc>',
        '    </fileDesc>',
        '    <encodingDesc><p type="XCSURI" value="tbxxcs.xcs"/></encodingDesc>',
        '  </martifHeader>',
        '  <text><body>',
    ]
    for i, (s, t, d, df, sy) in enumerate(rows, start=1):
        parts.append('    <termEntry id="otb-%d">' % i)
        if sy:
            # 英文 langSet：主术语 + 每个同义词各一个 tig（TBX-Min 允许 0..n tig）
            tigs = ['<tig><term>%s</term></tig>' % escape(s)]
            for alt in (x.strip() for x in sy.split(";")):
                if alt and alt.lower() != s.lower():
                    tigs.append('<tig><term>%s</term></tig>' % escape(alt))
            parts.append('      <langSet xml:lang="en">%s</langSet>' % "".join(tigs))
        else:
            parts.append('      <langSet xml:lang="en"><tig><term>%s</term></tig></langSet>'
                         % escape(s))
        parts.append('      <langSet xml:lang="zh-CN"><tig><term>%s</term></tig></langSet>'
                     % escape(t))
        parts.append('      <descrip type="subjectField">%s</descrip>' % escape(d))
        if df:
            parts.append('      <descrip type="definition">%s</descrip>' % escape(df))
        parts.append('    </termEntry>')
    parts.append('  </body></text>')
    parts.append('</martif>')

    with io.open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(parts) + "\n")
    print("已导出 %d 条 → %s" % (len(rows), path))
    return 0


if __name__ == "__main__":
    sys.exit(main())
