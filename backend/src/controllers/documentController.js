// backend/src/controllers/documentController.js

import { AppError } from "../middleware/errorHandler.js";
import { removeFileQuietly } from "../utils/fileHelpers.js";

export function createDocumentController({ documentService }) {
  async function upload(req, res) {
    const files = req.files ?? [];

    if (files.length === 0) {
      throw new AppError(400, "NO_FILES", 'Choose at least one PDF (form field name: "files").');
    }

    const results = [];

    try {
      for (const file of files) {
        results.push(await documentService.processUploadedFile(file));
      }
    } catch (error) {
      // Something unexpected broke. Delete the files we did not finish.
      await Promise.all(
        files.slice(results.length).map((file) => removeFileQuietly(file.path))
      );

      throw error;
    }

    const summary = { indexed: 0, failed: 0, rejected: 0, duplicate: 0 };

    for (const result of results) {
      summary[result.status] += 1;
    }

    res.status(summary.indexed > 0 ? 201 : 200).json({ results, summary });
  }

  return { upload };
}