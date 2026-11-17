// backend/src/services/documentService.js

import { randomUUID } from "node:crypto";
import path from "node:path";

import { AppError } from "../middleware/errorHandler.js";
import { Document } from "../models/Document.js";
import {
  cleanOriginalName,
  looksLikePdf,
  removeFileQuietly,
  sha256File,
} from "../utils/fileHelpers.js";

// One result object is returned for each uploaded file.

function rejectedResult(filename, code, message) {
  return { filename, status: "rejected", document: null, error: { code, message } };
}

function duplicateResult(filename, existing) {
  const message = existing
    ? `This PDF was already uploaded as "${existing.originalName}".`
    : "This PDF was already uploaded.";

  return {
    filename,
    status: "duplicate",
    document: existing ? existing.toApi() : null,
    error: { code: "DUPLICATE_DOCUMENT", message },
  };
}

export function createDocumentService({ semanticClient, uploadDir }) {
  /**
   * The whole pipeline for ONE uploaded file.
   * `file` is the object multer gives us (file.path, file.filename, file.size...).
   */
  async function processUploadedFile(file) {
    const filename = cleanOriginalName(file.originalname);

    // 1. Cheap checks first.
    if (path.extname(filename).toLowerCase() !== ".pdf") {
      await removeFileQuietly(file.path);
      return rejectedResult(filename, "INVALID_FILE_TYPE", "Only .pdf files are accepted.");
    }

    if (!(await looksLikePdf(file.path))) {
      await removeFileQuietly(file.path);
      return rejectedResult(filename, "INVALID_PDF", "The file is not a valid PDF.");
    }

    // 2. Fingerprint and duplicate check.
    const sha256 = await sha256File(file.path);
    let record = await Document.findOne({ sha256 });

    if (record && record.status !== "failed") {
      await removeFileQuietly(file.path);
      return duplicateResult(filename, record);
    }

    // 3. Create the MongoDB record (or reuse the one from a failed attempt).
    try {
      if (record) {
        await removeFileQuietly(path.join(uploadDir, record.storedName));

        record.originalName = filename;
        record.storedName = file.filename;
        record.sizeBytes = file.size;
        record.status = "processing";
        record.pageCount = 0;
        record.chunkCount = 0;
        record.errorCode = null;
        record.errorMessage = null;

        await record.save();
      } else {
        record = await Document.create({
          documentId: randomUUID(),
          originalName: filename,
          storedName: file.filename,
          sizeBytes: file.size,
          sha256,
        });
      }
    } catch (error) {
      await removeFileQuietly(file.path);

      // 11000 = the unique fingerprint was taken a moment ago by another upload.
      if (error.code === 11000) {
        const existing = await Document.findOne({ sha256 });
        return duplicateResult(filename, existing);
      }

      throw error;
    }

    // 4. Ask Python to read, chunk, embed and store the PDF.
    try {
      const result = await semanticClient.ingest({
        filePath: file.path,
        documentId: record.documentId,
        filename,
      });

      record.status = "indexed";
      record.pageCount = Number(result.page_count) || 0;
      record.chunkCount = Number(result.chunk_count) || 0;
      await record.save();

      return { filename, status: "indexed", document: record.toApi(), error: null };
    } catch (error) {
      const known = error instanceof AppError;
      const code = known ? error.code : "PROCESSING_FAILED";
      const message = known ? error.message : "The PDF could not be processed.";

      if (!known) {
        console.error("Unexpected error while processing a PDF:", error);
      }

      record.status = "failed";
      record.errorCode = code;
      record.errorMessage = message.slice(0, 500);
      await record.save();

      // The file is not needed: the user can upload it again to retry.
      await removeFileQuietly(file.path);

      return { filename, status: "failed", document: record.toApi(), error: { code, message } };
    }
  }

  return { processUploadedFile };
}

/**
 * Runs once when the server starts. A record still "processing" at that
 * moment belongs to an upload that was cut off (crash or restart), because
 * this server has not handled any request yet. We mark it as failed.
 * (This assumes only one backend is running.)
 */
export async function recoverStaleDocuments() {
  const result = await Document.updateMany(
    { status: "processing" },
    {
      $set: {
        status: "failed",
        errorCode: "INTERRUPTED",
        errorMessage: "Processing was interrupted. Please upload the file again.",
      },
    }
  );

  return result.modifiedCount;
}