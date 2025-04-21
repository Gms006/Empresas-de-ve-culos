# app.py - Painel Streamlit para Estoque de Veículos

import zipfile
import pandas as pd
import streamlit as st
import tempfile
import os
from estoque_veiculos import processar_arquivos_xml
from transformadores_veiculos import (
    gerar_estoque_fiscal,
    gerar_alertas_auditoria,
    gerar_kpis,
    gerar_resumo_mensal
)

# === FORMATADORES DE VISUALIZAÇÃO ===
def formatar_df_exibicao(df):
    df = df.copy()
    col_cnpj = [col for col in df.columns if "CNPJ" in col]
    col_reais = [col for col in df.columns if "Valor" in col or "Total" in col]
    col_pct = [col for col in df.columns if "Alíquota" in col]

    for col in col_cnpj:
        df[col] = df[col].astype(str)

    for col in col_reais:
        df[col] = df[col].apply(lambda x: f"R$ {x:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))

    for col in col_pct:
        df[col] = df[col].apply(lambda x: f"{x:.2f}%")

    return df
    col_reais = [col for col in df.columns if "Valor" in col or "Total" in col]
    col_pct = [col for col in df.columns if "Alíquota" in col]

    for col in col_cnpj:
        df[col] = df[col].astype(str)

    for col in col_reais:
        df[col] = df[col].apply(lambda x: f"R$ {x:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))

    for col in col_pct:
        df[col] = df[col].apply(lambda x: f"{x:.2f}%")

    return df

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
# Exportar para Excel com formatação
        import io
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df_estoque.to_excel(writer, sheet_name="Estoque", index=False)
            df_alertas.to_excel(writer, sheet_name="Auditoria", index=False)
            df_resumo.to_excel(writer, sheet_name="Resumo", index=False)

            workbook = writer.book
            real_fmt = workbook.add_format({"num_format": "R$ #,##0.00"})
            pct_fmt = workbook.add_format({"num_format": "0.00%"})
            text_fmt = workbook.add_format({"num_format": "@"})

            for sheet in ["Estoque", "Auditoria", "Resumo"]:
                worksheet = writer.sheets[sheet]
                for col_num, col_name in enumerate(df_estoque.columns):
                    if "R$" in col_name or "Valor" in col_name or "Total" in col_name or "Lucro" in col_name:
                        worksheet.set_column(col_num, col_num, 14, real_fmt)
                    elif "Alíquota" in col_name:
                        worksheet.set_column(col_num, col_num, 12, pct_fmt)
                    elif "CNPJ" in col_name:
                        worksheet.set_column(col_num, col_num, 20, text_fmt)
                    else:
                        worksheet.set_column(col_num, col_num, 18)

        st.download_button("📥 Baixar Planilha Completa", data=output.getvalue(), file_name="relatorio_veiculos.xlsx")
    )
