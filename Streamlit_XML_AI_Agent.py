import streamlit as st
import xml.etree.ElementTree as ET
import pandas as pd
import base64
from ai_engine import AIEngine

# ---------------- UI SETUP ----------------
st.set_page_config(
    page_title="XML AI Mapper",
    page_icon="🤖",
    layout="wide"
)

st.title("🔍 XML Field Mapper (AI Powered)")
st.caption("Upload → Clean → Compare → Ask AI → Export")

# Sidebar AI Info
llm = AIEngine()
st.sidebar.success(f"🧠 AI Engine Active: **{llm.active_model.upper()}**")

# ---------------- XML FUNCTIONS ----------------
def parse_xml(xml_text):
    try:
        return ET.fromstring(xml_text)
    except Exception as e:
        st.error(f"❌ Invalid XML: {e}")
        return None

def normalize_option_text(option):
    names = option.get('name', '').replace(" ", "").split(",")
    values = option.get('value', '').replace(" ", "").split(",")
    return names, values

def merge_dependents(xml_root):
    grouped = {}

    for opt in xml_root.findall("option"):
        names, values = normalize_option_text(opt)
        deps = [(d.get("id"), d.get("name")) for d in opt.findall("dependent")]

        deps_key = tuple(sorted(deps))

        if deps_key not in grouped:
            grouped[deps_key] = {"names": set(), "values": set(), "dependents": deps}

        grouped[deps_key]["names"].update(names)
        grouped[deps_key]["values"].update(values)

    return grouped

def generate_clean_xml(original_root):
    grouped = merge_dependents(original_root)

    new_root = ET.Element("dependents", original_root.attrib)

    for entry in grouped.values():
        opt = ET.SubElement(new_root, "option")
        opt.set("name", ",".join(sorted(entry["names"])))
        opt.set("value", ",".join(sorted(entry["values"])))

        for dep_id, dep_name in entry["dependents"]:
            ET.SubElement(
                opt, "dependent", {
                    "type": "0",
                    "id": dep_id,
                    "name": dep_name,
                    "reset": "false",
                    "retainonedit": "false"
                }
            )

    return ET.tostring(new_root, encoding="unicode")

def suggest_mapping(xml_text):
    prompt = f"""
Analyze the following XML structure and produce:

- Grouping logic summary
- Duplicate detection
- Suggested optimized field relationships

Return format:
1️⃣ Summary  
2️⃣ Recommendations  
3️⃣ Clean Mapping (JSON or table)

XML:
{xml_text}
"""
    return llm.generate(prompt)

# ---------------- FILE UPLOAD AREA ----------------

uploaded_file = st.file_uploader("📁 Upload XML File", type=["xml"])

xml_input_col, cleaned_xml_col, compare_col = st.columns(3)

xml_text = None
cleaned_xml = None

if uploaded_file:
    xml_text = uploaded_file.read().decode("utf-8")
    original_root = parse_xml(xml_text)

    with xml_input_col:
        st.subheader("📄 Original XML")
        st.code(xml_text, language="xml")

    # Clean XML
    cleaned_xml = generate_clean_xml(original_root)

    with cleaned_xml_col:
        st.subheader("🧹 Cleaned XML")
        st.code(cleaned_xml, language="xml")

    # Comparison Table
    with compare_col:
        st.subheader("🔄 Before vs After Count")
        df = pd.DataFrame([
            ["Option Count", len(original_root.findall('option')), cleaned_xml.count("<option")],
            ["Dependent Count", xml_text.count("<dependent"), cleaned_xml.count("<dependent")]
        ], columns=["Metric", "Original", "Cleaned"])

        st.dataframe(df)

# ---------------- AI MAPPING BUTTON ----------------
st.divider()

if st.button("🤖 Suggest Mapping (AI)"):
    if not uploaded_file:
        st.warning("⚠️ Upload an XML file first.")
    else:
        with st.spinner("🔍 AI analyzing structure..."):
            result = suggest_mapping(cleaned_xml)
        st.success("📌 AI Mapping Suggestion Ready")
        st.code(result, language="markdown")

# ---------------- DOWNLOAD CLEANED XML ----------------
if cleaned_xml:
    st.download_button(
        label="📥 Download Clean XML",
        data=cleaned_xml,
        file_name="cleaned_output.xml",
        mime="text/xml"
    )

# ---------------- EXPORT TO EXCEL ----------------
if cleaned_xml:
    df_export = pd.DataFrame({"Cleaned XML": [cleaned_xml]})
    excel_data = df_export.to_excel(index=False, sheet_name="XML", engine="xlsxwriter")

    st.download_button(
        label="📊 Export to Excel",
        data=excel_data,
        file_name="mapped_output.xlsx"
    )
