# pages/2_find_a_doctor.py
import math
import re
import requests
import streamlit as st
import pgeocode
from PIL import Image

# -------------------------
# Page chrome
# -------------------------
st.set_page_config(
    page_title="AI Clinic | Find a Doctor",
    page_icon="assets/h4u_icon2.ico",
    layout="wide"
)

col1, col2 = st.columns([1, 1])
with col1:
    image = Image.open("assets/h4u_logo.png")
    st.image(image.resize((600, 250)))
with col2:
    image = Image.open("assets/ai_doctor_hero4.jpg")
    st.image(image.resize((600, 350)))

# -------------------------
# Helpers
# -------------------------
def _normalize_zip(raw: str | None) -> str | None:
    if not raw:
        return None
    m = re.match(r"^\s*(\d{5})(?:-\d{4})?\s*$", raw)
    return m.group(1) if m else None

@st.cache_resource
def geocoder():
    return pgeocode.Nominatim("us")

@st.cache_data(ttl=900, show_spinner=False)
def geocode_zip(z: str):
    rec = geocoder().query_postal_code(z)
    try:
        lat, lon = float(rec.latitude), float(rec.longitude)
        if math.isnan(lat) or math.isnan(lon):
            return None
        return (lat, lon, (rec.state_code or "").strip())
    except Exception:
        return None

def miles(lat1, lon1, lat2, lon2):
    r = 3958.8
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lon2 - lon1)
    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlmb/2)**2
    return 2 * r * math.asin(math.sqrt(a))

# Query params: Streamlit 1.32+ has st.query_params; older versions: experimental fallback
def _get_query_params():
    try:
        return st.query_params  # type: ignore[attr-defined]
    except Exception:
        return st.experimental_get_query_params()

# -------------------------
# Inputs from session OR URL OR manual fields
# -------------------------
qp = _get_query_params()
condition_summary = st.session_state.get("condition_summary", "")
primary_spec = st.session_state.get("primary_specialty", "")
zip_code = st.session_state.get("zip_code", "")
first_name = st.session_state.get("first_name", "")

# Fallbacks from URL query params (e.g. /pages/2_find_a_doctor?zip=33351&specialty=Cardiology)
if not zip_code:
    zip_code = _normalize_zip((qp.get("zip") or [""])[0])

if not primary_spec:
    primary_spec = (qp.get("specialty") or [""])[0].strip()

# Soft header (works even if names are missing)
st.title(f"👨‍⚕️ Find a Doctor near {first_name or 'you'} {f'in {zip_code}' if zip_code else ''}")

# If missing, show manual fields so the page is still usable
st.markdown("#### Search Settings")

inp_col1, inp_col2, inp_col3 = st.columns([1, 1, 1])

with inp_col1:
    zip_input = st.text_input(
        "ZIP code",
        value=zip_code or "",
        placeholder="e.g., 33351",
        help="Enter a US 5-digit ZIP code."
    )
    zip_code = _normalize_zip(zip_input) or ""

with inp_col2:
    # Prefill specialty from primary specialty if available
    if "specialty_input" not in st.session_state:
        st.session_state["specialty_input"] = (primary_spec or "")
    elif primary_spec and not st.session_state["specialty_input"]:
        st.session_state["specialty_input"] = primary_spec

    specialty_in = st.text_input(
        "Specialty (taxonomy description)",
        value=st.session_state["specialty_input"],
        key="specialty_input",
        placeholder="e.g., Cardiology, Gastroenterology, Orthopaedic Surgery"
    )

with inp_col3:
    radius_mi = st.slider("Radius (miles)", 5, 100, 25, 5, key="radius_input")

if primary_spec:
    st.caption(f"Prefilled from symptoms: **{primary_spec}** (you can change it)")

# -------------------------
# NPI Registry search
# -------------------------
NPI_API = "https://npiregistry.cms.hhs.gov/api/"
NPI_VERSION = "2.1"

@st.cache_data(ttl=600, show_spinner=False)
def npi_search_state(taxonomy_desc: str, state: str, enum_type: str, limit: int = 1200):
    """Search NPI Registry by state + taxonomy; enum_type: 'NPI-1' or 'NPI-2'."""
    params = {
        "version": NPI_VERSION,
        "taxonomy_description": taxonomy_desc,
        "state": state,
        "country_code": "US",
        "enumeration_type": enum_type,
        "limit": min(max(limit, 1), 1200),
    }
    r = requests.get(NPI_API, params=params, timeout=25)
    r.raise_for_status()
    return r.json()

