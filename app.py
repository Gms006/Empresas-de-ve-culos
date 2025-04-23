import streamlit as st
import pandas as pd
import zipfile
import tempfile
import os

from estoque_veiculos import processar_xmls
from configurador_planilha import configurar_planilha
from transformadores_veiculos import gerar_estoque_fiscal, gerar_alertas_auditoria, gerar_kpis, gerar_resumo_mensal
from apuracao_fiscal import calcular_apuracao

st.set_page_config(page_title="Painel Fiscal de Veículos", layout="wide")
st.title("🚗 Painel Fiscal de Veículos")

uploaded_files = st.file_uploader("Envie seus XMLs", type=["xml", "zip"], accept_multiple_files=True)

if uploaded_files:
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

        # Processar XMLs e já obter DataFrame padronizado
        df_extraido = processar_xmls(xml_paths)

        if df_extraido.empty:
            st.warning("⚠️ Nenhum dado extraído dos XMLs. Verifique os arquivos enviados.")
        else:
            # Configuração adicional (se necessário)
            df_configurado = configurar_planilha(df_extraido)

            if 'Tipo Nota' in df_configurado.columns:
                df_entrada = df_configurado[df_configurado['Tipo Nota'] == 'Entrada'].copy()
                df_saida = df_configurado[df_configurado['Tipo Nota'] == 'Saída'].copy()

                df_estoque = gerar_estoque_fiscal(df_entrada, df_saida)

                st.sidebar.header("🔎 Diagnóstico de Processamento")
                st.sidebar.write(f"**Total de Notas Processadas:** {len(df_configurado)}")
                st.sidebar.write(f"**Notas de Entrada:** {len(df_entrada)}")
                st.sidebar.write(f"**Notas de Saída:** {len(df_saida)}")
                st.sidebar.write(f"**Veículos Vendidos:** {df_estoque[df_estoque['Situação'] == 'Vendido'].shape[0]}")

                if df_saida.empty:
                    st.info("ℹ️ Nenhuma nota de saída detectada. Verifique CFOPs e destinatários.")

                aba = st.tabs(["📦 Estoque", "🕵️ Auditoria", "📈 KPIs e Resumo", "🧾 Apuração Fiscal"])

                with aba[0]:
                    st.subheader("📦 Estoque Fiscal")
                    st.dataframe(df_estoque)

                with aba[1]:
                    st.subheader("🕵️ Relatório de Auditoria")
                    df_alertas = gerar_alertas_auditoria(df_entrada, df_saida)
                    st.dataframe(df_alertas)

                with aba[2]:
                    st.subheader("📊 KPIs")
                    kpis = gerar_kpis(df_estoque)
                    st.json(kpis)

                    st.subheader("📅 Resumo Mensal")
                    df_resumo = gerar_resumo_mensal(df_estoque)
                    st.dataframe(df_resumo)

                with aba[3]:
                    st.subheader("🧾 Apuração Fiscal")
                    df_apuracao, _ = calcular_apuracao(df_estoque)
                    if df_apuracao.empty:
                        st.info("ℹ️ Nenhuma venda registrada para apuração.")
                    else:
                        st.dataframe(df_apuracao)
            else:
                st.error("❌ A coluna 'Tipo Nota' não foi gerada. Verifique a configuração e classificação.")
