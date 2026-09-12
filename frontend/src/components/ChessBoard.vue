<template>
  <div class="chess-container">
    <!-- 左边（黑棋）AI界面 -->
    <div class="AI-chat">
      <div class="AI-config" v-if="showBlackConfig">
        <div class="config"><p>base url</p><input v-model="blackConfig.base_url"></div>
        <div class="config"><p>api key</p><input v-model="blackConfig.api_key"></div>
        <div class="config"><p>model</p><input v-model="blackConfig.model"></div>
        <div class="config-btn">
          <button @click="showBlackConfig = false">取消</button>
          <button @click="initBlack">确定</button>
        </div>
      </div>
      <button v-if="!showBlackConfig"
              class="AI-config"
              @click="showBlackConfig = true"
              style="font-size: 20px">黑棋设置</button>
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
      <div class="chess-board">
        <div
            v-for="(cell, k) in chess.flat(1)"
            :key="k"
            class="chess-cell">
          <div v-if="cell === 1" class="black-piece"/>
          <div v-if="cell === 2" class="white-piece"/>
        </div>
      </div>
      <button class="start-btn" v-if="!game.started" @click="startGame">开始</button>
    </div>
    <!-- 右边（白棋）AI界面 -->
    <div class="AI-chat">
      <div class="AI-config" v-if="showWhiteConfig">
        <div class="config"><p>base url</p><input v-model="whiteConfig.base_url"></div>
        <div class="config"><p>api key</p><input v-model="whiteConfig.api_key"></div>
        <div class="config"><p>model</p><input v-model="whiteConfig.model"></div>
        <div class="config-btn">
          <button @click="showWhiteConfig = false">取消</button>
          <button @click="initWhite">确定</button>
        </div>
      </div>
      <button v-if="!showWhiteConfig"
              class="AI-config"
              @click="showWhiteConfig = true"
              style="font-size: 20px">白棋设置</button>
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
  started: false,
  chat_id: 1,
  side: 1
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
onMounted(() => {
  // 本地获取保存的设置信息
  blackConfig.value = JSON.parse(localStorage.getItem("blackConfig"));
  whiteConfig.value = JSON.parse(localStorage.getItem("whiteConfig"));
  if (!blackConfig.value) {
    blackConfig.value = {
      base_url:null,
      api_key:null,
      model:null
    }
  }
  if (!whiteConfig.value) {
    whiteConfig.value = {
      base_url:null,
      api_key:null,
      model:null
    }
  }
})
// 发请求 创建黑棋agent
async function initBlack() {
  const res = await axios.post("/api/create_black",{
    base_url:blackConfig.value.base_url,
    api_key:blackConfig.value.api_key,
    model:blackConfig.value.model
  })
  if(res.data.type === "success") {
    localStorage.setItem("blackConfig", JSON.stringify(whiteConfig.value));
    showBlackConfig.value = false
  }
}
//  发请求 创建白棋agent
async function initWhite() {
  const res = await axios.post("/api/create_white",{
    base_url:whiteConfig.value.base_url,
    api_key:whiteConfig.value.api_key,
    model:whiteConfig.value.model
  })
  if(res.data.type === "success") {
    localStorage.setItem("whiteConfig", JSON.stringify(whiteConfig.value));
    showWhiteConfig.value = false
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
  await nextTurn()
}

// 游戏结束
function GameOver(side) {
  switch (side) {
    case 1:
      alert("黑方获胜");
      break;
    case 2:
      alert("白方获胜");
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
            nextTurn()
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

.chess-board {
  display: grid;
  width: 100%;
  aspect-ratio: 1/1;
  grid-template-columns: repeat(13, 1fr);
  grid-template-rows: repeat(13, 1fr);
  border: 1px solid black;
  background-color: rgb(198 153 78);
}

.chess-cell {
  aspect-ratio: 1/1;
  display: flex;
  align-items: center;
  justify-content: center;
  background-image: linear-gradient(to bottom, transparent calc(50% - 1px), #111111 calc(50% - 1px), #111111 calc(50% + 1px), transparent calc(50% + 1px)),
  linear-gradient(to right, transparent calc(50% - 1px), #111111 calc(50% - 1px), #111111 calc(50% + 1px), transparent calc(50% + 1px));
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

.start-btn {
  border: none;
  background-color: antiquewhite;
  height: 5%;
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
  padding:5px;
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
