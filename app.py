import streamlit as st
import pandas as pd
import dropbox
from io import BytesIO

def download_from_dropbox(dropbox_token, dropbox_path):
    dbx = dropbox.Dropbox(dropbox_token)
    _, res = dbx.files_download(dropbox_path)
    return BytesIO(res.content)

def upload_to_dropbox(file_content, filename, dropbox_token, dropbox_path):
    dbx = dropbox.Dropbox(dropbox_token)
    dbx.files_upload(file_content.getvalue(), f"{dropbox_path}/{filename}", mode=dropbox.files.WriteMode("overwrite"))
    st.success(f"El archivo {filename} se ha subido a Dropbox correctamente.")

def check_if_already_submitted(dropbox_token, dropbox_path, identificador):
    dbx = dropbox.Dropbox(dropbox_token)
    try:
        files = dbx.files_list_folder(dropbox_path).entries
        for file in files:
            if isinstance(file, dropbox.files.FileMetadata) and identificador in file.name and file.name.endswith(".csv"):
                return True
    except Exception as e:
        st.error(f"Error al comprobar archivos en Dropbox: {e}")
    return False

def main():
    st.set_page_config(page_title="Evaluación de Proyecto", layout="centered")

    # Inicializamos el estado si no existe
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False
    if "encuesta_enviada" not in st.session_state:
        st.session_state.encuesta_enviada = False

    # Si la encuesta ya se ha enviado, mostramos el mensaje y reiniciamos estado
    if st.session_state.encuesta_enviada:
        st.success("✅ Encuesta realizada satisfactoriamente !!!")
        st.session_state.authenticated = False
        st.session_state.encuesta_enviada = False
        st.stop()

    # Autenticación
    if not st.session_state.authenticated:
        with st.form("auth_form"):
            st.markdown("### 🔒 Acceso a la encuesta")
            username_input = st.text_input("Usuario")
            password_input = st.text_input("Contraseña", type="password")
            login = st.form_submit_button("Iniciar sesión")

            if login:
                if username_input == st.secrets["auth"]["username"] and password_input == st.secrets["auth"]["password"]:
                    st.session_state.authenticated = True
                else:
                    st.error("❌ No tienes autorización para acceder a la encuesta.")
                    st.stop()
        st.stop()

    # LOGOS y TÍTULO (solo si ya estás autenticado)
    col1, _, col3 = st.columns([5, 2, 1])
    with col1:
        st.image("https://www.upc.edu/comunicacio/ca/identitat/descarrega-arxius-grafics/fitxers-marca-principal/upc-positiu-p3005.png", width=150)
    with col3:
        st.image("https://ideai.upc.edu/ca/shared/ideai_logo.png", width=80)

    st.markdown("<h2 style='text-align: center;'>Evaluación de Integrantes del Proyecto</h2>", unsafe_allow_html=True)

    # Lógica principal de la encuesta
    dropbox_token = st.secrets["DROPBOX_ACCESS_TOKEN"]
    notas_path = "/Notas.xlsx"
    dropbox_path = "/qualificacions"

    try:
        file_stream = download_from_dropbox(dropbox_token, notas_path)
        df = pd.read_excel(file_stream, usecols=["DNI", "NOMBRE", "PROYECTO"])
    except Exception as e:
        st.error(f"Error al descargar el archivo de Dropbox: {e}")
        return

    identificador_input = st.text_input("Introduce tu Identificador:", max_chars=10)
    proyectos_unicos = df["PROYECTO"].unique().tolist()

    if identificador_input:
        ya_enviado = check_if_already_submitted(dropbox_token, dropbox_path, identificador_input)
        if ya_enviado:
            st.warning("Ya has enviado tu evaluación. Solo se permite una respuesta por persona.")
            return

    grupo_input = st.selectbox("Selecciona tu grupo de proyecto:", proyectos_unicos)

    if identificador_input and grupo_input:
        grupo_df = df[df["PROYECTO"] == grupo_input]
        dnis_del_grupo = grupo_df["DNI"].astype(str).str.strip().tolist()
        identificador_normalizado = str(identificador_input).strip()

        if identificador_normalizado not in dnis_del_grupo:
            st.error("❌ El identificador no pertenece al grupo de proyecto seleccionado.")
            return

        evaluaciones = []
        st.subheader("Evalúa a tus compañeros (incluyéndote a ti mismo)")
        cols = st.columns(2)

        for idx, (_, row) in enumerate(grupo_df.iterrows()):
            with cols[idx % 2]:
                nota = st.number_input(f"{row['NOMBRE']}", min_value=0.00, max_value=10.00, value=5.00, step=0.01)
                evaluaciones.append({
                    "Evaluador": identificador_normalizado,
                    "Evaluado": row['DNI'],
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
            upload_to_dropbox(output_csv, filename_csv, dropbox_token, dropbox_path)

            # Activamos la bandera para mostrar mensaje final y reiniciar login
            st.session_state.encuesta_enviada = True
            st.rerun()

if __name__ == "__main__":
    main()
