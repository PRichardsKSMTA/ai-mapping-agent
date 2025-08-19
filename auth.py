from __future__ import annotations

import os
import time
import logging
from functools import wraps
from typing import Optional, Set

import streamlit as st

try:
    from dotenv import load_dotenv
except Exception:
    def load_dotenv() -> bool:  # type: ignore
        return False

load_dotenv()


def _get_config(name: str, default: Optional[str] = None) -> Optional[str]:
    try:
        return str(st.secrets[name])
    except Exception:
        return os.environ.get(name, default)


DISABLE_AUTH = (_get_config("DISABLE_AUTH", "0") == "1")

CLIENT_ID = _get_config("AAD_CLIENT_ID")
TENANT_ID = _get_config("AAD_TENANT_ID")
REDIRECT_URI = _get_config("AAD_REDIRECT_URI")

EMPLOYEE_GROUP_IDS: Set[str] = {
    g.strip() for g in (_get_config("AAD_EMPLOYEE_GROUP_IDS", "") or "").split(",") if g.strip()
}
EMPLOYEE_DOMAINS: Set[str] = {
    d.strip().lower() for d in (_get_config("AAD_EMPLOYEE_DOMAINS", "ksmcpa.com,ksmta.com") or "").split(",") if d.strip()
}
KSMTA_GROUP_IDS: Set[str] = {
    g.strip() for g in (_get_config("AAD_KSMTA_GROUP_IDS", "") or "").split(",") if g.strip()
}
ADMIN_GROUP_IDS: Set[str] = {
    g.strip() for g in (_get_config("AAD_ADMIN_GROUP_IDS", "") or "").split(",") if g.strip()
}

if not DISABLE_AUTH:
    missing = [k for k, v in {"AAD_CLIENT_ID": CLIENT_ID, "AAD_TENANT_ID": TENANT_ID, "AAD_REDIRECT_URI": REDIRECT_URI}.items() if not v]
    if missing:
        DISABLE_AUTH = True
        msg = "Auth disabled: missing secrets -> " + ", ".join(missing)
        try:
            st.warning(msg)
        except Exception:
            logging.warning(msg)


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
                for k in ["user_email","user_name","groups","is_employee","is_ksmta","is_admin","id_token","token_acquired_at"]:
                    st.session_state.pop(k, None)
                st.query_params.clear()
                st.rerun()

    def get_user_email() -> Optional[str]:
        return st.session_state.get("user_email")

    def ensure_user_email() -> Optional[str]:
        _ensure_user()
        return st.session_state.get("user_email")

else:
    from msal_streamlit_authentication import msal_authentication

    AUTHORITY = f"https://login.microsoftonline.com/{TENANT_ID}".rstrip("/")
    SCOPES = ["openid","profile","email","User.Read"]

    def _render_login_ui() -> None:
        st.markdown(
            "<h1 style='text-align:center;'>AI Mapping Agent</h1>"
            "<h3 style='text-align:center;'>Please sign in</h3>",
            unsafe_allow_html=True,
        )

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
            login_request={
                "scopes": SCOPES,
                "prompt": "select_account",
            },
            logout_request={},
            login_button_text="🔒 Sign in with Microsoft",
            logout_button_text="Sign out",
            key="msal_popup_login",
        )

        if token:
            claims = token.get("idTokenClaims") or {}
            groups = set(claims.get("groups", []))
            email = (claims.get("preferred_username") or claims.get("email") or claims.get("upn") or "")
            domain = email.split("@")[-1].lower() if "@" in email else ""
            is_employee = bool(groups & EMPLOYEE_GROUP_IDS) or any(domain.endswith(d) for d in EMPLOYEE_DOMAINS)

            st.session_state.update(
                user_email=email,
                user_name=claims.get("name",""),
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
        if st.session_state.get("user_email") and st.session_state.get("id_token"):
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
        if "user_email" not in st.session_state:
            return
        with st.sidebar:
            if hasattr(st.sidebar, "divider"):
                st.sidebar.divider()
            token_sidebar = msal_authentication(
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
            if st.session_state.get("id_token") and token_sidebar is None:
                for k in ["user_email","user_name","groups","is_employee","is_ksmta","is_admin","id_token","token_acquired_at"]:
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
