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
