# 贡献指南 · open-termbank

感谢补域、补条、纠错！本库是**机器消费的术语数据仓**，PR 合入前须过数据门禁
（CI 自动跑 `scripts/build_index.py --check`，红灯不能合）。本文件是唯一的贡献契约。

## 数据契约（每行必须满足）

```csv
source,target,domain,definition,synonyms
quenching,淬火,材料,将钢加热保温后快速冷却以获得马氏体组织的热处理,quench hardening
```

| 列 | 约束 |
|----|------|
| source | 英文术语；通用小写（缩写/专名除外）；文件内唯一（大小写不敏感） |
| target | 规范中文译名：教科书/国标/学界通行写法 |
| domain | 中文域标签，须在 `data/domains.json` 已登记 |
| definition | **必填**，15~60 字简明中文定义，**自编**（不得抄词典/教科书原文整句） |
| synonyms | 可空；英文同义词/缩写，多个用 `; ` 分隔 |

**字节纪律**（CI 硬校验）：

- UTF-8 **无 BOM**；换行一律 **LF**；文件末尾恰好一个换行；
- 字段内**禁止** ASCII 逗号 `,`、双引号 `"`、换行——定义一律用中文标点（，、；：（））；
  这条纪律让最朴素的 `split(",")` 解析也安全，请勿破坏。

## 三种贡献方式

1. **补条**（最常用）：改对应 `data/<slug>.csv`，追加/修订条目（保持上述契约）。
2. **纠错**：直接改行；译法有争议时在 PR 描述里给出依据（教科书/标准/语料）。
3. **补域**：`data/domains.json` 登记（domain/slug/en/source_note）+ 新建
   `data/<slug>.csv`（首批建议 ≥50 条，子领域覆盖均匀），PR 描述说明该域的
   学术/行业地位与术语来源。

## 提交前自检（本地 30 秒）

```bash
python scripts/build_index.py            # 校验全部数据并同步 index.json
python scripts/build_index.py --check    # 复核 index.json 与数据一致
```

两条都绿再提 PR。**index.json 必须与数据同 commit**（它是消费方的增量同步协议）。

## 来源与许可纪律

- 你提交的数据按 **CC BY 4.0** 授权（与全库一致）；提交即表示你有权再分发这些内容。
- **只收**：自编条目、你自有版权的词表、IATE 导出（须署名，用 `scripts/import_iate.py`
  或 `scripts/extract_iate_full.py`，并在 `data/SOURCES.md` 登记一行）。
- **禁收**：UMLS/SNOMED 派生、搜狗词库衍生、微软术语集及其 CSV 衍生、商业词典转换产物、
  机器之心 AITD 表格直搬（许可不明）。完整清单见 README「贡献纪律」。
- 外部导入**必须**在 `data/SOURCES.md` 登记：日期 / 领域 / 来源 / 许可 / 说明。

## PR 礼仪

- 一个 PR 只做一件事（补某域一批条 / 修一批错 / 补一个域），标题写清域与条数；
- CI 红 → 先看 `build_index.py` 输出的行号与原因，多为列数错（混入了 ASCII 逗号）、
  定义为空、source 重复三类；
- 维护者可能要求抽样说明译法依据，请保留查证记录。
