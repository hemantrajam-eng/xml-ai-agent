import os
import requests
from openai import OpenAI

class AIEngine:

    def __init__(self):
        self.openai_key = os.getenv("OPENAI_API_KEY")
        self.grok_key = os.getenv("GROK_API_KEY")

        self.active_model = None 
        
        if self.openai_key:
            self.active_model = "openai"
        elif self.grok_key:
            self.active_model = "grok"
        else:
            raise Exception("No LLM API key found. Please configure secrets.")

        if self.active_model == "openai":
            self.client = OpenAI(api_key=self.openai_key)

    def generate(self, prompt):
        if self.active_model == "openai":
            return self._use_openai(prompt)
        elif self.active_model == "grok":
            return self._use_grok(prompt)

    def _use_openai(self, prompt):
        response = self.client.chat.completions.create(
            model="gpt-4.1-mini",
            messages=[{"role": "user", "content": prompt}]
        )
        return response.choices[0].message.content.strip()

    def _use_grok(self, prompt):
        response = requests.post(
            "https://api.x.ai/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {self.grok_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": "grok-beta",
                "messages": [{"role": "user", "content": prompt}]
            }
        )
        return response.json()['choices'][0]['message']['content'].strip()
