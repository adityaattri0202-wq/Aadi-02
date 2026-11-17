import os, json, re, asyncio, requests
from pathlib import Path
import edge_tts

def srt_time(seconds):
    ms = int(seconds * 1000)
    h, ms = divmod(ms, 3600000)
    m, ms = divmod(ms, 60000)
    s, ms = divmod(ms, 1000)
    return f"{h:02}:{m:02}:{s:02},{ms:03}"

def make_plan(script):
    key = os.getenv("GROQ_API_KEY")
    if not key:
        raise RuntimeError("GROQ_API_KEY is missing.")
    prompt = (
        'Return only JSON with key "scenes", an array of 8-20 objects. '
        'Each object must contain "title", "visual_description", and "narration". '
        'Preserve the supplied facts and meaning; do not invent details.\n\nSCRIPT:\n' + script
    )
    response = requests.post(
        "https://api.groq.com/openai/v1/chat/completions",
        headers={"Authorization": "Bearer " + key, "Content-Type": "application/json"},
        json={
            "model": "llama-3.3-70b-versatile",
            "messages": [{"role": "user", "content": prompt}],
            "response_format": {"type": "json_object"},
            "temperature": 0.3
        },
        timeout=180
    )
    response.raise_for_status()
    data = json.loads(response.json()["choices"][0]["message"]["content"])
    if not data.get("scenes"):
        raise RuntimeError("The AI returned no scenes.")
    return data["scenes"]

async def make_audio(text, voice, path):
    await edge_tts.Communicate(text, voice, rate="-2%").save(str(path))

def build_project(script, name, voice):
    safe = re.sub(r"[^A-Za-z0-9_-]+", "_", name).strip("_") or "documentary"
    folder = Path("outputs") / safe
    folder.mkdir(parents=True, exist_ok=True)
    scenes = make_plan(script)

    json_path = folder / "scene_plan.json"
    json_path.write_text(json.dumps({"scenes": scenes}, ensure_ascii=False, indent=2), encoding="utf-8")

    narration = "\n\n".join(str(scene.get("narration", "")).strip() for scene in scenes)
    audio_path = folder / "narration.mp3"
    asyncio.run(make_audio(narration, voice, audio_path))

    words = narration.split()
    chunks = [" ".join(words[i:i+12]) for i in range(0, len(words), 12)]
    subtitle_lines, current_time = [], 0.0
    for index, chunk in enumerate(chunks, 1):
        duration = max(2.0, len(chunk.split()) / 2.5)
        subtitle_lines.extend([
            str(index),
            f"{srt_time(current_time)} --> {srt_time(current_time + duration)}",
            chunk,
            ""
        ])
        current_time += duration

    srt_path = folder / "subtitles.srt"
    srt_path.write_text("\n".join(subtitle_lines), encoding="utf-8")

    summary = [
        {"title": scene.get("title", ""), "visual_description": scene.get("visual_description", "")}
        for scene in scenes
    ]
    return {"json": str(json_path), "srt": str(srt_path), "audio": str(audio_path), "scenes": summary}
