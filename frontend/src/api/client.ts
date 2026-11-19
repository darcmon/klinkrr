import { useAuth } from '../composables/useAuth';
import { useCurrentUser } from '../composables/useCurrentUser';

const { selectedOrganizationId, loseOrganizationAccess, logout } = useAuth();

export const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

/** The server answered with an error. `code` is set for structured errors
 * (`{ detail: { code, message, ...extra } }`) the UI can branch on. */
export class ApiError extends Error {
  readonly status: number;
  readonly code: string | null;
  readonly detail: Record<string, unknown> | null;

  constructor(
    message: string,
    status: number,
    code: string | null = null,
    detail: Record<string, unknown> | null = null,
  ) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.code = code;
    this.detail = detail;
  }
}

/** No response arrived (offline, timeout, connection dropped), so whether the
 * request took effect on the server is unknown. */
export class NetworkError extends Error {
  constructor(message = 'Network error') {
    super(message);
    this.name = 'NetworkError';
  }
}

function errorFromResponse(
  status: number,
  statusText: string,
  body: unknown,
): ApiError {
  const detail =
    typeof body === 'object' && body !== null && 'detail' in body
      ? (body as { detail: unknown }).detail
      : null;
  let message = statusText || 'Request failed';

  if (typeof detail === 'string') {
    return new ApiError(detail, status);
  }

  if (Array.isArray(detail)) {
    const messages = detail
      .map((item: unknown) =>
        typeof item === 'object' &&
        item !== null &&
        'msg' in item &&
        typeof item.msg === 'string'
          ? item.msg
          : '',
      )
      .filter((text: string) => text.length > 0);

    if (messages.length > 0) message = messages.join('; ');
    return new ApiError(message, status);
  }

  // Structured errors: { code, message, ...extra }
  if (typeof detail === 'object' && detail !== null) {
    const structured = detail as Record<string, unknown>;
    if (typeof structured.message === 'string') message = structured.message;
    const code = typeof structured.code === 'string' ? structured.code : null;
    return new ApiError(message, status, code, structured);
  }

  return new ApiError(message, status);
}

/** Builds the error, and drops a revoked organization selection. An ordinary
 * permission 403 has a different code and leaves the selection alone. */
function failure(
  status: number,
  statusText: string,
  body: unknown,
  sentOrganizationId: string | null,
): ApiError {
  const error = errorFromResponse(status, statusText, body);

  // An explicit selection was revoked. Skip stale replies: the user may have
  // switched since this request was sent.
  const selectionRevoked =
    error.code === 'organization_access_denied' &&
    sentOrganizationId !== null &&
    sentOrganizationId === selectedOrganizationId.value;

  // A sole, automatically selected membership was revoked: no header was sent,
  // but the cached user still shows an organization.
  const soleMembershipRevoked =
    error.code === 'organization_membership_required' &&
    sentOrganizationId === null &&
    selectedOrganizationId.value === null &&
    useCurrentUser().user.value?.organization != null;

  if (selectionRevoked || soleMembershipRevoked) loseOrganizationAccess();
  return error;
}

function signOut() {
  // ponytail: 401 expiry clears auth without asking; draft recovery would need persistent storage.
  logout();
  window.location.href = '/login';
}

function authHeaders(): Record<string, string> {
  const token = localStorage.getItem('token');
  if (!token) return {};

  const headers: Record<string, string> = {
    Authorization: `Bearer ${token}`,
  };

  if (selectedOrganizationId.value !== null) {
    headers['X-Organization-ID'] = selectedOrganizationId.value;
  }

  return headers;
}

async function send(path: string, init: RequestInit): Promise<Response> {
  try {
    return await fetch(`${API_URL}${path}`, init);
  } catch (e) {
    // fetch only rejects when no response arrived.
    throw new NetworkError(e instanceof Error ? e.message : undefined);
  }
}

async function request(
  path: string,
  options: RequestInit = {},
  responseType: 'json' | 'blob' = 'json',
) {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(options.headers as Record<string, string>),
    ...authHeaders(),
  };
  const sentOrganizationId = selectedOrganizationId.value;

  const response = await send(path, { ...options, headers });

  if (response.status === 401) {
    signOut();
    return;
  }

  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw failure(response.status, response.statusText, body, sentOrganizationId);
  }

  if (response.status === 204) return null;

  if (responseType === 'blob') {
    return response.blob();
  }

  return response.json();
}

/** Multipart POST with upload progress, which fetch can't report.
 * `onProgress` receives 0–1 while the request body is sent; reaching 1 means
 * the server has the bytes and is processing them. */
function uploadWithProgress(
  path: string,
  formData: FormData,
  onProgress?: (fraction: number) => void,
): Promise<any> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open('POST', `${API_URL}${path}`);
    const sentOrganizationId = selectedOrganizationId.value;
    for (const [name, value] of Object.entries(authHeaders())) {
      xhr.setRequestHeader(name, value);
    }
    // No Content-Type: the browser sets the multipart boundary itself.

    xhr.upload.onprogress = (event) => {
      if (event.lengthComputable) onProgress?.(event.loaded / event.total);
    };
    xhr.upload.onload = () => onProgress?.(1);

    xhr.onload = () => {
      if (xhr.status === 401) {
        signOut();
        resolve(undefined);
        return;
      }

      let body: unknown = null;
      try {
        body = xhr.responseText ? JSON.parse(xhr.responseText) : null;
      } catch {
        body = null;
      }

      if (xhr.status >= 200 && xhr.status < 300) {
        resolve(xhr.status === 204 ? null : body);
      } else {
        reject(failure(xhr.status, xhr.statusText, body, sentOrganizationId));
      }
    };
    xhr.onerror = () => reject(new NetworkError());
    xhr.ontimeout = () => reject(new NetworkError('The upload timed out'));
    xhr.onabort = () => reject(new NetworkError('The upload was cancelled'));

    xhr.send(formData);
  });
}

export default {
  get: (path: string) => request(path),
  download: (path: string) => request(path, {}, 'blob'),
  post: (path: string, body?: unknown) =>
    request(path, {
      method: 'POST',
      body: body ? JSON.stringify(body) : undefined,
    }),
  postForm: async (path: string, formData: FormData) => {
    // Deliberately NO Content-Type — the browser sets multipart boundary itself
    const sentOrganizationId = selectedOrganizationId.value;
    const response = await send(path, {
      method: 'POST',
      headers: authHeaders(),
      body: formData,
    });

    if (response.status === 401) {
      signOut();
      return;
    }
    if (!response.ok) {
      const body = await response.json().catch(() => null);
      throw failure(response.status, response.statusText, body, sentOrganizationId);
    }
    return response.json();
  },
  uploadWithProgress,
  patch: (path: string, body: unknown) =>
    request(path, { method: 'PATCH', body: JSON.stringify(body) }),
  del: (path: string) => request(path, { method: 'DELETE' }),
};
