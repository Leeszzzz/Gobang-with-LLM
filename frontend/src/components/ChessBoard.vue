<template>
  <div class="chess-board">
    <div
        v-for="(cell, k) in chess.flat(1)"
        :key="k"
        class="chess-cell">
      <div v-if="cell === 1" class="black-piece"></div>
      <div v-if="cell === 2" class="white-piece"></div>
    </div>
  </div>
</template>

<script setup>
import { ref } from "vue";

const chess = ref([]);
const row = 13;
const col = 13;

for (let i = 0; i < row; i++) {
  chess.value.push([]);
  for (let j = 0; j < col; j++) {
    chess.value[i].push(0);
  }
}

</script>

<style scoped>
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
  background-image:
      linear-gradient(to bottom, transparent calc(50% - 1px), #111111 calc(50% - 1px), #111111 calc(50% + 1px), transparent calc(50% + 1px)),
      linear-gradient(to right, transparent calc(50% - 1px), #111111 calc(50% - 1px), #111111 calc(50% + 1px), transparent calc(50% + 1px));
}

.black-piece {
  width: 70%;
  height: 70%;
  border-radius: 50%;
  background-color: #111111;
  box-shadow: 2px 2px 4px rgba(0,0,0,0.35);
}

.white-piece {
  width: 70%;
  height: 70%;
  border-radius: 50%;
  background-color: #ffffff;
  box-shadow: 2px 2px 4px rgba(0,0,0,0.25);
}
</style>
