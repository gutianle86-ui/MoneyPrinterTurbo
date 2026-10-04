<script setup lang="ts">
import { computed, onBeforeUnmount, ref } from "vue";
import { useStudio } from "../composables/useStudio";
import { isVideo } from "../domain";
import type { Candidate } from "../types";
const props = defineProps<{ candidate: Candidate; muted?: boolean }>();
const { asset } = useStudio();
const video = ref<HTMLVideoElement | null>(null);
const source = computed(() =>
  props.candidate.file ? asset(props.candidate.file) : "",
);
onBeforeUnmount(() => video.value?.pause());
defineExpose({
  pause: () => video.value?.pause(),
  play: () => {
    if (!video.value) return Promise.resolve();
    video.value.currentTime = 0;
    return video.value.play();
  },
});
</script>
<template>
  <video
    v-if="source && isVideo(candidate)"
    ref="video"
    :src="source"
    :muted="muted"
    controls
    playsinline
    preload="metadata"
  ></video
  ><img v-else-if="source" :src="source" alt="镜头候选预览" loading="lazy" />
</template>
