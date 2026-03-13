// =============================================================================
// Bezalel.AI — PM2 Ecosystem Configuration
// Manages the Next.js frontend and FastAPI backend processes.
// =============================================================================

module.exports = {
  apps: [
    // ── Next.js Frontend ───────────────────────────────────────────────────
    {
      name: "bezalel-frontend",
      script: "npm",
      args: "start",
      cwd: "/data/bezalel/frontend",
      env: {
        NODE_ENV: "production",
        PORT: 3000,
      },
      max_restarts: 10,
      restart_delay: 5000,
      autorestart: true,
      watch: false,
      log_date_format: "YYYY-MM-DD HH:mm:ss Z",
    },

    // ── FastAPI Backend ────────────────────────────────────────────────────
    {
      name: "bezalel-backend",
      script: "uvicorn",
      args: "main:app --host 127.0.0.1 --port 8000",
      cwd: "/data/bezalel/backend",
      interpreter: "/data/bezalel/backend/venv/bin/python",
      max_restarts: 10,
      restart_delay: 5000,
      autorestart: true,
      watch: false,
      log_date_format: "YYYY-MM-DD HH:mm:ss Z",
    },
  ],
};
