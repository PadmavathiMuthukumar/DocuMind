// backend/src/routes/documentRoutes.js

import { Router } from "express";

import { uploadPdfs } from "../middleware/uploadMiddleware.js";

export function createDocumentRoutes({ documentController }) {
  const router = Router();

  // First uploadPdfs saves the files, then the controller handles them.
  router.post("/upload", uploadPdfs, documentController.upload);

  return router;
}