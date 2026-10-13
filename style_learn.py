#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
安仔 · 学说话
读群聊 -> 让模型总结这个群平时怎么说话 -> 写进 group-style.json
安仔回话时读这个文件，说话就跟着群里的调子走。

只用 Python 标准库，不需要 pip 装东西。

记录从哪来，自动挑：
  1) 同目录 .env 里有 DATABASE_URL -> 直接读数据库里的群聊表（推荐，记录最全，能跨天抽样）
  2) 没有                            -> 读同目录的 group_log.txt（一行一条，见 index_snippet.js）

用法：
  python3 style_learn.py              # 学所有活跃群
  python3 style_learn.py 391262754    # 只学指定群（需要数据库）
"""

import html
import json
import os
import pathlib
import re
import subprocess
import sys
import urllib.request

HERE = pathlib.Path(__file__).resolve().parent
ENV = HERE / '.env'
LOG_FILE = HERE / 'group_log.txt'      # 没有数据库时读这个
OUT = HERE / 'group-style.json'        # 学习结果，安仔读这个

# ============ 想调就改这几行 ============
DAYS = 3                                # 学最近几天的群聊
PER_HOUR = 10                           # 每个小时最多抽几条，防止某个时段刷屏淹没样本
CHARS = 24000                           # 每个群最多喂给模型多少字
MAX = 20                                # 每个群最多留多少条规矩，别放大
MIN_MSGS = 50                           # 少于这么多条就不学，省得乱学
MAX_GROUPS = 4                          # 一次最多学几个群
TABLE = 'qq_group_msg'                  # 群聊表名
BOT_QQ = '3809709972'                   # 安仔自己的 QQ，用来跳过它自己说过的话
MODEL = '【AWS按量】claude-sonnet-5'      # 总结用哪个模型
API = ''                                # 留空则用 .env 里的 AI_BASE_URL
KEY = ''                                # 留空则用 .env 里的 AI_KEY
TIMEOUT = 180
# ========================================

PROMPT = """{chat_str}

请从上面这段群聊中提取群友的语言风格和说话方式。

要求：
1. 只看文字，不看表情包和图片
2. 标着 SELF 的是机器人自己说过的话，不要总结，别重复学自己
3. 不要出现具体人名，也不要出现具体名词
4. 优先找这个群特有的说法：只在这一群人之间才会出现的外号、黑话、固定搭配、奇怪的比喻
5. 任何群都会有的通用语气词一律不要（比如 哈哈哈哈、笑死、确实、我不行了、好的好的），写了等于没写
6. 例子仅供参考，严格根据群聊内容总结

总结成这种规律：当 "AAAAA" 时，可以 "BBBBB"。
- AAAAA 表示某个场景，不超过 20 个字
- BBBBB 表示对应的语言风格或句式，不超过 20 个字
- 一共 5 到 8 条，不要超过 10 条

