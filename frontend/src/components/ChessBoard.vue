<template>
  <div class="chess-container">
    <!-- 左边（黑棋）AI界面 -->
    <div class="AI-chat">
      <div class="AI-config" v-if="showBlackConfig">
        <div class="config"><p>base url</p><input v-model="blackConfig.base_url"></div>
        <div class="config"><p>api key</p><input v-model="blackConfig.api_key"></div>
        <div class="config"><p>model</p><input v-model="blackConfig.model"></div>
        <div v-if="game.blackConfigBtn" class="config-btn">
          <button @click="showBlackConfig = false">取消</button>
          <button @click="initBlack">确定</button>
        </div>
        <div v-else-if="!game.blackConfigBtn" style="text-align: center;font-size: 18px">
          模型加载中...（加载完自动关闭此页）
        </div>
      </div>
      <button v-if="!showBlackConfig"
              class="AI-config"
              @click="showBlackConfig = true"
              style="font-size: 20px">黑棋设置
      </button>
      <div class="message-container" ref="blackChat">
        <div v-for="(message,i) in messages_black" :key="i">
          <div v-if="message.type === 'reasoning_content'" class="ReasoningMessage">
            {{ message.content }}
          </div>
          <div v-else-if="message.type === 'content'" class="AIMessage">
            {{ message.content }}
          </div>
          <div v-else-if="message.type === 'tool_calls'" class="toolMessage">
            {{ message.content }}
          </div>
        </div>
      </div>
    </div>
    <!-- 中间棋盘 -->
    <div class="chess-body">
      <div class="top-message">
        {{ game.message }}
      </div>
      <div class="chess-board">
        <div
            v-for="(cell, k) in chess.flat(1)"
            :key="k"
            class="chess-cell"
            :class="{
              'edge-left':   k % col === 0,
              'edge-right':  k % col === col - 1,
              'edge-top':    Math.floor(k / col) === 0,
              'edge-bottom': Math.floor(k / col) === row - 1
            }"
            @click="setPiece(Math.floor(k / col), k % col)">
          <div v-if="cell === 1" class="black-piece"/>
          <div v-if="cell === 2" class="white-piece"/>
        </div>
      </div>
      <div class="game-config" v-if="!game.started && game.BlackInitialed && game.WhiteInitialed">
        <div class="mode-select">
          <p>选择模式</p>
          <select class="game-mode" v-model="game.mode">
            <option :value="0">双方都为大模型</option>
            <option :value="1">执黑棋（先手）</option>
            <option :value="2">执白棋（后手）</option>
          </select>
        </div>
        <button class="start-btn" @click="startGame">开始</button>
      </div>
      <div v-else-if="!game.started && !game.configed">
        请先配置模型
      </div>
      <div v-else-if="!game.started && game.configed && !game.BlackInitialed && !game.WhiteInitialed"
           class="game-config"
           style="font-size: 20px;font-weight: bolder">
        正在加载模型...
      </div>
      <div v-else-if="game.started" class="game-config" style="font-size: 20px;font-weight: bolder">
        当前为{{ game.side === 1 ? "黑棋回合" : "白棋回合" }}
      </div>
    </div>
    <!-- 右边（白棋）AI界面 -->
    <div class="AI-chat">
      <div class="AI-config" v-if="showWhiteConfig">
        <div class="config"><p>base url</p><input v-model="whiteConfig.base_url"></div>
        <div class="config"><p>api key</p><input v-model="whiteConfig.api_key"></div>
        <div class="config"><p>model</p><input v-model="whiteConfig.model"></div>
        <div v-if="game.whiteConfigBtn" class="config-btn">
          <button @click="showWhiteConfig = false">取消</button>
          <button @click="initWhite">确定</button>
        </div>
        <div v-else-if="!game.whiteConfigBtn" style="text-align: center;font-size: 18px">
          模型加载中...（加载完自动关闭此页）
        </div>
      </div>
      <button v-if="!showWhiteConfig"
              class="AI-config"
              @click="showWhiteConfig = true"
              style="font-size: 20px">白棋设置
      </button>
      <div class="message-container" ref="whiteChat">
        <div v-for="(message,i) in messages_white" :key="i">
          <div v-if="message.type === 'reasoning_content'" class="ReasoningMessage">
            {{ message.content }}
          </div>
          <div v-else-if="message.type === 'content'" class="AIMessage">
            {{ message.content }}
          </div>
          <div v-else-if="message.type === 'tool_calls'" class="toolMessage">
            {{ message.content }}
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import {reactive, ref, watch, nextTick, onMounted} from "vue";
import {fetchEventSource} from "@microsoft/fetch-event-source";
import axios from "axios";
// 全局游戏状态
const game = reactive({
  configed: false,
  BlackInitialed: false,
  WhiteInitialed: false,
  blackConfigBtn: true,
  whiteConfigBtn: true,
  started: false,
  chat_id: 1,
  side: 1,
  mode: 0, // 0 双方人机，1 我方黑棋，2 我方白棋
  message: ""
});
// 黑白棋设置可见
const showBlackConfig = ref(false)
const showWhiteConfig = ref(false)
// 黑白棋设置
const blackConfig = ref({})
const whiteConfig = ref({})
// 黑白棋消息
const messages_black = ref([])
const messages_white = ref([])
//黑白棋消息框
const blackChat = ref(null)
const whiteChat = ref(null)
// 棋盘
const chess = ref([]);
// 行高列宽
const row = 13;
const col = 13;
// 初始化棋盘
for (let i = 0; i < row; i++) {
  chess.value.push([]);
  for (let j = 0; j < col; j++) {
    chess.value[i].push(0);
  }
}
// 初始化设置
onMounted(async () => {
  // 本地获取保存的设置信息
  blackConfig.value = JSON.parse(localStorage.getItem("blackConfig"));
  whiteConfig.value = JSON.parse(localStorage.getItem("whiteConfig"));
  if (blackConfig.value && whiteConfig.value) {
    game.configed = true;
    game.blackConfigBtn = false
    game.whiteConfigBtn = false
  }
  if (!blackConfig.value) {
    blackConfig.value = {
      base_url: null,
      api_key: null,
      model: null
    }
    game.blackConfigBtn = true
  } else {
    await initBlack()
  }
  if (!whiteConfig.value) {
    whiteConfig.value = {
      base_url: null,
      api_key: null,
      model: null
    }
    game.whiteConfigBtn = true
  } else {
    await initWhite()
  }
})

