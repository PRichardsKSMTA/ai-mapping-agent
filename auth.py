from __future__ import annotations

import os
import time
import json
import logging
from functools import wraps
from typing import Optional, Set

import streamlit as st

# -----------------------------
# Pre-bind public API (no-op)
# -----------------------------
def require_login(func):  # type: ignore
    return func

def require_employee(func):  # type: ignore
    return func

def require_admin(func):  # type: ignore
    return func

def require_ksmta(func):  # type: ignore
    return func

def logout_button() -> None:  # type: ignore
    return None

def get_user_email() -> Optional[str]:  # type: ignore
    try:
        return st.session_state.get("user_email")
    except Exception:
        return None

def ensure_user_email() -> Optional[str]:  # type: ignore
    try:
        return st.session_state.get("user_email")
    except Exception:
        return None

__all__ = [
    "require_login",
    "require_employee",
    "require_admin",
    "require_ksmta",
    "logout_button",
    "get_user_email",
    "ensure_user_email",
]

# Optional .env support (safe if not installed)
try:
    from dotenv import load_dotenv  # type: ignore
except Exception:
    def load_dotenv() -> bool:  # type: ignore
        return False
load_dotenv()

# -----------------------------
# Config helpers
# -----------------------------
def _get_config(name: str, default: Optional[str] = None) -> Optional[str]:
    try:
        return str(st.secrets[name])
    except Exception:
        return os.environ.get(name, default)

# -----------------------------
# Settings & toggles
# -----------------------------
DISABLE_AUTH = (_get_config("DISABLE_AUTH", "0") == "1")

CLIENT_ID = _get_config("AAD_CLIENT_ID")
TENANT_ID = _get_config("AAD_TENANT_ID")
REDIRECT_URI = _get_config("AAD_REDIRECT_URI")  # SPA redirect (exact match; can include ?msal=popup)

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
    missing = [k for k, v in {
        "AAD_CLIENT_ID": CLIENT_ID,
        "AAD_TENANT_ID": TENANT_ID,
        "AAD_REDIRECT_URI": REDIRECT_URI,
    }.items() if not v]
    if missing:
        DISABLE_AUTH = True
        msg = "Auth disabled: missing secrets -> " + ", ".join(missing)
        try:
            st.warning(msg)
        except Exception:
            logging.warning(msg)

