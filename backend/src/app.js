// backend/src/app.js

import cors from "cors";
import express from "express";

import { config } from "./config/env.js";
import { createDocumentController } from "./controllers/documentController.js";
import { errorHandler, notFoundHandler } from "./middleware/errorHandler.js";
import { createDocumentRoutes } from "./routes/documentRoutes.js";
import { createDocumentService } from "./services/documentService.js";
import { semanticService } from "./services/semanticService.js";

/**
 * Builds the Express app but does NOT start listening.
 * The Python client can be replaced (tests use a pretend one).
 */
export function createApp({ semanticClient = semanticService } = {}) {
  const app = express();

  app.disable("x-powered-by");

  app.use(cors({ origin: config.corsOrigins }));
  app.use(express.json({ limit: "100kb" }));

  app.get("/api/health", (req, res) => {
    res.json({ status: "ok", service: "documind-backend" });
  });

  const documentService = createDocumentService({
    semanticClient,
    uploadDir: config.uploadDir,
  });
  const documentController = createDocumentController({ documentService });

  app.use("/api/documents", createDocumentRoutes({ documentController }));

  // Order matters: these two must come last.
  app.use(notFoundHandler);
  app.use(errorHandler);

  return app;
}