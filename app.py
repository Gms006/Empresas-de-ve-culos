# app.py - Painel Streamlit para Estoque de Veículos

import streamlit as st
import os
import tempfile
import zipfile
import pandas as pd
from estoque_veiculos import processar_arquivos_xml
from transformadores_veiculos import (
    gerar_estoque_fiscal,
    gerar_alertas_auditoria,
    gerar_kpis,
    gerar_resumo_mensal
)

st.set_page_config(page_title="Painel de Estoque de Veículos", layout="wide")
st.title("📦 Painel Fiscal - Veículos")

st.markdown("""
Este painel permite o upload de arquivos XML (ou ZIP com XMLs), extração automática de dados e análise fiscal/comercial de veículos.
""")

# Upload dos arquivos
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

            df_entrada, df_saida = processar_arquivos_xml(xml_paths)
            df_estoque = gerar_estoque_fiscal(df_entrada, df_saida)
            df_alertas = gerar_alertas_auditoria(df_entrada, df_saida)
            kpis = gerar_kpis(df_estoque)
            df_resumo = gerar_resumo_mensal(df_estoque)

    st.success("✅ Arquivos processados com sucesso!")

    aba = st.sidebar.radio("Escolha o relatório", ["📦 Estoque", "🕵️ Auditoria", "📈 KPIs e Resumo"])

    if aba == "📦 Estoque":
        st.subheader("📦 Veículos em Estoque e Vendidos")
        st.dataframe(df_estoque, use_container_width=True)

    elif aba == "🕵️ Auditoria":
        st.subheader("🕵️ Relatório de Alertas Fiscais")
        st.dataframe(df_alertas, use_container_width=True)

    elif aba == "📈 KPIs e Resumo":
        st.subheader("📊 Indicadores de Desempenho")
        col1, col2, col3 = st.columns(3)
        col1.metric("Total Vendido (R$)", f"R$ {kpis['Total Vendido (R$)']:,.2f}")
        col2.metric("Lucro Total (R$)", f"R$ {kpis['Lucro Total (R$)']:,.2f}")
        col3.metric("Estoque Atual (R$)", f"R$ {kpis['Estoque Atual (R$)']:,.2f}")

        st.markdown("### 📆 Resumo Mensal")
        st.dataframe(df_resumo, use_container_width=True)

    # Download da planilha consolidada
    def to_excel(dfs: dict):
        from io import BytesIO
        output = BytesIO()
        with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
            for name, df in dfs.items():
                df.to_excel(writer, sheet_name=name[:31], index=False)
        output.seek(0)
        return output

    st.download_button(
        "📥 Baixar Relatório Consolidado (.xlsx)",
        data=to_excel({
            "Entradas": df_entrada,
            "Saidas": df_saida,
            "Estoque": df_estoque,
            "Auditoria": df_alertas,
            "ResumoMensal": df_resumo
        }),
        file_name="relatorio_veiculos.xlsx"
    )
