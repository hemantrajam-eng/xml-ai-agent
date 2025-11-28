import streamlit as st
import xml.etree.ElementTree as ET
import os
from openai import OpenAI
from groq import Groq

st.set_page_config(page_title="XML AI Agent", page_icon="🤖")

# -------------------------
# SECRET KEYS
# -------------------------
OPENAI_KEY = st.secrets.get("OPENAI_API_KEY", "")
GROK_KEY = st.secrets.get("GROK_API_KEY", "")

# -------------------------
# Initialize Clients Only If Keys Exist
# -------------------------

openai_client = None
if OPENAI_KEY:
    openai_client = OpenAI(api_key=OPENAI_KEY)

grok_client = None
if GROK_KEY:
    grok_client = Groq(api_key=GROK_KEY)

# -------------------------
# AI CALL FUNCTIONS
# -------------------------

def ask_openai(prompt):
    try:
        response = openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}]
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"⚠ Error (OpenAI): {str(e)}"


def ask_grok(prompt):
    try:
        response = grok_client.chat.completions.create(
            model="grok-1",
            messages=[{"role": "user", "content": prompt}]
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"⚠ Error (Grok): {str(e)}"


def ask_ai(prompt, provider):
    if provider == "Grok":
        if not GROK_KEY:
            return "❌ Grok API key missing."
        reply = ask_grok(prompt)
        if "⚠ Error" in reply:  # fallback
            reply += "\n🔁 Fallback triggered → Trying OpenAI..."
            reply += "\n\n" + ask_openai(prompt)
        return reply

    elif provider == "OpenAI":
        if not OPENAI_KEY:
            return "❌ OpenAI API key missing."
        return ask_openai(prompt)


# -------------------------
# XML Processing
# -------------------------

def clean_xml(xml_string):
    try:
        tree = ET.ElementTree(ET.fromstring(xml_string))
        return ET.tostring(tree.getroot(), encoding="unicode")
    except:
        return "❌ Invalid XML format"


# -------------------------
# STREAMLIT UI
# -------------------------

st.title("🤖 XML Cleanup & Mapping AI Agent")

ai_model = st.radio("Select AI Model:", ["OpenAI", "Grok"], horizontal=True)

uploaded_file = st.file_uploader("📁 Upload XML File", type=["xml"])

xml_text = ""
if uploaded_file:
    xml_text = uploaded_file.read().decode("utf-8")
    st.text_area("📄 XML Content", xml_text, height=300, key="raw_xml")

cleaned_xml = ""

if st.button("✨ Clean XML"):
    cleaned_xml = clean_xml(xml_text)
    st.text_area("🧼 Cleaned XML Output", cleaned_xml, height=300, key="cleaned_xml")

if st.button("🤖 Suggest Mapping (AI Powered)"):
    if cleaned_xml:
        with st.spinner("Thinking... 🤔"):
            ai_response = ask_ai(f"Suggest structured mapping based on this XML:\n\n{cleaned_xml}", ai_model)
            st.text_area("💡 AI Insight & Suggestions", ai_response, height=300)
    else:
        st.warning("Upload XML and clean it first.")

# -------------------------
# DOWNLOAD BUTTON
# -------------------------

if cleaned_xml:
    st.download_button("⬇ Download Cleaned XML", cleaned_xml, file_name="cleaned_output.xml")

# Footer
st.markdown("---")
st.caption("⚡ Powered by OpenAI + Grok Fusion Agent")


