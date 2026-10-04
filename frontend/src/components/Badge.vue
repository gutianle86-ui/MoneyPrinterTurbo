<script setup lang="ts">
defineProps<{ tone?: string }>();
</script>
<template>
  <span class="badge" :class="tone"><slot /></span>
</template>
