import streamlit as st
import hmac


def check_password() -> bool:
    """Retorna True si el usuario ingresó la contraseña correcta."""

    def password_entered():
        try:
            expected = st.secrets["app_password"]
        except (KeyError, FileNotFoundError, Exception):
            st.session_state["password_correct"] = False
            st.session_state["auth_error"] = "no_config"
            return
        if not expected:
            st.session_state["password_correct"] = False
            st.session_state["auth_error"] = "no_config"
            return
        if hmac.compare_digest(st.session_state.get("password_input", ""), expected):
            st.session_state["password_correct"] = True
            if "password_input" in st.session_state:
                del st.session_state["password_input"]
        else:
            st.session_state["password_correct"] = False

    if st.session_state.get("password_correct", False):
        return True

    st.markdown("# 🔒 Dashboard - Soluciones Migratorias")
    st.markdown("Ingresá la contraseña para acceder al análisis de datos:")

    st.text_input(
        "Contraseña",
        type="password",
        on_change=password_entered,
        key="password_input",
    )

    if st.session_state.get("auth_error") == "no_config":
        st.error("⚠️ La contraseña no está configurada. Contactá al administrador.")
    elif "password_correct" in st.session_state and not st.session_state["password_correct"]:
        st.error("❌ Contraseña incorrecta")

    st.caption("Dashboard de uso interno de Soluciones Migratorias.")
    return False
