// backend/src/models/Document.js

import mongoose from "mongoose";

export const DOCUMENT_STATUSES = ["processing", "indexed", "failed"];

const documentSchema = new mongoose.Schema(
  {
    // The id shared with the Python service and the API (a UUID).
    // It is separate from MongoDB's own internal _id.
    documentId: {
      type: String,
      required: true,
      unique: true,
      match: /^[A-Za-z0-9_-]{1,64}$/,
    },

    // The name the user sees (folders already removed).
    originalName: { type: String, required: true, trim: true, maxlength: 255 },

    // The random name of the file on disk. Never sent to the browser.
    storedName: { type: String, required: true },

    sizeBytes: { type: Number, required: true, min: 1 },

    // SHA-256 fingerprint of the file contents. "unique" means MongoDB itself
    // refuses a second record with the same fingerprint (duplicate PDF).
    sha256: {
      type: String,
      required: true,
      unique: true,
      match: /^[a-f0-9]{64}$/,
    },

    status: { type: String, enum: DOCUMENT_STATUSES, default: "processing" },

    pageCount: { type: Number, default: 0, min: 0 },
    chunkCount: { type: Number, default: 0, min: 0 },

    // Filled only when status is "failed".
    errorCode: { type: String, default: null },
    errorMessage: { type: String, default: null, maxlength: 500 },
  },
  { timestamps: true } // adds createdAt and updatedAt automatically
);

// Makes "newest first" lists fast.
documentSchema.index({ createdAt: -1 });

/**
 * The version of this record that is safe to send to the browser.
 * It leaves out storedName, sha256 and MongoDB's _id, and it uses
 * the same snake_case names as the Python service.
 */
documentSchema.methods.toApi = function toApi() {
  return {
    document_id: this.documentId,
    filename: this.originalName,
    size_bytes: this.sizeBytes,
    status: this.status,
    page_count: this.pageCount,
    chunk_count: this.chunkCount,
    error:
      this.status === "failed"
        ? { code: this.errorCode, message: this.errorMessage }
        : null,
    uploaded_at: this.createdAt,
  };
};

export const Document = mongoose.model("Document", documentSchema);