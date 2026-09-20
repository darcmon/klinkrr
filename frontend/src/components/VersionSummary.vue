<script setup lang="ts">
import { formatSize } from '../utils/format';
import type { Version } from '../types/version';

defineProps<{
  version: Version;
}>();

function formatFileType(contentType: string): string {
  switch (contentType) {
    case 'application/pdf':
      return 'PDF';
    case 'image/png':
      return 'PNG';
    case 'image/jpeg':
      return 'JPEG';
    default:
      return contentType;
  }
}
</script>

<template>
  <div class="version-summary">
    <template v-if="version.kind === 'file'">
      <strong class="version-title">
        {{ version.original_filename }}
      </strong>

      <span class="version-detail">
        {{ formatFileType(version.content_type) }}
        · {{ formatSize(version.file_size_bytes) }}
      </span>
    </template>

    <template v-else>
      <strong class="version-title">
        {{ version.link_url }}
      </strong>

      <span class="version-detail">Redirect link</span>
    </template>
  </div>
</template>

<style scoped>
.version-summary {
  display: grid;
  gap: var(--space-1);
  min-width: 0;
}

.version-title,
.version-detail {
  overflow-wrap: anywhere;
}

.version-detail {
  color: var(--color-muted);
  font-size: var(--text-small);
}
</style>
