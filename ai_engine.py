import streamlit as st
from openai import OpenAI
from groq import Groq

class AIEngine:
    def __init__(self):
        # fallback logic for secrets names
        self.openai_key = (
            st.secrets.get("OPENAI_API_KEY")
            or st.secrets.get("openai_api_key")
            or st.secrets.get("OPENAI")
        )

        self.grok_key = (
            st.secrets.get("GROK_API_KEY")
            or st.secrets.get("groq_api_key")
        )

        self.active_model = None

        # Only create clients if keys exist
        self.openai_client = OpenAI(api_key=self.openai_key) if self.openai_key else None
        self.grok_client = Groq(api_key=self.grok_key) if self.grok_key else None

    def generate(self, prompt: str):

        # --- Try OpenAI first ---
        if self.openai_client:
            try:
                response = self.openai_client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[{"role": "user", "content": prompt}]
                )
                self.active_model = "OpenAI GPT-4o-mini"
                return response.choices[0].message.content

            except Exception as e:
                # fallback if quota exceeded or invalid model
                print("OpenAI error -> switching to Grok:", e)

        # --- Fallback to Grok ---
        if self.grok_client:
            try:
                response = self.grok_client.chat.completions.create(
                    model="grok-2",
                    messages=[{"role": "user", "content": prompt}]
                )
                self.active_model = "Grok-2"
                return response.choices[0].message.content

            except Exception as e:
                return f"⚠️ AI error: {e}"

        return "❌ No valid AI model available. Please configure API keys."
