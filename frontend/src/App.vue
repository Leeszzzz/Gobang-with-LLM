<template>
  <div class="app-container">
    <div class="ai">
      <AIBoard/>
    </div>
    <div class="board">
      <ChessBoard/>
    </div>
    <div class="ai">
      <AIBoard/>
    </div>
  </div>
</template>

<script setup>
import ChessBoard from "./components/ChessBoard.vue";
import AIBoard from "./components/AIBoard.vue";
</script>

<style scoped>

.app-container {
  width: 100%;
  height: 100%;
  display: flex;
  flex-direction: row;
}

.ai {
  flex: 2;
  height: 100%;
}

.board {
  flex: 5;
  height: 100%;
  align-content: center;
}

</style>

