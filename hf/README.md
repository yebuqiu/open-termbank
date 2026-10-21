---
license: cc-by-4.0
task_categories:
  - translation
  - text-retrieval
language:
  - en
  - zh
tags:
  - terminology
  - termbase
  - translation-memory
  - TBX
  - IATE
size_categories:
  - 1K<n<10K
pretty_name: open-termbank
configs:
  - config_name: default
    data_files:
      - split: train
        path: data/*.csv
---

# open-termbank · 多学科中英术语对照数据库

按学科领域组织的英中术语对照（termbase）开放数据库：**20 个领域**，
每条含 `source`（英文术语）/ `target`（规范中文译名）/ `domain`（领域）/
`definition`（简明中文定义）/ `synonyms`（英文同义词，可空）。

- **仓库主页与增量同步协议**：<https://github.com/yebuqiu/open-termbank>
- **TBX-Min 导出**（CAT 工具直接导入）：`tbx/open-termbank.tbx`
- **领域注册表**：`data/domains.json`；**机器入口**：`data/index.json`（版本 + 每域 sha256）
- 领域一览：计算机、医学、金融、法律、工程、生物、化学、物理、数学、教育、
  心理学、语言学、艺术、环境、材料、能源、管理、传播、农业、天文

## 许可与署名

数据 **CC BY 4.0**：`open-termbank contributors, CC BY 4.0`。
含 IATE 来源条目，附加署名：`Download IATE, European Union, 2026`。

## 加载示例

```python
import pandas as pd
df = pd.read_csv("data/medicine.csv")   # 任一域
```
