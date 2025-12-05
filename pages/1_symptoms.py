# pages/1_symptoms.py
import re
import os
import json
import uuid
import streamlit as st
from PIL import Image
from openai import OpenAI
import psycopg2
from psycopg2.extras import RealDictCursor

# -------------------------
# App Setup
# -------------------------
st.set_page_config(
    page_title="AI Clinic | AI Symptom Checker",
    page_icon="assets/h4u_icon2.ico",
    layout="wide"
)

col1, col2 = st.columns([1, 1])
with col1:
    image = Image.open("assets/h4u_logo.png")
    st.image(image.resize((600, 250)))
with col2:
    image = Image.open("assets/symptom.jpg")
    st.image(image.resize((600, 400)))

st.title("🩺 AI Symptom Checker")
st.markdown("Describe your symptoms and/or upload a medical image for AI-powered suggestions (not a diagnosis).")

# -------------------------
# OpenAI client init
# -------------------------
@st.cache_resource
def get_openai_client():
    key = st.secrets.get("OPENAI_API_KEY") or os.environ.get("OPENAI_API_KEY")
    if not key:
        raise RuntimeError("Missing OPENAI_API_KEY.")
    return OpenAI(api_key=key)

client = get_openai_client()

# -------------------------
# Database helpers
# -------------------------
def _db_url_from_secrets():
    url = st.secrets.get("DATABASE_URL") or os.environ.get("DATABASE_URL")
    if url:
        return url
    pg = st.secrets.get("postgres", {})
    if pg:
        return f"postgresql://{pg['user']}:{pg['password']}@{pg['host']}:{pg.get('port',5432)}/{pg['dbname']}"
    return "postgresql://ai_clinic_user:YOUR_PASSWORD@localhost:5432/ai_clinic"

@st.cache_resource
def get_db_conn():
    return psycopg2.connect(_db_url_from_secrets(), cursor_factory=RealDictCursor)

def init_db():
    ddl = """
    BEGIN;

    CREATE TABLE IF NOT EXISTS public.contacts (
      id SERIAL PRIMARY KEY,
      first_name TEXT NOT NULL,
      last_name  TEXT NOT NULL,
      email      TEXT,
      zip_code   TEXT,
      created_at TIMESTAMPTZ NOT NULL DEFAULT now()
    );

    ALTER TABLE public.contacts
      ADD COLUMN IF NOT EXISTS first_name_key TEXT GENERATED ALWAYS AS (lower(trim(first_name))) STORED,
      ADD COLUMN IF NOT EXISTS last_name_key  TEXT GENERATED ALWAYS AS (lower(trim(last_name))) STORED,
      ADD COLUMN IF NOT EXISTS email_key      TEXT GENERATED ALWAYS AS (COALESCE(lower(trim(email)), '')) STORED,
      ADD COLUMN IF NOT EXISTS zip_key        TEXT GENERATED ALWAYS AS (COALESCE(trim(zip_code), '')) STORED;

    DO $$
    BEGIN
      IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'contacts_identity_unique'
      ) THEN
        ALTER TABLE public.contacts
          ADD CONSTRAINT contacts_identity_unique
          UNIQUE (first_name_key, last_name_key, email_key, zip_key);
      END IF;
    END $$;

    CREATE TABLE IF NOT EXISTS public.symptoms (
      id SERIAL PRIMARY KEY,
      contact_id INTEGER NOT NULL REFERENCES public.contacts(id) ON DELETE CASCADE,
      run_id UUID NOT NULL,
      age INTEGER,
      sex TEXT,
      duration_days INTEGER,
      symptoms_text TEXT,
      created_at TIMESTAMPTZ NOT NULL DEFAULT now()
    );
    CREATE INDEX IF NOT EXISTS idx_symptoms_contact_run ON public.symptoms (contact_id, run_id);

    CREATE TABLE IF NOT EXISTS public.diagnoses (
      id SERIAL PRIMARY KEY,
      contact_id INTEGER NOT NULL REFERENCES public.contacts(id) ON DELETE CASCADE,
      run_id UUID NOT NULL,
      rank INTEGER NOT NULL,
      condition TEXT NOT NULL,
      explanation TEXT,
      created_at TIMESTAMPTZ NOT NULL DEFAULT now()
    );
    CREATE INDEX IF NOT EXISTS idx_diagnoses_contact_run ON public.diagnoses (contact_id, run_id);

    COMMIT;
    """
    conn = get_db_conn()
    with conn, conn.cursor() as cur:
        cur.execute(ddl)

def upsert_contact(first_name, last_name, email, zip_code):
    sql = """
    INSERT INTO public.contacts (first_name, last_name, email, zip_code)
    VALUES (%s, %s, %s, %s)
    ON CONFLICT (first_name_key, last_name_key, email_key, zip_key)
    DO UPDATE SET email = EXCLUDED.email, zip_code = EXCLUDED.zip_code
    RETURNING id;
    """
    conn = get_db_conn()
    with conn, conn.cursor() as cur:
        cur.execute(sql, (first_name, last_name, email, zip_code))
        return cur.fetchone()["id"]

