// backend/src/services/semanticService.js

import { readFile } from "node:fs/promises";

import { config } from "../config/env.js";
import { AppError } from "../middleware/errorHandler.js";

/**
 * Builds a client for the Python semantic service.
 * Settings are passed in, so tests can use a pretend service.
 */
export function createSemanticClient({ baseUrl, timeoutMs, ingestTimeoutMs }) {
  // One function does every call, so error handling is written once.
  async function request(path, options, timeout) {
    let response;
    let text;

    try {
      response = await fetch(new URL(path, baseUrl), {
        ...options,
        // Cancel the call if Python does not answer in time.
        signal: AbortSignal.timeout(timeout),
      });

      // Read the body inside the try block, so a timeout while
      // reading is also caught.
      text = await response.text();
    } catch (error) {
      if (error.name === "TimeoutError") {
        throw new AppError(
          504,
          "SEMANTIC_SERVICE_TIMEOUT",
          "The document service took too long to answer."
        );
      }

      throw new AppError(
        503,
        "SEMANTIC_SERVICE_UNAVAILABLE",
        "The document service is not reachable. Please try again later."
      );
    }

    let body = null;

    try {
      body = JSON.parse(text);
    } catch {
      body = null;
    }

    if (response.ok) {
      if (body === null) {
        throw new AppError(
          502,
          "SEMANTIC_SERVICE_ERROR",
          "The document service sent an unreadable answer."
        );
      }

      return body;
    }

    // Python explained a problem with the request or the PDF (4xx).
    // Its messages are written to be safe for users, so we pass them on.
    const pythonError = body?.error;

    if (
      response.status >= 400 &&
      response.status < 500 &&
      pythonError?.code &&
      pythonError?.message
    ) {
      throw new AppError(response.status, pythonError.code, pythonError.message);
    }

    // Anything else is a failure inside Python. Details stay in our console.
    console.error(`Semantic service answered ${response.status} for ${path}`);

    throw new AppError(
      502,
      "SEMANTIC_SERVICE_ERROR",
      "The document service failed. Please try again later."
    );
  }

  return {
    health() {
      return request("/health", { method: "GET" }, timeoutMs);
    },

    async ingest({ filePath, documentId, filename }) {
      const buffer = await readFile(filePath);

      // FormData + Blob is how Node builds a file upload (multipart form).
      // Do NOT set the Content-Type header yourself: fetch adds it
      // together with the boundary that multipart needs.
      const form = new FormData();
      form.append("file", new Blob([buffer], { type: "application/pdf" }), filename);
      form.append("document_id", documentId);
      form.append("filename", filename);

      return request("/ingest", { method: "POST", body: form }, ingestTimeoutMs);
    },

    search({ query, documentId = null, topK = null }) {
      const payload = { query };

      if (documentId) {
        payload.document_id = documentId;
      }

      if (topK) {
        payload.top_k = topK;
      }

      return request(
        "/search",
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        },
        timeoutMs
      );
    },

    deleteDocument(documentId) {
      // encodeURIComponent makes sure the id cannot change the URL path.
      return request(
        `/documents/${encodeURIComponent(documentId)}`,
        { method: "DELETE" },
        timeoutMs
      );
    },
  };
}

// The real client, built from your .env settings.
export const semanticService = createSemanticClient({
  baseUrl: config.semanticServiceUrl,
  timeoutMs: config.semanticTimeoutMs,
  ingestTimeoutMs: config.semanticIngestTimeoutMs,
});