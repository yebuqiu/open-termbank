# open-termbank · 多学科中英术语对照数据库

> 一个**按学科领域组织、可自由选择与下载**的英中术语对照（termbase）开放数据库。
> 供翻译工具、CAT 插件、词典应用、NLP 术语一致性评测等直接消费。

## 为什么需要它

GitHub 上已有的中英术语资源都是**散的**：

- **单领域散库**：计算机（EECS-Terminology）、AI（机器之心 AITD）、医学（meddict、rime_clinic）、
  金融（finance_i18n）……格式各异（CSV/YAML/MD/txt）、许可不明、各自停更；
- **机构门户**：IATE（欧盟）/ EuroTermBank / 微软术语集——多领域+可筛领域，但**不在 GitHub**、
  下载受限（IATE 要登录、EuroTermBank 无批量下载、微软许可绑定其产品生态）；
- **通用词典**：ECDICT 等无学科维度。

「**多学科领域分类 + 中英对照 + 机器可读 + 按域取用 + 宽松许可**」四者兼备的库不存在
（结构上最接近的先例是南非 11 语言的 [za-marito](https://github.com/dsfsi/za-marito)，
语言对不同）。本库补上 en→zh-CN 这一格。详细调研见
PaperPilot 仓库《术语库开源项目调研与术语表领域化设计》文档（15 个项目的逐项对比）。

## 数据规范

```
data/
  domains.json            领域注册表（域标签 / slug / 英文名）
  computer-science.csv    每域一文件，UTF-8 无 BOM
  medicine.csv            表头固定：source,target,domain
  finance.csv             domain 列 = domains.json 里的规范中文域标签
  law.csv
  index.json              同步协议入口：版本 + 每域 sha256 + 条数（脚本生成，勿手改）
  SOURCES.md              来源与许可登记（每笔外部导入必须记一行）
tbx/
  open-termbank.tbx       TBX-Min 导出（CAT 工具通用，脚本生成）
```

- **行格式**：`transformer,Transformer,计算机`——三列，不多不少；
- **同 source 不重复**（文件内大小写不敏感去重；跨域同词允许但会告警）；
- **域标签即分类**：加领域 = 在 `domains.json` 登记 + 新建 `data/<slug>.csv`；
- 机器入口是 `index.json`：`version`、`updated`、每域 `file/count/sha256`。

## 怎么用（消费方）

**直接取文件**（任选其一）：

```
https://cdn.jsdelivr.net/gh/yebuqiu/open-termbank@main/data/medicine.csv   # jsDelivr（有缓存）
https://raw.githubusercontent.com/yebuqiu/open-termbank/main/data/medicine.csv
```

**增量同步**（推荐给应用做「在线词包」）：轮询 `index.json`，对比本地记录的每域
`sha256`，变了才重新拉对应 CSV——一次请求即可判断有无更新。

**CAT 工具**：导入 `tbx/open-termbank.tbx`（TBX-Min 方言；或自己跑
`python scripts/export_tbx.py` 生成最新版）。

**示例（PaperPilot 等「术语表」型消费方）**：CSV 三列即
`source,target,domain`——下载后整文件导入术语表即可获得带领域标注的条目，
领域启停、命中优先注入等能力直接生效。

## 构建 / 校验 / 导入

```bash
python scripts/build_index.py --version 1.0.0   # 校验所有数据 + 生成 index.json
python scripts/build_index.py --check           # 只校验（CI / 提交前）
python scripts/export_tbx.py                    # 重新生成 TBX
python scripts/import_csv.py 输入.csv --domain 计算机          # 通用导入（CSV/TSV/JSON/行式）
python scripts/import_iate.py iate导出.tbx --domain 医学 --reliability 3   # IATE TBX 导入
```

全部 Python 3 标准库、零依赖。

## 贡献纪律（重要）

**欢迎 PR**：改对应 `data/<slug>.csv` 或登记新域（`domains.json` + 新 CSV），
提交前跑 `python scripts/build_index.py` 让 index.json 同步；外部导入须在
`data/SOURCES.md` 登记来源与许可。

**只收你能合法再分发的数据**。明确**禁止**直收（即使它们公开可下载）：

| 来源 | 为什么不能收 |
|------|--------------|
| UMLS / SNOMED 派生翻译（如 meddict 的 umls_* 文件） | UMLS 许可证限制再分发 |
| 搜狗词库衍生数据（如 rime_clinic 部分词库） | 上游词库版权不明 |
| 微软术语集（MicrosoftTermCollection 及其 CSV 衍生） | Language Portal 许可绑定微软产品生态，非开放再分发 |
| 商业词典的任何转换产物 | 版权 |
| 机器之心 AITD 表格直搬 | 仓库许可不明（未声明开放数据许可） |

**可以收**：自编/原创条目（附来源说明）、你自有版权的词表、
**IATE 导出**（其条款允许再分发，只需署名 `Download IATE, European Union, [年份]`——
用 `scripts/import_iate.py` 并在 SOURCES.md 登记署名行）。

## 许可

- **数据**（`data/` 全部 CSV/JSON 与 `tbx/` 导出物）：[CC BY 4.0](data/LICENSE)——
  署名后可商用与演绎；建议署名格式：`open-termbank contributors, CC BY 4.0`；
- **代码**（`scripts/`）：[Apache-2.0](LICENSE)。

## 现状与路线

- v1.0.0（2026-10）：4 域 80 条自编种子（计算机/AI、医学、金融、法律），
  数据规范与同步协议定型，IATE 导入器就绪；
- 下一步：用 IATE 导入器成规模扩充（en+zh 全域）；社区 PR 补域（化学、生物、
  心理学、电子工程…）；可选 Zenodo/HuggingFace 镜像发布 DOI。
