/**
 * VIDYA-X AI — Deployment Runtime Configuration (Step 16)
 * In production deployments, override API_BASE_URL to point to your deployed backend HTTPS URL.
 * Example for Render / Railway / Fly.io:
 *   API_BASE_URL: "https://vidya-x-api.onrender.com/api"
 */
window.VIDYAX_CONFIG = {
  // Set null or empty string to use automatic relative origin or localhost:8000 fallback
  API_BASE_URL: null,
  APP_ENV: "production",
  VERSION: "1.0.0",
};
