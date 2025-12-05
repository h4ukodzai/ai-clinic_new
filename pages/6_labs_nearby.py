# pages/6_labs_nearby.py
import os
import math
import re
import time
import requests
import streamlit as st
import pgeocode
import urllib.parse
from PIL import Image

st.set_page_config(
    page_title="AI Clinic | Labs Nearby",
    page_icon="assets/h4u_icon2.ico",  # point to your PNG
    layout="wide"
)


# ---------- Header (two images) ----------
col1, col2 = st.columns([1, 1])
with col1:
    image = Image.open("assets/h4u_logo.png")
    st.image(image.resize((600, 250)))
with col2:
    image = Image.open("assets/ai_doctor_hero5.jpg")
    st.image(image.resize((600, 350)))

st.title("🧪 Medical Labs Near You")
#This is a Test!

# ---------- Helpers ----------
def link_btn(label: str, url: str, *, fill_width: bool = True):
    """Prefer Streamlit link_button; fallback to a styled <a> for older versions."""
    try:
        return st.link_button(label, url, use_container_width=fill_width)
    except Exception:
        style = (
            "display:inline-block;padding:0.6rem 1rem;border-radius:0.5rem;"
            "text-decoration:none;background:#f0f2f6;color:#111;font-weight:600;"
            "border:1px solid #d0d3da;width:100%;text-align:center;"
        ) if fill_width else (
            "display:inline-block;padding:0.6rem 1rem;border-radius:0.5rem;"
            "text-decoration:none;background:#f0f2f6;color:#111;font-weight:600;"
            "border:1px solid #d0d3da;"
        )
        st.markdown(
            f'<a href="{url}" target="_blank" rel="noopener noreferrer" style="{style}">{label}</a>',
            unsafe_allow_html=True,
        )

def _zip5(z: str | None) -> str | None:
    if not z:
        return None
    m = re.match(r"^\s*(\d{5})(?:-\d{4})?\s*$", z)
    return m.group(1) if m else None

def haversine_miles(lat1, lon1, lat2, lon2):
    r = 3958.8
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lon2 - lon1)
    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlmb/2)**2
    return 2 * r * math.asin(math.sqrt(a))

# ---------- Session inputs from Symptom Checker ----------
zip_code = st.session_state.get("zip_code", "")
first_name = st.session_state.get("first_name", "")
zip5_user = _zip5(zip_code)

if not zip5_user:
    st.warning("⚠️ Please enter your ZIP on the Symptom Checker first.")
    st.page_link("pages/1_symptoms.py", label="Go to Symptom Checker", icon="🩺")
    st.stop()

st.caption(f"Searching **medical labs near ZIP {zip5_user}** for {first_name or 'you'} using Google Maps.")

# ---------- Geocoding (ZIP → lat/lon) ----------
@st.cache_resource
def geocoder():
    return pgeocode.Nominatim("us")

@st.cache_data(ttl=900, show_spinner=False)
def geocode_zip(z5: str):
    rec = geocoder().query_postal_code(z5)
    try:
        lat, lon = float(rec.latitude), float(rec.longitude)
        if math.isnan(lat) or math.isnan(lon):
            return None
        return lat, lon
    except Exception:
        return None

geo = geocode_zip(zip5_user)
if not geo:
    st.error("Could not geolocate your ZIP. Please double-check it.")
    st.stop()

user_lat, user_lon = geo

# ---------- Google Places (Nearby + Details) ----------
GOOGLE_API_KEY = st.secrets.get("GOOGLE_MAPS_API_KEY") or os.environ.get("GOOGLE_MAPS_API_KEY")
if not GOOGLE_API_KEY:
    st.error("Missing Google Maps API key. Set GOOGLE_MAPS_API_KEY in Streamlit secrets or env.")
    st.stop()

PLACES_NEARBY_URL = "https://maps.googleapis.com/maps/api/place/nearbysearch/json"
PLACE_DETAILS_URL = "https://maps.googleapis.com/maps/api/place/details/json"

