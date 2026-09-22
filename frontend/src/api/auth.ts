import { API_URL } from './client';

interface LoginResponse {
  access_token: string;
  token_type: string;
}

export async function loginWithPassword(
  email: string,
  password: string,
): Promise<LoginResponse> {
  let response: Response;

  try {
    response = await fetch(`${API_URL}/admin/login`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        email: email.trim(),
        password,
      }),
    });
  } catch {
    throw new Error('Unable to reach the sign-in service. Please try again.');
  }

  if (response.status === 401) {
    throw new Error('Invalid email or password.');
  }

  if (!response.ok) {
    throw new Error('Sign-in is unavailable. Please try again.');
  }

  const data = await response.json().catch(() => null);

  if (
    !data ||
    typeof data.access_token !== 'string' ||
    data.access_token.trim() === '' ||
    data.token_type !== 'bearer'
  ) {
    throw new Error(
      'The sign-in service returned an unexpected response. Please try again.',
    );
  }

  return {
    access_token: data.access_token,
    token_type: data.token_type,
  };
}
