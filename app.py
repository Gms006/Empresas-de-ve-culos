
import zipfile
import pandas as pd
import streamlit as st
import tempfile
import os
import io
import json

from estoque_veiculos import processar_arquivos_xml
from transformadores_veiculos import gerar_estoque_fiscal, gerar_alertas_auditoria, gerar_kpis, gerar_resumo_mensal
from apuracao_fiscal import calcular_apuracao
from interface_utils import criar_aba_padrao

st.set_page_config(page_title="Painel de Veículos", layout="wide")
st.title("📦 Painel Fiscal - Veículos")

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
                        xml_paths += [os.path.join(tmpdir, name) for name in zip_ref.namelist() if name.endswith(".xml")]
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
            df_apuracao, df_detalhado = calcular_apuracao(df_estoque)

    st.success("✅ Arquivos processados com sucesso!")

    aba = st.sidebar.radio("Escolha o relatório", [
        "📦 Estoque",
        "🕵️ Auditoria",
        "📈 KPIs e Resumo",
        "🧾 Apuração Fiscal"
    ])

    if aba == "📦 Estoque":
        criar_aba_padrao("📦 Veículos em Estoque e Vendidos", df_estoque, "Data Entrada")

    elif aba == "🕵️ Auditoria":
        criar_aba_padrao("🕵️ Relatório de Alertas Fiscais", df_alertas, "Data")

    elif aba == "📈 KPIs e Resumo":
        criar_aba_padrao("📄 Resumo Mensal", df_resumo, "Mês")  # ou outro campo conforme necessidade

    elif aba == "🧾 Apuração Fiscal":
        criar_aba_padrao("📃 Apuração Resumida por Trimestre", df_apuracao, "Trimestre")
        with st.expander("📋 Ver Detalhamento por Veículo"):
            criar_aba_padrao("Detalhamento Fiscal de Vendas", df_detalhado, "Data Saída")