@st.cache_data(ttl=600, show_spinner=False)
def places_nearby_labs(lat: float, lon: float, radius_m: int, max_pages: int = 3):
    """
    Query Google Places Nearby for labs using type=health + keyword=laboratory.
    Returns up to ~60 results (3 pages).
    """
    params = {
        "key": GOOGLE_API_KEY,
        "location": f"{lat},{lon}",
        "radius": radius_m,
        "type": "health",            # closest type bucket for labs
        "keyword": "laboratory",     # keyword to target diagnostic/medical labs
    }
    results = []
    page = 0
    token = None
    while page < max_pages:
        if token:
            params["pagetoken"] = token
            time.sleep(2)  # required delay before using next_page_token
        resp = requests.get(PLACES_NEARBY_URL, params=params, timeout=30).json()
        results.extend(resp.get("results", []))
        token = resp.get("next_page_token")
        page += 1
        if not token:
            break
    return results

@st.cache_data(ttl=1200, show_spinner=False)
def place_details(place_id: str):
    params = {
        "key": GOOGLE_API_KEY,
        "place_id": place_id,
        "fields": ",".join([
            "name",
            "formatted_address",
            "formatted_phone_number",
            "geometry/location",
            "opening_hours",
            "current_opening_hours",
            "website",
            "url"
        ]),
    }
    return requests.get(PLACE_DETAILS_URL, params=params, timeout=30).json().get("result", {})

def is_24_hours(opening: dict | None) -> bool:
    """
    Heuristic for 24/7:
    - Any weekday_text line with 'Open 24 hours'
    - Any period spans 00:00–24:00 (or close missing)
    """
    if not opening:
        return False
    texts = opening.get("weekday_text") or []
    for t in texts:
        if "open 24 hours" in t.lower():
            return True
    periods = opening.get("periods") or []
    for p in periods:
        o = (p.get("open") or {})
        c = (p.get("close") or {})
        if o.get("time") == "0000" and (c.get("time") in ("0000", "2400") or not c):
            return True
    # Also consider nested 'current_opening_hours'
    curr = opening.get("current_opening_hours") if isinstance(opening, dict) and "current_opening_hours" in opening else None
    if curr and is_24_hours(curr):
        return True
    return False

def normalize_google_place(p: dict, lat0: float, lon0: float):
    pid = p.get("place_id")
    name = p.get("name") or "(Lab)"
    loc = (p.get("geometry") or {}).get("location") or {}
    plat, plon = loc.get("lat"), loc.get("lng")
    dist = None
    if plat is not None and plon is not None:
        dist = round(haversine_miles(float(plat), float(plon), lat0, lon0), 1)
    addr = p.get("vicinity") or p.get("formatted_address") or ""
    open_now = (p.get("opening_hours") or {}).get("open_now")
    map_url = f"https://www.google.com/maps/place/?q=place_id:{pid}" if pid else \
              f"https://www.google.com/maps/search/?api=1&query={urllib.parse.quote_plus(name)}"

    return {
        "place_id": pid,
        "name": name,
        "address": addr,
        "distance_mi": dist,
        "open_now": open_now,
        "maps_url": map_url,
    }

# ---------- Controls ----------
c1, c2 = st.columns([1, 1])
with c1:
    radius_miles = st.slider("Search radius (miles)", 1, 25, 10, 1, help="How far around your ZIP center to look.")
with c2:
    how_many = st.selectbox("Show how many (nearest)", [5, 10, 15, 20, 30, 50], index=1)

go = st.button("🔎 Search Labs")
if not go:
    st.stop()

radius_m = int(radius_miles * 1609.344)

with st.spinner("Querying Google Places for labs…"):
    raw = places_nearby_labs(user_lat, user_lon, radius_m)
    if not raw:
        st.info("No labs found from Google Places near your ZIP. Try increasing the radius.")
        st.stop()

