// backend/tests/document.model.test.js

import assert from "node:assert/strict";
import test from "node:test";

import { Document } from "../src/models/Document.js";

function validData(overrides = {}) {
  return {
    documentId: "3f2b8c1e-aaaa-bbbb-cccc-123456789abc",
    originalName: "report.pdf",
    storedName: "3f2b8c1e-aaaa-bbbb-cccc-123456789abc.pdf",
    sizeBytes: 2048,
    sha256: "a".repeat(64),
    ...overrides,
  };
}

// Runs the schema checks. Returns null if the record is fine,
// or the validation error (with .errors for each bad field).
async function validationError(doc) {
  try {
    await doc.validate();
    return null;
  } catch (error) {
    return error;
  }
}

test("a complete record is valid and starts as 'processing'", async () => {
  const doc = new Document(validData());

  assert.equal(await validationError(doc), null);
  assert.equal(doc.status, "processing");
});

test("missing required fields are reported", async () => {
  const error = await validationError(new Document({}));

  for (const field of ["documentId", "originalName", "storedName", "sizeBytes", "sha256"]) {
    assert.ok(error.errors[field], `${field} should be required`);
  }
});

test("an unknown status is rejected", async () => {
  const error = await validationError(new Document(validData({ status: "banana" })));

  assert.ok(error.errors.status);
});

test("an unsafe id and a malformed fingerprint are rejected", async () => {
  const badId = await validationError(new Document(validData({ documentId: "../evil" })));
  const badHash = await validationError(new Document(validData({ sha256: "ABC123" })));

  assert.ok(badId.errors.documentId);
  assert.ok(badHash.errors.sha256);
});

test("documentId and sha256 have unique indexes", () => {
  const indexes = Document.schema.indexes();

  for (const field of ["documentId", "sha256"]) {
    const found = indexes.some(
      ([fields, options]) => fields[field] === 1 && options.unique === true
    );

    assert.ok(found, `${field} should have a unique index`);
  }
});

test("toApi hides private fields and uses snake_case", () => {
  const doc = new Document(validData());
  doc.createdAt = new Date("2026-01-01T00:00:00Z");

  const api = doc.toApi();

  assert.deepEqual(Object.keys(api).sort(), [
    "chunk_count",
    "document_id",
    "error",
    "filename",
    "page_count",
    "size_bytes",
    "status",
    "uploaded_at",
  ]);
  assert.equal(api.error, null);

  doc.status = "failed";
  doc.errorCode = "INVALID_PDF";
  doc.errorMessage = "The file is not a valid PDF.";

  assert.deepEqual(doc.toApi().error, {
    code: "INVALID_PDF",
    message: "The file is not a valid PDF.",
  });
});