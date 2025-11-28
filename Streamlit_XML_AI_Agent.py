import streamlit as st
import pandas as pd
from openai import OpenAI
from lxml import etree
from io import BytesIO


# ---------------- UI Styling ---------------- #
st.set_page_config(page_title="XML Smart Cleaner & Mapper", page_icon="🤖", layout="wide")

st.markdown("""
<style>
    .main {background-color: #f9fafc;}
    .title {font-size: 32px; font-weight: bold; color:#333;}
    .sub {font-size:14px; color:#777;}
    .stButton > button {border-radius:10px; padding:10px 20px; font-weight:bold;}
    .footer {text-align:center; padding:12px; font-size:12px; color:#aaa;}
</style>
""", unsafe_allow_html=True)

# ---------------- Header ---------------- #
st.markdown('<div class="title">🧠 XML AI Assistant (Pro Mode)</div>', unsafe_allow_html=True)
st.markdown('<div class="sub">Upload → Clean → Analyze → AI Mapping → Export</div>', unsafe_allow_html=True)
st.write("---")

# ---------------- Sidebar ---------------- #
st.sidebar.header("⚙️ Settings")

llm_provider = st.sidebar.selectbox(
    "AI Model Provider", ["OpenAI", "Groq"]
)

api_key = st.sidebar.text_input("Enter API Key", type="password")

model_name = "gpt-4o-mini" if llm_provider == "OpenAI" else "llama-3.2-90b-vision-preview"

client = None
if api_key:
    if llm_provider == "OpenAI":
        client = OpenAI(api_key=api_key)
    else:
        from groq import Groq
        client = Groq(api_key=api_key)


# ---------------- Main Panels ---------------- #

col1, col2 = st.columns([1, 1.5])

with col1:
    st.subheader("📂 Upload XML")
    uploaded = st.file_uploader("Select XML File", type=["xml"])

    xml_content = None
    cleaned_xml = None

    if uploaded:
        xml_content = uploaded.read().decode("utf-8")
        st.code(xml_content, language="xml")

    # Clean Button
    if st.button("🧹 Clean & Normalize XML", disabled=(not uploaded)):
        with st.spinner("Cleaning XML..."):
            try:
                root = etree.fromstring(xml_content)
                cleaned_xml = etree.tostring(root, pretty_print=True).decode("utf-8")
                st.success("XML successfully normalized! 🎯")
            except Exception as e:
                st.error(f"❌ Parsing error: {e}")


with col2:
    st.subheader("🔍 Cleaned XML Output")

    if cleaned_xml:
        st.code(cleaned_xml, language="xml")
        st.download_button("⬇️ Download Cleaned XML", cleaned_xml, "cleaned.xml")

    st.write("---")

    # 🔥 AI Mapping Suggestion
    st.subheader("🤖 AI Mapping & Insights")

    if st.button("🚀 Generate Smart Mapping (AI)", disabled=(client is None or cleaned_xml is None)):
        with st.spinner("AI analyzing your XML structure 🚧..."):
            prompt = f"""
            You are an XML workflow analyzer. Based on the given XML, identify:

            - Duplicate option groups
            - Similar dependency sets
            - Recommended merges
            - Suggested final cleaned output XML

            XML:
            {cleaned_xml}
            """

            try:
                response = client.chat.completions.create(
                    model=model_name,
                    messages=[{"role": "user", "content": prompt}]
                )

                ai_output = response.choices[0].message.content
                st.success("AI Mapping Completed 🎯")
                st.markdown(f"### 📌 AI Recommendation\n\n{ai_output}")

                st.download_button("💾 Download AI Report", ai_output, "AI_Mapping_Summary.txt")

            except Exception as e:
                st.error(f"❌ AI Error: {e}")


# ---------------- Footer ---------------- #
st.markdown('<div class="footer">Made with ❤️ using Streamlit + AI</div>', unsafe_allow_html=True)

# ---------------- Comparison & Export Tools ---------------- #
st.write("---")
st.subheader("📊 Comparison View")

if xml_content or cleaned_xml or "ai_output" in locals():

    compare_tabs = st.tabs(["📄 Original XML", "🧼 Cleaned XML", "🤖 AI Suggested Output"])

    with compare_tabs[0]:
        st.code(xml_content or "No file uploaded", language="xml")

    with compare_tabs[1]:
        st.code(cleaned_xml or "Not processed yet", language="xml")

    with compare_tabs[2]:
        st.markdown(ai_output if "ai_output" in locals() else "_Run AI mapping first._")


    # ---------- Excel Export Button ---------- #
    st.write("---")
    st.subheader("📁 Export Mapping to Excel")

    # Convert to table for Excel if AI structured block exists
    df = pd.DataFrame({
        "Version": ["Original", "Cleaned", "AI Suggested"],
        "Content": [xml_content, cleaned_xml, ai_output if "ai_output" in locals() else None]
    })

    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name="XML Comparison")

        # Add pretty formatting
        workbook = writer.book
        worksheet = writer.sheets["XML Comparison"]
        wrap_format = workbook.add_format({'text_wrap': True, 'valign': 'top'})

        worksheet.set_column("A:A", 20)
        worksheet.set_column("B:B", 120, wrap_format)

    st.download_button(
        label="⬇ Download Comparison Excel",
        data=output.getvalue(),
        file_name="XML_AI_Comparison.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
