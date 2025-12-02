import streamlit as st
import xml.etree.ElementTree as ET
import pandas as pd
from io import BytesIO
import os
st.sidebar.title("🔧 AI Configuration")

try:
    from ai_engine import AIEngine
    llm = AIEngine()
except Exception:
    llm = None
    
if llm is None:
    st.sidebar.error("❌ AI engine not loaded.")
else:

    # UI Helper to mask key
    def mask(key):
        return f"****{key[-4:]}" if key else "None"

    # Status Display
    st.sidebar.subheader("API Status")

    openai_status = "🟢 Connected" if llm.openai_key else "🔴 Missing"
    grok_status = "🟢 Connected" if llm.grok_key else "🔴 Missing"

    st.sidebar.write(f"**OpenAI:** {openai_status} | {mask(llm.openai_key)}")
    st.sidebar.write(f"**Grok:** {grok_status} | {mask(llm.grok_key)}")

    # Test Button
    if st.sidebar.button("🔍 Test Connection"):
        result = llm.test_connection()

        if result.get("openai"):
            st.sidebar.success("🟢 OpenAI Responding")
        else:
            st.sidebar.error("🔴 OpenAI Failed")

        if result.get("grok"):
            st.sidebar.success("🟢 Grok Responding")
        else:
            st.sidebar.error("🔴 Grok Failed")


st.set_page_config(page_title="XML AI Mapper", page_icon="🤖", layout="wide")
st.title("🔍 XML Field Mapper (AI Powered)")
st.caption("Upload → Clean → Compare → Ask AI → Export")

# Show which AI engine is active (if ai_engine exists)
if llm and llm.active_model:
    st.sidebar.success(f"🧠 Model in use: {llm.active_model}")
else:
    st.sidebar.warning("⚠️ AI model not initialized yet.")

# ------------------- Helper functions (correct algorithm) -------------------

def _split_field(text):
    """Split comma-separated attribute safely and return stripped tokens."""
    if not text:
        return []
    return [t.strip() for t in text.split(",") if t.strip()]

def _prettify_xml(elem):
    """
    Simple pretty printer to indent XML for readability.
    """
    def _indent(e, level=0):
        i = "\n" + level*"  "
        if len(e):
            if not e.text or not e.text.strip():
                e.text = i + "  "
            for child in e:
                _indent(child, level+1)
            if not child.tail or not child.tail.strip():
                child.tail = i
        if level and (not e.tail or not e.tail.strip()):
            e.tail = i
    _indent(elem)
    
    return ET.tostring(elem, encoding="unicode")

def generate_clean_xml_from_root(root):
    """
    Cleans and rebuilds <option> XML while preserving original ordering.

    Rules:
    1️⃣ Split comma-separated options into individual records.
    2️⃣ If the same value appears multiple times → treat as a single item.
    3️⃣ Union dependents for each unique value.
    4️⃣ If multiple values share identical dependents → merge under one <option>.
    5️⃣ DO NOT sort — preserve original ordering exactly as first encountered.

    Additional:
    - Dependent <name> attribute uses first occurrence name permanently.
    - Names and their corresponding values stay aligned.
    """

    def _split(text):
        return [t.strip() for t in text.split(",") if t.strip()] if text else []

    flat = []
    dep_id_to_name = {}      # Tracks first seen dependent name
    name_to_value = {}       # Tracks first mapping name->value

    # --- STEP 1: FLATTEN INPUT ---
    for opt in root.findall("option"):
        names = _split(opt.get("name", ""))
        values = _split(opt.get("value", ""))

        deps = opt.findall("dependent")
        dep_ids = []

        for d in deps:
            dep_id = d.get("id")
            dep_name = d.get("name", "")
            dep_ids.append(dep_id)

            if dep_id not in dep_id_to_name:
                dep_id_to_name[dep_id] = dep_name   # keep first seen dependent name

        for idx, name in enumerate(names):
            value = values[idx] if idx < len(values) else values[-1] if values else ""
            flat.append({"name": name, "value": value, "deps": set(dep_ids)})

            if name not in name_to_value:
                name_to_value[name] = value

    # --- STEP 2: UNION DEPENDENTS PER VALUE ---
    value_to_deps = {}
    for item in flat:
        val = item["value"]
        if val not in value_to_deps:
            value_to_deps[val] = set()
        value_to_deps[val].update(item["deps"])

    # --- STEP 3: MERGE VALUES WITH IDENTICAL DEPENDENTS ---
    merged = []
    seen_dep_sets = {}

    for item in flat:
        val = item["value"]
        dep_key = frozenset(value_to_deps[val])

        if dep_key not in seen_dep_sets:
            seen_dep_sets[dep_key] = {
                "names": [],
                "values": [],
                "deps": dep_key
            }

        group = seen_dep_sets[dep_key]
        if item["name"] not in group["names"]:
            group["names"].append(item["name"])
        if val not in group["values"]:
            group["values"].append(val)

    # Preserve first-seen group order
    merged = list(seen_dep_sets.values())

    # --- STEP 4: REBUILD CLEAN XML ---
    new_root = ET.Element("dependents", root.attrib)

    for group in merged:
        opt = ET.SubElement(new_root, "option")
        opt.set("name", ",".join(group["names"]))
        opt.set("value", ",".join(group["values"]))

        # dependents sorted only for consistent XML formatting (not required, safe)
        for dep_id in sorted(group["deps"], key=str):
            ET.SubElement(opt, "dependent", {
                "type": "0",
                "id": dep_id,
                "name": dep_id_to_name.get(dep_id, ""),
                "reset": "false",
                "retainonedit": "false"
            })


    return _prettify_xml(new_root)


