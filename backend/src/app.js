// backend/src/app.js

import cors from "cors";
import express from "express";

import { config } from "./config/env.js";
import { errorHandler, notFoundHandler } from "./middleware/errorHandler.js";

/**
 * Builds the Express app but does NOT start listening.
 * Keeping this separate from server.js lets our tests start the app
 * on a temporary port.
 */
export function createApp() {
  const app = express();

  // Do not tell the world which framework we use.
  app.disable("x-powered-by");

  // Only the browser addresses listed in CORS_ORIGINS may call this API.
  app.use(cors({ origin: config.corsOrigins }));

  // Read JSON request bodies (search questions are small).
  app.use(express.json({ limit: "100kb" }));

  app.get("/api/health", (req, res) => {
    res.json({ status: "ok", service: "documind-backend" });
  });

  // Order matters: these two must come last.
  app.use(notFoundHandler);
  app.use(errorHandler);

  return app;
}