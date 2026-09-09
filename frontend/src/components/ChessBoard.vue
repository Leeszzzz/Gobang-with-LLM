<template>
  <div class="chess-container">
    <div class="AI-chat">
      <div class="message-container">
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
    <div class="AI-chat">
      <div class="message-container">
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
import {reactive, ref} from "vue";
import {fetchEventSource} from "@microsoft/fetch-event-source";

const game = reactive({
  started: false,
  chat_id: 1,
  side: 1
});

const messages_black = ref([])
const messages_white = ref([])
const chess = ref([]);
const row = 13;
const col = 13;

for (let i = 0; i < row; i++) {
  chess.value.push([]);
  for (let j = 0; j < col; j++) {
    chess.value[i].push(0);
  }
}

function addContent(messages, type, data) {
  if (type === "new_chess") {
    chess.value = JSON.parse(data)
    return
  } else if (type === "end") {
    chess.value = JSON.parse(data)
    game.started = false
    return
  }

  if (((messages.value.length === 0 || messages.value.at(-1).type !== type) && type !== "") || type === "tool_calls") {
    messages.value.push({
      type: type,
      content: ""
    })
  }
  messages.value.at(-1).content += data
}

async function startGame() {
  game.started = true
  await nextSide()
}

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

async function nextSide() {
  await fetchEventSource("/api/chat", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          chat_id: game.chat_id,
          side: game.side
        }),
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
        onclose() {
          if (game.started) {
            game.side = 3 - game.side
            nextSide()
          } else {
            GameOver(game.side)
          }
        }
      }
  )
}

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
  background-color: rgb(198 153 78 / 0.78);
}

.message-container {
  flex: 1;
  width: 100%;
  display: flex;
  flex-direction: column;
  overflow-y: auto;
  overflow-x: hidden;
  scrollbar-width: none;
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
