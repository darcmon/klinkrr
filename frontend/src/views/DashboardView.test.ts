import { afterEach, expect, it, vi } from 'vitest';
import { flushPromises, shallowMount } from '@vue/test-utils';
import DashboardView from './DashboardView.vue';

const registerGuard = vi.hoisted(() => vi.fn());
vi.mock('../composables/useLeaveGuard', () => ({ useLeaveGuard: registerGuard }));
vi.mock('vue-router', () => ({
  useRoute: () => ({ query: {} }),
  useRouter: () => ({ replace: vi.fn() }),
}));
vi.mock('../api/client', () => ({ default: { get: async () => [] } }));
vi.mock('../composables/useCurrentUser', () => ({
  useCurrentUser: () => ({ load: async () => null, can: () => false }),
}));
afterEach(() => vi.restoreAllMocks());

it('detects notes only while a rejection is open', async () => {
  const wrapper = shallowMount(DashboardView);
  await flushPromises();
  const guard = registerGuard.mock.lastCall![0] as Parameters<
    typeof import('../composables/useLeaveGuard').useLeaveGuard
  >[0];
  const state = wrapper.vm as unknown as {
    rejectionTarget: { id: string } | null;
    rejectionNotes: string;
    actioningId: string | null;
  };
  try {
    state.rejectionNotes = 'Leftover notes';
    expect(guard.isDirty()).toBe(false);
    state.rejectionTarget = { id: 'version-1' };
    state.rejectionNotes = '  ';
    expect(guard.isDirty()).toBe(false);
    state.rejectionNotes = 'Needs correction';
    expect(guard.isDirty()).toBe(true);
    state.rejectionTarget = null;
    state.actioningId = 'version-1';
    expect(guard.isDirty()).toBe(false);
  } finally {
    wrapper.unmount();
  }
});
