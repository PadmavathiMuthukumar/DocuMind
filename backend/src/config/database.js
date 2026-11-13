// backend/src/config/database.js

import mongoose from "mongoose";

import { config } from "./env.js";

// Mongoose gives each connection state a number. These are their names.
const STATE_NAMES = {
  0: "disconnected",
  1: "connected",
  2: "connecting",
  3: "disconnecting",
};

export async function connectDatabase() {
  if (!config.mongoUri) {
    throw new Error(
      "MONGODB_URI is empty. Set it in backend/.env (see .env.example)."
    );
  }

  // Tell us about problems that happen AFTER the first connection.
  mongoose.connection.on("error", (error) => {
    console.error("MongoDB error:", error.message);
  });
  mongoose.connection.on("disconnected", () => {
    console.warn("MongoDB disconnected.");
  });

  // Give up after 10 seconds, so a wrong address fails fast.
  // We never print the connection string, because it contains the password.
  await mongoose.connect(config.mongoUri, { serverSelectionTimeoutMS: 10_000 });
}

export async function disconnectDatabase() {
  await mongoose.disconnect();
}

export function getDatabaseState() {
  return STATE_NAMES[mongoose.connection.readyState] ?? "unknown";
}