只输出 JSON 数组，不要重复，不要解释，格式如下：
[
{{"situation": "对某件事表示惊叹", "style": "用 我嘞个xxxx"}},
{{"situation": "讽刺地赞同", "style": "只回 对对对"}}
]
"""


def load_env():
    env = {}
    if ENV.exists():
        for line in ENV.read_text(encoding='utf-8').splitlines():
            line = line.strip()
            if not line or line.startswith('#') or '=' not in line:
                continue
            k, v = line.split('=', 1)
            env[k.strip()] = v.strip()
    return env


ENV_VARS = load_env()
DB_URL = os.environ.get('DATABASE_URL') or ENV_VARS.get('DATABASE_URL', '')
API = API or ENV_VARS.get('AI_BASE_URL', '')
KEY = KEY or ENV_VARS.get('AI_KEY', '')


# ------------------------------------------------------------------ 读记录

CQ = re.compile(r'\[CQ:[a-zA-Z_]+(?:[^\[\]]|\[[^\[\]]*\])*\]')
JUNK = re.compile(
    r'\b(file|url|summary|content|qq|id|type|sub_type|key|name|text|title|'
    r'duration|size|width|height|app|prompt|data|path|md5|no|count|flag|'
    r'style|color|poster|source|desc|ver|token)=[^\s\]]*'
)


def clean(text):
    """把 CQ 码、图片、@、HTML 转义清掉，只留真正说出口的字。"""
    if not text:
        return ''
    t = html.unescape(text)
    prev = None
    while prev != t:
        prev = t
        t = CQ.sub(' ', t)
    t = JUNK.sub(' ', t)
    t = re.sub(r'[\r\n\t]+', ' ', t)
    t = re.sub(r'\s+', ' ', t).strip(' ,;|[]')
    return t


def psql(sql):
    """跑一条只读 SQL，返回行列表（每行是字段列表）。"""
    r = subprocess.run(
        ['psql', DB_URL, '-At', '-F', '\t', '-v', 'ON_ERROR_STOP=1', '-c', sql],
        capture_output=True, text=True, timeout=120
    )
    if r.returncode != 0:
        sys.exit('读数据库失败：' + (r.stderr or '').strip()[:400])
    return [line.split('\t') for line in r.stdout.splitlines() if line != '']


def db_groups():
    rows = psql(
        "SELECT group_id, count(*) FROM {t} "
        "WHERE group_id > 0 AND created_at > now() - interval '{d} days' "
        "GROUP BY 1 ORDER BY 2 DESC LIMIT {n};".format(t=TABLE, d=DAYS, n=MAX_GROUPS)
    )
    return [r[0] for r in rows if int(r[1]) >= MIN_MSGS]


def db_log(group_id):
    """
    跨天抽样：按小时分桶，每桶均匀抽 PER_HOUR 条。
    只取最后若干条的话，学到的是「今天下午怎么说话」，不是「这个群平时怎么说话」。
    """
    sql = (
        "WITH src AS ("
        "  SELECT sender_name, sender_id, content, created_at, date_trunc('hour', created_at) AS h"
        "  FROM {t}"
        "  WHERE group_id = {gid} AND content IS NOT NULL"
        "    AND created_at > now() - interval '{d} days'"
        "), r AS ("
        "  SELECT *, row_number() OVER (PARTITION BY h ORDER BY created_at) AS rn,"
        "         count(*) OVER (PARTITION BY h) AS cnt"
        "  FROM src"
        ")"
        " SELECT sender_name, sender_id, content FROM r"
        " WHERE rn % GREATEST(1, (cnt / {ph})) = 0"
        " ORDER BY h, rn;"
    ).format(t=TABLE, gid=int(re.sub(r'[^0-9-]', '', str(group_id))), d=DAYS, ph=PER_HOUR)

    lines = []
    for row in psql(sql):
        if len(row) < 3:
            continue
        name, sender_id, content = row[0], row[1], row[2]
        body = clean(content)
        if len(body) < 2:
            continue
        who = 'SELF' if str(sender_id) == str(BOT_QQ) else (name or '某人')
        lines.append('%s: %s' % (who, body))
    return lines


def file_log():
    if not LOG_FILE.exists():
        sys.exit('找不到群聊记录：%s\n要么在 .env 里配 DATABASE_URL，要么让安仔先把群聊写进 group_log.txt' % LOG_FILE)
    lines = []
    for line in LOG_FILE.read_text(encoding='utf-8', errors='ignore').splitlines():
        body = clean(re.sub(r'^[^:：]{1,20}[:：]\s*', '', line))
        if len(body) < 2:
            continue
        who = 'SELF' if line.startswith('SELF') else '某人'
        lines.append('%s: %s' % (who, body))
    return lines


def thin(lines):
    """太长就隔行抽稀，保住时间上的分布，而不是把前面几天砍掉。"""
    text = '\n'.join(lines)
    while len(text) > CHARS and len(lines) > MIN_MSGS:
        lines = lines[::2]
        text = '\n'.join(lines)
    return text[-CHARS:]


# ------------------------------------------------------------------ 问模型

def call_model(prompt):
    payload = {
        'model': MODEL,
        'max_tokens': 1500,
        'messages': [{'role': 'user', 'content': prompt}],
    }
    req = urllib.request.Request(
        API,
        data=json.dumps(payload).encode('utf-8'),
        headers={'Content-Type': 'application/json', 'Authorization': 'Bearer ' + KEY},
    )
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        return json.loads(resp.read().decode('utf-8'))['choices'][0]['message']['content']


def learn_one(key, lines):
    if len(lines) < MIN_MSGS:
        print('  跳过 %s：记录太少（%d 条）' % (key, len(lines)))
        return None
    text = call_model(PROMPT.replace('{chat_str}', thin(lines)))
    m = re.search(r'\[.*\]', text, re.S)
    if not m:
        print('  跳过 %s：模型没按要求返回 JSON -> %s' % (key, text[:200]))
        return None
    try:
        items = json.loads(m.group(0))
    except Exception as e:
        print('  跳过 %s：解析失败 %s' % (key, e))
        return None
    return [x for x in items if isinstance(x, dict) and x.get('situation') and x.get('style')]


def merge(new, old):
    merged, seen = [], set()
    for item in list(new) + list(old):
        key = str(item.get('situation', '')).strip()
        if not key or key in seen:
            continue
        seen.add(key)
        merged.append({'situation': key, 'style': str(item.get('style', '')).strip()})
    return merged[:MAX]


def main():
    if not API or not KEY:
        sys.exit('缺接口地址或 key：在 .env 里配 AI_BASE_URL / AI_KEY，或改脚本最上面那两行')

    old = {}
    if OUT.exists():
        try:
            data = json.loads(OUT.read_text(encoding='utf-8'))
            if isinstance(data, list):          # 兼容最初的单文件格式
                old = {'_default': data}
            elif isinstance(data, dict):
                old = data
        except Exception:
            old = {}

    result = dict(old)

    if DB_URL:
        print('📚 记录来源：数据库（最近 %d 天，每小时最多抽 %d 条）' % (DAYS, PER_HOUR))
        groups = sys.argv[1:] or db_groups()
        if not groups:
            sys.exit('没有找到活跃的群，先攒点群聊记录再来')
        for gid in groups:
            print('📖 学群 %s ...' % gid)
            items = learn_one(gid, db_log(gid))
            if items:
                result[str(gid)] = merge(items, old.get(str(gid), []))
                print('   这次学 %d 条，库里现在 %d 条' % (len(items), len(result[str(gid)])))
                for item in result[str(gid)]:
                    print('   · %s -> %s' % (item['situation'], item['style']))
    else:
        print('📚 记录来源：group_log.txt')
        items = learn_one('_default', file_log())
        if items:
            result['_default'] = merge(items, old.get('_default', []))
            print('   这次学 %d 条，库里现在 %d 条' % (len(items), len(result['_default'])))
            for item in result['_default']:
                print('   · %s -> %s' % (item['situation'], item['style']))

    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding='utf-8')
    print('✅ 已写入 %s' % OUT)


if __name__ == '__main__':
    main()
