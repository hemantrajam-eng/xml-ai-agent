import streamlit as st
from openai import OpenAI
from groq import Groq

class AIEngine:
    def __init__(self):
        self.openai_key = st.secrets.get("OPENAI_API_KEY", None)
        self.grok_key = st.secrets.get("GROK_API_KEY", None)

        self.openai_client = OpenAI(api_key=self.openai_key) if self.openai_key else None
        self.grok_client = Groq(api_key=self.grok_key) if self.grok_key else None

        self.active_model = None

    def test_connection(self):
        results = {}

        if self.openai_client:
            try:
                self.openai_client.models.list()
                results["openai"] = True
            except:
                results["openai"] = False
        else:
            results["openai"] = False

        if self.grok_client:
            try:
                self.grok_client.models.list()
                results["grok"] = True
            except:
                results["grok"] = False
        else:
            results["grok"] = False

        return results
        
        
    def generate(self, prompt: str):

        # --- Try OpenAI first ---
        if self.openai_client:
            try:
                response = self.openai_client.chat.completions.create(
                    model="gpt-4o-mini-latest",
                    messages=[{"role": "user", "content": prompt}]
                )
                self.active_model = "OpenAI GPT-4o-mini-latest"
                return response.choices[0].message.content

            except Exception as e:
                print("OpenAI error -> switching to Grok:", e)

        # --- Fallback to Grok ---
        if self.grok_client:
            try:
                response = self.grok_client.chat.completions.create(
                    model="mixtral-8x7b-32768",
                    messages=[{"role": "user", "content": prompt}]
                )
                self.active_model = "Grok Mixtral-8x7b-32768"
                return response.choices[0].message.content

            except Exception as e:
                return f"⚠️ Grok error: {e}"

        return "❌ No valid AI model available. Please configure API keys."
