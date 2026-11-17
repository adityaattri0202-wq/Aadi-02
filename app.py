import os
import streamlit as st
from pipeline import build_project

st.set_page_config(page_title="Documentary AI Studio", page_icon="🎬", layout="wide")
st.title("🎬 Documentary AI Studio")
st.caption("Phase 1: scene plan, narration, and subtitles from your script.")

uploaded = st.file_uploader("Upload English script (.txt)", type=["txt"])
pasted = st.text_area("Or paste your script here", height=240)
project = st.text_input("Project name", "my_documentary")
voice = st.selectbox("Voice", ["en-US-GuyNeural", "en-US-ChristopherNeural", "en-US-EricNeural"])

if st.button("Create project", type="primary"):
    script = uploaded.getvalue().decode("utf-8", errors="replace") if uploaded else pasted
    if not script.strip():
        st.error("Upload or paste a script first.")
    elif not os.getenv("GROQ_API_KEY"):
        st.error("GROQ_API_KEY is missing. Add it in Streamlit Secrets; never put it in GitHub.")
    else:
        with st.spinner("Generating scene plan and narration..."):
            try:
                result = build_project(script, project, voice)
                st.success("Phase 1 project created.")
                st.json(result["scenes"])
                for label, path in [("Scene plan JSON", result["json"]), ("Subtitles SRT", result["srt"]), ("Narration MP3", result["audio"])]:
                    with open(path, "rb") as f:
                        st.download_button("Download " + label, f.read(), file_name=os.path.basename(path))
                st.info("This starter does not yet render a finished 4K video.")
            except Exception as exc:
                st.error(f"Pipeline error: {exc}")