def search_radius_by_state_then_filter(user_zip: str, radius: int, specialty_text: str):
    """Fetch state-wide, compute distance to user's ZIP, and filter to radius."""
    geo = geocode_zip(user_zip)
    if not geo:
        return [], {"reason": "Could not geolocate ZIP."}
    u_lat, u_lon, state = geo
    if not state:
        return [], {"reason": "Could not infer state from ZIP."}

    all_hits = []
    # Prefer individuals (NPI-1), then organizations (NPI-2)
    for enum in ["NPI-1", "NPI-2"]:
        data = npi_search_state(specialty_text, state, enum_type=enum, limit=1200)
        results = data.get("results") or []
        if not results:
            continue

        rows = []
        for rec in results:
            basic = rec.get("basic", {}) or {}
            addr_list = rec.get("addresses", []) or []
            loc = next((a for a in addr_list if a.get("address_purpose","").lower() == "location"), None) \
                  or (addr_list[0] if addr_list else {})
            zip5 = (loc.get("postal_code","") or "")[:5]

            # Distance calc (zip centroid to zip centroid)
            latlon = geocode_zip(zip5) if zip5 else None
            dist = miles(u_lat, u_lon, latlon[0], latlon[1]) if latlon else None

            phone = (loc.get("telephone_number") or
                     next((a.get("telephone_number") for a in addr_list if a.get("telephone_number")), None))

            primary_tax = next((t for t in (rec.get("taxonomies") or []) if t.get("primary")), None)
            if not primary_tax and rec.get("taxonomies"):
                primary_tax = rec["taxonomies"][0]

            display_name = (f"{basic.get('first_name','')} {basic.get('last_name','')}".strip()
                            or basic.get("organization_name","(Provider)"))

            rows.append({
                "name": display_name,
                "npi": rec.get("number"),
                "taxonomy": (primary_tax or {}).get("desc") or (primary_tax or {}).get("code") or "",
                "phone": phone or "",
                "address": f"{loc.get('address_1','')} {loc.get('address_2','')}, "
                           f"{loc.get('city','')}, {loc.get('state','')} {zip5}".strip(),
                "zip": zip5,
                "distance_mi": round(dist, 1) if dist is not None else None,
            })
        all_hits.extend(rows)
        if all_hits:
            break

    in_radius = [p for p in all_hits if p["distance_mi"] is not None and p["distance_mi"] <= radius]
    in_radius.sort(key=lambda x: (x["distance_mi"] if x["distance_mi"] is not None else 1e9, x["name"]))
    return (in_radius or all_hits), {"state": state, "total_raw": len(all_hits)}

# -------------------------
# Search button
# -------------------------
go = st.button("🔍 Search", key="search_btn")

def _store_results(providers, meta, zip_code, radius, specialty):
    st.session_state["providers"] = providers
    st.session_state["providers_meta"] = meta
    st.session_state["search_zip"] = zip_code
    st.session_state["search_radius"] = radius
    st.session_state["search_specialty"] = specialty
    st.session_state["provider_radio"] = 0
    st.session_state.pop("selected_doctor", None)

# Guard: need both zip + specialty to search
if go:
    if not zip_code:
        st.warning("Please enter a valid 5-digit ZIP.")
        st.stop()
    if not specialty_in.strip():
        st.warning("Please enter a specialty.")
        st.stop()

    st.caption(f"Searching NPI for **{specialty_in.strip()}** within **{radius_mi} mi** of **{zip_code}**…")
    with st.spinner("Searching providers…"):
        try:
            providers, meta = search_radius_by_state_then_filter(zip_code, radius_mi, specialty_in.strip())
        except requests.HTTPError as e:
            st.error(f"NPI Registry error: {e}")
            st.stop()
        except requests.RequestException as e:
            st.error(f"Network error querying NPI Registry: {e}")
            st.stop()

    if not providers:
        st.info("No matches found. Try another specialty or a larger radius.")
        st.session_state.pop("providers", None)
        st.session_state.pop("providers_meta", None)
        st.stop()
    _store_results(providers, meta, zip_code, radius_mi, specialty_in.strip())

# If still no stored results (first visit and no search yet), show a gentle nudge but don't block the page
if "providers" not in st.session_state:
    st.info("Enter your ZIP and specialty, then click **Search** to find providers.")
    st.stop()

# -------------------------
# Results + selection
# -------------------------
providers = st.session_state["providers"]
meta = st.session_state.get("providers_meta", {})
st.caption(f"Found {len(providers)} provider(s) in {meta.get('state','')}.")

labels = ["-- Please select a provider --"] + [
    f"{p['name']} — {p['taxonomy']} — {p.get('phone','No phone')} — {p.get('zip','')}"
    + (f" — {p['distance_mi']} mi" if p.get('distance_mi') is not None else "")
    for p in providers
]

idx = st.radio(
    "Select a provider to proceed:",
    options=range(len(labels)),
    format_func=lambda i: labels[i],
    index=st.session_state.get("provider_radio", 0),
    key="provider_radio"
)

if idx == 0:
    st.session_state.pop("selected_doctor", None)
    st.info("Please select a provider above to continue.")
else:
    selected = providers[idx - 1]
    st.session_state["selected_doctor"] = selected

    st.success(
        f"**Selected:** {selected['name']}  \n"
        f"{selected['taxonomy']} • NPI {selected.get('npi','')}  \n"
        f"{selected['address']}  \n"
        f"{selected.get('phone','No phone on file')}"
        + (f"  \n~{selected['distance_mi']} miles away" if selected.get('distance_mi') is not None else "")
    )

    if st.button(f"📅 Make appointment with {selected['name']}", type="primary", key="make_appt_btn"):
        st.switch_page("pages/4_book_appointment.py")

st.markdown("---")
st.page_link("pages/3_otc_medication.py", label="See OTC Medications", icon="💊")
st.page_link("pages/1_symptoms.py", label="Back to Symptom Checker", icon="🩺")
st.page_link("pages/5_pharmacies_nearby.py", label="Find Nearby Pharmacies", icon="🏪")
