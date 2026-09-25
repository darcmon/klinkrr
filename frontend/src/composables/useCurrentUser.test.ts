import { beforeEach, expect, it, vi } from 'vitest';

const get = vi.hoisted(() => vi.fn());
vi.mock('../api/client', () => ({ default: { get } }));

beforeEach(() => {
  vi.resetModules();
  get.mockReset();
  localStorage.clear();
});

it('does not request the protected profile while signed out', async () => {
  const { useCurrentUser } = await import('./useCurrentUser');
  const profile = useCurrentUser();

  expect(await profile.load()).toBeNull();
  expect(await profile.refresh()).toBeNull();
  expect(get).not.toHaveBeenCalled();
});

it('loads the profile after signing in and stops requesting it after logout', async () => {
  const { nextTick } = await import('vue');
  const { useAuth } = await import('./useAuth');
  const { useCurrentUser } = await import('./useCurrentUser');
  const auth = useAuth();
  const profile = useCurrentUser();
  const user = { id: 'user-1', avatar_url: null };
  get.mockResolvedValue(user);

  auth.setToken('test-token');
  await nextTick();
  expect(await profile.load()).toEqual(user);
  expect(get).toHaveBeenCalledWith('/admin/me');

  auth.logout();
  await nextTick();
  expect(await profile.load()).toBeNull();
  expect(get).toHaveBeenCalledTimes(1);
});
