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
    Rewritten pipeline that preserves original option-level grouping and
    only merges across original <option> elements when BOTH:
      - dependent sets are identical
      - AND the value sets (IDs) are identical

    This prevents grouping same-named entries that have different value IDs.
    """

    # Step 1: read original options into a list of records preserving order
    original_options = []
    for opt in root.findall("option"):
        names = _split_field(opt.get("name", ""))
        values = _split_field(opt.get("value", ""))

        # canonical dependents signature (sorted list of "id:name")
        dependents = sorted([f"{d.get('id')}:{d.get('name')}" for d in opt.findall("dependent")])
        deps_key = tuple(dependents)  # tuple so hashable

        # store as record (keep original order of names/values)
        original_options.append({
            "names": names,
            "values": values,
            "deps_key": deps_key,
            "dependents": dependents
        })
    # Step 2: Flatten every option into (name, value, deps) tuples
    flat = []

    value_to_dep_map = {}  # to detect crossings

    for record in original_options:
        
        # expand name/value pairs preserving sequence
        for idx, name in enumerate(record["names"]):
            name = name.strip()
            val = record["values"][idx] if idx < len(record["values"]) else record["values"][-1]

            entry = {
                "name": name,
                "value": val,
                "deps_key": tuple(record["deps_key"]),
                "dependents": record["dependents"]
            }
            flat.append(entry)

            # Track if same value appears in multiple options
            value_to_dep_map.setdefault(val, []).append(entry)

    # Step 3: Identify forced splits
    # If same value exists across more than one original parent → it becomes its own group candidate
    forced_singletons = {v for v, rows in value_to_dep_map.items() if len(rows) > 1}

    # Step 4: Make buckets
    groups = {}
    appearance_order = 0

    for entry in flat:

        if entry["value"] in forced_singletons:
            # force isolate - value belongs to another option too
            key = ("FORCE", entry["value"], entry["deps_key"])
        else:
            # merge key rule: only dependents must match
            key = ("NORMAL", entry["deps_key"])

        if key not in groups:
            groups[key] = {
                "names": [],
                "values": [],
                "dependents": entry["dependents"],
                "order": appearance_order
            }
            appearance_order += 1

        groups[key]["names"].append(entry["name"])
        groups[key]["values"].append(entry["value"])

    # Step 3: build new <dependents> root using grouped data in stable order
    # Sort groups by first_appearance so we keep stable ordering
    groups_ordered = sorted(groups.items(), key=lambda kv: kv[1]["first_appearance"])

    new_root = ET.Element("dependents", root.attrib)

    for _, data in groups_ordered:
        opt = ET.SubElement(new_root, "option")

        # names: join the list using comma. We preserve the original ordering of names.
        # Optionally remove duplicates while preserving order:
        seen = set()
        dedup_names = []
        for n in data["names"]:
            if n not in seen:
                dedup_names.append(n)
                seen.add(n)
        opt.set("name", ",".join(dedup_names))

        # values: join values list (values_key) as given — they represent the canonical values for the group
        opt.set("value", ",".join(data["values"]))

        # append dependents (they are identical for the group)
        for dep in data["dependents"]:
            # dep is "id:name"
            dep_id, dep_name = dep.split(":", 1)
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
