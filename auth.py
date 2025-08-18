"""
auth.py  –  Stand-alone + demo-bypass
====================================

• DISABLE_AUTH=1   → skips Azure login for fast demos.
• Robust MSAL auth-code flow without any deprecated Streamlit APIs.
• Global _FLOW_CACHE keyed by `state` so flow survives redirect.
• logout_button uses st.rerun (current API).

Environment variables
---------------------
AAD_CLIENT_ID, AAD_CLIENT_SECRET, AAD_TENANT_ID, AAD_REDIRECT_URI
AAD_EMPLOYEE_GROUP_IDS=            # optional
AAD_EMPLOYEE_DOMAINS=ksmcpa.com,ksmta.com
AAD_KSMTA_GROUP_IDS=cccccccc-cccc-cccc-cccc-cccccccccccc
DISABLE_AUTH=1                     # set to 0 or unset for real login
DEV_USER_EMAIL=pete.richards@ksmta.com
"""

from __future__ import annotations

import os
import time
import logging
from functools import wraps
from typing import Any, Dict, Set

import streamlit as st

try:  # pragma: no cover - optional dependency
    from dotenv import load_dotenv
except Exception:  # pragma: no cover - if python-dotenv not installed
    def load_dotenv() -> bool:  # type: ignore
        return False

load_dotenv()

# Helper to retrieve configuration from st.secrets or environment
def _get_config(name: str, default: str | None = None) -> str | None:
    """Return a config value from st.secrets or environment."""
    try:
        return str(st.secrets[name])
    except Exception:
        return os.environ.get(name, default)

# --------------------------------------------------------------------------- #
# 1.  Dev bypass mode                                                         #
# --------------------------------------------------------------------------- #
DISABLE_AUTH = _get_config("DISABLE_AUTH", "0") == "1"
CLIENT_ID = _get_config("AAD_CLIENT_ID")
CLIENT_SECRET = _get_config("AAD_CLIENT_SECRET")
TENANT_ID = _get_config("AAD_TENANT_ID")
REDIRECT_URI = _get_config("AAD_REDIRECT_URI")

REQUIRED_SECRETS = {
    "AAD_CLIENT_ID": CLIENT_ID,
    "AAD_CLIENT_SECRET": CLIENT_SECRET,
    "AAD_TENANT_ID": TENANT_ID,
    "AAD_REDIRECT_URI": REDIRECT_URI,
}

if not DISABLE_AUTH:
    missing = [name for name, value in REQUIRED_SECRETS.items() if not value]
    if missing:
        DISABLE_AUTH = True
        msg = (
            "Auth disabled: missing secrets -> " + ", ".join(missing)
        )
        try:
            st.warning(msg)
        except Exception:  # pragma: no cover - streamlit not initialized
            logging.warning(msg)

if DISABLE_AUTH:
    if _get_config("DISABLE_AUTH", "0") == "1":
        st.session_state.setdefault(
            "user_email", _get_config("DEV_USER_EMAIL", "pete.richards@ksmta.com")
        )
        st.session_state.setdefault("is_employee", True)
        st.session_state.setdefault("is_ksmta", True)
        st.session_state.setdefault("is_admin", True)
    # No-op decorators
    def _ensure_user() -> None:  # type: ignore
        return
    def require_login(func):  # type: ignore
        return func

    def require_employee(func):  # type: ignore
        return func

    def require_ksmta(func):  # type: ignore
        return func

    def require_admin(func):  # type: ignore
        return func

    def logout_button():  # type: ignore
        return

    def get_user_email() -> str | None:  # type: ignore
        return st.session_state.get("user_email")

    def ensure_user_email() -> str | None:  # type: ignore
        _ensure_user()
        return st.session_state.get("user_email")

