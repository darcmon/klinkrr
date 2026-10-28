import { API_URL } from '../api/client';

const MAX_SLUG_LENGTH = 100;
export const SLUG_PATTERN = /^[a-z0-9-]+$/;

/** A URL path suggestion from a display name: lowercase letters, numbers and
 * single hyphens. The user can always edit it. */
export function slugify(name: string): string {
  return name
    .normalize('NFKD')
    .replace(/[̀-ͯ]/g, '')
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
    .slice(0, MAX_SLUG_LENGTH)
    .replace(/-+$/, '');
}

export function isValidSlug(slug: string): boolean {
  return slug.length > 0 && slug.length <= MAX_SLUG_LENGTH && SLUG_PATTERN.test(slug);
}

export function publicUrl(path: string): string {
  const base = API_URL.replace(/\/$/, '');
  const normalizedPath = path.startsWith('/') ? path : `/${path}`;
  return `${base}${normalizedPath}`;
}

/** The public URL without the scheme, for display. */
export function publicUrlLabel(path: string): string {
  return publicUrl(path).replace(/^https?:\/\//, '');
}
