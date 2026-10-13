// ===== 安仔 · 学说话：要加进 index.js 的三块 =====
// 把这个文件里的三块分别抄进 index.js，其它代码一个字都不用动。

const fs = require("fs");
const path = require("path");

// ---------------------------------------------------------------
// 第 1 块：收到消息时，把群聊记下来
// 加在你处理每条群消息的地方。机器人自己的话标成 SELF，
// 学习脚本靠这个标记跳过它自己的发言，不然它会越学越自恋。
// ---------------------------------------------------------------
function logMessage(senderName, text, isSelf) {
  if (!text) return;
  if (text.startsWith("/")) return; // 指令不用记
  const who = isSelf ? "SELF" : senderName;
  try {
    fs.appendFileSync(
      path.join(__dirname, "group_log.txt"),
      `${who}: ${text.replace(/\n/g, " ")}\n`
    );
  } catch (e) {
    // 记不上就算了，别影响回话
  }
}

// ---------------------------------------------------------------
// 第 2 块：回话之前读一次学习结果，拼到行为提示词后面
// 文件还没生成、或者内容是坏的，就当没有，绝不报错。
// ---------------------------------------------------------------
function styleHint() {
  try {
    const list = JSON.parse(
      fs.readFileSync(path.join(__dirname, "group-style.json"), "utf8")
    );
    if (!list.length) return "";
    return (
      "\n群里最近这么说话，你可以跟着用：\n" +
      list.map((x) => `· ${x.situation} → ${x.style}`).join("\n")
    );
  } catch (e) {
    return "";
  }
}

// ---------------------------------------------------------------
// 第 3 块：发消息给模型的地方
// 原来传 BEHAVIOR_PROMPT 的那一处，改成两个拼起来：
// ---------------------------------------------------------------
//   const behavior = BEHAVIOR_PROMPT + styleHint();
//
// 就这一处。PERSONA 和 BEHAVIOR_PROMPT 本身一个字都不用改。
// ---------------------------------------------------------------

module.exports = { logMessage, styleHint };
