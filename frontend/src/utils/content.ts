import type { ContentDraft } from '../types/submit';

export const ALLOWED_FILE_TYPES: Record<string, string> = {
  'application/pdf': 'PDF',
  'image/png': 'PNG',
  'image/jpeg': 'JPEG',
};
export const MAX_FILE_MB = 50;

/** Why a file can't be submitted, or null if it can. */
export function fileProblem(file: File): string | null {
  if (!(file.type in ALLOWED_FILE_TYPES)) {
    return 'That file type isn’t supported. Use PDF, PNG or JPEG.';
  }
  if (file.size === 0) return 'That file is empty.';
  if (file.size > MAX_FILE_MB * 1024 * 1024) {
    return `That file is larger than ${MAX_FILE_MB} MB.`;
  }
  return null;
}

/** The host of a valid HTTPS link, or null. The server runs the full checks
 * (and the safety check) on submit. */
export function linkHost(link: string): string | null {
  try {
    const url = new URL(link.trim());
    return url.protocol === 'https:' && url.hostname.includes('.')
      ? url.hostname
      : null;
  } catch {
    return null;
  }
}

/** The active tab's value, if it's ready to submit. */
export function hasContent(content: ContentDraft): boolean {
  return content.tab === 'file'
    ? content.file !== null
    : linkHost(content.link) !== null;
}
