<script setup lang="ts">
import { ref } from "vue";
import { useStudio } from "../composables/useStudio";
defineProps<{
  accept: string;
  label: string;
  upload: (file: File) => Promise<unknown>;
}>();
const { locked, failure } = useStudio();
const input = ref<HTMLInputElement | null>(null);
async function changed(event: Event, upload: (file: File) => Promise<unknown>) {
  const control = event.target as HTMLInputElement,
    file = control.files?.[0];
  if (!file) return;
  try {
    await upload(file);
  } catch (error) {
    failure(error);
  } finally {
    control.value = "";
  }
}
</script>
<template>
  <button
    class="button ghost"
    :disabled="locked"
    type="button"
    @click="input?.click()"
  >
    {{ label }}</button
  ><input
    ref="input"
    class="visually-hidden"
    type="file"
    :accept="accept"
    tabindex="-1"
    aria-hidden="true"
    @change="changed($event, upload)"
  />
</template>
