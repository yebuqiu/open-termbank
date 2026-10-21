# open-termbank · 多学科中英术语对照数据库

[![check](https://github.com/yebuqiu/open-termbank/actions/workflows/check.yml/badge.svg)](https://github.com/yebuqiu/open-termbank/actions/workflows/check.yml)
[![数据许可 CC BY 4.0](https://img.shields.io/badge/data-CC%20BY%204.0-blue.svg)](data/LICENSE)
<!-- Zenodo DOI 徽标：开启 Zenodo 集成后替换（见 PUBLISHING.md） -->

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
  computer-science.csv    每域一文件，UTF-8 无 BOM、LF 换行
  medicine.csv            表头固定：source,target,domain,definition,synonyms
  …（共 20 域）           domain 列 = domains.json 里的规范中文域标签
  index.json              同步协议入口：版本 + 每域 sha256 + 条数（脚本生成，勿手改）
  SOURCES.md              来源与许可登记（每笔外部导入必须记一行）
tbx/
  open-termbank.tbx       TBX-Min 导出（CAT 工具通用，脚本生成）
```

**行格式**（v2.0.0 起五列）：

```
quenching,淬火,材料,将钢加热保温后快速冷却以获得马氏体组织的热处理,quench hardening
```

| 列 | 含义 | 约束 |
|----|------|------|
| source | 英文术语 | 通用小写（缩写/专名除外）；文件内唯一（大小写不敏感） |
| target | 规范中文译名 | 教科书/标准/学界通行译法 |
| domain | 领域标签 | 须在 `domains.json` 登记 |
| definition | 简明中文定义 | **必填**，15~60 字，自编（不抄词典） |
| synonyms | 英文同义词/缩写 | 可空；多个用 `; ` 分隔 |

- **字节纪律**：字段内禁止 ASCII 逗号 / 双引号 / 换行（定义用中文标点）——
  全库「无引号纯文本」，朴素 `split(",")` 解析也安全；三列时代的消费方
  按位置取前三列即可，多余列自然忽略（向后兼容）；
- **同 source 不重复**（文件内大小写不敏感去重；跨域同词允许但会告警）；
- **域标签即分类**：加领域 = 在 `domains.json` 登记 + 新建 `data/<slug>.csv`；
- 机器入口是 `index.json`：`version`、`updated`、`schema`、每域 `file/count/sha256`。

**领域一览（v2.0.0，20 域 × 100 条）**：计算机、医学、金融、法律、工程、
生物、化学、物理、数学、教育、心理学、语言学、艺术、环境、材料、能源、
管理、传播、农业、天文。

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
python scripts/build_index.py --version 2.0.0   # 校验所有数据 + 生成 index.json
python scripts/build_index.py --check           # 只校验（CI / 提交前）
python scripts/export_tbx.py                    # 重新生成 TBX
python scripts/import_csv.py 输入.csv --domain 计算机          # 通用导入（CSV/TSV/JSON/行式）
python scripts/import_iate.py iate导出.tbx --domain 医学 --reliability 3   # IATE 按域导出 TBX 导入
python scripts/extract_iate_full.py dump.tbx --out en-zh.tsv   # IATE 全量 dump 流式抽取
python scripts/select_iate.py en-zh.tsv --reliability 3        # 候选遴选（域映射+去重+限额）
python scripts/sync_remote.py             # 同步到 GitHub（REST 通道，见下）
```

全部 Python 3 标准库、零依赖（仅 HF 镜像推送脚本需要 `huggingface_hub`）。
**为什么发布走 REST 而不是 git push**：本机的
github.com git 协议被网络阻断（api.github.com 通畅）——`sync_remote.py` 沿用
PaperPilot 项目 sync-github.py 的「blob 内容寻址增量」打法；令牌从
`PP_GITHUB_TOKEN` 环境变量或密钥库文件读取，不进命令行。

## 社区贡献与镜像

- **贡献**：见 [CONTRIBUTING.md](CONTRIBUTING.md)（数据契约 / 质量门槛 / PR 流程）；
  CI 门禁自动校验每个 PR；
- **镜像与 DOI**：Zenodo（`.zenodo.json` 已备，开启集成即发 Release 自动铸 DOI）与
  HuggingFace Datasets（`hf/` 数据集卡 + 推送脚本）——操作步骤见
  [PUBLISHING.md](PUBLISHING.md)；引用格式见 [CITATION.cff](CITATION.cff)。

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
⚠️ **2026-10-21 实测：IATE 官方全量 dump 仅含欧盟 24 种官方语言，没有中文**；
`import_iate.py` / `extract_iate_full.py` 仅在 IATE 未来收录中文或处理其它语言对时有用，
en+zh 方向本库靠**自编扩充**。

## 许可

- **数据**（`data/` 全部 CSV/JSON 与 `tbx/` 导出物）：[CC BY 4.0](data/LICENSE)——
  署名后可商用与演绎；建议署名格式：`open-termbank contributors, CC BY 4.0`；
- **代码**（`scripts/`）：[Apache-2.0](LICENSE)。

## 现状与路线

- v1.0.0（2026-10-18，已发布）：4 域 80 条自编种子，数据规范与同步协议定型；
- v2.0.0（2026-10-21，已发布）：20 域 × 100 条 = 2000 条，五列模式定型；
- **v2.1.0（2026-10-21，已发布）**：**20 域 3998 条**（第二批每域 +100 条进阶级术语，
  覆盖更细子领域）；社区基础设施上线——CONTRIBUTING.md / 数据门禁 CI（Actions）/
  issue 与 PR 模板；Zenodo（.zenodo.json + CITATION.cff）与 HuggingFace（hf/ 数据集卡
  + 推送脚本）镜像就绪（步骤见 PUBLISHING.md）；
- **IATE 路径证伪**：2026-10-21 实测官方全量 dump（93.5 万条目）无任何中文——
  en+zh 成规模扩充不能走 IATE，本库坚持自编为主、社区 PR 为辅；
- 下一步：社区 PR 补域与补条；Zenodo DOI 与 HF 镜像启用（一次性人工步骤）；
  视需求继续第三批扩充或补新域（如心理学分支、地质、海洋科学）。