else:
    # ----------------------------------------------------------------------- #
    # 2.  Real MSAL authentication                                            #
    # ----------------------------------------------------------------------- #
    import msal  # only when auth enabled

    EMPLOYEE_GROUP_IDS: Set[str] = {
        g.strip()
        for g in _get_config("AAD_EMPLOYEE_GROUP_IDS", "").split(",")
        if g.strip()
    }
    EMPLOYEE_DOMAINS: Set[str] = {
        d.strip().lower()
        for d in _get_config("AAD_EMPLOYEE_DOMAINS", "").split(",")
        if d.strip()
    }
    KSMTA_GROUP_IDS: Set[str] = {
        g.strip() for g in _get_config("AAD_KSMTA_GROUP_IDS", "").split(",") if g.strip()
    }
    ADMIN_GROUP_IDS: Set[str] = {
        g.strip() for g in _get_config("AAD_ADMIN_GROUP_IDS", "").split(",") if g.strip()
    }

    AUTHORITY = f"https://login.microsoftonline.com/{TENANT_ID}"
    SCOPE = ["User.Read"]

    # Global cache for flows keyed by state
    _FLOW_CACHE: Dict[str, Dict[str, Any]] = {}

    # -------------------- MSAL helpers ------------------------------------ #
    def _build_msal_app() -> msal.ConfidentialClientApplication:
        if "msal_app" not in st.session_state:
            st.session_state.msal_app = msal.ConfidentialClientApplication(
                client_id=CLIENT_ID,
                authority=AUTHORITY,
                client_credential=CLIENT_SECRET,
            )
        return st.session_state.msal_app

    def _initiate_flow() -> str:
        """Start MSAL auth-code flow (once per session) and return login URL."""
        state = st.session_state.get("msal_state")
        if not state or state not in _FLOW_CACHE:
            app = _build_msal_app()
            flow = app.initiate_auth_code_flow(scopes=SCOPE, redirect_uri=REDIRECT_URI, prompt="select_account")
            state = flow["state"]
            st.session_state["msal_state"] = state
            _FLOW_CACHE[state] = flow
        return _FLOW_CACHE[state]["auth_uri"]

    def _complete_flow() -> None:
        query = st.query_params.to_dict()
        if "code" not in query or "state" not in query:
            return  # not an auth return
        state = query["state"]
        flow = _FLOW_CACHE.pop(state, None)
        if not flow:
            st.error("Authentication session expired. Please sign in again.")
            st.session_state.pop("msal_state", None)
            return

        app = _build_msal_app()
        result = app.acquire_token_by_auth_code_flow(flow, query)

        if "error" in result:
            st.error(f"AAD error: {result.get('error_description')}")
            st.session_state.pop("msal_state", None)
            return

        claims = result.get("id_token_claims") or {}
        groups: Set[str] = set(claims.get("groups", []))
        email = claims.get("preferred_username", "")
        domain = email.split("@")[-1].lower() if "@" in email else ""

        is_employee = (
            bool(groups & EMPLOYEE_GROUP_IDS)
            or any(domain.endswith(d) for d in EMPLOYEE_DOMAINS)
        )

        st.session_state.update(
            user_email=email,
            user_name=claims.get("name", ""),
            groups=groups,
            is_employee=is_employee,
            is_ksmta=bool(groups & KSMTA_GROUP_IDS),
            is_admin=bool(groups & ADMIN_GROUP_IDS),
            id_token=result["id_token"],
            token_acquired_at=time.time(),
        )

        # Clean up
        st.session_state.pop("msal_state", None)
        st.query_params.clear()

    # -------------------- Decorators & helpers ---------------------------- #
    def _ensure_user() -> None:
        if "user_email" in st.session_state:
            return

        _complete_flow()
        if "user_email" in st.session_state:
            return

        login_url = _initiate_flow()
        st.markdown(
            "<h1 style='text-align:center;'>AI Mapping Agent</h1>"
            "<h3 style='text-align:center;'>Please sign in</h3>",
            unsafe_allow_html=True)
        _, col, _ = st.columns((1, 2, 1))
        col.link_button("🔒 Sign in with Microsoft", login_url, type="primary", use_container_width=True)
        st.stop()

    def require_login(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            _ensure_user()
            return func(*args, **kwargs)

        return wrapper

    def require_employee(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            _ensure_user()
            if not st.session_state.get("is_employee", False):
                st.error("🚫 KSM employees only.")
                st.stop()
            return func(*args, **kwargs)

        return wrapper

    def require_admin(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            _ensure_user()
            if not st.session_state.get("is_admin", False):
                st.error("🚫 Admins only.")
                st.stop()
            return func(*args, **kwargs)

        return wrapper

    def require_ksmta(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            _ensure_user()
            if not st.session_state.get("is_ksmta", False):
                st.error("🚫 KSMTA members only.")
                st.stop()
            return func(*args, **kwargs)

        return wrapper

    def logout_button() -> None:
        with st.sidebar:
            if hasattr(st.sidebar, "divider"):
                st.sidebar.divider()
            # email: str | None = st.session_state.get("user_email")
            # st.caption(f"Signed in as {email}")
            st.markdown(
                "<div style='height: 3rem'></div>",
                unsafe_allow_html=True,
            )
            if st.button(
                "Sign out", type="primary", use_container_width=True
            ):
                for k in [
                    "user_email",
                    "user_name",
                    "groups",
                    "is_employee",
                    "is_ksmta",
                    "is_admin",
                    "id_token",
                    "token_acquired_at",
                    "msal_state",
                ]:
                    st.session_state.pop(k, None)
                st.query_params.clear()
                st.rerun()

    def get_user_email() -> str | None:
        return st.session_state.get("user_email")

    def ensure_user_email() -> str | None:
        """Ensure user email is available, invoking login if needed."""
        email = st.session_state.get("user_email")
        if email:
            return email
        _ensure_user()
        return st.session_state.get("user_email")
