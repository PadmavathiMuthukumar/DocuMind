// backend/tests/semanticService.test.js

import assert from "node:assert/strict";
import { mkdtemp, rm, writeFile } from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import test from "node:test";

import express from "express";

import { AppError } from "../src/middleware/errorHandler.js";
import { createSemanticClient } from "../src/services/semanticService.js";

// Starts a pretend Python service, runs the test, then stops it.
async function withFakePython(setup, run) {
  const app = express();
  setup(app);

  const server = app.listen(0, "127.0.0.1");
  await new Promise((resolve) => server.once("listening", resolve));

  const baseUrl = `http://127.0.0.1:${server.address().port}`;

  try {
    await run(baseUrl);
  } finally {
    server.closeAllConnections();
    await new Promise((resolve) => server.close(resolve));
  }
}

function clientFor(baseUrl, overrides = {}) {
  return createSemanticClient({
    baseUrl,
    timeoutMs: 2000,
    ingestTimeoutMs: 2000,
    ...overrides,
  });
}

// Used with assert.rejects: is this the AppError we expect?
function isAppError(statusCode, code) {
  return (error) =>
    error instanceof AppError && error.statusCode === statusCode && error.code === code;
}

test("health returns what Python says", async () => {
  await withFakePython(
    (app) => {
      app.get("/health", (req, res) =>
        res.json({ status: "ok", model: "test-model", chunk_count: 3 })
      );
    },
    async (baseUrl) => {
      const result = await clientFor(baseUrl).health();

      assert.deepEqual(result, { status: "ok", model: "test-model", chunk_count: 3 });
    }
  );
});

test("search sends snake_case JSON with the optional fields", async () => {
  await withFakePython(
    (app) => {
      app.post("/search", express.json(), (req, res) =>
        res.json({ query: req.body.query, no_match: false, message: "m", results: [], received: req.body })
      );
    },
    async (baseUrl) => {
      const result = await clientFor(baseUrl).search({
        query: "cats",
        documentId: "abc",
        topK: 3,
      });

      assert.deepEqual(result.received, { query: "cats", document_id: "abc", top_k: 3 });
    }
  );
});

test("search leaves out optional fields that are not given", async () => {
  await withFakePython(
    (app) => {
      app.post("/search", express.json(), (req, res) =>
        res.json({ query: req.body.query, no_match: false, message: "m", results: [], received: req.body })
      );
    },
    async (baseUrl) => {
      const result = await clientFor(baseUrl).search({ query: "cats" });

      assert.deepEqual(result.received, { query: "cats" });
    }
  );
});

test("delete encodes the id in the URL", async () => {
  await withFakePython(
    (app) => {
      app.delete("/documents/:id", (req, res) =>
        res.json({ document_id: req.params.id, deleted_chunks: 2 })
      );
    },
    async (baseUrl) => {
      const result = await clientFor(baseUrl).deleteDocument("doc 1");

      assert.deepEqual(result, { document_id: "doc 1", deleted_chunks: 2 });
    }
  );
});

test("ingest sends the file and fields as multipart form data", async () => {
  const folder = await mkdtemp(path.join(os.tmpdir(), "documind-"));
  const filePath = path.join(folder, "sample.pdf");

  await writeFile(filePath, "%PDF-1.4 fake pdf body");

  try {
    await withFakePython(
      (app) => {
        app.post("/ingest", async (req, res) => {
          const parts = [];

          for await (const part of req) {
            parts.push(part);
          }

          const raw = Buffer.concat(parts).toString("latin1");

          res.json({
            content_type: req.headers["content-type"],
            has_file_part: raw.includes('name="file"'),
            has_document_id: raw.includes('name="document_id"') && raw.includes("doc-123"),
            has_filename: raw.includes('name="filename"') && raw.includes("my report.pdf"),
            has_pdf_bytes: raw.includes("%PDF-1.4 fake pdf body"),
          });
        });
      },
      async (baseUrl) => {
        const result = await clientFor(baseUrl).ingest({
          filePath,
          documentId: "doc-123",
          filename: "my report.pdf",
        });

        assert.ok(result.content_type.startsWith("multipart/form-data; boundary="));
        assert.equal(result.has_file_part, true);
        assert.equal(result.has_document_id, true);
        assert.equal(result.has_filename, true);
        assert.equal(result.has_pdf_bytes, true);
      }
    );
  } finally {
    await rm(folder, { recursive: true, force: true });
  }
});

test("a 4xx answer from Python keeps its status, code and message", async () => {
  await withFakePython(
    (app) => {
      app.post("/search", (req, res) =>
        res.status(422).json({
          error: { code: "INVALID_REQUEST", message: "Search query cannot be empty." },
        })
      );
    },
    async (baseUrl) => {
      await assert.rejects(
        clientFor(baseUrl).search({ query: "x" }),
        (error) =>
          isAppError(422, "INVALID_REQUEST")(error) &&
          error.message === "Search query cannot be empty."
      );
    }
  );
});

test("a crash inside Python gives a generic 502 with no details", async () => {
  await withFakePython(
    (app) => {
      app.get("/health", (req, res) =>
        res.status(500).json({ detail: "Traceback secret C:\\private\\path" })
      );
    },
    async (baseUrl) => {
      await assert.rejects(
        clientFor(baseUrl).health(),
        (error) =>
          isAppError(502, "SEMANTIC_SERVICE_ERROR")(error) &&
          !error.message.includes("secret")
      );
    }
  );
});

test("a service that is not running gives 503", async () => {
  // Find a free port, then close it, so nothing is listening there.
  const probe = express().listen(0, "127.0.0.1");
  await new Promise((resolve) => probe.once("listening", resolve));

  const { port } = probe.address();
  await new Promise((resolve) => probe.close(resolve));

  await assert.rejects(
    clientFor(`http://127.0.0.1:${port}`).health(),
    isAppError(503, "SEMANTIC_SERVICE_UNAVAILABLE")
  );
});

test("a slow service gives 504", async () => {
  await withFakePython(
    (app) => {
      app.get("/health", (req, res) => {
        const timer = setTimeout(() => res.json({ status: "ok" }), 1000);
        res.on("close", () => clearTimeout(timer));
      });
    },
    async (baseUrl) => {
      await assert.rejects(
        clientFor(baseUrl, { timeoutMs: 100 }).health(),
        isAppError(504, "SEMANTIC_SERVICE_TIMEOUT")
      );
    }
  );
});