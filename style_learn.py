#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
安仔 · 学说话
读群聊记录 -> 让模型总结这个群的说话方式 -> 写进 group-style.json
安仔下次回话读这个文件，说话就会跟着群里的调子走。

只用 Python 标准库，不需要 pip 装东西。
用法：python3 style_learn.py
"""

import json
import pathlib
import re
import sys
import urllib.request

HERE = pathlib.Path(__file__).resolve().parent

# ============ 改这四行 ============
LOG = HERE / "group_log.txt"                     # 群聊记录，一行一条
API = "https://你的中转站/v1/chat/completions"    # OpenAI 兼容接口
KEY = "sk-xxxx"                                  # 你的 key
MODEL = "claude-sonnet-4"                        # 按你手上有哪个填
# ==================================

OUT = HERE / "group-style.json"   # 学习结果，安仔读这个
MAX = 20                          # 最多留多少条规矩，别放大
CHARS = 8000                      # 每次最多读多少字
KEEP_LOG = 20000                  # 学完把记录裁到这么长，防止它无限长大

PROMPT = """{chat_str}
请从上面这段群聊中提取群友的语言风格和说话方式。
1. 只看文字，不看表情包和图片
2. 标着 SELF 的是机器人自己说过的话，不要总结，别重复学自己
3. 不要出现具体人名，也不要出现具体名词
4. 有特殊的梗，一并总结成语言风格
5. 例子仅供参考，严格根据群聊内容总结

总结成这种规律：当 "AAAAA" 时，可以 "BBBBB"。
- AAAAA 表示某个场景，不超过 20 个字
- BBBBB 表示对应的语言风格或句式，不超过 20 个字
- 一共 3 到 5 条，不要超过 10 条

只输出 JSON 数组，不要重复，不要解释，格式如下：
[
  {"situation": "对某件事表示惊叹", "style": "用 我嘞个xxxx"},
  {"situation": "讽刺地赞同", "style": "只回 对对对"}
]
"""


def call_model(prompt):
    payload = {
        "model": MODEL,
        "max_tokens": 1500,
        "messages": [{"role": "user", "content": prompt}],
    }
    req = urllib.request.Request(
        API,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": "Bearer " + KEY,
        },
    )
    with urllib.request.urlopen(req, timeout=180) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    return data["choices"][0]["message"]["content"]


def main():
    if not LOG.exists():
        sys.exit("找不到群聊记录文件：%s\n先让安仔把群聊记下来（见 index_snippet.js 第 1 块）" % LOG)

    log = LOG.read_text(encoding="utf-8", errors="ignore")[-CHARS:]
    if len(log.strip()) < 200:
        sys.exit("群聊记录太短，先攒一天再来")

    text = call_model(PROMPT.replace("{chat_str}", log))

    m = re.search(r"\[.*\]", text, re.S)
    if not m:
        sys.exit("模型没按要求返回 JSON，原文如下：\n" + text)
    try:
        new = json.loads(m.group(0))
    except Exception as e:
        sys.exit("解析失败：%s\n原文：\n%s" % (e, m.group(0)))

    new = [x for x in new if isinstance(x, dict) and x.get("situation") and x.get("style")]

    old = []
    if OUT.exists():
        try:
            old = json.loads(OUT.read_text(encoding="utf-8"))
        except Exception:
            old = []

    # 去重：同一个场景只留一条，新的优先
    merged, seen = [], set()
    for item in new + old:
        key = item["situation"]
        if key in seen:
            continue
        seen.add(key)
        merged.append(item)
    merged = merged[:MAX]

    OUT.write_text(json.dumps(merged, ensure_ascii=False, indent=1), encoding="utf-8")

    # 裁一下记录文件，别让它长到把磁盘吃干净
    if len(log) >= CHARS:
        full = LOG.read_text(encoding="utf-8", errors="ignore")
        if len(full) > KEEP_LOG:
            LOG.write_text(full[-KEEP_LOG:], encoding="utf-8")

    print("这次学 %d 条，库里现在 %d 条 -> %s" % (len(new), len(merged), OUT))
    for item in merged:
        print("  · %s -> %s" % (item["situation"], item["style"]))


if __name__ == "__main__":
    main()
