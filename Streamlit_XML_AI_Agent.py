import streamlit as st
import xmltodict
from bs4 import BeautifulSoup
from collections import defaultdict
from openai import OpenAI
import json

st.set_page_config(page_title="XML Optimizer AI", layout="wide")

# ---------------------------
# CONFIG & API KEY SECTION
# ---------------------------

api_key = st.sidebar.text_input("🔑 Enter OpenAI API Key", type="password")

use_ai = st.sidebar.checkbox("🤖 Enable AI Reasoning", value=True)


# ---------------------------
# PROCESSING FUNCTION
# ---------------------------

def dedupe_xml(xml_content):
    soup = BeautifulSoup(xml_content, 'xml')
    options = soup.find_all('option')

    grouped = defaultdict(lambda: {"names": [], "values": [], "deps": set()})

    for op in options:
        names = [n.strip() for n in op["name"].split(",")]
        values = [v.strip() for v in op["value"].split(",")]
        deps = [str(dep) for dep in op.find_all("dependent")]

        for name, value in zip(names, values):
            grouped[frozenset(deps)]["names"].append(name)
            grouped[frozenset(deps)]["values"].append(value)
            grouped[frozenset(deps)]["deps"] = deps

    # Build cleaned XML
    base = soup.find("dependents")
    base.clear()

    for key, info in grouped.items():
        op = soup.new_tag("option")
        op["name"] = ",".join(sorted(set(info["names"])))
        op["value"] = ",".join(sorted(set(info["values"])))

        for dep_xml in info["deps"]:
            dep_soup = BeautifulSoup(dep_xml, "xml").dependent
            op.append(dep_soup)

        base.append(op)

    return soup.prettify()


# ---------------------------
# AI Suggestion Function
# ---------------------------

def ask_ai(original, cleaned):
    if not api_key:
        return "⚠️ API key missing. Please enter your key."

    client = OpenAI(api_key=api_key)

    prompt = f"""
Act as an XML rules optimizer expert. Compare the following:

Original XML:
{original}

Cleaned XML:
{cleaned}

Explain in bullet points:
- What improvements were made?
- What patterns were detected?
- Any optimization still possible?
"""

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}]
    )

    return response.choices[0].message.content


# ---------------------------
# UI
# ---------------------------

st.title("🧠 XML Rule Optimizer + AI Reasoning")

uploaded = st.file_uploader("📂 Upload XML File", type=['xml'])

if uploaded:

    original_xml = uploaded.read().decode("utf-8")

    st.subheader("📌 Raw XML Preview")
    st.code(original_xml, language="xml")

    cleaned_xml = dedupe_xml(original_xml)

    st.success("✨ XML Optimization Complete!")

    st.subheader("📌 Cleaned Output")
    st.code(cleaned_xml, language="xml")

    # Download Button
    st.download_button(
        label="⬇️ Download Cleaned XML",
        data=cleaned_xml,
        file_name="cleaned_output.xml",
        mime="text/xml"
    )

    # AI Insight Panel
    if use_ai and api_key:
        st.subheader("🤖 AI Insight & Suggestions")
        with st.spinner("Thinking..."):
            ai_response = ask_ai(original_xml, cleaned_xml)

        st.write(ai_response)
    elif use_ai and not api_key:
        st.warning("Enter OpenAI key to enable AI explanations 🔧")

else:
    st.info("📄 Upload XML to begin processing.")
