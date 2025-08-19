from __future__ import annotations

import os
import time
from functools import wraps
from typing import Optional, Set

import streamlit as st


# ------------------------------
# Config helper
# ------------------------------
def _get_config(key: str, default: Optional[str] = None) -> Optional[str]:
    try:
        if hasattr(st, "secrets") and key in st.secrets:
            val = st.secrets[key]
            return default if val is None else str(val)
    except Exception:
        pass
    return os.environ.get(key, default)


# -------------------------------------------------
# Common flags and groups/domains configuration
# -------------------------------------------------
DISABLE_AUTH = (_get_config("DISABLE_AUTH", "0") == "1")

CLIENT_ID = _get_config("AAD_CLIENT_ID", "")
TENANT_ID = _get_config("AAD_TENANT_ID", "")

EMPLOYEE_GROUP_IDS: Set[str] = {
    g.strip() for g in (_get_config("AAD_EMPLOYEE_GROUP_IDS", "") or "").split(",") if g.strip()
}
KSMTA_GROUP_IDS: Set[str] = {
    g.strip() for g in (_get_config("AAD_KSMTA_GROUP_IDS", "") or "").split(",") if g.strip()
}
ADMIN_GROUP_IDS: Set[str] = {
    g.strip() for g in (_get_config("AAD_ADMIN_GROUP_IDS", "") or "").split(",") if g.strip()
}
EMPLOYEE_DOMAINS: Set[str] = {
    d.strip().lower()
    for d in (_get_config("AAD_EMPLOYEE_DOMAINS", "ksmcpa.com,ksmta.com") or "").split(",")
    if d.strip()
}


# ============================================================
# 1) Development bypass mode (DISABLE_AUTH = 1)
# ============================================================
if DISABLE_AUTH:
    def _ensure_user() -> None:
        if "user_email" in st.session_state:
            return
        email = _get_config("DEV_USER_EMAIL", "dev@ksmta.com")
        name = _get_config("DEV_USER_NAME", "Dev User")
        st.session_state.update(
            user_email=email,
            user_name=name,
            groups=set(),
            is_employee=True,
            is_ksmta=True,
            is_admin=True,
            id_token="DEV_MODE",
            token_acquired_at=time.time(),
        )

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
            return func(*args, **kwargs)
        return wrapper

    def require_admin(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            _ensure_user()
            return func(*args, **kwargs)
        return wrapper

    def require_ksmta(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            _ensure_user()
            return func(*args, **kwargs)
        return wrapper

    def logout_button() -> None:
        with st.sidebar:
            if hasattr(st.sidebar, "divider"):
                st.sidebar.divider()
            if st.button("Sign out (dev)"):
                for k in [
                    "user_email", "user_name", "groups",
                    "is_employee", "is_ksmta", "is_admin",
                    "id_token", "token_acquired_at",
                ]:
                    st.session_state.pop(k, None)
                st.query_params.clear()
                st.rerun()

    def get_user_email() -> Optional[str]:
        return st.session_state.get("user_email")

    def ensure_user_email() -> Optional[str]:
        _ensure_user()
        return st.session_state.get("user_email")


# ============================================================
# 2) Real authentication (POPUP via msal-streamlit-authentication)
# ============================================================
else:
    # Popup-based Streamlit component built on MSAL.js
    from msal_streamlit_authentication import msal_authentication

    AUTHORITY = f"https://login.microsoftonline.com/{TENANT_ID}".rstrip("/")
    # Use the exact SPA redirect you registered (prod). Override via env/secrets if needed.
    REDIRECT_URI = _get_config(
        "AAD_REDIRECT_URI_JS",
        "https://freightmath-rfp-automation.streamlit.app/",
    )

    # Scopes: OIDC basics + Graph profile
    SCOPES = ["openid", "profile", "email", "User.Read"]

    def _render_login_ui() -> None:
        st.markdown(
            "<h1 style='text-align:center;'>AI Mapping Agent</h1>"
            "<h3 style='text-align:center;'>Please sign in</h3>",
            unsafe_allow_html=True,
        )

        # ---- IMPORTANT ----
        # Use localStorage so tokens written in the POPUP are visible to the main window.
        # (sessionStorage is isolated per window and can leave the parent unaware.)
        token = msal_authentication(
            auth={
                "clientId": CLIENT_ID,
                "authority": AUTHORITY,
                "redirectUri": REDIRECT_URI,
                "postLogoutRedirectUri": REDIRECT_URI,
            },
            cache={
                "cacheLocation": "localStorage",
                "storeAuthStateInCookie": False,
            },
            login_request={"scopes": SCOPES},
            logout_request={},
            login_button_text="🔒 Sign in with Microsoft",
            logout_button_text="Sign out",
            key="msal_popup_login",
        )

        if token:
            claims = token.get("idTokenClaims") or {}
            groups = set(claims.get("groups", []))
            email = (
                claims.get("preferred_username")
                or claims.get("email")
                or claims.get("upn")
                or ""
            )
            domain = email.split("@")[-1].lower() if "@" in email else ""
            is_employee = bool(groups & EMPLOYEE_GROUP_IDS) or any(
                domain.endswith(d) for d in EMPLOYEE_DOMAINS
            )

            st.session_state.update(
                user_email=email,
                user_name=claims.get("name", ""),
                groups=groups,
                is_employee=is_employee,
                is_ksmta=bool(groups & KSMTA_GROUP_IDS),
                is_admin=bool(groups & ADMIN_GROUP_IDS),
                id_token=token.get("idToken"),
                token_acquired_at=time.time(),
            )
            st.rerun()

        st.stop()

    def _ensure_user() -> None:
        if "user_email" in st.session_state and st.session_state.get("id_token"):
            return
        _render_login_ui()

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
        # Only render the component here *after* login, so we don’t mount two instances at once.
        if "user_email" not in st.session_state:
            return

        with st.sidebar:
            if hasattr(st.sidebar, "divider"):
                st.sidebar.divider()

            _ = msal_authentication(
                auth={
                    "clientId": CLIENT_ID,
                    "authority": AUTHORITY,
                    "redirectUri": REDIRECT_URI,
                    "postLogoutRedirectUri": REDIRECT_URI,
                },
                cache={
                    "cacheLocation": "localStorage",
                    "storeAuthStateInCookie": False,
                },
                login_request={"scopes": SCOPES},
                logout_request={},
                login_button_text="🔒 Sign in with Microsoft",
                logout_button_text="Sign out",
                key="msal_popup_logout",
            )

            # If the component has logged us out, clear server-side state too.
            if "user_email" in st.session_state and not st.session_state.get("id_token"):
                for k in [
                    "user_email", "user_name", "groups",
                    "is_employee", "is_ksmta", "is_admin",
                    "id_token", "token_acquired_at",
                ]:
                    st.session_state.pop(k, None)
                st.query_params.clear()
                st.rerun()

    def get_user_email() -> Optional[str]:
        return st.session_state.get("user_email")

    def ensure_user_email() -> Optional[str]:
        email = st.session_state.get("user_email")
        if email:
            return email
        _ensure_user()
        return st.session_state.get("user_email")
