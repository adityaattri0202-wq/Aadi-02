# Documentary AI Studio — Phase 1

This starter creates:
- a scene plan (`scene_plan.json`)
- English narration audio (`narration.mp3`)
- approximate subtitles (`subtitles.srt`)

**Important:** This is only Phase 1. It does not yet create cinematic AI video, add stock footage, or render a finished 4K MP4. Subtitle timing is approximate and should be reviewed.

## Deploy
1. Upload the project files to a private GitHub repository.
2. Deploy the repository using Streamlit Community Cloud.
3. In the app's Secrets settings, add:
   `GROQ_API_KEY = "your_key_here"`
4. Never upload API keys, `.env`, or secrets to GitHub.

## Local run
Python 3.10+: `pip install -r requirements.txt` then `streamlit run app.py`.

Check provider pricing, limits, and commercial-use terms before publishing. Do not assume a free voice service permits every commercial use.
