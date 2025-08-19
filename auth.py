from __future__ import annotations

import os
import time
import json
import logging
from functools import wraps
from typing import Optional, Set

import streamlit as st

# Optional .env support
try:
    from dotenv import load_dotenv  # type: ignore
except Exception:
    def load_dotenv() -> bool:  # type: ignore
        return False

load_dotenv()


# -----------------------------------------------------------------------------
# Config helpers
# -----------------------------------------------------------------------------
def _get_config(name: str, default: Optional[str] = None) -> Optional[str]:
    """Read from st.secrets or environment."""
    try:
        return str(st.secrets[name])
    except Exception:
        return os.environ.get(name, default)


# -----------------------------------------------------------------------------
# Shared configuration
# -----------------------------------------------------------------------------
DISABLE_AUTH = (_get_config("DISABLE_AUTH", "0") == "1")

CLIENT_ID = _get_config("AAD_CLIENT_ID")
TENANT_ID = _get_config("AAD_TENANT_ID")
REDIRECT_URI = _get_config("AAD_REDIRECT_URI")  # SPA redirect (may include ?msal=popup)

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


# -----------------------------------------------------------------------------
# Exported API placeholders (bound below in each mode)
# -----------------------------------------------------------------------------
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
    return st.session_state.get("user_email")

def ensure_user_email() -> Optional[str]:  # type: ignore
    return st.session_state.get("user_email")


# =============================================================================
# 1) Development bypass (DISABLE_AUTH=1)
# =============================================================================
if DISABLE_AUTH:

    def _dev_ensure_user() -> None:
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

    def _dev_require_login(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            _dev_ensure_user()
            return func(*args, **kwargs)
        return wrapper

    def _dev_require_employee(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            _dev_ensure_user()
            return func(*args, **kwargs)
        return wrapper

    def _dev_require_admin(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            _dev_ensure_user()
            return func(*args, **kwargs)
        return wrapper

    def _dev_require_ksmta(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            _dev_ensure_user()
            return func(*args, **kwargs)
        return wrapper

    def _dev_logout_button() -> None:
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

    def _dev_get_user_email() -> Optional[str]:
        return st.session_state.get("user_email")

    def _dev_ensure_user_email() -> Optional[str]:
        _dev_ensure_user()
        return st.session_state.get("user_email")

    # Bind exports
    require_login = _dev_require_login
    require_employee = _dev_require_employee
    require_admin = _dev_require_admin
    require_ksmta = _dev_require_ksmta
    logout_button = _dev_logout_button
    get_user_email = _dev_get_user_email
    ensure_user_email = _dev_ensure_user_email


# =============================================================================
# 2) Real auth (POPUP via msal_streamlit_t2)
# =============================================================================
else:
    # Maintained fork; add to requirements.txt: msal_streamlit_t2==1.1.5
    from msal_streamlit_t2 import msal_authentication  # type: ignore
    import streamlit.components.v1 as components

    AUTHORITY = f"https://login.microsoftonline.com/{TENANT_ID}".rstrip("/")
    SCOPES = ["openid", "profile", "email", "User.Read"]

    # ---------- Login screen (single component instance) ----------
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
                "redirectUri": REDIRECT_URI,            # exact SPA redirect you added
                "postLogoutRedirectUri": REDIRECT_URI,
            },
            cache={
                "cacheLocation": "localStorage",         # popup + opener share cache
                "storeAuthStateInCookie": False,
            },
            login_request={
                "scopes": SCOPES,
                "prompt": "select_account",
            },
            logout_request={},                            # required by component API
            login_button_text="🔒 Sign in with Microsoft",
            logout_button_text="Sign out",
            key="msal_popup_login_singleton",
        )

        # Only transition when we have a real token; never treat None as logout.
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

    def _real_ensure_user() -> None:
        if st.session_state.get("user_email") and st.session_state.get("id_token"):
            return
        _render_login_ui()

    # ---------- Decorators ----------
    def _real_require_login(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            _real_ensure_user()
            return func(*args, **kwargs)
        return wrapper

    def _real_require_employee(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            _real_ensure_user()
            if not st.session_state.get("is_employee", False):
                st.error("🚫 KSM employees only.")
                st.stop()
            return func(*args, **kwargs)
        return wrapper

    def _real_require_admin(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            _real_ensure_user()
            if not st.session_state.get("is_admin", False):
                st.error("🚫 Admins only.")
                st.stop()
            return func(*args, **kwargs)
        return wrapper

    def _real_require_ksmta(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            _real_ensure_user()
            if not st.session_state.get("is_ksmta", False):
                st.error("🚫 KSMTA members only.")
                st.stop()
            return func(*args, **kwargs)
        return wrapper

    # ---------- Logout (client-side clear + hard navigate; no extra component) ----------
    def _clear_msal_storage_and_reload() -> None:
        """Remove MSAL keys from both storages and hard-reload to SPA redirect."""
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
                      if (k && k.toLowerCase().indexOf('msal') !== -1) keys.push(k);
                    }}
                    keys.forEach(function(k) {{ try {{ store.removeItem(k); }} catch(e){{}} }});
                  }});
                }} catch (e) {{}}
                var target = {json.dumps(REDIRECT_URI)};
                if (window.top) window.top.location.href = target;
                else window.location.href = target;
              }})();
            </script>
            """,
            height=0,
        )

    def _real_logout_button() -> None:
        if "user_email" not in st.session_state or not st.session_state.get("id_token"):
            return
        with st.sidebar:
            if hasattr(st.sidebar, "divider"):
                st.sidebar.divider()
            if st.button("Sign out", type="primary", use_container_width=True, key="ksm_logout"):
                # Clear server-side state first to avoid any residual UI, then client clear+reload.
                for k in [
                    "user_email", "user_name", "groups",
                    "is_employee", "is_ksmta", "is_admin",
                    "id_token", "token_acquired_at",
                ]:
                    st.session_state.pop(k, None)
                st.query_params.clear()
                _clear_msal_storage_and_reload()
                st.stop()

    def _real_get_user_email() -> Optional[str]:
        return st.session_state.get("user_email")

    def _real_ensure_user_email() -> Optional[str]:
        email = st.session_state.get("user_email")
        if email:
            return email
        _real_ensure_user()
        return st.session_state.get("user_email")

    # Bind exports
    require_login = _real_require_login
    require_employee = _real_require_employee
    require_admin = _real_require_admin
    require_ksmta = _real_require_ksmta
    logout_button = _real_logout_button
    get_user_email = _real_get_user_email
    ensure_user_email = _real_ensure_user_email
