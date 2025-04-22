
import streamlit as st
import pandas as pd
from estoque_veiculos_reescrito import processar_arquivos_xml
from transformadores_veiculos import gerar_estoque_fiscal, gerar_alertas_auditoria, gerar_kpis, gerar_resumo_mensal
from apuracao_fiscal import calcular_apuracao

st.title("🚗 Painel Fiscal de Veículos")

uploaded_files = st.file_uploader("Envie seus XMLs", type=["xml", "zip"], accept_multiple_files=True)

if uploaded_files:
    xml_paths = [file.name for file in uploaded_files]  # Simulação
    df_entrada, df_saida = processar_arquivos_xml(xml_paths)
    df_estoque = gerar_estoque_fiscal(df_entrada, df_saida)

    if df_saida.empty:
        st.warning("⚠️ Nenhuma nota de saída detectada. Verifique a classificação de CFOPs e destinatário.")

    st.subheader("📦 Estoque")
    st.dataframe(df_estoque)

    st.subheader("🕵️ Auditoria")
    df_alertas = gerar_alertas_auditoria(df_entrada, df_saida)
    st.dataframe(df_alertas)

    st.subheader("📈 KPIs")
    kpis = gerar_kpis(df_estoque)
    st.write(kpis)

    st.subheader("🧾 Apuração Fiscal")
    df_apuracao, _ = calcular_apuracao(df_estoque)
    if df_apuracao.empty:
        st.info("ℹ️ Nenhuma venda registrada para apuração.")
    else:
        st.dataframe(df_apuracao)