// 发请求 创建黑棋agent
async function initBlack() {
  game.blackConfigBtn = false;
  const res = await axios.post("/api/create_black", {
    base_url: blackConfig.value.base_url,
    api_key: blackConfig.value.api_key,
    model: blackConfig.value.model
  })
  if (res.data.type === "success" && JSON.stringify(blackConfig.value).length > 2) {
    localStorage.setItem("blackConfig", JSON.stringify(blackConfig.value));
    showBlackConfig.value = false
    game.BlackInitialed = true
    game.blackConfigBtn = true;
  }
}

//  发请求 创建白棋agent
async function initWhite() {
  game.whiteConfigBtn = false;
  const res = await axios.post("/api/create_white", {
    base_url: whiteConfig.value.base_url,
    api_key: whiteConfig.value.api_key,
    model: whiteConfig.value.model
  })
  if (res.data.type === "success" && JSON.stringify(whiteConfig.value).length > 2) {
    localStorage.setItem("whiteConfig", JSON.stringify(whiteConfig.value));
    showWhiteConfig.value = false
    game.WhiteInitialed = true
    game.whiteConfigBtn = true;
  }
}

// 在黑/白棋消息中添加新消息
function addContent(messages, type, data) {
  // 更新棋盘和判断游戏是否结束
  if (type === "new_chess") {
    chess.value = JSON.parse(data)
    return
  } else if (type === "end") {
    chess.value = JSON.parse(data)
    game.started = false
    return
  }
// 添加新消息
  if (((messages.value.length === 0 || messages.value.at(-1).type !== type) && type !== "") || type === "tool_calls") {
    messages.value.push({
      type: type,
      content: ""
    })
  }
  messages.value.at(-1).content += data
}

// 游戏开始
async function startGame() {
  game.started = true
  switch (game.mode) {
    case 0:
      await nextTurn()
      break;
    case 1:
      break;
    case 2:
      await nextTurn()
      break;
  }
}

// 游戏结束
function GameOver(side) {
  game.started = false
  switch (side) {
    case 1:
      alert("黑方获胜");
      break;
    case 2:
      alert("白方获胜");
      break;
  }
}

// 人类下棋
async function setPiece(row, col) {
  if (game.side !== game.mode) {
    alert("现在不是你的回合")
    return;
  }
  if (chess.value[row][col] !== 0) {
    alert("此处已被其他棋子占用")
    return;
  }
  chess.value[row][col] = game.mode
  const res = await axios.post("/api/set_chess", {
    row: row,
    col: col,
    side: game.mode
  })
  const data = res.data
  switch (data.type) {
    case "error":
      alert(data.content)
      break;
    case "new_chess":
      game.side = 3 - game.side;
      chess.value = data.chess
      await nextTurn()
      break;
    case "end":
      chess.value = data.chess
      GameOver(game.mode)
      break;
  }
}

// 下一回合
async function nextTurn() {
  // 微软的fetch-event-source npm包，用于实现post+传参+流式输出
  await fetchEventSource("/api/chat", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          chat_id: game.chat_id,
          side: game.side
        }),
        // 会话进行中
        onmessage(event) {
          switch (game.side) {
            case 1:
              addContent(messages_black, event.event, event.data)
              break;
            case 2:
              addContent(messages_white, event.event, event.data)
              break;
          }
        },
        // 会话结束
        onclose() {
          if (game.started) {
            game.side = 3 - game.side
            switch (game.mode) {
              case 0:
                nextTurn()
                break;
              case 1:
                break;
              case 2:
                break;
            }
          } else {
            GameOver(game.side)
          }
        }
      }
  )
}

