# Try ScholarDesk on Render

This configuration uses a **free web service** and one password-protected shared workspace. It does not create separate accounts. Hosting changes are prepared locally; deploying still requires your Render account.

## 1. Push the deployment changes

```bash
git add server.py static/app.js render.yaml .env.example README.md RENDER.md tests/test_server.py
git commit -m "Prepare ScholarDesk for Render hosting"
git push origin main
```

Never add `.env` or your SQLite database to GitHub.

## 2. Create the service

Sign in at https://dashboard.render.com with GitHub. Choose **New → Blueprint**, connect `saianoop324/scholardesk`, and select the `main` branch. Render reads `render.yaml`.

Enter these secret values when prompted:

- `SEMANTIC_SCHOLAR_API_KEY`: your replacement Semantic Scholar key.
- `APP_PASSWORD`: a unique password of at least 16 characters. This is your app login password, not your GitHub password or API key.

The login username defaults to `scholar`. Confirm the plan is **Free** and deploy. Open the HTTPS URL shown by Render when deployment is live. Your browser will prompt for the app username and password. The browser remembers HTTP Basic credentials for its session; use a private window and close it when finished on a shared device.

Render supplies `PORT` and `RENDER_EXTERNAL_HOSTNAME` automatically. Do not upload `.env` or override those values. Set secrets in the Render dashboard. The server refuses to start on Render without a sufficiently long password.

### Alternative: New → Web Service

If you use a Web Service instead of a Blueprint, connect the same repository and use:

- Language: Python
- Branch: main
- Build command: `python -m compileall -q server.py`
- Start command: `python server.py`
- Instance type: Free
- Health check path: `/healthz`
- Environment variables: `SEMANTIC_SCHOLAR_API_KEY`, `APP_USERNAME=scholar`, `APP_PASSWORD`

## Free-plan limitations

Free services sleep after 15 minutes without incoming traffic; the next request may take about a minute to wake the service. Their filesystem is ephemeral: the SQLite library and saved searches can disappear on restarts, redeploys, and spin-down. This is a trial deployment, not durable storage. The hosted library starts separately from your local library. JSON exports preserve paper metadata and notes as backups, but the current import interface accepts identifiers, not JSON backup restoration.

For durable SQLite storage later, choose a paid service with a persistent disk mounted at `/var/data` and set `DATABASE_PATH=/var/data/research.sqlite3`. That is a separate paid change, not included in this free configuration.

Documentation: https://render.com/docs/free and https://render.com/docs/blueprint-spec
