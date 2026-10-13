// ===== 安仔 · 学说话：要加进 index.js 的几块 =====
// 第 2、3 块是必须的；第 1 块只有在「没有数据库、靠 group_log.txt 喂记录」时才需要。
const fs = require("fs");
const path = require("path");

// ---------------------------------------------------------------
// 第 1 块（可选）：收到消息时，把群聊记下来
// 只有没有数据库、靠 group_log.txt 喂记录时才需要。
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
// 学习结果按群分开存的时候，用 groupId 取自己那份；
// 旧格式（一整份数组）也认。文件没生成、内容坏了，就当没有，绝不报错。
// ---------------------------------------------------------------
function styleHint(groupId) {
  try {
    const raw = fs.readFileSync(path.join(__dirname, "group-style.json"), "utf8");
    const data = JSON.parse(raw);
    let list = null;
    if (Array.isArray(data)) {
      list = data;                                  // 旧格式：一份通吃
    } else if (data && typeof data === "object") {
      list = data[String(groupId)] || data._default || null;
    }
    if (!Array.isArray(list) || !list.length) return "";
    return (
      "\n\n【群里最近这么说话，可以跟着用】\n" +
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
// const behavior = BEHAVIOR_PROMPT + styleHint(groupId);
//
// 就这一处。PERSONA 和 BEHAVIOR_PROMPT 本身一个字都不用改。
// groupId 要记得一路传进 callAI（或者你拼提示词的那个函数）里。
// ---------------------------------------------------------------
