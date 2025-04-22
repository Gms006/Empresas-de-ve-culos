
import zipfile
import pandas as pd
import streamlit as st
import tempfile
import os
import io
import json

from estoque_veiculos import processar_arquivos_xml
from transformadores_veiculos import gerar_estoque_fiscal, gerar_alertas_auditoria, gerar_kpis, gerar_resumo_mensal

# === CARREGAR FORMATO PARA FORMATAR EXIBIÇÃO E EXPORTAÇÃO ===
with open("formato_colunas.json", "r", encoding="utf-8") as f:
    formato = json.load(f)

# === FORMATADOR PARA EXIBIÇÃO NO SITE ===
def formatar_df_exibicao(df):
    df = df.copy()
    for col in df.columns:
        if any(key in col for key in formato.get("moeda", [])):
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0.0)
            df[col] = df[col].apply(lambda x: f"R$ {x:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
        elif any(key in col for key in formato.get("percentual", [])):
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0.0)
            df[col] = df[col].apply(lambda x: f"{x:.2f}%")
        elif col in formato.get("inteiro", []):
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0).astype(int)
    return df

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

            if df_estoque.empty or "Situação" not in df_estoque.columns:
                st.warning("⚠️ Nenhum veículo identificado nos arquivos XML enviados.")
                st.stop()

            df_alertas = gerar_alertas_auditoria(df_entrada, df_saida)
            kpis = gerar_kpis(df_estoque)
            df_resumo = gerar_resumo_mensal(df_estoque)

    st.success("✅ Arquivos processados com sucesso!")

    # === INTERFACE ===
    aba = st.sidebar.radio("Escolha o relatório", ["📦 Estoque", "🕵️ Auditoria", "📈 KPIs e Resumo"])

    def exibir_tabela(titulo, df):
        st.subheader(titulo)
        st.dataframe(formatar_df_exibicao(df), use_container_width=True)

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
        workbook = writer.book
        real_fmt = workbook.add_format({"num_format": "R$ #,##0.00"})
        pct_fmt = workbook.add_format({"num_format": "0.00%"})
        text_fmt = workbook.add_format({"num_format": "@"})
        int_fmt = workbook.add_format({"num_format": "0"})

        abas = {
            "Entradas": df_entrada,
            "Saídas": df_saida,
            "Estoque": df_estoque,
            "Auditoria": df_alertas,
            "Resumo": df_resumo,
        }

        for aba_nome, df in abas.items():
            df.to_excel(writer, sheet_name=aba_nome, index=False)
            worksheet = writer.sheets[aba_nome]
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

    st.download_button(
        label="📥 Baixar Relatório Completo",
        data=output.getvalue(),
        file_name="relatorio_completo_veiculos.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
