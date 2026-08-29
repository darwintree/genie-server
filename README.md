## FastAPI Server

Deployment and operations: [DEPLOYMENT.md](DEPLOYMENT.md)

Copy `worker/wrangler.example.jsonc` to `worker/wrangler.jsonc` and fill in
your Cloudflare resource identifiers before deploying the Worker. The local
configuration is ignored by Git.

1. Install dependencies:

   ```bash
   uv sync --locked
   ```

2. Run the server:

   ```bash
   uv run uvicorn server:app --reload --port 12451
   ```

   The server uploads completed WAV and OGG files to Cloudflare R2. Copy
   `.env.example` to `.env` and configure the R2 credentials before starting.

3. Endpoints:
   - `POST /tasks` – create a TTS task. Body:

     ```json
     {
       "character_name": "hazuki",
       "reference_audio_id": "12345",
       "reference_audio_text": "参考文本",
       "text": "要合成的文本"
     }
     ```

   - `GET /tasks/{task_id}` – query task status.
   - `GET /health` – readiness probe.

   Task creation is limited to 6 requests per minute and 100 requests per day
   per client IP. `MAX_PENDING_TASKS` controls the pending queue size and
   defaults to `20`.

4. Configure two R2 lifecycle rules:
   - Delete objects under `wav/` after 14 days.
   - Delete objects under `ogg/` after 30 days.
