# -*- coding: utf-8 -*-
"""
Contact Us (Standalone Page) — Microsoft Graph (app-only)
Place this file in: pages/07_Contact_Us.py
Requires: pip install streamlit msal requests
"""

import os
import time
import json
import urllib.parse
from email.utils import formataddr
from typing import Tuple

import streamlit as st
import requests
import msal
from PIL import Image


# ---------------------------------------------------------------------
# Basic page config + subtle styling to align with other pages
# ---------------------------------------------------------------------

#st.set_page_config(page_title="Contact Us", layout="centered")
st.set_page_config(
    page_title="AI Clinic | Contact Us",
    page_icon="assets/h4u_icon2.ico",
    layout="wide"
)


try:
    image = Image.open("assets/h4u_logo.png")
    st.image(image.resize((650, 225)))
except Exception:
    st.info("Logo not found at assets/h4u_logo.png (optional).")


# Optional: tighten max width for consistency
CUSTOM_CSS = """
<style>
  .main > div { max-width: 900px; margin-left: auto; margin-right: auto; }
  .contact-card { border: 1px solid #e5e7eb; border-radius: 10px; padding: 16px; background: #f8fafc; }
  .muted { color: #6b7280; font-size: 0.9rem; }
</style>
"""
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)


# ---------------------------------------------------------------------
# Config loader: Streamlit secrets override env vars
# ---------------------------------------------------------------------

def load_cfg() -> dict:
    keys = ["TENANT_ID", "CLIENT_ID", "CLIENT_SECRET", "SENDER", "CONTACT_TO", "APP_NAME"]
    cfg = {k: "" for k in keys}

    # from secrets
    try:
        for k in keys:
            if k in st.secrets:
                cfg[k] = str(st.secrets[k])
    except Exception:
        pass

    # env overrides
    for k in keys:
        v = os.getenv(k)
        if v:
            cfg[k] = v

    # sensible defaults
    if not cfg["CONTACT_TO"]:
        cfg["CONTACT_TO"] = "health4uai@health4uai.com"
    if not cfg["APP_NAME"]:
        cfg["APP_NAME"] = "AI Clinic"

    return cfg


# ---------------------------------------------------------------------
# Microsoft Graph helpers (Client Credentials flow)
# ---------------------------------------------------------------------

GRAPH_SCOPE = ["https://graph.microsoft.com/.default"]
GRAPH_BASE = "https://graph.microsoft.com/v1.0"

def acquire_token(tenant_id: str, client_id: str, client_secret: str) -> Tuple[bool, str]:
    """Acquire app-only token via client credentials."""
    try:
        authority = f"https://login.microsoftonline.com/{tenant_id}"
        app = msal.ConfidentialClientApplication(
            client_id, authority=authority, client_credential=client_secret
        )
        result = app.acquire_token_for_client(scopes=GRAPH_SCOPE)
        if "access_token" in result:
            return True, result["access_token"]
        # Bubble up a readable reason
        return False, result.get("error_description", json.dumps(result))
    except Exception as e:
        return False, f"Token error: {e}"

def graph_send_mail(sender: str, to_addr: str, subject: str, body_text: str, token: str) -> Tuple[bool, str]:
    """
    Send email via Graph app-only. Important:
    - Use /users/{sender}/sendMail (NOT /me/sendMail)
    - Do NOT include "from" in the JSON when using app-only.
    """
    try:
        url = f"{GRAPH_BASE}/users/{sender}/sendMail"
        payload = {
            "message": {
                "subject": subject,
                "body": {"contentType": "Text", "content": body_text},
                "toRecipients": [{"emailAddress": {"address": to_addr}}],
            },
            "saveToSentItems": True,
        }
        r = requests.post(
            url,
            json=payload,
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            timeout=20,
        )
        if r.status_code in (200, 202):
            return True, "Message sent."
        return False, f"Graph send failed: {r.status_code} {r.text}"
    except Exception as e:
        return False, f"Graph exception: {e}"


# ---------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------

def mailto_fallback_link(to_addr: str, app_name: str, subject: str, name: str, email: str, message: str) -> str:
    subj = f"{app_name} - {subject or 'Contact'}"
    body = f"From: {formataddr((name or 'N/A', email or 'noreply@example.com'))}\n\n{message or ''}"
    return "mailto:" + to_addr + "?" + urllib.parse.urlencode({"subject": subj, "body": body})

def rate_limited(key: str, seconds: int = 10) -> bool:
    now = time.time()
    last = st.session_state.get(key)
    if last and now - last < seconds:
        return True
    st.session_state[key] = now
    return False



# ---------------------------------------------------------------------
# Page UI
# ---------------------------------------------------------------------

def render_contact_page():
    cfg = load_cfg()
    st.title("Contact Us")

    st.markdown(
        "<div class='contact-card'>"
        "<div class='muted'>Questions, feedback, or ideas? Send us a note.</div>"
        "</div>",
        unsafe_allow_html=True,
    )
    st.write("")

    # Form
    with st.form("contact_form", clear_on_submit=True):
        c1, c2 = st.columns(2)
        with c1:
            name = st.text_input("Your name", placeholder="Jane Doe")
        with c2:
            email = st.text_input("Your email", placeholder="you@example.com")

        subject = st.text_input("Subject", placeholder="Feedback / Question / Issue")
        message = st.text_area("Message", placeholder="Type your message here...", height=160)

        submitted = st.form_submit_button("Send")

    if not submitted:
        return

    # Simple validations and rate-limit
    if not message.strip():
        st.warning("Please enter a message.")
        return
    if rate_limited("_contact_last_submit"):
        st.info("Please wait a few seconds before sending another message.")
        return

    # If Graph is not configured, provide a mailto fallback
    missing = [k for k in ("TENANT_ID", "CLIENT_ID", "CLIENT_SECRET", "SENDER") if not cfg.get(k)]
    if missing:
        st.error(
            "Microsoft Graph mail is not configured. Please set TENANT_ID, CLIENT_ID, CLIENT_SECRET, and SENDER."
        )
        st.link_button(
            "Open your email app instead",
            mailto_fallback_link(cfg["CONTACT_TO"], cfg["APP_NAME"], subject, name, email, message),
            use_container_width=True,
        )
        return

    # Acquire token, then send
    ok_tok, token_or_err = acquire_token(cfg["TENANT_ID"], cfg["CLIENT_ID"], cfg["CLIENT_SECRET"])
    if not ok_tok:
        st.error(f"Auth error: {token_or_err}")
        st.link_button(
            "Open your email app instead",
            mailto_fallback_link(cfg["CONTACT_TO"], cfg["APP_NAME"], subject, name, email, message),
            use_container_width=True,
        )
        return

    body = (
        f"New {cfg['APP_NAME']} contact form submission\n\n"
        f"From: {formataddr((name or 'N/A', email or '') )}\n"
        f"Subject: {subject or 'Contact'}\n\n"
        f"Message:\n{message}\n"
    )

    ok_send, info = graph_send_mail(
        sender=cfg["SENDER"],
        to_addr=cfg["CONTACT_TO"],
        subject=subject or f"{cfg['APP_NAME']} - Contact Form",
        body_text=body,
        token=token_or_err,
    )
    if ok_send:
        st.success("Message sent successfully.")
    else:
        st.error(info)
        st.link_button(
            "Open your email app instead",
            mailto_fallback_link(cfg["CONTACT_TO"], cfg["APP_NAME"], subject, name, email, message),
            use_container_width=True,
        )


# ---------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------

render_contact_page()
