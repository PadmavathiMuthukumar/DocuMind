// backend/src/config/env.js

import path from "node:path";
import { fileURLToPath } from "node:url";

import dotenv from "dotenv";

// In ES modules, __dirname does not exist, so we build it ourselves.
const currentFile = fileURLToPath(import.meta.url);
const currentDirectory = path.dirname(currentFile);

// This file is backend/src/config/env.js, so two levels up is backend/.
export const BACKEND_ROOT = path.resolve(currentDirectory, "..", "..");

// Read backend/.env if it exists (if not, we use the defaults below).
dotenv.config({ path: path.join(BACKEND_ROOT, ".env") });

function readString(name, fallback) {
  const value = (process.env[name] ?? "").trim();
  return value || fallback;
}

function readPositiveInt(name, fallback) {
  const raw = (process.env[name] ?? "").trim();

  if (!raw) {
    return fallback;
  }

  const value = Number(raw);

  if (!Number.isInteger(value) || value <= 0) {
    throw new Error(`${name} must be a positive whole number, got "${raw}".`);
  }

  return value;
}

function readList(name, fallback) {
  return readString(name, fallback)
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
}

export const config = Object.freeze({
  port: readPositiveInt("PORT", 5000),
  host: readString("HOST", "127.0.0.1"),
  corsOrigins: readList(
    "CORS_ORIGINS",
    "http://localhost:5173,http://127.0.0.1:5173"
  ),

  // Used in later steps
  mongoUri: readString("MONGODB_URI", ""),
  semanticServiceUrl: readString("SEMANTIC_SERVICE_URL", "http://127.0.0.1:8000"),
  semanticTimeoutMs: readPositiveInt("SEMANTIC_TIMEOUT_MS", 30_000),
  semanticIngestTimeoutMs: readPositiveInt("SEMANTIC_INGEST_TIMEOUT_MS", 300_000),

  uploadDir: path.resolve(BACKEND_ROOT, readString("UPLOAD_DIR", "uploads")),
  maxFileSizeMb: readPositiveInt("MAX_FILE_SIZE_MB", 50),
  maxFilesPerUpload: readPositiveInt("MAX_FILES_PER_UPLOAD", 5),
});