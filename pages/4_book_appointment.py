# pages/4_book_appointment.py
import streamlit as st
from datetime import date, time
from PIL import Image

st.set_page_config(
    page_title="AI Clinic | Book An Appointment",
    page_icon="assets/h4u_icon2.ico",  # point to your PNG
    layout="wide"
)

col1, col2 = st.columns([1, 1])  # two equal-width columns
with col1:
    #st.image("assets/appoint.jpg", use_container_width=True)
    image = Image.open("assets/h4u_logo.png") 
    resized_image = image.resize((600, 250)) 
    st.image(resized_image) 
with col2:
    #st.image("assets/h4u_logo.png", use_container_width=True)
    image = Image.open("assets/appoint2.jpg") 
    resized_image = image.resize((600,350)) # Width x Height in pixels
    st.image(resized_image)



#st.title("🧪 Medical Labs Near You (NPI Registry — No API Key)")
#st.image("assets/ai_doctor_hero5.jpg", width=600)
st.title("📅 Book an Appointment")

# Pull data saved by prior pages
#with st.expander("Session debug (temporary)"):
 #   st.write({
 #       "symptoms_input": st.session_state.get("symptoms_input"),
 #       "condition_summary": st.session_state.get("condition_summary"),
 #        "primary_specialty": st.session_state.get("primary_specialty"),
 #       "selected_doctor": st.session_state.get("selected_doctor"),
 #   })

selected_doctor = st.session_state.get("selected_doctor")
symptoms_input = st.session_state.get("symptoms_input")
condition_summary = st.session_state.get("condition_summary")
primary_specialty = st.session_state.get("primary_specialty")


# Validate required context
if not selected_doctor:
    st.warning("⚠️ Please return to 'Find a Doctor' and select a provider first.")
    st.page_link("pages/2_find_a_doctor.py", label="Go to Find a Doctor", icon="👨‍⚕️")
    st.stop()

if not condition_summary or not symptoms_input:
    st.warning("⚠️ Please complete the Symptom Checker before booking.")
    st.page_link("pages/1_symptoms.py", label="Go to Symptom Checker", icon="🩺")
    st.stop()

# Normalize keys from NPI search (or your legacy local DB)
doc_name = selected_doctor.get("name", "Selected Provider")
doc_taxonomy = selected_doctor.get("taxonomy") or selected_doctor.get("specialty") or "Provider"
doc_phone = selected_doctor.get("phone", "Not provided")
doc_address = selected_doctor.get("address", "")
doc_npi = selected_doctor.get("npi")
doc_zip = selected_doctor.get("zip")
doc_distance = selected_doctor.get("distance_mi")

# Header details
st.markdown(f"#### Booking with: 🩺 {doc_name} ({doc_taxonomy})")
meta_bits = []
if doc_npi: meta_bits.append(f"NPI: {doc_npi}")
if doc_zip: meta_bits.append(f"ZIP: {doc_zip}")
if isinstance(doc_distance, (int, float)): meta_bits.append(f"{doc_distance} mi away")
if meta_bits:
    st.caption(" • ".join(meta_bits))

st.write(f"**Clinic Phone:** {doc_phone}")
if doc_address:
    st.write(f"**Address:** {doc_address}")

# Context from previous steps
st.markdown("### Your Symptoms:")
st.write(symptoms_input)

st.markdown("### Possible Differentials:")
st.write(condition_summary)

default_reason = (
    f"Symptoms: {symptoms_input}\n"
    f"Possible differentials: {condition_summary}\n"
    f"Additional reason: "
)

# Booking form
with st.form("appointment_form"):
    col1, col2 = st.columns(2)
    with col1:
        first_name = st.text_input("First Name")
        phone_number = st.text_input("Phone Number")
        appointment_date = st.date_input("Select appointment date:", value=date.today())
    with col2:
        last_name = st.text_input("Last Name")
        insurance_name = st.text_input("Insurance Name")
        appointment_time = st.time_input("Select appointment time:", value=time(9, 0))

    reason = st.text_area("Reason for visit (you can add details):", value=default_reason, height=140)
    submit_appt = st.form_submit_button("Book Appointment")

# Submit handling
if submit_appt:
    if not (first_name and last_name and phone_number and insurance_name):
        st.error("Please complete all required fields.")
    else:
        st.success(
            f"✅ Appointment booked with {doc_name} on "
            f"{appointment_date.strftime('%A, %B %d, %Y')} at {appointment_time.strftime('%I:%M %p')}."
        )
        st.info(f"""
**Patient:** {first_name} {last_name}  
**Phone:** {phone_number}  
**Insurance:** {insurance_name}  

**Provider:** {doc_name} ({doc_taxonomy}){f" — NPI {doc_npi}" if doc_npi else ""}  
**Clinic Phone:** {doc_phone}  
**Address:** {doc_address or "Not provided"}  

**Reason:**  
{reason}
        """)
        st.info("The clinic or the doctor's office will contact you to confirm your appointment.")

st.markdown("---")
st.page_link("pages/2_find_a_doctor.py", label="Back to Find a Doctor", icon="👨‍⚕️")
st.page_link("pages/1_symptoms.py", label="Back to Symptom Checker", icon="🩺")
st.page_link("pages/3_otc_medication.py", label="See OTC Medications", icon="💊")
st.page_link("pages/5_pharmacies_nearby.py", label="Find Nearby Pharmacies", icon="🏪")
st.caption("© 2025 AI Doctor | This app is not a substitute for professional medical advice.")


