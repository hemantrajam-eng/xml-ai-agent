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

def aggregate_per_name(root):
    """
    For each individual name (exploded from option/@name), collect:
      - values: set of values for that name across options
      - dependents: set of (id, name) tuples across options
    Also record first appearance index of name for stable ordering.
    Returns: per_name dict, name_first_index dict
    """
    per_name = {}
    name_first_index = {}
    appearance_counter = 0

    for opt in root.findall("option"):
        names = _split_field(opt.get("name", ""))
        values = _split_field(opt.get("value", ""))

        # dependents in this option
        deps = []
        for d in opt.findall("dependent"):
            dep_id = d.get("id")
            dep_name = d.get("name")
            deps.append((dep_id, dep_name))

        # assign each name a corresponding value if available
        for i, name in enumerate(names):
            # if fewer values than names, last value used for remaining names (safe fallback)
            value = values[i] if i < len(values) else (values[-1] if values else "")
            if name not in per_name:
                per_name[name] = {"values": set(), "dependents": set()}
            per_name[name]["values"].add(value)
            per_name[name]["dependents"].update(deps)

            # record first appearance
            if name not in name_first_index:
                name_first_index[name] = appearance_counter
                appearance_counter += 1

    return per_name, name_first_index

def group_by_deps(per_name, name_first_index):
    """
    Group names only if:
      - They have identical dependent sets
      - AND identical value sets

    If dependents match but value sets differ → keep as separate groups.
    """

    groups_map = {}  # key: (deps_key, values_key) -> group data

    for name, info in per_name.items():

        deps_key = tuple(sorted(info["dependents"]))
        values_key = tuple(sorted(info["values"], key=lambda v: (int(v) if v.isdigit() else v)))

        group_key = (deps_key, values_key)

        if group_key not in groups_map:
            groups_map[group_key] = {
                "names": set(),
                "values": set(),
                "dependents": list(sorted(info["dependents"]))
            }

        groups_map[group_key]["names"].add(name)
        groups_map[group_key]["values"].update(info["values"])

    # Convert result to ordered list
    groups = []
    for (_, _), data in groups_map.items():

        # Sorting for stable output
        ordered_names = sorted(data["names"], key=lambda n: name_first_index.get(n, 10**9))
        ordered_values = sorted(data["values"], key=lambda v: (int(v) if v.isdigit() else v))

        order_key = min(name_first_index.get(n, 10**9) for n in ordered_names)

        groups.append({
            "names": ordered_names,
            "values": ordered_values,
            "dependents": data["dependents"],
            "order_key": order_key
        })

    groups.sort(key=lambda x: x["order_key"])
    return groups

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
    Full pipeline:
      - aggregate per name
      - group names by identical dependent sets
      - build new <dependents> XML preserving original attributes
    """
    per_name, name_first_index = aggregate_per_name(root)
    groups = group_by_deps(per_name, name_first_index)

    new_root = ET.Element("dependents", root.attrib)

    for g in groups:
        opt = ET.SubElement(new_root, "option")
        opt.set("name", ",".join(g["names"]))
        opt.set("value", ",".join(g["values"]))
        # append dependents in stable order
        for dep_id, dep_name in g["dependents"]:
            ET.SubElement(opt, "dependent", {
                "type": "0",
                "id": dep_id,
                "name": dep_name,
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

    # Parse both XMLs
    root_clean = ET.fromstring(cleaned_xml)
    root_original = ET.fromstring(xml_text)

    # ------- STEP 1: Build mapping from original XML -------
    original_map = {}  # key: dependents signature → set of individual names

    for opt in root_original.findall("option"):
        names = [n.strip() for n in opt.get("name", "").split(",")]

        deps = sorted([f"{d.get('id')}:{d.get('name')}" for d in opt.findall("dependent")])
        deps_key = "|".join(deps)

        if deps_key not in original_map:
            original_map[deps_key] = set()

        original_map[deps_key].update(names)


    # ------- STEP 2: Build cleaned mapping -------
    export_rows = []
    group_number = 1
    change_notes = {}

    for opt in root_clean.findall("option"):

        group_id = f"G{group_number}"
        names = [n.strip() for n in opt.get("name","").split(",")]
        values = [v.strip() for v in opt.get("value","").split(",")]

        deps = sorted([f"{d.get('id')}:{d.get('name')}" for d in opt.findall("dependent")])
        deps_key = "|".join(deps)

        # Compare original vs cleaned
        original_names = original_map.get(deps_key, set())

        if len(original_names) > 1 and len(names) == 1:
            status = "🔄 Merged"
            note = f"Merged {len(original_names)} → 1"
        elif len(names) > 1:
            status = "✂ Split"
            note = f"Split into {len(names)}"
        elif names == list(original_names):
            status = "🟢 Unchanged"
            note = ""
        else:
            status = "❓ Modified"
            note = "Names altered / dependency changed"

        # Store per grouped option
        for i, name in enumerate(names):
            val = values[i] if i < len(values) else values[-1]

            export_rows.append([
                group_id, name, val, deps_key.replace("|", ";"), status, note
            ])

        group_number += 1


    # ------- STEP 3: DataFrame & Export -------
    df = pd.DataFrame(export_rows, columns=[
        "Group ID", "Option Name", "Option Value", "Dependents", "Status", "Notes"
    ])
    
    df.insert(0, "Sr No", range(1, len(df)+1))

    excel_buffer = BytesIO()
    df.to_excel(excel_buffer, index=False, sheet_name="Mapping")
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
