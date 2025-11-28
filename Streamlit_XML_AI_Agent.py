import streamlit as st
import xml.etree.ElementTree as ET
import pandas as pd
from io import BytesIO
import os

# --- AI PROVIDERS ---
from openai import OpenAI
from groq import Groq

# ---------- APP CONFIG ----------
st.set_page_config(page_title="XML Optimizer AI", page_icon="⚙️", layout="wide")

st.markdown("""
<h2>⚙️ XML Cleaner + Smart Mapper (AI Powered)</h2>
<p style="color:gray;">Upload → Clean → Analyze → Export</p>
""", unsafe_allow_html=True)

# ---------- LOAD API KEYS ----------
OPENAI_API_KEY = st.secrets.get("OPENAI_API_KEY", None)
GROK_API_KEY = st.secrets.get("GROK_API_KEY", None)

openai_client = OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None
groq_client = Groq(api_key=GROK_API_KEY) if GROK_API_KEY else None

# ---------- PARSING + MERGE LOGIC FIXED ----------

def merge_dependents(xml_root):

    extracted = []

    for opt in xml_root.findall("option"):
        name_list = set(opt.get("name", "").replace(" ", "").split(","))
        value_list = set(opt.get("value", "").replace(" ", "").split(","))

        dependents = {(d.get("id"), d.get("name")) for d in opt.findall("dependent")}

        extracted.append({
            "names": name_list,
            "values": value_list,
            "dependents": dependents
        })

    # ---- SMART MERGING ----
    merged = []

    for item in extracted:
        merged_flag = False

        for grp in merged:
            # Merge if dependents overlap at least 1 field
            if grp["dependents"].intersection(item["dependents"]):
                grp["names"].update(item["names"])
                grp["values"].update(item["values"])
                grp["dependents"].update(item["dependents"])
                merged_flag = True
                break

        if not merged_flag:
            merged.append(item)

    # Cleanup + sorting
    for grp in merged:
        grp["names"] = sorted(grp["names"])
        grp["values"] = sorted(grp["values"], key=lambda x: int(x) if x.isdigit() else x)
        grp["dependents"] = sorted(list(grp["dependents"]))

    return merged


def generate_clean_xml(original_root):
    grouped = merge_dependents(original_root)

    new_root = ET.Element("dependents", original_root.attrib)

    for entry in grouped:
        opt = ET.SubElement(new_root, "option")
        opt.set("name", ",".join(entry["names"]))
        opt.set("value", ",".join(entry["values"]))

        for dep_id, dep_label in entry["dependents"]:
            ET.SubElement(opt, "dependent", {
                "type": "0",
                "id": dep_id,
                "name": dep_label,
                "reset": "false",
                "retainonedit": "false"
            })

    return ET.tostring(new_root, encoding="unicode")


# ---------- UI: XML UPLOAD ----------
uploaded_file = st.file_uploader("📁 Upload XML File", type=["xml"])

cleaned_xml = None
parsed_root = None

if uploaded_file:
    xml_string = uploaded_file.read().decode("utf-8")

    try:
        parsed_root = ET.fromstring(xml_string)
        cleaned_xml = generate_clean_xml(parsed_root)

        st.success("XML successfully cleaned and optimized! ✅")

        st.code(cleaned_xml, language="xml")

    except Exception as e:
        st.error(f"❌ XML Parsing Error: {str(e)}")

# ---------- EXPORT XML ----------
if cleaned_xml:
    st.download_button(
        "📥 Download Clean XML",
        cleaned_xml,
        file_name="optimized_dependents.xml"
    )

# ---------- EXPORT TO EXCEL ----------
if cleaned_xml:
    df_export = pd.DataFrame({"Optimized XML": [cleaned_xml]})
    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:
        df_export.to_excel(writer, sheet_name="XML", index=False)

    st.download_button(
        "📊 Export to Excel",
        data=buffer.getvalue(),
        file_name="xml_mapping.xlsx"
    )

# ---------- AI SUGGESTION SECTION ----------

st.divider()
st.subheader("🤖 AI Insight & Suggestions")

# AI button disabled until XML processed
ai_prompt_button = st.button("💡 Suggest Mapping (AI Powered)", disabled=cleaned_xml is None)

if ai_prompt_button:
    with st.spinner("Analyzing and thinking... 🤖"):

        prompt = f"Analyze this cleaned XML and suggest improvements:\n\n{cleaned_xml}"

        model_used = "GPT-4o-mini"

        try:
            if groq_client:
                response = groq_client.chat.completions.create(
                    model="llama3-70b-8192",
                    messages=[{"role": "user", "content": prompt}]
                )
                ai_output = response.choices[0].message["content"]
                model_used = "Grok LLaMA3 🔥"

            elif openai_client:
                response = openai_client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[{"role": "user", "content": prompt}]
                )
                ai_output = response.choices[0].message["content"]
                model_used = "OpenAI GPT-4o Mini"

            else:
                ai_output = "⚠️ No API Key detected in Streamlit Secrets."

            st.success(f"AI Analysis Completed using **{model_used}**:")
            st.write(ai_output)

        except Exception as e:
            st.error(f"AI Error: {str(e)}")


st.caption("Built by IBL Digital Team • AI XML Mapping Assistant 🔧🚀")
