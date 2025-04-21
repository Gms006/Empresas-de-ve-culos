# app.py - Interface Streamlit para o painel de estoque fiscal

import streamlit as st
import tempfile
import zipfile
import os
from estoque_veiculos import processar_arquivos_xml

st.set_page_config(page_title="Painel de Estoque de Veículos", layout="wide")
st.title("📦 Painel Fiscal - Veículos")

st.markdown("""
Este painel permite que você envie arquivos XML (ou .zip contendo XMLs) e visualize os dados fiscais de forma organizada.
""")

# Upload de arquivos XML ou ZIP
uploaded_files = st.file_uploader(
    "Envie arquivos XML ou ZIP com XMLs",
    type=["xml", "zip"],
    accept_multiple_files=True
)

if uploaded_files:
    with st.spinner("🔍 Processando arquivos..."):
        with tempfile.TemporaryDirectory() as tmpdir:
            xml_paths = []

            for file in uploaded_files:
                filepath = os.path.join(tmpdir, file.name)
                with open(filepath, "wb") as f:
                    f.write(file.read())

                if file.name.endswith(".zip"):
                    with zipfile.ZipFile(filepath, "r") as zip_ref:
                        zip_ref.extractall(tmpdir)
                        for name in zip_ref.namelist():
                            if name.endswith(".xml"):
                                xml_paths.append(os.path.join(tmpdir, name))
                elif file.name.endswith(".xml"):
                    xml_paths.append(filepath)

            df_entrada, df_saida, df_estoque = processar_arquivos_xml(xml_paths)

    st.success("✅ Arquivos processados com sucesso!")

    # Tabelas
    st.subheader("📥 Entradas")
    st.dataframe(df_entrada, use_container_width=True)

    st.subheader("📤 Saídas")
    st.dataframe(df_saida, use_container_width=True)

    st.subheader("📦 Estoque Fiscal")
    st.dataframe(df_estoque, use_container_width=True)
