#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""open-termbank → GitHub 同步（REST 通道）。

为什么不用 git push：本机 github.com git 协议被网络长期阻断（api.github.com 通畅），
PaperPilot 的 sync-github.py 即为此而生；本脚本是同一打法的 open-termbank 版：
blob 内容寻址（sha 同的文件直接复用远端）→ 组 tree → 建提交 → 更新 main。

令牌：环境变量 PP_GITHUB_TOKEN，缺省读 H:/project/_brain/keys/github-api.pat
（值不落命令行、不进输出）。仓库：环境变量 OTB_REPO，缺省 yebuqiu/open-termbank。

用法：
  python scripts/sync_remote.py            # 增量同步工作区全部文件到 main
  python scripts/sync_remote.py --dry-run  # 只看差异不上传

注意：同步的是**当前工作区内容**（不是 git 提交历史）——与 sync-github.py 同语义。
发版请先 commit（留本地历史与可回溯性），再跑本脚本。
"""
import argparse
import base64
import hashlib
import io
import json
import os
import sys
import time
import urllib.request
import urllib.error

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOKEN_FILE = "H:/project/_brain/keys/github-api.pat"
API = "https://api.github.com"
UA = "open-termbank-sync/1.0"


def token():
    v = os.environ.get("PP_GITHUB_TOKEN", "")
    if v:
        return v.strip()
    try:
        with io.open(TOKEN_FILE, encoding="utf-8") as f:
            return f.read().strip()
    except Exception:
        return ""


def api_req(tok, repo, method, path, body=None, expect=(200, 201), raw_body=None,
            content_type="application/json"):
    url = "%s/repos/%s%s" % (API, repo, path) if path.startswith("/") else path
    data = None
    headers = {
        "Authorization": "Bearer " + tok,
        "User-Agent": UA,
        "Accept": "application/vnd.github+json",
    }
    if raw_body is not None:
        data = raw_body
        headers["Content-Type"] = content_type
    elif body is not None:
        data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    for attempt in (1, 2, 3):
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                code = r.getcode()
                if code in expect:
                    payload = r.read()
                    return code, (json.loads(payload.decode("utf-8"))
                                  if payload and payload[:1] in (b"{", b"[") else payload)
                raise RuntimeError("HTTP %s" % code)
        except urllib.error.HTTPError as e:
            err = e.read().decode("utf-8", "replace")
            if e.code in expect:  # 预期内的错误码（如空仓 404/409）按正常返回处理
                try:
                    return e.code, json.loads(err)
                except Exception:
                    return e.code, err
            if e.code in (403, 429) and attempt < 3:  # 限流：退避重试
                time.sleep(8 * attempt)
                continue
            raise RuntimeError("HTTP %s: %s" % (e.code, err[:400]))
        except Exception as e:
            if attempt < 3 and "timed out" in str(e).lower():
                time.sleep(4 * attempt)
                continue
            raise
    raise RuntimeError("unreachable")


def list_files():
    out = []
    for dirpath, dirnames, filenames in os.walk(ROOT):
        dirnames[:] = [d for d in dirnames if d != ".git"]
        for name in filenames:
            full = os.path.join(dirpath, name)
            rel = os.path.relpath(full, ROOT).replace("\\", "/")
            out.append((rel, full))
    return sorted(out)


def blob_sha(data):
    h = hashlib.sha1()
    h.update(b"blob %d\0" % len(data))
    h.update(data)
    return h.hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--message", default=None)
    args = ap.parse_args()

    tok = token()
    if not tok:
        print("没有 GitHub 令牌（PP_GITHUB_TOKEN 或 %s）" % TOKEN_FILE)
        return 1
    repo = os.environ.get("OTB_REPO", "yebuqiu/open-termbank")

    # 远端 main 现状（空仓库时 GET ref 返回 409 Conflict，同「无基线」处理）
    base_commit = None
    base_tree = None
    remote_blobs = {}
    code, ref = api_req(tok, repo, "GET", "/git/ref/heads/main", expect=(200, 404, 409))
    if code == 200:
        base_commit = ref["object"]["sha"]
        _, commit = api_req(tok, repo, "GET", "/git/commits/" + base_commit)
        base_tree = commit["tree"]["sha"]
        _, tree = api_req(tok, repo, "GET", "/git/trees/" + base_tree + "?recursive=1")
        for it in tree.get("tree", []):
            if it["type"] == "blob":
                remote_blobs[it["path"]] = it["sha"]

    files = list_files()
    tree_entries = []
    uploaded = reused = 0
    for rel, full in files:
        with open(full, "rb") as f:
            data = f.read()
        sha = blob_sha(data)
        if remote_blobs.get(rel) == sha:
            reused += 1
        else:
            if args.dry_run:
                print("  变更：" + rel)
                continue
            _, b = api_req(tok, repo, "POST", "/git/blobs",
                           {"content": base64.b64encode(data).decode("ascii"),
                            "encoding": "base64"})
            sha = b["sha"]
            uploaded += 1
        tree_entries.append({"path": rel, "mode": "100644", "type": "blob", "sha": sha})

    if args.dry_run:
        print("复用 %d / 变更 %d（未上传）" % (reused, len(files) - reused))
        return 0
    if uploaded == 0 and remote_blobs:
        print("远端已一致（复用 %d，无变更）" % reused)
        return 0

    body = {"tree": tree_entries, "message": args.message or "sync: open-termbank 数据更新"}
    if base_tree:
        body["base_tree"] = base_tree
    _, t = api_req(tok, repo, "POST", "/git/trees", body)
    cbody = {"message": args.message or "sync: open-termbank 数据更新", "tree": t["sha"]}
    if base_commit:
        cbody["parents"] = [base_commit]
    _, c = api_req(tok, repo, "POST", "/git/commits", cbody)

    if base_commit:
        code, _ = api_req(tok, repo, "PATCH", "/git/refs/heads/main",
                          {"sha": c["sha"], "force": False})
    else:
        code, _ = api_req(tok, repo, "POST", "/git/refs",
                          {"ref": "refs/heads/main", "sha": c["sha"]})
    print("同步完成：复用 %d / 上传 %d / %d 文件 → main = %s"
          % (reused, uploaded, len(files), c["sha"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