// 滚动到底部
function scrollToBottom(el) {
  if (!el) return
  el.scrollTop = el.scrollHeight
}

// 监听黑棋消息（deep 才能感知 content 的追加）
watch(messages_black, async () => {
  // DOM更新后滚动
  await nextTick()
  scrollToBottom(blackChat.value)
}, {deep: true, flush: 'post'})

watch(messages_white, async () => {
  await nextTick()
  scrollToBottom(whiteChat.value)
}, {deep: true, flush: 'post'})

</script>

<style scoped>
.chess-container {
  height: 100%;
  width: 100%;
  display: flex;
  flex-direction: row;
  gap: 2px;
}

.chess-body {
  display: flex;
  flex-direction: column;
  flex: 6;
  align-items: center;
  text-align: center;
  justify-content: center;
  gap: 10px;
  background-color: rgb(198 153 78 / 0.49);
}

.top-message {

}

.chess-board {
  display: grid;
  width: 100%;
  aspect-ratio: 1/1;
  grid-template-columns: repeat(13, 1fr);
  grid-template-rows: repeat(13, 1fr);
  background-color: rgb(198 153 78);
}

.chess-cell {
  position: relative;
  aspect-ratio: 1/1;
  display: flex;
  align-items: center;
  justify-content: center;
}

/* 横线、竖线统一用伪元素画 */
.chess-cell::before,
.chess-cell::after {
  content: '';
  position: absolute;
  background: #111111;
  pointer-events: none;
}

/* 横线：默认贯穿整格 */
.chess-cell::before {
  left: 0;
  right: 0;
  top: 50%;
  height: 1px;
  transform: translateY(-50%);
}

/* 竖线：默认贯穿整格 */
.chess-cell::after {
  top: 0;
  bottom: 0;
  left: 50%;
  width: 1px;
  transform: translateX(-50%);
}

/* —— 边缘收口：超出中线的部分不画 —— */
/* 最左列：横线只从中点向右 */
.chess-cell.edge-left::before { left: 50%; }
/* 最右列：横线只从中点向左 */
.chess-cell.edge-right::before { right: 50%; }
/* 最上行：竖线只从中点向下 */
.chess-cell.edge-top::after { top: 50%; }
/* 最下行：竖线只从中点向上 */
.chess-cell.edge-bottom::after { bottom: 50%; }

/* 棋子压在线上面 */
.black-piece,
.white-piece {
  position: relative;
  z-index: 1;
}

.black-piece {
  width: 70%;
  height: 70%;
  border-radius: 50%;
  background-color: #111111;
  box-shadow: 2px 2px 4px rgba(0, 0, 0, 0.35);
}

.white-piece {
  width: 70%;
  height: 70%;
  border-radius: 50%;
  background-color: #ffffff;
  box-shadow: 2px 2px 4px rgba(0, 0, 0, 0.25);
}

.game-config {
  display: flex;
  flex-direction: row;
  width: 100%;
  height: 5%;
  align-items: center;
  justify-content: center;
  gap: 10%;
}

.mode-select {
  display: flex;
  flex-direction: row;
  align-items: center;
  justify-content: center;
  height: 60%;
  gap: 10px;
}

.game-mode {
  width: auto;
  height: 100%;
  border-radius: 10px;
  background-color: #FAEBD7FF;
}

.start-btn {
  border: none;
  background-color: antiquewhite;
  height: 100%;
  width: 20%;
  font-size: 30px;
  font-weight: bold;
  font-family: kaiti;
  border-radius: 20px;
}

.AI-chat {
  flex: 3;
  min-width: 0;
  display: flex;
  flex-direction: column;
  background-color: rgb(198 153 78 / 0.78);
}

.AI-config {
  display: flex;
  flex-direction: column;
  background-color: rgb(198 153 78 / 0.49);
  gap: 5px;
  padding: 20px;
}

.config {
  height: 50px;
  display: flex;
  flex-direction: row;
}

.config > p {
  flex: 1;
}

.config > input {
  flex: 3;
  font-size: 20px;
}

.config-btn {
  display: flex;
  flex-direction: row;
}

.config-btn > button {
  flex: 1;
  margin: 5px;
  padding: 5px;
  font-size: 15px;
}

.message-container {
  flex: 1;
  width: 100%;
  display: flex;
  flex-direction: column;
  overflow-y: auto;
  overflow-x: hidden;
  scrollbar-width: thin;
}

.ReasoningMessage {
  align-self: flex-start;
  text-align: start;
  margin-left: 10px;
  color: white;
  border-radius: 10px;
}

.AIMessage {
  align-self: flex-start;
  text-align: start;
  margin: 10px;
  padding: 10px;
  background-color: #f1f1f1;
  border-radius: 10px;
}

.toolMessage {
  align-self: flex-start;
  text-align: start;
  margin: 10px;
  padding: 2px;
  background-color: rgb(255 255 255 / 0.4);
}
</style>
