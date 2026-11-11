// backend/src/middleware/errorHandler.js

/**
 * An error we expect and can explain to the user.
 * `code` is a short label like "FILE_TOO_LARGE" (same idea as the Python service).
 */
export class AppError extends Error {
  constructor(statusCode, code, message) {
    super(message);
    this.name = "AppError";
    this.statusCode = statusCode;
    this.code = code;
  }
}

function sendError(res, statusCode, code, message) {
  return res.status(statusCode).json({ error: { code, message } });
}

// Runs when no route matched the URL.
export function notFoundHandler(req, res) {
  return sendError(res, 404, "NOT_FOUND", "This route does not exist.");
}

// Express knows this is an error handler because it has 4 parameters.
export function errorHandler(error, req, res, next) {
  // If a reply was already started, we cannot send a new one.
  if (res.headersSent) {
    return next(error);
  }

  if (error instanceof AppError) {
    return sendError(res, error.statusCode, error.code, error.message);
  }

  // Errors created by express.json() when the body is broken or too big.
  if (error.type === "entity.parse.failed") {
    return sendError(res, 400, "INVALID_JSON", "The request body is not valid JSON.");
  }

  if (error.type === "entity.too.large") {
    return sendError(res, 413, "REQUEST_TOO_LARGE", "The request body is too large.");
  }

  // Anything else is our bug. Details go to the server console only.
  console.error("Unexpected error:", error);

  return sendError(res, 500, "INTERNAL_ERROR", "Something went wrong on the server.");
}