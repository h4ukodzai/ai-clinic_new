# -*- coding: utf-8 -*-
"""
About Us — AI Clinic
Place this file in: pages/08_About_Us.py
Requires: streamlit, pillow
"""

import os
import streamlit as st
from PIL import Image

# ---------------------------------------------------------
# Page config
# ---------------------------------------------------------
st.set_page_config(
    page_title="AI Clinic | About Us",
    page_icon="assets/h4u_icon2.ico",
    layout="wide"
)

# ---------------------------------------------------------
# Custom CSS — readable on mobile and dark mode
# ---------------------------------------------------------
CUSTOM_CSS = """
<style>
  /* Force high-contrast base text color (handles dark/light mode) */
  html, body, [data-testid="stAppViewContainer"] {
      color: #111827 !important;
      background: transparent;
  }

  /* Container width */
  .main > div { max-width: 900px; margin-left: auto; margin-right: auto; }

  /* Card styles */
  .card {
      border: 1px solid #e5e7eb;
      border-radius: 10px;
      padding: 20px;
      background: #ffffff;
      color: #111827 !important;
      font-size: 14px;
      line-height: 1.7;
  }

  .muted {
      color: #6b7280 !important;
      font-size: 0.9rem;
      margin-top: 2rem;
      text-align: center;
  }

  h1, h2, h3 {
      line-height: 1.2;
      margin-top: 0.8rem;
      margin-bottom: 0.6rem;
      text-align: center;
      color: #111827 !important;
  }

  p { margin: 0.5rem 0 1rem 0; }

  /* Ensure responsive images */
  img { max-width: 100%; height: auto; }

  /* Mobile adjustments */
  @media (max-width: 640px) {
    .card { font-size: 16px; line-height: 1.75; }
  }

  /* Dark theme adjustments */
  [data-theme="dark"] .card {
      background: #0b0b0c;
      color: #f9fafb !important;
      border-color: #1f2937;
  }
  [data-theme="dark"] h1,
  [data-theme="dark"] h2,
  [data-theme="dark"] h3,
  [data-theme="dark"] .muted {
      color: #e5e7eb !important;
  }
</style>
"""
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

# ---------------------------------------------------------
# Logo / Hero Banner
# ---------------------------------------------------------
def _resolve_logo_path() -> str | None:
    candidates = [
        "assets/h4u_logo.png",
        "ai-clinic/assets/h4u_logo.png",
        os.path.join(os.path.dirname(__file__), "assets/h4u_logo.png"),
        os.path.join(os.path.dirname(__file__), "../assets/h4u_logo.png"),
    ]
    for p in candidates:
        if os.path.exists(p):
            return p
    return None

logo_path = _resolve_logo_path()
if logo_path:
    try:
        img = Image.open(logo_path)
        st.image(img.resize((750, 300)))
    except Exception as e:
        st.warning(f"Logo failed to load ({e})")
else:
    st.info("Logo not found at assets/h4u_logo.png (optional).")

# ---------------------------------------------------------
# About Us Content
# ---------------------------------------------------------
st.title("About Us")

st.markdown(
    """
    <div class="card">
      <p>We are a team with educational backgrounds from the University of UC Berkeley, and MIT, with extensive professional experience in medicine, data science, computer science, and artificial intelligence.</p>

      <p>United by a shared mission, Health4UAI is building the <b>AI Clinic</b> model — a platform designed to make healthcare more efficient, accessible, and intelligent for patients, hospitals, doctors, and laboratories.</p>

      <p>Our AI models are engineered to reach the standards of top physicians, providing insights and decision support that go beyond the average level of care. By improving efficiency across every step of the healthcare journey, we help patients save time and money while supporting doctors to focus on delivering higher-quality care.</p>

      <p>Founded in the United States, we are committed to bringing this new era of intelligent healthcare from the U.S. to the world.</p>
    </div>
    """,
    unsafe_allow_html=True,
)

# ---------------------------------------------------------
# Footer
# ---------------------------------------------------------
st.markdown(
    "<p class='muted'>© Health4U AI — All rights reserved.</p>",
    unsafe_allow_html=True,
)
