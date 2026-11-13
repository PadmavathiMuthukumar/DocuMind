// backend/scripts/checkDatabase.js
// Run with:  npm run db:check

import { randomUUID } from "node:crypto";

import { connectDatabase, disconnectDatabase } from "../src/config/database.js";
import { Document } from "../src/models/Document.js";

// A fake fingerprint, used only by this check.
const FAKE_HASH = "0".repeat(64);

function fakeRecord() {
  return {
    documentId: randomUUID(),
    originalName: "db-check.pdf",
    storedName: `${randomUUID()}.pdf`,
    sizeBytes: 1234,
    sha256: FAKE_HASH,
  };
}

async function main() {
  await connectDatabase();
  console.log("1. Connected to MongoDB.");

  // Create the indexes (including the unique one) if they do not exist yet.
  await Document.init();
  console.log("2. Indexes are ready.");

  // Remove leftovers from an earlier check that was interrupted.
  await Document.deleteMany({ sha256: FAKE_HASH });

  const saved = await Document.create(fakeRecord());

  try {
    console.log("3. Saved a test record:");
    console.log(saved.toApi());

    try {
      await Document.create(fakeRecord()); // same fingerprint again
      console.log("4. PROBLEM: the duplicate was accepted!");
      process.exitCode = 1;
    } catch (error) {
      if (error.code === 11000) {
        console.log("4. The duplicate fingerprint was rejected (good).");
      } else {
        throw error;
      }
    }
  } finally {
    await Document.deleteOne({ _id: saved._id });
    console.log("5. Test record removed.");
  }
}

main()
  .catch((error) => {
    console.error("Database check failed:", error.message);
    process.exitCode = 1;
  })
  .finally(() => disconnectDatabase());