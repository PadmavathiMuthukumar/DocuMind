// backend/tests/uploadMiddleware.test.js

import assert from "node:assert/strict";
import { access, mkdtemp, readdir, rm } from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import test from "node:test";

import express from "express";

import { errorHandler } from "../src/middleware/errorHandler.js";
import { createUploadMiddleware } from "../src/middleware/uploadMiddleware.js";

// Starts a small app that only has the upload middleware, using a
// temporary folder, then cleans everything up.
async function withUploadServer(options, run) {
  const uploadDir = await mkdtemp(path.join(os.tmpdir(), "documind-upload-"));

  const app = express();
  const upload = createUploadMiddleware({
    uploadDir,
    maxFileSizeMb: 1,
    maxFiles: 2,
    ...options,
  });

  app.post("/upload", upload, (req, res) => {
    res.json({
      files: (req.files ?? []).map((file) => ({
        originalname: file.originalname,
        filename: file.filename,
        size: file.size,
      })),
    });
  });
  app.use(errorHandler);

  const server = app.listen(0, "127.0.0.1");
  await new Promise((resolve) => server.once("listening", resolve));

  try {
    await run(`http://127.0.0.1:${server.address().port}`, uploadDir);
  } finally {
    server.closeAllConnections();
    await new Promise((resolve) => server.close(resolve));
    await rm(uploadDir, { recursive: true, force: true });
  }
}

function formWith(fieldName, files) {
  const form = new FormData();

  for (const { name, size } of files) {
    form.append(fieldName, new Blob([Buffer.alloc(size, "a")]), name);
  }

  return form;
}

test("files are saved under random .pdf names inside the upload folder", async () => {
  await withUploadServer({}, async (baseUrl, uploadDir) => {
    const response = await fetch(`${baseUrl}/upload`, {
      method: "POST",
      body: formWith("files", [{ name: "../../evil.pdf", size: 100 }]),
    });
    const body = await response.json();

    assert.equal(response.status, 200);
    assert.equal(body.files.length, 1);
    assert.match(
      body.files[0].filename,
      /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\.pdf$/
    );
    assert.ok(!body.files[0].originalname.includes(".."));

    await access(path.join(uploadDir, body.files[0].filename));
    assert.deepEqual(await readdir(uploadDir), [body.files[0].filename]);
  });
});

test("a file over the size limit gives 413 FILE_TOO_LARGE", async () => {
  await withUploadServer({}, async (baseUrl) => {
    const response = await fetch(`${baseUrl}/upload`, {
      method: "POST",
      body: formWith("files", [{ name: "big.pdf", size: 2 * 1024 * 1024 }]),
    });
    const body = await response.json();

    assert.equal(response.status, 413);
    assert.equal(body.error.code, "FILE_TOO_LARGE");
  });
});

test("too many files gives 400 TOO_MANY_FILES and leaves nothing behind", async () => {
  await withUploadServer({}, async (baseUrl, uploadDir) => {
    const response = await fetch(`${baseUrl}/upload`, {
      method: "POST",
      body: formWith("files", [
        { name: "a.pdf", size: 10 },
        { name: "b.pdf", size: 10 },
        { name: "c.pdf", size: 10 },
      ]),
    });
    const body = await response.json();

    assert.equal(response.status, 400);
    assert.equal(body.error.code, "TOO_MANY_FILES");
    assert.deepEqual(await readdir(uploadDir), []);
  });
});

test("a wrong form field name gives 400 UNEXPECTED_FILE", async () => {
  await withUploadServer({}, async (baseUrl) => {
    const response = await fetch(`${baseUrl}/upload`, {
      method: "POST",
      body: formWith("documents", [{ name: "a.pdf", size: 10 }]),
    });
    const body = await response.json();

    assert.equal(response.status, 400);
    assert.equal(body.error.code, "UNEXPECTED_FILE");
  });
});

test("a request that is not a file upload passes through with no files", async () => {
  await withUploadServer({}, async (baseUrl) => {
    const response = await fetch(`${baseUrl}/upload`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: "{}",
    });
    const body = await response.json();

    assert.equal(response.status, 200);
    assert.deepEqual(body.files, []);
  });
});