# Normalize and sort
base_items = [normalize_google_place(el, user_lat, user_lon) for el in raw]
base_items = [x for x in base_items if x.get("distance_mi") is not None]
base_items.sort(key=lambda x: (x["distance_mi"], x["name"]))

# Fetch Details for items we might display (overfetch so each tab has enough)
detail_take = min(len(base_items), max(how_many * 2, how_many + 10))
picked = base_items[:detail_take]
details_by_id = {}
for x in picked:
    if x["place_id"]:
        try:
            details_by_id[x["place_id"]] = place_details(x["place_id"])
        except Exception:
            details_by_id[x["place_id"]] = {}

def enrich(item):
    d = details_by_id.get(item["place_id"], {})
    addr = d.get("formatted_address") or item["address"]
    phone = d.get("formatted_phone_number") or ""
    website = d.get("website") or ""
    open_struct = d.get("current_opening_hours") or d.get("opening_hours") or {}
    open_texts = open_struct.get("weekday_text") or []
    open_now = open_struct.get("open_now", item.get("open_now"))
    twenty_four = is_24_hours({"weekday_text": open_texts, "periods": open_struct.get("periods", [])})
    maps_url = d.get("url") or item["maps_url"]
    return {
        **item,
        "address": addr,
        "phone_display": phone,
        "phone_tel": ("tel:" + re.sub(r"[^\d+]", "", phone)) if phone else "",
        "website": website,
        "open_now": open_now,
        "weekday_text": open_texts,
        "is_24h": twenty_four,
        "maps_url": maps_url,
    }

enriched = [enrich(it) for it in picked]

# ---------- Tabs: All / Open now / Open 24 hours ----------
tab_all, tab_open, tab_24 = st.tabs(["All", "Open now", "Open 24 hours"])

def render_cards(items, limit):
    items = items[:limit]
    st.caption(f"Showing {len(items)} nearest result(s) within ~{radius_miles} miles of ZIP {zip5_user}.")
    for i, p in enumerate(items, start=1):
        with st.container(border=True):
            st.markdown(f"### {i}. {p['name']}")
            bits = []
            if p["distance_mi"] is not None:
                bits.append(f"~{p['distance_mi']} mi")
            if p.get("open_now") is True:
                bits.append("Open now")
            elif p.get("open_now") is False:
                bits.append("Closed now")
            if p.get("is_24h"):
                bits.append("Open 24 hours")
            st.caption(" • ".join(bits) if bits else "Medical laboratory")

            st.write(p["address"] or "(No address)")
            if p.get("weekday_text"):
                with st.expander("Hours"):
                    for line in p["weekday_text"]:
                        st.write(line)

            colA, colB, colC = st.columns(3)
            with colA:
                link_btn("🗺️ Open in Google Maps", p["maps_url"], fill_width=True)
            with colB:
                if p.get("phone_tel"):
                    link_btn(f"📞 Call {p['phone_display']}", p["phone_tel"], fill_width=True)
                else:
                    st.button("📞 Call (phone unavailable)", disabled=True, use_container_width=True, key=f"no_call_{i}")
            with colC:
                if p.get("website"):
                    link_btn("🌐 Website", p["website"], fill_width=True)

with tab_all:
    render_cards(enriched, how_many)

with tab_open:
    open_now_items = [p for p in enriched if p.get("open_now") is True]
    if not open_now_items:
        st.info("No labs currently open found in this radius.")
    else:
        render_cards(open_now_items, how_many)

with tab_24:
    open_24_items = [p for p in enriched if p.get("is_24h")]
    if not open_24_items:
        st.info("No 'Open 24 hours' labs found from Google data here. Try a larger radius.")
    else:
        render_cards(open_24_items, how_many)

st.markdown("---")
st.page_link("pages/1_symptoms.py", label="Back to Symptom Checker", icon="🩺")
st.page_link("pages/5_pharmacies_nearby.py", label="Find Pharmacies", icon="🏪")
st.page_link("pages/2_find_a_doctor.py", label="Find a Doctor", icon="👨‍⚕️")
