"""Free Urdu speech-to-text for the voice agent.

Uses OpenAI's open-source Whisper large-v3, hosted for free on Groq
(free tier, no credit card: ~2,000 requests / 8 audio-hours a day).
It is a plain HTTPS call, so it works on serverless hosts like Vercel,
where a 1.5 GB model could never be loaded.

Set in .env:
    GROQ_API_KEY=gsk_...            (free key from https://console.groq.com/keys)
    GROQ_STT_MODEL=whisper-large-v3 (optional; whisper-large-v3-turbo is faster)

If no key is set, /api/stt answers 503 and the browser falls back to its own
built-in speech recognition, so the agent keeps working either way.
"""
import os
import re

import requests

GROQ_URL = "https://api.groq.com/openai/v1/audio/transcriptions"
MAX_AUDIO_BYTES = 4 * 1024 * 1024        # Vercel caps request bodies at 4.5 MB

# A short Urdu hint keeps Whisper in Urdu script (not Hindi/English) and
# primes the words people say in this conversation.
URDU_PROMPT = (
    "یہ پاسپورٹ ٹوکن کے لیے اردو گفتگو ہے۔ جی ہاں، نہیں، میرا نام، عمر، سال، "
    "پتہ، گلی، مکان نمبر، محلہ، شہر، صوبہ، پنجاب، سندھ، لاہور، کراچی، اسلام آباد۔"
)

# Things Whisper is known to "hear" in silence or noise (subtitle credits etc.).
_HALLUCINATIONS = re.compile(
    r"(سبسکرائب|subscribe|ترجمہ|subtitles|amara|شکریہ ادا|thanks for watching)", re.I)


class SpeechUnavailable(Exception):
    """No STT key configured, or the provider is down / rate-limited."""


def is_configured():
    return bool(os.getenv("GROQ_API_KEY"))


def transcribe_urdu(audio_bytes, filename="speech.webm", mimetype="audio/webm"):
    key = os.getenv("GROQ_API_KEY")
    if not key:
        raise SpeechUnavailable("GROQ_API_KEY is not set")
    try:
        resp = requests.post(
            GROQ_URL,
            headers={"Authorization": f"Bearer {key}"},
            files={"file": (filename, audio_bytes, mimetype or "application/octet-stream")},
            data={
                "model": os.getenv("GROQ_STT_MODEL", "whisper-large-v3"),
                "language": "ur",
                "temperature": "0",
                "response_format": "json",
                "prompt": URDU_PROMPT,
            },
            timeout=20,
        )
    except requests.RequestException as exc:
        raise SpeechUnavailable(f"network error: {exc}") from exc
    if resp.status_code != 200:
        raise SpeechUnavailable(f"provider returned {resp.status_code}")

    text = (resp.json().get("text") or "").strip()
    if _HALLUCINATIONS.search(text):
        return ""
    return text
