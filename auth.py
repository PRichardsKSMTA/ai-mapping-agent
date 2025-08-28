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
    val = os.environ.get(name)
    if val is not None:
        return val
    try:
        return str(st.secrets.get(name, default))  # type: ignore[attr-defined]
    except Exception:
        return default


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
    from urllib.parse import quote

    # --- Official Microsoft "Sign in with Microsoft" button assets (light/dark)
    MS_SIGNIN_SVG_LIGHT = (
        "https://learn.microsoft.com/en-us/entra/identity-platform/media/howto-add-branding-in-apps/"
        "ms-symbollockup_signin_light.svg"
    )
    MS_SIGNIN_SVG_DARK = (
        "https://raw.githubusercontent.com/MicrosoftDocs/entra-docs/main/docs/identity-platform/media/"
        "howto-add-branding-in-apps/ms-symbollockup_signin_dark.svg"
    )

    AUTHORITY = f"https://login.microsoftonline.com/{TENANT_ID}".rstrip("/")
    SCOPES = ["openid", "profile", "email", "User.Read"]

    # Tune these if your msal button has extra padding inside its iframe
    OVERLAY_OFFSET_X = 20   # px from iframe left
    OVERLAY_OFFSET_Y = 18   # px from iframe top
    TEXT_LEFT_OFFSET_PX = OVERLAY_OFFSET_X

    def _aad_logout_url() -> str:
        base = f"{AUTHORITY}/oauth2/v2.0/logout"
        # post_logout_redirect_uri must be one of your SPA Redirect URIs in Azure
        return f"{base}?post_logout_redirect_uri={quote(REDIRECT_URI, safe='')}"

    def _inject_component_centering_css() -> None:
        if st.session_state.get("_center_css_done"):
            return
        st.session_state["_center_css_done"] = True
        st.markdown(
            """
            <style>
            div[data-testid="stComponent"] {
                display: flex;
                justify-content: center;
            }
            div[data-testid="stComponent"] > iframe {
                max-width: 100%;
                margin: 0 auto;
                display: block;
            }
            </style>
            """,
            unsafe_allow_html=True,
        )


    def _remove_login_overlay_in_parent() -> None:
        # Remove the overlay + unhide any MSAL iframe we hid, then collapse THIS cleanup iframe
        import streamlit.components.v1 as components

        components.html(
            """
            <script>
            (function(){
                try {
                var PD = window.parent && window.parent.document;
                if (PD) {
                    // Remove our overlay image if present
                    var ov = PD.getElementById('ksm_msal_overlay');
                    if (ov && ov.parentNode) ov.parentNode.removeChild(ov);

                    // Restore opacity on any MSAL iframe we hid earlier
                    var hidden = PD.querySelectorAll('iframe[data-ksm-hidden="1"]');
                    for (var i = 0; i < hidden.length; i++) {
                    hidden[i].style.opacity = '1';
                    hidden[i].removeAttribute('data-ksm-hidden');
                    }
                }
                } catch(e){}

                // IMPORTANT: collapse this cleanup iframe so it leaves **zero** layout gap
                try {
                var me = window.frameElement;      // the <iframe> Streamlit created for this component
                if (me) {
                    me.style.width = '0';
                    me.style.height = '0';
                    me.style.border = '0';
                    me.style.position = 'absolute';
                    me.style.left = '-9999px';
                }
                } catch(e){}
            })();
            </script>
            """,
            height=0,
        )

    def _render_login_ui() -> None:
        _inject_component_centering_css()

        # Make the left column wider so the H1 stays on one line
        # (adjust 3,1,1 if you want it a bit narrower/wider)
        left, center, right = st.columns([3, 1, 1])

        with left:
            # Headings: add a small left margin so they align with the button
            st.markdown(
                f"""
                <div style="margin-left:{TEXT_LEFT_OFFSET_PX}px">
                <h1 style="margin:0 0 8px 0; white-space:nowrap;">AI Mapping Agent</h1>
                <h3 style="margin:0 0 16px 0;">Please sign in</h3>
                </div>
                """,
                unsafe_allow_html=True,
            )

            # Existing, working MSAL popup button (unchanged)
            token = msal_authentication(
                auth={
                    "clientId": CLIENT_ID,
                    "authority": f"https://login.microsoftonline.com/{TENANT_ID}".rstrip("/"),
                    "redirectUri": REDIRECT_URI,
                    "postLogoutRedirectUri": REDIRECT_URI,
                },
                cache={"cacheLocation": "localStorage", "storeAuthStateInCookie": False},
                login_request={"scopes": ["openid", "profile", "email", "User.Read"], "prompt": "select_account"},
                logout_request={},
                login_button_text="🔒 Sign in with Microsoft",
                logout_button_text="Sign out",
                key="msal_popup_login_singleton",
            )

            # Anchor + overlay (your current working overlay logic) — unchanged except it uses your OVERLAY_OFFSET_* values
            st.markdown("<div id='ksm_msal_sentinel'></div>", unsafe_allow_html=True)
            theme = (st.get_option("theme.base") or "light").lower()
            svg_url = MS_SIGNIN_SVG_DARK if theme == "dark" else MS_SIGNIN_SVG_LIGHT

            components.html(
                f"""
                <script>
                (function () {{
                    var PD = window.parent.document;
                    var selfFrame = window.frameElement;

                    // Ensure a single overlay <img> in parent
                    var ov = PD.getElementById('ksm_msal_overlay');
                    if (!ov) {{
                    ov = PD.createElement('img');
                    ov.id = 'ksm_msal_overlay';
                    ov.alt = 'Sign in with Microsoft';
                    ov.style.position = 'fixed';
                    ov.style.zIndex = '9999';
                    ov.style.pointerEvents = 'none';  // click passes through to real button
                    ov.style.display = 'none';
                    ov.style.height = '40px';
                    PD.body.appendChild(ov);
                    }}
                    ov.src = {json.dumps(svg_url)};

                    function colOf(el) {{
                    while (el && el !== PD.body) {{
                        if (el.getAttribute && el.getAttribute('data-testid') === 'column') return el;
                        el = el.parentElement;
                    }}
                    return null;
                    }}

                    function targetIframe() {{
                    var frames = PD.getElementsByTagName('iframe');
                    var idx = -1;
                    for (var i = 0; i < frames.length; i++) {{
                        if (frames[i] === selfFrame) {{ idx = i; break; }}
                    }}
                    if (idx <= 0) return null;
                    var myCol = colOf(selfFrame);
                    for (var j = idx - 1; j >= 0; j--) {{
                        if (colOf(frames[j]) === myCol) return frames[j];
                    }}
                    return null;
                    }}

                    function place() {{
                    try {{
                        var t = targetIframe();
                        if (!t) {{ ov.style.display = 'none'; return; }}

                        // keep the underlying iframe clickable but invisible
                        t.style.opacity = '0';
                        t.setAttribute('data-ksm-hidden', '1');

                        var r = t.getBoundingClientRect();
                        ov.style.display = 'block';
                        ov.style.left = (r.left + {OVERLAY_OFFSET_X}) + 'px';
                        ov.style.top  = (r.top  + {OVERLAY_OFFSET_Y}) + 'px';
                    }} catch (e) {{
                        ov.style.display = 'none';
                    }}
                    }}

                    place();
                    window.parent.addEventListener('resize', place);
                    window.parent.addEventListener('scroll', place, true);
                    var MO = window.parent.MutationObserver || MutationObserver;
                    new MO(place).observe(PD.body, {{ childList: true, subtree: true }});
                }})();
                </script>
                """,
                height=0,
            )

        # Success path: remove overlay and persist claims (unchanged)
        if isinstance(token, dict) and token.get("idToken"):
            _remove_login_overlay_in_parent()
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
        # If already authenticated, remove any leftover overlay and return
        if st.session_state.get("user_email") and st.session_state.get("id_token"):
            _remove_login_overlay_in_parent()
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
                  // Remove any login overlay before reload
                  var PD = window.parent && window.parent.document;
                  if (PD) {{
                    var ov = PD.getElementById('ksm_msal_overlay');
                    if (ov && ov.parentNode) ov.parentNode.removeChild(ov);
                  }}
                }} catch(e) {{}}
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

    def _logout_button_real() -> None:
        if "user_email" not in st.session_state or not st.session_state.get("id_token"):
            return
        with st.sidebar:
            if hasattr(st.sidebar, "divider"):
                st.sidebar.divider()
            if st.button("Sign out", type="primary", use_container_width=True, key="ksm_logout"):
                # Clear server state first, then client-side wipe + reload (no st.rerun()).
                for k in [
                    "user_email", "user_name", "groups",
                    "is_employee", "is_ksmta", "is_admin",
                    "id_token", "token_acquired_at", "_center_css_done",
                ]:
                    st.session_state.pop(k, None)
                st.query_params.clear()
                _clear_storage_and_reload()
                st.stop()

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
    logout_button = _logout_button_real
    get_user_email = _get_user_email_real
    ensure_user_email = _ensure_user_email_real
