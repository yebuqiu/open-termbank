# 镜像发布与 DOI 指南（维护者）

本仓已内置发布所需的全部元数据；以下每个镜像都是**一次性配置、之后随 Release 自动/一键**。

## Zenodo（铸 DOI）

仓库根已备好 `.zenodo.json`（标题/描述/许可/关键词）与 `CITATION.cff`。一次性操作：

1. 用 GitHub 账号登录 <https://zenodo.org> → 右上头像 → **GitHub**；
2. 在仓库列表找到 `yebuqiu/open-termbank`，打开 **On** 开关（授权 webhook）；
3. 回到 GitHub 发一个 Release（如 v2.1.0）——Zenodo 会自动归档该版本并铸造
   **概念 DOI**（随版本滚动）与版本 DOI；
4. 把 Zenodo 给的 DOI 徽标贴回 README（下方占位）。

> 本机网络 zenodo.org 不可达，以上步骤需在可访问网络下用浏览器完成（约 2 分钟）。

README 徽标占位（拿到 DOI 后替换 `DOI`）：

```markdown
[![DOI](https://zenodo.org/badge/DOI/DOI.svg)](https://doi.org/DOI)
```

## HuggingFace Datasets 镜像

数据集卡已备好：`hf/README.md`（YAML 头 + 说明）。推送步骤：

```bash
pip install huggingface_hub          # 一次性
huggingface-cli login                # 粘贴 HF token（hf.co/settings/tokens）
python scripts/push_huggingface.py <你的hf用户名>/open-termbank
```

脚本会把 `data/`（全部 CSV + index.json + domains.json）与 `tbx/open-termbank.tbx`、
数据集卡打包推到指定 dataset 仓库。**本机 huggingface.co 不可达**，请在可达网络执行；
HF 侧 CC BY 4.0 许可字段已在数据集卡写死。

## 发布清单（每次发版）

1. `python scripts/build_index.py --version X.Y.Z`（数据有变时）；
2. `python scripts/export_tbx.py`；
3. 更新 `CITATION.cff` 的 `version` / `date-released`；
4. `git commit` → `python scripts/sync_remote.py`（本机 REST 通道）；
5. GitHub Release（附 tbx）；Zenodo 自动归档（若已开启集成）；
6. HF 镜像重跑 `push_huggingface.py`（数据有变时）。