def save_symptoms(contact_id, run_id, age, sex, duration_days, symptoms_text):
    sql = """
    INSERT INTO public.symptoms (contact_id, run_id, age, sex, duration_days, symptoms_text)
    VALUES (%s, %s, %s, %s, %s, %s);
    """
    conn = get_db_conn()
    with conn, conn.cursor() as cur:
        cur.execute(sql, (contact_id, str(run_id), age, sex, duration_days, symptoms_text or None))

def save_diagnoses(contact_id, run_id, diagnoses):
    sql = """
    INSERT INTO public.diagnoses (contact_id, run_id, rank, condition, explanation)
    VALUES (%s, %s, %s, %s, %s);
    """
    conn = get_db_conn()
    with conn, conn.cursor() as cur:
        for i, d in enumerate(diagnoses, start=1):
            cur.execute(sql, (contact_id, str(run_id), i, d.get("name",""), d.get("explanation","")))

init_db()

# -------------------------
# Utility helpers
# -------------------------
def _normalize_zip(raw):
    if not raw:
        return None
    m = re.match(r"^\s*(\d{5})(?:-\d{4})?\s*$", raw)
    return m.group(1) if m else None

def _valid_email(s):
    return bool(s and re.match(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$", s))

# Specialty suggestions
CONDITION_TO_SPECIALTIES = [
    (["heart", "chest pain", "arrhythmia", "angina"], ["Cardiology", "Emergency Medicine", "Internal Medicine"]),
    (["shortness of breath", "wheezing", "pneumonia", "bronchitis"], ["Pulmonary Disease", "Internal Medicine"]),
    (["covid", "influenza", "flu", "infection", "malaria"], ["Infectious Disease", "Internal Medicine"]),
    (["migraine", "headache", "seizure", "numbness"], ["Neurology", "Emergency Medicine"]),
    (["anxiety", "depression", "panic"], ["Psychiatry", "Psychology"]),
    (["rash", "acne", "eczema", "psoriasis"], ["Dermatology"]),
    (["stomach", "abdominal pain", "gastro", "ulcer", "diarrhea"], ["Gastroenterology", "Internal Medicine"]),
    (["uti", "urinary", "kidney stone"], ["Urology"]),
]

def suggest_specialties(summary):
    text = (summary or "").lower()
    suggestions = []
    for keywords, specs in CONDITION_TO_SPECIALTIES:
        if any(k in text for k in keywords):
            suggestions += [s for s in specs if s not in suggestions]
    for gen in ["Family Medicine", "Internal Medicine", "General Practice"]:
        if gen not in suggestions:
            suggestions.append(gen)
    return suggestions

# Emergency detection (critical situations only)
EMERGENCY_KEYWORDS = {
    "heart attack", "myocardial infarction",
    "stroke", "cva", "brain hemorrhage",
    "pulmonary embolism", "aortic dissection",
    "sepsis", "anaphylaxis", "anaphylactic shock"
}

def _is_emergency(summary, diagnoses):
    text_blocks = [(summary or "").lower()] + [
        (d.get("name", "") + " " + d.get("explanation", "")).lower() for d in (diagnoses or [])
    ]
    matched = [k for k in EMERGENCY_KEYWORDS if any(k in t for t in text_blocks)]
    return (bool(matched), matched)

# OpenAI call
def get_conditions_from_gpt(symptoms=None, age=None, sex=None, duration=None):
    patient_info = ""
    if symptoms: patient_info += f"Symptoms: {', '.join(symptoms)}. "
    if age is not None: patient_info += f"Age: {age}. "
    if sex: patient_info += f"Sex: {sex}. "
    if duration: patient_info += f"Duration: {duration}. "
    if not patient_info:
        patient_info = "No symptoms provided. Please analyze only the uploaded image."

    messages = [
        {"role": "system", "content":
         "You are a careful medical triage assistant. Return JSON only (no prose) with keys: "
         "`summary_markdown` (a concise Markdown list of up to 5 likely conditions + short explanations + a brief disclaimer), "
         "and `diagnoses` (an array of objects with `name` and `explanation`, max 5)."},
        {"role": "user", "content": f"{patient_info} Provide likely conditions."}
    ]
    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=messages,
        max_tokens=700,
        temperature=0.3,
        response_format={"type": "json_object"}
    )
    try:
        return json.loads(resp.choices[0].message.content)
    except Exception:
        return {"summary_markdown": "", "diagnoses": []}

# -------------------------
# Inputs
# -------------------------
zip_raw = st.text_input("ZIP code (US)", placeholder="e.g., 33351")
zip_norm = _normalize_zip(zip_raw)
if zip_raw and not zip_norm:
    st.warning("Please enter a valid US ZIP (e.g., 33351 or 33351-1234).")

first_name = st.text_input("First Name", "").strip()
last_name  = st.text_input("Last Name", "").strip()
email      = st.text_input("Email (optional)", "").strip()
if email and not _valid_email(email):
    st.warning("Please enter a valid email.")

symptoms_text = st.text_area("Describe your symptoms", placeholder="e.g., fever, cough, chest pain")
age_input    = st.text_input("Age (years)", placeholder="e.g., 22")
sex_input    = st.selectbox("Sex", ["", "Male", "Female"])
days_input   = st.text_input("Duration (days)", placeholder="e.g., 3")

age_val = int(age_input) if age_input.isdigit() else None
dur_val = int(days_input) if days_input.isdigit() else None
duration_input = f"{dur_val} days" if dur_val else ""

# Share INPUTS immediately so other pages can read them if needed
st.session_state["first_name"] = first_name
st.session_state["last_name"]  = last_name
st.session_state["zip_code"]   = zip_norm  # may be None if invalid/empty
st.session_state["email"]      = email

# -------------------------
# Analyze
# -------------------------
if st.button("Analyze"):
    if not (symptoms_text or age_val or sex_input or dur_val):
        st.error("Please enter at least one detail.")
        st.stop()

    symptoms_list = [s.strip() for s in symptoms_text.split(",") if s.strip()]
    result = get_conditions_from_gpt(symptoms_list, age_val, sex_input or None, duration_input)
    summary   = result.get("summary_markdown", "")
    diagnoses = result.get("diagnoses", [])[:5]

    # --- Emergency alert (critical only) ---
    is_emergency, matched = _is_emergency(summary, diagnoses)
    if is_emergency:
        msg = "; ".join(matched).title()
        st.markdown("""
            <style>
            .er-alert {
                animation: pulse 1.2s infinite;
                border: 3px solid #ff0000;
                border-radius: 10px;
                padding: 14px 16px;
                background: #ffe6e6;
                font-weight: 700;
                color: #a10000;
                margin-bottom: 12px;
            }
            @keyframes pulse {
                0% { box-shadow: 0 0 0 0 rgba(255,0,0,0.7); }
                70% { box-shadow: 0 0 0 12px rgba(255,0,0,0); }
                100% { box-shadow: 0 0 0 0 rgba(255,0,0,0); }
            }
            </style>
        """, unsafe_allow_html=True)
        st.markdown(
            f"""
            <div class="er-alert">
                ⚠️ POTENTIAL EMERGENCY: {msg}<br/>
                If you are experiencing severe symptoms (e.g., crushing chest pain, severe shortness of breath, confusion, fainting),
                <u>call 911</u> or go to the nearest emergency department immediately.
            </div>
            """,
            unsafe_allow_html=True
        )

    # --- Summary ---
    st.markdown("### AI Summary")
    st.markdown(summary or "_No summary available._")

    # --- Top 5 Diagnoses (optional visible list) ---
    # st.markdown("### Top 5 Possible Diagnoses")
    # if diagnoses:
    #     for i, d in enumerate(diagnoses, start=1):
    #         name = d.get("name", "").strip() or "(Unknown)"
    #         expl = d.get("explanation", "").strip()
    #         st.markdown(f"**{i}. {name}** — {expl}")
    # else:
    #     st.write("_No diagnoses returned by the model._")

    # --- Suggested Specialists ---
    suggested = suggest_specialties(summary)
    st.markdown("### Suggested Specialist(s)")
    st.write(", ".join(suggested[:2]) + ("…" if len(suggested) > 2 else ""))

    # --- Build a robust symptoms summary string for downstream pages ---
    symptoms_list = [s.strip() for s in (symptoms_text or "").split(",") if s.strip()]

    parts = []
    if symptoms_list:
       parts.append(", ".join(symptoms_list))
    if age_val is not None:
       parts.append(f"Age {age_val}")
    if sex_input:
       parts.append(sex_input)
    if dur_val is not None:
       parts.append(f"{dur_val} days of symptoms")

    # This line is now safe even if image upload isn't implemented
    # (no reference to uploaded_image)
    constructed_symptoms = ", ".join(parts).strip() or "No free-text symptoms provided; AI summary only."

    # --- Save to session for other pages ---
    st.session_state["symptoms_input"] = constructed_symptoms
    st.session_state["condition_summary"] = summary
    st.session_state["diagnoses"] = diagnoses
    st.session_state["suggested_specialties"] = suggested
    st.session_state["primary_specialty"] = suggested[0] if suggested else None

    # --- Save Results ---
    try:
        contact_id = upsert_contact(first_name or "(Unknown)", last_name or "(Unknown)", email or None, zip_norm or None)
        run_id = uuid.uuid4()
        save_symptoms(contact_id, run_id, age_val, sex_input or None, dur_val, symptoms_text)
        if diagnoses:
            save_diagnoses(contact_id, run_id, diagnoses)

        # Let other pages know which run/contact we just saved
        st.session_state["last_run_id"] = str(run_id)
        st.session_state["contact_id"]  = contact_id

        # st.success("Saved to database.")
    except Exception as e:
        st.error(f"Database error: {e}")

    st.info("Next steps:")
    st.page_link("pages/2_find_a_doctor.py", label="Find a Doctor", icon="👨‍⚕️")
    st.page_link("pages/3_otc_medication.py", label="OTC Medication Suggestions", icon="💊")
    st.page_link("pages/5_pharmacies_nearby.py", label="Find Nearby Pharmacies", icon="🏪")

st.info("Disclaimer: This tool does not provide medical diagnoses. Always consult a qualified clinician.")
