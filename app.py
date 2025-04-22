
# app_corrigido.py - Painel Streamlit para Estoque de Veículos com melhorias

import zipfile
import pandas as pd
import streamlit as st
import tempfile
import os
import io
import json

from estoque_veiculos import processar_arquivos_xml
from transformadores_veiculos_corrigido import gerar_estoque_fiscal, gerar_alertas_auditoria, gerar_kpis, gerar_resumo_mensal

# === FORMATADORES COM JSON ===
with open("formato_colunas.json", "r", encoding="utf-8") as f:
    formato = json.load(f)
with open("ordem_colunas.json", "r", encoding="utf-8") as f:
    ordem = json.load(f)

def formatar_df_exibicao(df):
    df = df.copy()
    colunas = df.columns.tolist()

    if 'ordem_preferida' in ordem:
        ordem_padrao = [col for col in ordem['ordem_preferida'] if col in colunas]
        extras = [col for col in colunas if col not in ordem_padrao]
        df = df[ordem_padrao + extras]

    for col in formato.get("texto", []):
        if col in df.columns:
            df[col] = df[col].astype(str)

    for col in formato.get("moeda", []):
        for c in df.columns:
            if col in c:
                df[c] = pd.to_numeric(df[c], errors='coerce').fillna(0.0)
                df[c] = df[c].apply(lambda x: f"R$ {x:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))

    for col in formato.get("percentual", []):
        for c in df.columns:
            if col in c:
                df[c] = pd.to_numeric(df[c], errors='coerce').fillna(0.0)
                df[c] = df[c].apply(lambda x: f"{x:.2f}%")

    for col in formato.get("inteiro", []):
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0).astype(int)

    return df

st.set_page_config(page_title="Painel de Estoque de Veículos", layout="wide")
st.title("📦 Painel Fiscal - Veículos")

st.markdown("""
Este painel permite o upload de arquivos XML (ou ZIP com XMLs), extração automática de dados e análise fiscal/comercial de veículos.
""")

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
                        for name in zip_ref.namelist():
                            if name.endswith(".xml"):
                                xml_paths.append(os.path.join(tmpdir, name))
                elif file.name.endswith(".xml"):
                    xml_paths.append(filepath)

            df_entrada, df_saida = processar_arquivos_xml(xml_paths)

            if df_entrada.empty and df_saida.empty:
                st.warning("⚠️ Nenhum dado encontrado nos arquivos XML.")
                st.stop()

            if "Tipo Produto" not in df_entrada.columns or "Tipo Produto" not in df_saida.columns:
                st.error("❌ Estrutura inválida. Verifique se os XMLs são de veículos.")
                st.stop()

            df_estoque = gerar_estoque_fiscal(df_entrada, df_saida)

            if df_estoque.empty:
                st.warning("⚠️ Nenhum veículo encontrado nos XMLs enviados.")
                st.stop()

            df_alertas = gerar_alertas_auditoria(df_entrada, df_saida)
            kpis = gerar_kpis(df_estoque)
            df_resumo = gerar_resumo_mensal(df_estoque)

    st.success("✅ Arquivos processados com sucesso!")

    aba = st.sidebar.radio("Escolha o relatório", ["📦 Estoque", "🕵️ Auditoria", "📈 KPIs e Resumo"])

    if aba == "📦 Estoque":
        st.subheader("📦 Veículos em Estoque e Vendidos")
        st.dataframe(formatar_df_exibicao(df_estoque), use_container_width=True)

    elif aba == "🕵️ Auditoria":
        st.subheader("🕵️ Relatório de Alertas Fiscais")
        st.dataframe(formatar_df_exibicao(df_alertas), use_container_width=True)

    elif aba == "📈 KPIs e Resumo":
        st.subheader("📊 Indicadores de Desempenho")
        col1, col2, col3 = st.columns(3)
        col1.metric("Total Vendido (R$)", f"R$ {kpis['Total Vendido (R$)']:,.2f}")
        col2.metric("Lucro Total (R$)", f"R$ {kpis['Lucro Total (R$)']:,.2f}")
        col3.metric("Estoque Atual (R$)", f"R$ {kpis['Estoque Atual (R$)']:,.2f}")

        st.subheader("📄 Resumo Mensal")
        st.dataframe(formatar_df_exibicao(df_resumo), use_container_width=True)

    # Exportação
    output_all = io.BytesIO()
    with pd.ExcelWriter(output_all, engine='xlsxwriter') as writer:
        abas = {
            "Entradas": formatar_df_exibicao(df_entrada),
            "Saídas": formatar_df_exibicao(df_saida),
            "Estoque": formatar_df_exibicao(df_estoque),
            "Auditoria": formatar_df_exibicao(df_alertas),
            "Resumo": formatar_df_exibicao(df_resumo)
        }

        workbook = writer.book
        real_fmt = workbook.add_format({"num_format": "R$ #,##0.00"})
        pct_fmt = workbook.add_format({"num_format": "0.00%"})
        text_fmt = workbook.add_format({"num_format": "@"})
        int_fmt = workbook.add_format({"num_format": "0"})

        for aba, df in abas.items():
            try:
                df.to_excel(writer, sheet_name=aba, index=False)
                worksheet = writer.sheets[aba]
                for col_num, col_name in enumerate(df.columns):
                    if any(key in col_name for key in formato.get("moeda", [])):
                        worksheet.set_column(col_num, col_num, 14, real_fmt)
                    elif any(key in col_name for key in formato.get("percentual", [])):
                        worksheet.set_column(col_num, col_num, 12, pct_fmt)
                    elif any(key in col_name for key in formato.get("texto", [])):
                        worksheet.set_column(col_num, col_num, 20, text_fmt)
                    elif col_name in formato.get("inteiro", []):
                        worksheet.set_column(col_num, col_num, 10, int_fmt)
                    else:
                        worksheet.set_column(col_num, col_num, 18)
            except Exception as e:
                st.error(f"Erro ao exportar aba '{aba}': {e}")

    st.download_button("📥 Baixar Relatório Completo", data=output_all.getvalue(), file_name="relatorio_completo_veiculos.xlsx")
