// backend/src/server.js

import { createApp } from "./app.js";
import { config } from "./config/env.js";
import { connectDatabase, disconnectDatabase } from "./config/database.js";
import { recoverStaleDocuments } from "./services/documentService.js";

async function start() {
  // 1. Connect to MongoDB first. If it fails, there is no point starting.
  try {
    await connectDatabase();
    console.log("MongoDB connected.");

    // Uploads cut off by an earlier crash are marked as failed.
    const recovered = await recoverStaleDocuments();

    if (recovered > 0) {
      console.log(`Marked ${recovered} unfinished document(s) as failed.`);
    }
  } catch (error) {
    console.error("Could not connect to MongoDB:", error.message);
    process.exit(1);
  }

  // 2. Start the web server.
  const app = createApp();
  const server = app.listen(config.port, config.host);

  server.on("listening", () => {
    console.log(`DocuMind backend running at http://${config.host}:${config.port}`);
  });

  server.on("error", (error) => {
    if (error.code === "EADDRINUSE") {
      console.error(
        `Port ${config.port} is already in use. Close the other server or change PORT in .env.`
      );
    } else {
      console.error("Server error:", error);
    }

    process.exit(1);
  });

  // 3. Shut down politely on Ctrl+C: stop the server, then close MongoDB.
  async function shutdown(signal) {
    console.log(`${signal} received. Shutting down...`);

    // If something hangs, force-exit after 10 seconds.
    setTimeout(() => process.exit(1), 10_000).unref();

    server.close(async () => {
      await disconnectDatabase();
      process.exit(0);
    });

    server.closeIdleConnections();
  }

  process.on("SIGINT", () => shutdown("SIGINT"));
  process.on("SIGTERM", () => shutdown("SIGTERM"));
}

start();