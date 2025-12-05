import os, json, textwrap
import streamlit as st
from PIL import Image
from openai import OpenAI


st.set_page_config(
    page_title="AI Clinic | OTC Medication",
    page_icon="assets/h4u_icon2.ico",  # point to your PNG
    layout="wide"
)


# --- Header images (unchanged) ---
col1, col2 = st.columns([1, 1])
with col1:
    image = Image.open("assets/h4u_logo.png")
    st.image(image.resize((600, 250)))
with col2:
    image = Image.open("assets/otc.png")
    st.image(image.resize((600, 350)))

st.title("💊 OTC Medication Suggestions & Pharma Offers")

condition_summary = st.session_state.get("condition_summary", "")
if not condition_summary:
    st.warning("⚠️ No suggestions found. Please run the symptom checker first.")
    st.stop()

# ----------------- OpenAI call -----------------
def get_otc_suggestions(symptom_summary: str, age: int | None = None, allergies: str | None = None, meds: str | None = None):
    """
    Returns dict with:
      - otc_recommendations: list[{name, purpose, dosage_general, notes}]
      - red_flags: list[str]
      - when_to_seek_care: list[str]
      - lifestyle: list[str]
    """
    # If no API key, return fallback
    if not os.getenv("OPENAI_API_KEY"):
        return None

    client = OpenAI()  # uses OPENAI_API_KEY env var

    system_msg = (
        "You are a careful, concise clinical assistant. "
        "Provide OTC symptom-relief options only (no diagnosis). "
        "Never give personalized dosing; give general label-based guidance only. "
        "Flag dangerous symptoms and advise when to seek urgent/non-urgent care. "
        "Be brief and practical; US OTC context."
    )
    user_msg = textwrap.dedent(f"""
    USER PROFILE (if provided):
    - Age: {age if age else "unknown"}
    - Allergies: {allergies or "unknown"}
    - Current Medications: {meds or "unknown"}

    SYMPTOM SUMMARY (from app):
    {symptom_summary}

    OUTPUT STRICTLY AS COMPACT JSON with keys:
    {{
      "otc_recommendations": [
        {{"name": "...", "purpose": "...", "dosage_general": "...", "notes": "..."}}
      ],
      "red_flags": ["..."],
      "when_to_seek_care": ["..."],
      "lifestyle": ["..."]
    }}
    """).strip()

    try:
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "system", "content": system_msg},
                      {"role": "user", "content": user_msg}],
            temperature=0.2,
        )
        content = resp.choices[0].message.content
        # Extract JSON (in case the model adds extra text)
        start = content.find("{")
        end = content.rfind("}")
        data = json.loads(content[start:end+1])
        return data
    except Exception as e:
        st.warning(f"OTC assistant unavailable ({e}). Showing a generic list instead.")
        return None

# Optional: capture a bit more context if you store these in session
age = st.session_state.get("age")
allergies = st.session_state.get("allergies")
meds = st.session_state.get("meds")

with st.spinner("Asking AI for OTC suggestions…"):
    suggestions = get_otc_suggestions(condition_summary, age=age, allergies=allergies, meds=meds)

# ----------------- Render -----------------
st.markdown("### Your Possible Suggestions:")
st.write(condition_summary)

st.markdown("### Suggested OTC Medications (AI-assisted)")
if suggestions and suggestions.get("otc_recommendations"):
    for rec in suggestions["otc_recommendations"]:
        with st.container(border=True):
            st.markdown(f"**{rec.get('name','')}** — {rec.get('purpose','')}")
            st.markdown(f"- *General label guidance:* {rec.get('dosage_general','')}")
            if rec.get("notes"):
                st.markdown(f"- *Notes/Cautions:* {rec['notes']}")
else:
    # Fallback if API/key failed
    st.markdown("- Acetaminophen — reduces fever & aches. Use per label.")
    st.markdown("- Ibuprofen — reduces pain/inflammation (avoid if sensitive to NSAIDs).")
    st.markdown("- Saline nasal spray — helps congestion/dryness.")
    st.markdown("- Cough drops — soothe throat irritation.")

# Red flags & care guidance
if suggestions:
    if suggestions.get("red_flags"):
        st.warning("**Red flags** (if present, seek medical advice):\n- " + "\n- ".join(suggestions["red_flags"]))
    if suggestions.get("when_to_seek_care"):
        st.info("**When to seek care:**\n- " + "\n- ".join(suggestions["when_to_seek_care"]))
    if suggestions.get("lifestyle"):
        st.markdown("**Helpful non-drug measures:**\n- " + "\n- ".join(suggestions["lifestyle"]))

st.markdown("---")
st.markdown("## 🏷️ Pharma Offers")

# Ibuprofen Banner
with st.container(border=True):
    st.markdown("### 💊 Tylenol (Acetaminophen 500mg)")
    st.markdown("**FAST RELIEF for pain & inflammation**")
    st.markdown(":red[20% OFF – Limited Time Offer!]")
    st.image("assets/20% OFF Pain Relief Offer.png", width=250)
    st.caption("Always read the label and use as directed.")

# Tylenol Banner
with st.container(border=True):
 
    st.markdown("### 💊 Ibuprofen 200mg")
    st.markdown("**GENTLE ON STOMACH, STRONG ON PAIN**")
    st.markdown(":green[Buy 1, Get 1 Half Off!]")
    st.image("assets/Ibuprofen Buy One, Get One Free.png", width=250)         
    st.caption("For occasional pain relief. Consult a healthcare professional if symptoms persist.")


st.caption("⚠️ Educational suggestions for symptom relief only — not a diagnosis. Always read labels and consult a pharmacist/clinician, especially for children, pregnancy, chronic illness, or drug interactions.")
st.page_link("pages/1_symptoms.py", label="Return to Symptom Checker", icon="🩺")