# =============================================================================
# 1) Dev bypass (exports rebound to real implementations)
# =============================================================================
if DISABLE_AUTH:

    def _ensure_user_dev() -> None:
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

    def _require_login_dev(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            _ensure_user_dev()
            return func(*args, **kwargs)
        return wrapper

    def _require_employee_dev(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            _ensure_user_dev()
            return func(*args, **kwargs)
        return wrapper

    def _require_admin_dev(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            _ensure_user_dev()
            return func(*args, **kwargs)
        return wrapper

    def _require_ksmta_dev(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            _ensure_user_dev()
            return func(*args, **kwargs)
        return wrapper

    def _logout_button_dev() -> None:
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

    def _get_user_email_dev() -> Optional[str]:
        return st.session_state.get("user_email")

    def _ensure_user_email_dev() -> Optional[str]:
        _ensure_user_dev()
        return st.session_state.get("user_email")

    # Rebind public API
    require_login = _require_login_dev
    require_employee = _require_employee_dev
    require_admin = _require_admin_dev
    require_ksmta = _require_ksmta_dev
    logout_button = _logout_button_dev
    get_user_email = _get_user_email_dev
    ensure_user_email = _ensure_user_email_dev

# =============================================================================
# 2) Real auth — popup via msal_streamlit_t2 (exports rebound to real impls)
# =============================================================================
else:
    # Maintained drop-in replacement; add to requirements.txt: msal_streamlit_t2==1.1.5
    from msal_streamlit_t2 import msal_authentication  # type: ignore
    import streamlit.components.v1 as components
    # add near the top of the REAL-AUTH section:
    from urllib.parse import quote

    AUTHORITY = f"https://login.microsoftonline.com/{TENANT_ID}".rstrip("/")
    SCOPES = ["openid", "profile", "email", "User.Read"]
    
    def _aad_logout_url() -> str:
        base = f"{AUTHORITY}/oauth2/v2.0/logout"
        # post_logout_redirect_uri must be one of your SPA Redirect URIs in Azure
        return f"{base}?post_logout_redirect_uri={quote(REDIRECT_URI, safe='')}"

    def _render_login_ui() -> None:
        st.markdown(
            "<h1 style='text-align:center;'>AI Mapping Agent</h1>"
            "<h3 style='text-align:center;'>Please sign in</h3>",
            unsafe_allow_html=True,
        )

        # SINGLE instance; no auto-refresh; no sidebar copy
        token = msal_authentication(
            auth={
                "clientId": CLIENT_ID,
                "authority": AUTHORITY,
                "redirectUri": REDIRECT_URI,            # must match SPA redirect exactly
                "postLogoutRedirectUri": REDIRECT_URI,
            },
            cache={
                "cacheLocation": "localStorage",         # popup & opener share cache
                "storeAuthStateInCookie": False,
            },
            login_request={
                "scopes": SCOPES,
                "prompt": "select_account",
            },
            logout_request={},                            # required param
            login_button_text="🔒 Sign in with Microsoft",
            logout_button_text="Sign out",
            key="msal_popup_login_singleton",
        )

        # Only transition when a real token exists; ignore None
        if isinstance(token, dict) and token.get("idToken"):
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

    def _ensure_user_real() -> None:
        if st.session_state.get("user_email") and st.session_state.get("id_token"):
            return
        _render_login_ui()

    def _require_login_real(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            _ensure_user_real()
            return func(*args, **kwargs)
        return wrapper

    def _require_employee_real(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            _ensure_user_real()
            if not st.session_state.get("is_employee", False):
                st.error("🚫 KSM employees only.")
                st.stop()
            return func(*args, **kwargs)
        return wrapper

    def _require_admin_real(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            _ensure_user_real()
            if not st.session_state.get("is_admin", False):
                st.error("🚫 Admins only.")
                st.stop()
            return func(*args, **kwargs)
        return wrapper

    def _require_ksmta_real(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            _ensure_user_real()
            if not st.session_state.get("is_ksmta", False):
                st.error("🚫 KSMTA members only.")
                st.stop()
            return func(*args, **kwargs)
        return wrapper

    def _clear_storage_and_reload() -> None:
        """Clear both storages and hard-navigate to the SPA redirect."""
        components.html(
            f"""
            <script>
              (function() {{
                try {{
                  ['localStorage','sessionStorage'].forEach(function(storeName){{
                    var store = window[storeName];
                    if (!store) return;
                    var keys = [];
                    for (var i = 0; i < store.length; i++) {{
                      var k = store.key(i);
                      if (k) keys.push(k);
                    }}
                    keys.forEach(function(k) {{ try {{ store.removeItem(k); }} catch(e){{}} }});
                  }});
                }} catch (e) {{}}
                var u = new URL({json.dumps(REDIRECT_URI)}, window.location.href);
                u.searchParams.set('logoutts', Date.now().toString());
                if (window.top) window.top.location.href = u.toString();
                else window.location.href = u.toString();
              }})();
            </script>
            """,
            height=0,
        )

    def logout_button() -> None:
        # Only show when logged in
        if "user_email" not in st.session_state or not st.session_state.get("id_token"):
            return

        from msal_streamlit_t2 import msal_authentication  # uses the maintained popup component
        import streamlit as st

        AUTHORITY = f"https://login.microsoftonline.com/{TENANT_ID}".rstrip("/")
        SCOPES = ["openid", "profile", "email", "User.Read"]

        with st.sidebar:
            if hasattr(st.sidebar, "divider"):
                st.sidebar.divider()

            # Mount ONE instance here; when clicked, the component performs logout via MSAL.js.
            token_sidebar = msal_authentication(
                auth={
                    "clientId": CLIENT_ID,
                    "authority": AUTHORITY,
                    "redirectUri": REDIRECT_URI,            # must match a SPA redirect exactly
                    "postLogoutRedirectUri": REDIRECT_URI,
                },
                cache={
                    "cacheLocation": "localStorage",
                    "storeAuthStateInCookie": False,
                },
                login_request={"scopes": SCOPES},
                logout_request={},                            # required by the component API
                login_button_text="🔒 Sign in with Microsoft",
                logout_button_text="Sign out",
                key="msal_popup_logout_singleton",
            )

            # After the user clicks "Sign out", the component returns None on the next run.
            if token_sidebar is None and st.session_state.get("id_token"):
                for k in [
                    "user_email", "user_name", "groups",
                    "is_employee", "is_ksmta", "is_admin",
                    "id_token", "token_acquired_at",
                ]:
                    st.session_state.pop(k, None)
                st.query_params.clear()
                st.rerun()

    def _get_user_email_real() -> Optional[str]:
        return st.session_state.get("user_email")

    def _ensure_user_email_real() -> Optional[str]:
        email = st.session_state.get("user_email")
        if email:
            return email
        _ensure_user_real()
        return st.session_state.get("user_email")

    # Rebind public API
    require_login = _require_login_real
    require_employee = _require_employee_real
    require_admin = _require_admin_real
    require_ksmta = _require_ksmta_real
    logout_button = logout_button
    get_user_email = _get_user_email_real
    ensure_user_email = _ensure_user_email_real
