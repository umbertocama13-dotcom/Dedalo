// Bridge to the Dedalo backend: knows endpoints, HTTP and the auth token,
// nothing about how the data is displayed.

const API_BASE_URL = import.meta.env.VITE_API_URL ?? "http://127.0.0.1:8000";

// sessionStorage instead of localStorage: on shared shop-floor terminals the token
// is discarded when the tab is closed, so the next person is not logged in as someone else.
const TOKEN_KEY = "dedalo_token";

/** Error raised for failed API calls; `status` is 0 when the server is unreachable. */
export class ApiError extends Error {
  constructor(status, message) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

export function getToken() {
  return sessionStorage.getItem(TOKEN_KEY);
}

export function logout() {
  sessionStorage.removeItem(TOKEN_KEY);
}

function extractMessage(body, status) {
  const detail = body?.detail;
  if (typeof detail === "string") {
    return detail;
  }
  // Validation errors (400) arrive as a list of { loc, msg } objects.
  if (Array.isArray(detail)) {
    return detail.map((error) => error.msg).join("; ");
  }
  return `Errore del server (HTTP ${status})`;
}

async function request(path, { method = "GET", json, form } = {}) {
  const headers = {};
  const token = getToken();
  if (token) {
    headers.Authorization = `Bearer ${token}`;
  }

  let body;
  if (form) {
    // URLSearchParams makes fetch send application/x-www-form-urlencoded, the format of the OAuth2 login.
    body = new URLSearchParams(form);
  } else if (json !== undefined) {
    headers["Content-Type"] = "application/json";
    body = JSON.stringify(json);
  }

  let response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, { method, headers, body });
  } catch {
    throw new ApiError(0, "Server non raggiungibile: verifica che il backend sia avviato.");
  }

  const data = await response.json().catch(() => null);
  if (!response.ok) {
    if (response.status === 401) {
      logout();
    }
    throw new ApiError(response.status, extractMessage(data, response.status));
  }
  return data;
}

export async function login(username, password) {
  const data = await request("/auth/login", { method: "POST", form: { username, password } });
  sessionStorage.setItem(TOKEN_KEY, data.access_token);
}

export function getCurrentUser() {
  return request("/auth/me");
}

export function getFamilies() {
  return request("/families");
}

export function getPhases(familyId) {
  return request(`/families/${familyId}/phases`);
}

export function diagnose(symptom, familyId, cyclePhaseId) {
  return request("/diagnosis", {
    method: "POST",
    json: { symptom, family_id: familyId, cycle_phase_id: cyclePhaseId },
  });
}