# ------------------- Streamlit app UI -------------------

uploaded = st.file_uploader("📁 Upload XML file", type=["xml"])
xml_text = None
cleaned_xml = None
original_root = None

if uploaded:
    xml_text = uploaded.read().decode("utf-8")
    st.subheader("📄 Original XML Preview")
    st.code("\n".join(xml_text.splitlines()[:10]) + ("\n..." if len(xml_text.splitlines())>10 else ""), language="xml")


    # parse and clean
    try:
        original_root = ET.fromstring(xml_text)
        cleaned_xml = generate_clean_xml_from_root(original_root)
        st.subheader("🧼 Cleaned / Optimized XML Preview (Max 50 lines)")
        cleaned_lines = cleaned_xml.splitlines()
        preview_lines = cleaned_lines[:50]
        st.code("\n".join(preview_lines) + ("\n..." if len(cleaned_lines) > 50 else ""), language="xml")

        st.success("✅ Cleaned output generated (per-name aggregation & grouping by identical dependents).")

    except Exception as e:
        st.error(f"XML parse / cleaning error: {e}")

# Comparison counts
if uploaded and cleaned_xml:
    st.subheader("🔄 Summary (Before vs After)")
    df = pd.DataFrame([
        ["Option Count", len(original_root.findall('option')), cleaned_xml.count("<option")],
        ["Dependent Count", xml_text.count("<dependent"), cleaned_xml.count("<dependent")]
    ], columns=["Metric", "Original", "Cleaned"])
    st.dataframe(df)

# Download cleaned xml
if cleaned_xml:
    st.download_button("📥 Download Clean XML", cleaned_xml, file_name="cleaned_dependents.xml", mime="text/xml")

# ------------------- Export Mapping with Change Tracking -------------------
if cleaned_xml and uploaded:

    root_clean = ET.fromstring(cleaned_xml)
    root_original = ET.fromstring(xml_text)

    # ---- Build original flattened record list ----
    original_records = []
    for opt in root_original.findall("option"):
        names = _split_field(opt.get("name", ""))
        values = _split_field(opt.get("value", ""))
        deps = sorted([f"{d.get('id')}:{d.get('name')}" for d in opt.findall("dependent")])
        
        for i, name in enumerate(names):
            val = values[i] if i < len(values) else values[-1]
            original_records.append({
                "name": name,
                "value": val,
                "dependents": deps,
                "group_key": "|".join(sorted(names))  # original grouping signature
            })

    df_original = pd.DataFrame(original_records)

    # ---- Build cleaned flattened record list ----
    cleaned_records = []
    for opt in root_clean.findall("option"):
        names = _split_field(opt.get("name", ""))
        values = _split_field(opt.get("value", ""))
        deps = sorted([f"{d.get('id')}:{d.get('name')}" for d in opt.findall("dependent")])
        
        for i, name in enumerate(names):
            val = values[i] if i < len(values) else values[-1]
            cleaned_records.append({
                "name": name,
                "value": val,
                "dependents": deps,
                "group_key": "|".join(sorted(names))  # cleaned grouping signature
            })

    df_clean = pd.DataFrame(cleaned_records)

    # ---- Merge original vs cleaned for change tracking ----
    df_compare = df_clean.merge(df_original, on=["name", "value"], how="left", suffixes=("_new", "_old"))

    # ---- Determine statuses ----
    df_compare["Group Status"] = df_compare.apply(
        lambda x: "Modified" if x["group_key_new"] != x["group_key_old"] else "Non-modified",
        axis=1
    )

    df_compare["Dependency Status"] = df_compare.apply(
        lambda x: "Modified" if x["dependents_new"] != x["dependents_old"] else "Non-modified",
        axis=1
    )

    # ---- Final export structure ----
    df_export = df_compare[[
        "name",
        "value",
        "dependents_new",
        "Group Status",
        "Dependency Status"
    ]].rename(columns={
        "name": "Option Name",
        "value": "Option Value",
        "dependents_new": "Final Dependents"
    })

    df_export.insert(0, "Sr No", range(1, len(df_export) + 1))

    # ---- Export to Excel ----
    excel_buffer = BytesIO()
    df_export.to_excel(excel_buffer, index=False, sheet_name="Mapping")
    excel_buffer.seek(0)

    st.download_button(
        "📥 Download Mapping Excel",
        data=excel_buffer,
        file_name="option_mapping.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

    
# AI Suggest mapping (if ai_engine present)
st.markdown("---")
st.subheader("🤖 AI: Suggest Mapping (Optional)")

if st.button("💡 Suggest Mapping (AI)"):
    if not cleaned_xml:
        st.warning("Please upload and generate cleaned XML first.")
    else:
        if not llm:
            st.warning("No AI engine available (ensure ai_engine.py exists and secrets set).")
        else:
            with st.spinner("AI analyzing cleaned XML..."):
                try:
                    # generate prompt & call
                    prompt = f"""You are an XML expert. Given the cleaned <dependents> XML below,
explain grouping decisions, detect duplicates, and produce a suggested mapping table.
Return a short summary and a JSON mapping example.

Cleaned XML:
{cleaned_xml}
"""
                    ai_text = llm.generate(prompt)
                    st.subheader("AI Output")
                    if "⚠️" in ai_text or "Error" in ai_text:
                        st.error(ai_text)
                    else:
                        st.code(ai_text)
                except Exception as e:
                    st.error(f"AI call error: {e}")


st.caption("Built by IBL Digital Team • AI XML Mapping Assistant 🔧🚀")
