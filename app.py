import streamlit as st
import pandas as pd
import dropbox
import requests
from io import BytesIO

# 🔄 Función para refrescar el access token de Dropbox
def refresh_access_token():
    try:
        refresh_token = st.secrets["DROPBOX_REFRESH_TOKEN"]
        client_id = st.secrets["DROPBOX_CLIENT_ID"]
        client_secret = st.secrets["DROPBOX_CLIENT_SECRET"]
        
        url = "https://api.dropbox.com/oauth2/token"
        data = {
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "client_id": client_id,
            "client_secret": client_secret
        }
        
        response = requests.post(url, data=data)
        
        if response.status_code == 200:
            return response.json().get("access_token")
        else:
            st.error(f"❌ Error al refrescar el token de acceso: {response.json()}")
            return None
    except Exception as e:
        st.error(f"❌ Error inesperado al obtener el token de Dropbox: {e}")
        return None

# 📥 Descargar archivo desde Dropbox
def download_from_dropbox(dropbox_path):
    access_token = refresh_access_token()
    if not access_token:
        return None

    try:
        dbx = dropbox.Dropbox(access_token)
        _, res = dbx.files_download(dropbox_path)
        return BytesIO(res.content)
    except Exception as e:
        st.error(f"❌ Error al descargar desde Dropbox: {e}")
        return None

# 📤 Subir archivo a Dropbox
def upload_to_dropbox(file_content, filename, dropbox_path):
    access_token = refresh_access_token()
    if not access_token:
        return None

    try:
        dbx = dropbox.Dropbox(access_token)
        dbx.files_upload(file_content.getvalue(), f"{dropbox_path}/{filename}", mode=dropbox.files.WriteMode("overwrite"))
        st.success(f"✅ Archivo {filename} subido correctamente.")
    except Exception as e:
        st.error(f"❌ Error al subir el archivo a Dropbox: {e}")

# 🔍 Verificar si ya se ha enviado la evaluación
def check_if_already_submitted(dropbox_path, identificador):
    access_token = refresh_access_token()
    if not access_token:
        return None

    try:
        dbx = dropbox.Dropbox(access_token)
        files = dbx.files_list_folder(dropbox_path).entries
        for file in files:
            if isinstance(file, dropbox.files.FileMetadata) and identificador in file.name and file.name.endswith(".csv"):
                return True
    except Exception as e:
        st.error(f"❌ Error al comprobar archivos en Dropbox: {e}")
    
    return False

# 🚀 Función principal de la aplicación
def main():
    st.set_page_config(page_title="Evaluación de Proyecto", layout="centered")

    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False
    if "encuesta_enviada" not in st.session_state:
        st.session_state.encuesta_enviada = False

    if st.session_state.encuesta_enviada:
        st.success("✅ Encuesta enviada correctamente.")
        st.session_state.authenticated = False
        st.session_state.encuesta_enviada = False
        st.stop()

    # 🔒 Autenticación
    if not st.session_state.authenticated:
        with st.form("auth_form"):
            st.markdown("### 🔒 Acceso a la encuesta")
            username_input = st.text_input("Usuario")
            password_input = st.text_input("Contraseña", type="password")
            login = st.form_submit_button("Iniciar sesión")

            if login:
                usuarios_validos = st.secrets["auth_users"]
                if username_input in usuarios_validos and password_input == usuarios_validos[username_input]:
                    st.session_state.authenticated = True
                    st.session_state.username = username_input
                else:
                    st.error("❌ Usuario o contraseña incorrectos.")
                    st.stop()
        st.stop()

    st.markdown(f"👋 Bienvenido, **{st.session_state['username']}**")

    st.markdown("<h2 style='text-align: center;'>Evaluación de Integrantes del Proyecto</h2>", unsafe_allow_html=True)

    notas_path = "/Notas.xlsx"
    dropbox_path = "/qualificacions"

    file_stream = download_from_dropbox(notas_path)
    if not file_stream:
        return
    
    try:
        df = pd.read_excel(file_stream, usecols=["IDENTIFICADOR", "NOMBRE", "PROYECTO"])
    except Exception as e:
        st.error(f"❌ Error al procesar el archivo de Dropbox: {e}")
        return

    identificador_input = st.text_input("Introduce tu IDENTIFICADOR:", max_chars=10)
    proyectos_unicos = df["PROYECTO"].unique().tolist()

    if identificador_input:
        if check_if_already_submitted(dropbox_path, identificador_input):
            st.warning("⚠️ Ya enviaste tu evaluación. Solo se permite una respuesta por persona.")
            return

    grupo_input = st.selectbox("Selecciona tu grupo de proyecto:", proyectos_unicos)

    if identificador_input and grupo_input:
        grupo_df = df[df["PROYECTO"] == grupo_input]
        dnis_del_grupo = grupo_df["IDENTIFICADOR"].astype(str).str.strip().tolist()
        identificador_normalizado = str(identificador_input).strip()

        if identificador_normalizado not in dnis_del_grupo:
            st.error("❌ El IDENTIFICADOR no pertenece al grupo de proyecto seleccionado.")
            return

        evaluaciones = []
        st.subheader("Evalúa a tus compañeros (incluyéndote a ti mismo)")
        cols = st.columns(2)

        for idx, (_, row) in enumerate(grupo_df.iterrows()):
            with cols[idx % 2]:
                nota = st.number_input(f"{row['NOMBRE']}", min_value=0.00, max_value=10.00, value=5.00, step=0.01)
                evaluaciones.append({
                    "Evaluador": identificador_normalizado,
                    "Evaluado": row['IDENTIFICADOR'],
                    "Nombre": row['NOMBRE'],
                    "Proyecto": grupo_input,
                    "Nota": nota
                })

        if st.button("Guardar Evaluaciones"):
            eval_df = pd.DataFrame(evaluaciones)
            output_csv = BytesIO()
            eval_df.to_csv(output_csv, index=False, encoding='utf-8')
            output_csv.seek(0)
            filename_csv = f"evaluacion_{identificador_normalizado}_{grupo_input}.csv"
            upload_to_dropbox(output_csv, filename_csv, dropbox_path)

            st.session_state.encuesta_enviada = True
            st.rerun()

if __name__ == "__main__":
    main()
