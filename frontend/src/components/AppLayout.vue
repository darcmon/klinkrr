<template>
  <div class="app-layout">
    <header class="app-header">
      <slot name="header" />
    </header>

    <main class="app-content">
      <slot />
    </main>
  </div>
</template>

<style scoped>
.app-layout {
  min-height: 100svh;
}

.app-header {
  padding: var(--space-4);
  background-color: var(--color-surface);
  border-bottom: 1px solid var(--color-border);
}

.app-content {
  width: 100%;
  max-width: 1200px;
  margin-inline: auto;
  padding: var(--space-6) var(--space-4);
}

@media (min-width: 768px) {
  .app-header {
    padding-inline: var(--space-8);
  }

  .app-content {
    padding: var(--space-8);
  }
}
@media (max-width: 767px) {
  .app-content {
    padding-bottom: calc(
      var(--mobile-nav-height) + env(safe-area-inset-bottom, 0px) +
        var(--space-6)
    );
  }
}
</style>
