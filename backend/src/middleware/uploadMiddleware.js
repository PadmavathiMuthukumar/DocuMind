// backend/src/middleware/uploadMiddleware.js

import { randomUUID } from "node:crypto";
import { mkdirSync } from "node:fs";

import multer from "multer";

import { config } from "../config/env.js";
import { AppError } from "./errorHandler.js";

/** Turns multer's errors into our standard AppError. */
export function translateUploadError(error, { maxFileSizeMb, maxFiles }) {
  if (error instanceof AppError) {
    return error;
  }

  if (error instanceof multer.MulterError) {
    if (error.code === "LIMIT_FILE_SIZE") {
      return new AppError(413, "FILE_TOO_LARGE", `Each PDF must be at most ${maxFileSizeMb} MB.`);
    }

    // Too many files can be reported in two ways.
    if (
      error.code === "LIMIT_FILE_COUNT" ||
      (error.code === "LIMIT_UNEXPECTED_FILE" && error.field === "files")
    ) {
      return new AppError(400, "TOO_MANY_FILES", `You can upload at most ${maxFiles} PDFs at a time.`);
    }

    if (error.code === "LIMIT_UNEXPECTED_FILE") {
      return new AppError(400, "UNEXPECTED_FILE", 'Send the PDFs in a form field named "files".');
    }

    return new AppError(400, "INVALID_UPLOAD", "The upload could not be read.");
  }

  // Broken multipart data from the browser.
  if (/^(Multipart|Unexpected end of form)/.test(error.message ?? "")) {
    return new AppError(400, "INVALID_UPLOAD", "The upload could not be read.");
  }

  return error;
}

/**
 * Builds the upload middleware. Settings are passed in, so tests can use
 * a temporary folder and small limits.
 */
export function createUploadMiddleware({ uploadDir, maxFileSizeMb, maxFiles }) {
  mkdirSync(uploadDir, { recursive: true });

  const storage = multer.diskStorage({
    destination: (req, file, callback) => callback(null, uploadDir),

    // The name on disk is random. The name sent by the user is NEVER used,
    // so it cannot point to another folder or overwrite another file.
    filename: (req, file, callback) => callback(null, `${randomUUID()}.pdf`),
  });

  const upload = multer({
    storage,
    limits: {
      fileSize: maxFileSizeMb * 1024 * 1024,
      files: maxFiles,
    },
  });

  // "files" is the form field name the browser must use.
  const receiveFiles = upload.array("files", maxFiles);

  return function uploadPdfs(req, res, next) {
    receiveFiles(req, res, (error) => {
      if (!error) {
        return next();
      }

      return next(translateUploadError(error, { maxFileSizeMb, maxFiles }));
    });
  };
}

// The real middleware, built from your .env settings.
export const uploadPdfs = createUploadMiddleware({
  uploadDir: config.uploadDir,
  maxFileSizeMb: config.maxFileSizeMb,
  maxFiles: config.maxFilesPerUpload,
});