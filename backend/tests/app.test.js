// backend/tests/app.test.js

import assert from "node:assert/strict";
import test from "node:test";

import express from "express";

import { createApp } from "../src/app.js";
import { AppError, errorHandler } from "../src/middleware/errorHandler.js";

// Starts an app on a free port, runs the test, then stops the app.
async function withServer(app, run) {
  const server = app.listen(0, "127.0.0.1"); // port 0 = "pick any free port"

  await new Promise((resolve) => server.once("listening", resolve));

  const { port } = server.address();

  try {
    await run(`http://127.0.0.1:${port}`);
  } finally {
    server.closeAllConnections();
    await new Promise((resolve) => server.close(resolve));
  }
}

test("health endpoint answers ok", async () => {
  await withServer(createApp(), async (baseUrl) => {
    const response = await fetch(`${baseUrl}/api/health`);
    const body = await response.json();

    assert.equal(response.status, 200);
    assert.equal(body.status, "ok");
  });
});

test("unknown route gives the standard error format", async () => {
  await withServer(createApp(), async (baseUrl) => {
    const response = await fetch(`${baseUrl}/api/nothing-here`);
    const body = await response.json();

    assert.equal(response.status, 404);
    assert.equal(body.error.code, "NOT_FOUND");
  });
});

test("broken JSON gives 400 INVALID_JSON", async () => {
  await withServer(createApp(), async (baseUrl) => {
    const response = await fetch(`${baseUrl}/api/search`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: "{bad json",
    });
    const body = await response.json();

    assert.equal(response.status, 400);
    assert.equal(body.error.code, "INVALID_JSON");
  });
});

test("AppError becomes its own status and message", async () => {
  const app = express();

  app.get("/known", () => {
    throw new AppError(422, "SOME_CODE", "Friendly message");
  });
  app.use(errorHandler);

  await withServer(app, async (baseUrl) => {
    const response = await fetch(`${baseUrl}/known`);
    const body = await response.json();

    assert.equal(response.status, 422);
    assert.equal(body.error.code, "SOME_CODE");
    assert.equal(body.error.message, "Friendly message");
  });
});

test("unexpected errors do not leak details", async () => {
  const app = express();

  app.get("/boom", () => {
    throw new Error("secret C:\\private\\path");
  });
  app.use(errorHandler);

  await withServer(app, async (baseUrl) => {
    const response = await fetch(`${baseUrl}/boom`);
    const text = await response.text();

    assert.equal(response.status, 500);
    assert.ok(text.includes("INTERNAL_ERROR"));
    assert.ok(!text.includes("secret"));
  });
});