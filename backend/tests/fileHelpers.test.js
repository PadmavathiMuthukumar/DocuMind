// backend/tests/fileHelpers.test.js

import assert from "node:assert/strict";
import { mkdtemp, rm, writeFile } from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import test from "node:test";

import {
  cleanOriginalName,
  looksLikePdf,
  removeFileQuietly,
  sha256File,
} from "../src/utils/fileHelpers.js";

async function withTempFile(content, run) {
  const folder = await mkdtemp(path.join(os.tmpdir(), "documind-"));
  const filePath = path.join(folder, "file.bin");

  await writeFile(filePath, content);

  try {
    await run(filePath);
  } finally {
    await rm(folder, { recursive: true, force: true });
  }
}

test("a file starting with %PDF- is recognised as a PDF", async () => {
  await withTempFile("%PDF-1.7 rest of the file", async (filePath) => {
    assert.equal(await looksLikePdf(filePath), true);
  });
});

test("text files and empty files are not PDFs", async () => {
  await withTempFile("just some text", async (filePath) => {
    assert.equal(await looksLikePdf(filePath), false);
  });

  await withTempFile("", async (filePath) => {
    assert.equal(await looksLikePdf(filePath), false);
  });
});

test("sha256File gives the known fingerprint of 'abc'", async () => {
  await withTempFile("abc", async (filePath) => {
    assert.equal(
      await sha256File(filePath),
      "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
    );
  });
});

test("cleanOriginalName removes folders and control characters", () => {
  assert.equal(cleanOriginalName("C:\\secret\\folder\\report.pdf"), "report.pdf");
  assert.equal(cleanOriginalName("../../evil.pdf"), "evil.pdf");
  assert.equal(cleanOriginalName("bad\u0000name\n.pdf"), "badname.pdf");
});

test("cleanOriginalName repairs UTF-8 names read as latin1", () => {
  const sentByBrowser = Buffer.from("வணக்கம்.pdf", "utf8").toString("latin1");

  assert.equal(cleanOriginalName(sentByBrowser), "வணக்கம்.pdf");
});

test("cleanOriginalName handles empty and very long names", () => {
  assert.equal(cleanOriginalName(""), "document.pdf");
  assert.equal(cleanOriginalName(undefined), "document.pdf");
  assert.equal(cleanOriginalName("a".repeat(400) + ".pdf").length, 255);
});

test("removeFileQuietly does not fail for a missing file", async () => {
  await removeFileQuietly(path.join(os.tmpdir(), "documind-does-not-exist.pdf"));
});