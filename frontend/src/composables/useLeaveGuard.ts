import { onBeforeUnmount, onMounted } from 'vue';
import { onBeforeRouteLeave } from 'vue-router';

interface LeaveGuardOptions {
  // Work that must finish before leaving (e.g. an upload in flight).
  isBusy?: () => boolean;
  busyMessage?: string;
  // Unsaved input the person would lose by leaving.
  isDirty: () => boolean;
  dirtyMessage: string;
}

// ponytail: One active routed page; scope by route record if guarded nested layouts are added.
const guards = new Set<LeaveGuardOptions>();

// Shared by route navigation and organization changes, which remount the layout.
export function canLeave(): boolean {
  for (const guard of guards) {
    if (guard.isBusy?.()) {
      window.alert(guard.busyMessage ?? 'Please wait for this to finish.');
      return false;
    }
  }

  const messages = [...guards]
    .filter((guard) => guard.isDirty())
    .map((guard) => guard.dirtyMessage);
  return messages.length === 0 || window.confirm([...new Set(messages)].join('\n\n'));
}

export function useLeaveGuard(options: LeaveGuardOptions) {
  guards.add(options);
  onBeforeUnmount(() => guards.delete(options));

  onBeforeRouteLeave(() => {
    // Only one registered callback asks, even when several forms share a route.
    return guards.values().next().value === options ? canLeave() : true;
  });

  // Tab close, refresh, and typed URLs never reach the router.
  function onBeforeUnload(event: BeforeUnloadEvent) {
    if (options.isBusy?.() || options.isDirty()) {
      event.preventDefault();
    }
  }
  onMounted(() => window.addEventListener('beforeunload', onBeforeUnload));
  onBeforeUnmount(() => window.removeEventListener('beforeunload', onBeforeUnload));
}
