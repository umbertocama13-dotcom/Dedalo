/**
 * Makes the browser save a Blob as a file.
 *
 * fetch cannot start a download by itself: a temporary link pointing to an object URL
 * is clicked programmatically instead.
 *
 * @param {Blob} blob File content.
 * @param {string} filename Name proposed to the user.
 */
export function saveBlob(blob, filename) {
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  // Revoked a moment later: revoking immediately can cancel the download in some browsers,
  // never revoking keeps the file in memory until the tab is closed.
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
