## FastAPI Server

1. Install dependencies:

   ```bash
   uv pip install .
   ```

2. Run the server:

   ```bash
   uvicorn server:app --reload
   ```

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
