// backend/src/utils/fileHelpers.js

import { createHash } from "node:crypto";
import { createReadStream } from "node:fs";
import { open, unlink } from "node:fs/promises";

/**
 * A real PDF contains "%PDF-" near the start (these are its "magic bytes").
 * This catches a text file that was only renamed to .pdf.
 */
export async function looksLikePdf(filePath) {
  const handle = await open(filePath, "r");

  try {
    const buffer = Buffer.alloc(1024);
    const { bytesRead } = await handle.read(buffer, 0, 1024, 0);

    return buffer.subarray(0, bytesRead).includes("%PDF-");
  } finally {
    await handle.close();
  }
}

/**
 * SHA-256 fingerprint of a file. It reads the file in small pieces
 * (a "stream"), so even a big PDF does not fill the memory.
 */
export function sha256File(filePath) {
  return new Promise((resolve, reject) => {
    const hash = createHash("sha256");
    const stream = createReadStream(filePath);

    stream.on("error", reject);
    stream.on("data", (piece) => hash.update(piece));
    stream.on("end", () => resolve(hash.digest("hex")));
  });
}

/**
 * Turns the file name sent by the browser into a safe display name:
 * no folders, no control characters, at most 255 characters.
 */
export function cleanOriginalName(rawName) {
  const raw = rawName ?? "";

  // The upload library reads names as latin1, but browsers send UTF-8.
  // Converting back repairs names like Tamil or accented letters.
  let name = Buffer.from(raw, "latin1").toString("utf8");

  if (name.includes("\uFFFD")) {
    name = raw; // the conversion did not make sense, keep the original
  }

  name = name.replace(/\\/g, "/").split("/").pop();
  name = name.replace(/[\u0000-\u001f\u007f]/g, "").trim();

  if (!name) {
    name = "document.pdf";
  }

  return name.slice(0, 255);
}

/** Deletes a file. A file that is already gone is not an error. */
export async function removeFileQuietly(filePath) {
  try {
    await unlink(filePath);
  } catch (error) {
    if (error.code !== "ENOENT") {
      console.error("Could not delete a file:", error.code);
    }
  }
}