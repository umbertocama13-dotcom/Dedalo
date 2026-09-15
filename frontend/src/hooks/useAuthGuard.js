import { useCallback } from "react";

import { ApiError } from "../services/api.js";

/**
 * Returns a wrapper for API calls used by expert pages.
 *
 * An expired or revoked session (401) sends the user back to the login page; any other
 * error is rethrown, so the page can show it where it happened.
 *
 * @param {() => void} onLogout Called on a 401 answer.
 * @returns {(call: (...args: any[]) => Promise<any>) => (...args: any[]) => Promise<any>}
 */
export function useAuthGuard(onLogout) {
  return useCallback(
    (call) =>
      async (...args) => {
        try {
          return await call(...args);
        } catch (error) {
          if (error instanceof ApiError && error.status === 401) {
            onLogout();
          }
          throw error;
        }
      },
    [onLogout],
  );
}
