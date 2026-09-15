// Bridge to the Dedalo backend: knows endpoints, HTTP and the auth token,
// nothing about how the data is displayed.

const API_BASE_URL = import.meta.env.VITE_API_URL ?? "http://127.0.0.1:8000";

// sessionStorage instead of localStorage: on shared shop-floor terminals the token
// is discarded when the tab is closed, so the next person is not logged in as someone else.
const TOKEN_KEY = "dedalo_token";

/**
 * Error raised for failed API calls.
 * `status` is 0 when the server is unreachable; `detail` keeps structured error bodies,
 * such as the report of a CSV import rejected for errors.
 */
export class ApiError extends Error {
  constructor(status, message, detail = null) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
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
  // A CSV import with errors answers 400 with its report as detail.
  if (Array.isArray(detail?.errors)) {
    return "Il file contiene errori: nessuna riga è stata salvata.";
  }
  return `Errore del server (HTTP ${status})`;
}

function filenameFrom(contentDisposition) {
  const match = /filename="([^"]+)"/.exec(contentDisposition ?? "");
  return match ? match[1] : "dedalo.csv";
}

// Drops empty filters, so they are not sent as the strings "null" or "".
function withoutEmptyValues(params) {
  return Object.fromEntries(Object.entries(params).filter(([, value]) => value !== null && value !== undefined && value !== ""));
}

async function request(path, { method = "GET", json, form, formData, params, asBlob = false } = {}) {
  const headers = {};
  const token = getToken();
  if (token) {
    headers.Authorization = `Bearer ${token}`;
  }

  let body;
  if (form) {
    // URLSearchParams makes fetch send application/x-www-form-urlencoded, the format of the OAuth2 login.
    body = new URLSearchParams(form);
  } else if (formData) {
    // No Content-Type header: fetch sets multipart/form-data with the right boundary by itself.
    body = formData;
  } else if (json !== undefined) {
    headers["Content-Type"] = "application/json";
    body = JSON.stringify(json);
  }

  const query = params ? `?${new URLSearchParams(params)}` : "";
  let response;
  try {
    response = await fetch(`${API_BASE_URL}${path}${query}`, { method, headers, body });
  } catch {
    throw new ApiError(0, "Server non raggiungibile: verifica che il backend sia avviato.");
  }

  if (response.ok && asBlob) {
    return { blob: await response.blob(), filename: filenameFrom(response.headers.get("Content-Disposition")) };
  }

  const data = await response.json().catch(() => null);
  if (!response.ok) {
    if (response.status === 401) {
      logout();
    }
    throw new ApiError(response.status, extractMessage(data, response.status), data?.detail ?? null);
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

/**
 * One turn of the diagnosis conversation. The backend keeps no state: the whole
 * history and the hypotheses excluded by the operator are sent every time.
 */
export function diagnose({ familyId, cyclePhaseId, messages, excludedIds }) {
  return request("/diagnosis", {
    method: "POST",
    json: {
      family_id: familyId,
      cycle_phase_id: cyclePhaseId,
      messages,
      excluded_diagnostic_ids: excludedIds,
    },
  });
}

export function listDiagnostics({ familyId, cyclePhaseId, search } = {}) {
  return request("/diagnostics", {
    params: withoutEmptyValues({ family_id: familyId, cycle_phase_id: cyclePhaseId, search }),
  });
}

export function createDiagnostic(diagnostic) {
  return request("/diagnostics", { method: "POST", json: diagnostic });
}

export function updateDiagnostic(id, diagnostic) {
  return request(`/diagnostics/${id}`, { method: "PUT", json: diagnostic });
}

export function deleteDiagnostic(id) {
  return request(`/diagnostics/${id}`, { method: "DELETE" });
}

/** Resolves to { blob, filename }. */
export function exportDiagnosticsCsv() {
  return request("/diagnostics/export", { asBlob: true });
}

/** Resolves to { blob, filename }. */
export function downloadImportTemplate() {
  return request("/diagnostics/import-template", { asBlob: true });
}

/** With dryRun true nothing is written: the report shows what would change. */
export function importDiagnosticsCsv(file, { dryRun }) {
  const formData = new FormData();
  formData.append("file", file);
  return request("/diagnostics/import", { method: "POST", formData, params: { dry_run: String(dryRun) } });
}
