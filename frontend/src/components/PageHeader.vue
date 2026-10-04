<script setup lang="ts">
import { useStudio } from "../composables/useStudio";
defineProps<{ title: string; subtitle: string }>();
const { state } = useStudio();
</script>
<template>
  <div class="page-title">
    <div>
      <div class="eyebrow">
        EPISODE 01 / {{ String(state.stage + 1).padStart(2, "0") }}
      </div>
      <h1>{{ title }}</h1>
      <p>{{ subtitle }}</p>
    </div>
    <slot />
  </div>
</template>
