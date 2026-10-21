#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把 open-termbank 推送到 HuggingFace Datasets 镜像。

用法：
  pip install huggingface_hub
  huggingface-cli login                      # 或设 HF_TOKEN 环境变量
  python scripts/push_huggingface.py <用户名>/open-termbank

推送内容：data/（全部 CSV + index.json + domains.json + SOURCES.md + LICENSE）、
tbx/open-termbank.tbx、hf/README.md（数据集卡，含 YAML 头）。
幂等：重复推送覆盖同名文件。依赖 huggingface_hub（仅此一处需要第三方包，
且只在维护机上运行，不进 CI 门禁）。
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def main():
    if len(sys.argv) != 2 or "/" not in sys.argv[1]:
        print("用法：python scripts/push_huggingface.py <用户名>/open-termbank")
        return 1
    repo_id = sys.argv[1]
    try:
        from huggingface_hub import HfApi
    except ImportError:
        print("缺少 huggingface_hub：pip install huggingface_hub")
        return 1

    api = HfApi()
    api.create_repo(repo_id=repo_id, repo_type="dataset", exist_ok=True)

    puts = []
    for base, prefix in (("data", "data"), ("tbx", "tbx"), ("hf", "")):
        d = os.path.join(ROOT, base)
        if not os.path.isdir(d):
            continue
        for name in sorted(os.listdir(d)):
            full = os.path.join(d, name)
            if not os.path.isfile(full):
                continue
            rel = ("%s/%s" % (prefix, name)) if prefix else name
            puts.append((full, rel))

    for full, rel in puts:
        api.upload_file(path_or_fileobj=full, path_in_repo=rel,
                        repo_id=repo_id, repo_type="dataset")
        print("  ↑ %s" % rel)
    print("完成：https://huggingface.co/datasets/%s （%d 个文件）" % (repo_id, len(puts)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
