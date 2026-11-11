// backend/src/server.js

import { createApp } from "./app.js";
import { config } from "./config/env.js";

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