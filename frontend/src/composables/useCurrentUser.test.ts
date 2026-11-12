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

it('clears permissions immediately and ignores an old response after A → B → A', async () => {
  const { useAuth } = await import('./useAuth');
  const { useCurrentUser } = await import('./useCurrentUser');
  const auth = useAuth();
  const profile = useCurrentUser();
  auth.setToken('test-token');
  auth.selectOrganization('org-a');
  get.mockResolvedValueOnce({ permissions: ['manage_members'] });
  await profile.load();
  expect(profile.can('manage_members')).toBe(true);

  let resolveOld!: (value: unknown) => void;
  get.mockReturnValueOnce(new Promise((resolve) => { resolveOld = resolve; }));
  const oldRequest = profile.refresh();
  auth.selectOrganization('org-b');
  expect(profile.user.value).toBeNull();
  expect(profile.can('manage_members')).toBe(false);
  auth.selectOrganization('org-a');

  const currentUser = { permissions: ['submit'] };
  get.mockResolvedValueOnce(currentUser);
  await profile.load();
  resolveOld({ permissions: ['manage_members'] });
  expect(await oldRequest).toBeNull();
  expect(profile.user.value).toEqual(currentUser);
  expect(profile.can('manage_members')).toBe(false);
});
