
import zipfile
import pandas as pd
import streamlit as st
import tempfile
import os
import io
import json

from estoque_veiculos import processar_arquivos_xml
from transformadores_veiculos import gerar_estoque_fiscal, gerar_alertas_auditoria, gerar_kpis, gerar_resumo_mensal

# === CONFIGURAÇÕES INICIAIS ===
st.set_page_config(page_title="Painel de Veículos", layout="wide")
st.title("📦 Painel Fiscal - Veículos")

# === UPLOAD DE ARQUIVOS ===
uploaded_files = st.file_uploader("Envie arquivos XML ou ZIP com XMLs", type=["xml", "zip"], accept_multiple_files=True)

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
                        xml_paths += [
                            os.path.join(tmpdir, name)
                            for name in zip_ref.namelist()
                            if name.endswith(".xml")
                        ]
                elif file.name.endswith(".xml"):
                    xml_paths.append(filepath)

            df_entrada, df_saida = processar_arquivos_xml(xml_paths)
            df_estoque = gerar_estoque_fiscal(df_entrada, df_saida)
            df_alertas = gerar_alertas_auditoria(df_entrada, df_saida)
            kpis = gerar_kpis(df_estoque)
            df_resumo = gerar_resumo_mensal(df_estoque)

    st.success("✅ Arquivos processados com sucesso!")

    # === INTERFACE ===
    aba = st.sidebar.radio("Escolha o relatório", ["📦 Estoque", "🕵️ Auditoria", "📈 KPIs e Resumo"])

    def exibir_tabela(titulo, df):
        st.subheader(titulo)
        st.dataframe(df, use_container_width=True)

    if aba == "📦 Estoque":
        exibir_tabela("📦 Veículos em Estoque e Vendidos", df_estoque)

    elif aba == "🕵️ Auditoria":
        exibir_tabela("🕵️ Relatório de Alertas Fiscais", df_alertas)

    elif aba == "📈 KPIs e Resumo":
        st.subheader("📊 Indicadores de Desempenho")
        col1, col2, col3 = st.columns(3)
        col1.metric("Total Vendido (R$)", f"R$ {kpis['Total Vendido (R$)']:,.2f}")
        col2.metric("Lucro Total (R$)", f"R$ {kpis['Lucro Total (R$)']:,.2f}")
        col3.metric("Estoque Atual (R$)", f"R$ {kpis['Estoque Atual (R$)']:,.2f}")

        exibir_tabela("📄 Resumo Mensal", df_resumo)

    # === DOWNLOAD EXCEL ===
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
        abas = {
            "Entradas": df_entrada,
            "Saídas": df_saida,
            "Estoque": df_estoque,
            "Auditoria": df_alertas,
            "Resumo": df_resumo,
        }
        for aba_nome, df in abas.items():
            df.to_excel(writer, sheet_name=aba_nome, index=False)

    st.download_button(
        label="📥 Baixar Relatório Completo",
        data=output.getvalue(),
        file_name="relatorio_completo_veiculos.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
