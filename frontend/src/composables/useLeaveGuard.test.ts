import { afterEach, expect, it, vi } from 'vitest';
import { defineComponent, h } from 'vue';
import { mount } from '@vue/test-utils';
import { canLeave, useLeaveGuard } from './useLeaveGuard';

const registerGuard = vi.hoisted(() => vi.fn());
vi.mock('vue-router', () => ({ onBeforeRouteLeave: registerGuard }));
afterEach(() => vi.restoreAllMocks());

it('blocks while busy, confirms when dirty, and warns on unload', () => {
  const alert = vi.spyOn(window, 'alert').mockImplementation(() => {});
  const confirm = vi.spyOn(window, 'confirm').mockReturnValue(false);
  const state = { busy: false, dirty: false };
  const wrapper = mount(
    defineComponent({
      setup() {
        useLeaveGuard({
          isBusy: () => state.busy,
          isDirty: () => state.dirty,
          dirtyMessage: 'Discard?',
        });
        return () => h('div');
      },
    }),
  );
  const guard = registerGuard.mock.lastCall![0] as () => boolean;
  const unload = () => {
    const event = new Event('beforeunload', { cancelable: true });
    window.dispatchEvent(event);
    return event.defaultPrevented;
  };

  expect(guard()).toBe(true);
  expect(unload()).toBe(false);

  state.dirty = true;
  expect(guard()).toBe(false);
  expect(confirm).toHaveBeenCalledWith('Discard?');
  expect(unload()).toBe(true);

  state.busy = true;
  confirm.mockClear();
  expect(guard()).toBe(false);
  expect(alert).toHaveBeenCalledOnce();
  expect(confirm).not.toHaveBeenCalled();

  wrapper.unmount();
  expect(unload()).toBe(false);
});

it('combines active forms into one prompt and checks busy work first', () => {
  const alert = vi.spyOn(window, 'alert').mockImplementation(() => {});
  const confirm = vi.spyOn(window, 'confirm').mockReturnValue(true);
  const state = { busy: false };
  const first = mount(defineComponent({
    setup() {
      useLeaveGuard({ isDirty: () => true, dirtyMessage: 'Discard profile?' });
      return () => h('div');
    },
  }));
  const firstGuard = registerGuard.mock.lastCall![0] as () => boolean;
  const second = mount(defineComponent({
    setup() {
      useLeaveGuard({
        isBusy: () => state.busy,
        busyMessage: 'Saving password.',
        isDirty: () => true,
        dirtyMessage: 'Discard password?',
      });
      return () => h('div');
    },
  }));
  const secondGuard = registerGuard.mock.lastCall![0] as () => boolean;
  try {
    expect(firstGuard()).toBe(true);
    expect(secondGuard()).toBe(true);
    expect(confirm).toHaveBeenCalledExactlyOnceWith('Discard profile?\n\nDiscard password?');

    confirm.mockClear();
    confirm.mockReturnValue(false);
    expect(firstGuard()).toBe(false);
    expect(confirm).toHaveBeenCalledOnce();

    state.busy = true;
    confirm.mockClear();
    expect(firstGuard()).toBe(false);
    expect(alert).toHaveBeenCalledExactlyOnceWith('Saving password.');
    expect(confirm).not.toHaveBeenCalled();

    state.busy = false;
    first.unmount();
    confirm.mockReturnValue(true);
    expect(secondGuard()).toBe(true);
    expect(confirm).toHaveBeenCalledExactlyOnceWith('Discard password?');
  } finally {
    if (first.exists()) first.unmount();
    second.unmount();
  }
  expect(canLeave()).toBe(true);
});

it('exposes the same leave check for actions that bypass route navigation', () => {
  const confirm = vi.spyOn(window, 'confirm').mockReturnValue(false);
  const wrapper = mount(defineComponent({
    setup() {
      useLeaveGuard({ isDirty: () => true, dirtyMessage: 'Discard draft?' });
      return () => h('div');
    },
  }));
  try {
    expect(canLeave()).toBe(false);
    confirm.mockReturnValue(true);
    expect(canLeave()).toBe(true);
    expect(confirm).toHaveBeenLastCalledWith('Discard draft?');
  } finally {
    wrapper.unmount();
  }
});
