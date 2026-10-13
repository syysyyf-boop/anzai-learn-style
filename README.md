# 安仔 · 学说话

让安仔自己看群聊，自己总结「这群人平时怎么说话」，然后跟着用。

现在安仔的规矩（不许发 emoji、一句不超过 50 字、被吐槽就怼回去）都是你手写死的，
写完就定住了。这套东西是在旁边加一个小工：每天读一遍群聊，总结出新的说话习惯，
写进一个单独的文件，安仔回话时顺手读一下。**不用改你的 PERSONA 和 BEHAVIOR_PROMPT。**

## 三个文件

| 文件 | 作用 | 放哪 |
| --- | --- | --- |
| `style_learn.py` | 每天跑一次，读记录、问模型、写结果 | 跟 `index.js` 同目录 |
| `index_snippet.js` | 要抄进 `index.js` 的三块代码 | 参考用 |
| `group-style.json` | 学习结果（脚本自动生成） | 跟 `index.js` 同目录 |
| `group_log.txt` | 群聊记录（机器人自己写） | 跟 `index.js` 同目录 |

## 怎么用

### 1. 先让安仔把群聊记下来

打开 `index_snippet.js`，把**第 1 块**抄进 `index.js`，在你处理群消息的地方调一次：

```js
logMessage(senderName, text, isSelf);   // isSelf 是「这句是不是安仔自己说的」
```

没有这一步，学习脚本就没有东西可读。（也可以先把历史聊天记录导出成 `group_log.txt` 先学一次。）

### 2. 改 `style_learn.py` 最上面那四行

```python
LOG   = 群聊记录的路径
API   = 你的接口地址（OpenAI 兼容格式）
KEY   = 你的 key
MODEL = 你手上有哪个模型
```

### 3. 手动跑一次，先看结果

```bash
cd 你的机器人目录
python3 style_learn.py
```

跑完会打印它学到的东西，同时写出 `group-style.json`。**打开看一眼**——
像样了再往下走；要是学出来全是废话，先改 `style_learn.py` 里的 PROMPT，别急着自动化。

### 4. 接进安仔

抄 `index_snippet.js` 的**第 2 块**（`styleHint` 函数），
再把**第 3 块**那行接上：原来传 `BEHAVIOR_PROMPT` 的地方，改成

```js
const behavior = BEHAVIOR_PROMPT + styleHint();
```

就这一处。重启机器人。

### 5. 挂定时任务

每天凌晨跑一次（时间自己挑）：

```bash
crontab -e
# 加一行：
10 4 * * * cd /你的机器人目录 && /usr/bin/python3 style_learn.py >> style_learn.log 2>&1
```

## 三个坑

1. **PROMPT 里那句「标着 SELF 的不要总结」别删。** 删了它就把自己以前说的话当成群的风格，越学越只会复读自己。
2. **上限 20 条别放大。** 规矩一多就互相打架，安仔会变得四不像。
3. **记录文件会长大。** 脚本学完会自动把它裁到最后 2 万字，不用管。

## 出问题了怎么办

- 提示找不到记录文件 → 第 1 步没做，或者路径写错了。
- 提示模型没返回 JSON → 换个模型试，或者把 PROMPT 最后的格式要求再写死一点。
- 学出来的东西很水 → 记录太短或太杂。至少攒一天、几百条再学。

---

PROMPT 改写自开源项目 MaiBot（GPL-3.0）。
