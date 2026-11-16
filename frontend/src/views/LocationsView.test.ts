import { afterEach, expect, it, vi } from 'vitest';
import { shallowMount, flushPromises } from '@vue/test-utils';
import LocationsView from './LocationsView.vue';

const registerGuard = vi.hoisted(() => vi.fn());
vi.mock('../composables/useLeaveGuard', () => ({ useLeaveGuard: registerGuard }));
vi.mock('../api/client', () => ({
  API_URL: 'http://test',
  default: { get: async () => ({ locations: [] }) },
}));

afterEach(() => vi.restoreAllMocks());

it('detects hidden location drafts and ignores whitespace', async () => {
  const wrapper = shallowMount(LocationsView);
  await flushPromises();
  const guard = registerGuard.mock.lastCall![0] as Parameters<
    typeof import('../composables/useLeaveGuard').useLeaveGuard
  >[0];
  const state = wrapper.vm as unknown as {
    form: Record<'slug' | 'display_name' | 'description' | 'reminder_email', string>;
  };
  try {
    for (const field of ['slug', 'display_name', 'description', 'reminder_email'] as const) {
      state.form[field] = '   ';
      expect(guard.isDirty()).toBe(false);
      state.form[field] = 'Draft';
      expect(guard.isDirty()).toBe(true);
      state.form[field] = '';
      expect(guard.isDirty()).toBe(false);
    }
  } finally {
    wrapper.unmount();
  }
});
