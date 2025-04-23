import streamlit as st
import pandas as pd
import zipfile
import tempfile
import os
from io import BytesIO

from modules.estoque_veiculos import processar_xmls
from modules.configurador_planilha import configurar_planilha
from modules.transformadores_veiculos import (
    gerar_estoque_fiscal,
    gerar_alertas_auditoria,
    gerar_kpis,
    gerar_resumo_mensal
)
from modules.apuracao_fiscal import calcular_apuracao

# Configuração da página
st.set_page_config(page_title="Painel Fiscal de Veículos", layout="wide")
st.title("🚗 Painel Fiscal de Veículos")
st.markdown("### Upload de XMLs para análise fiscal e auditoria de veículos")

# Função utilitária para gerar Excel
def gerar_excel(df, nome_abas="Relatorio"):
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name=nome_abas[:31])
    output.seek(0)
    return output

# Upload de arquivos
uploaded_files = st.file_uploader("📤 Envie seus XMLs ou ZIP", type=["xml", "zip"], accept_multiple_files=True)

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

        df_extraido = processar_xmls(xml_paths)

        if df_extraido.empty:
            st.warning("⚠️ Nenhum dado extraído dos XMLs. Verifique os arquivos enviados.")
        else:
            df_configurado = configurar_planilha(df_extraido)

            st.success("✅ XMLs processados com sucesso!")
            st.download_button(
                label="📥 Baixar Planilha Completa",
                data=gerar_excel(df_configurado, "Extracao_Completa"),
                file_name="Extracao_Completa.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

            # Filtros Globais
            st.sidebar.header("🎛️ Filtros de Período")
            ano = st.sidebar.selectbox("Ano", options=[None] + sorted(df_configurado['Data Emissão'].dt.year.dropna().unique().tolist()))
            mes = st.sidebar.selectbox("Mês", options=[None] + sorted(df_configurado['Data Emissão'].dt.month.dropna().unique().tolist()))

            if ano:
                df_configurado = df_configurado[df_configurado['Data Emissão'].dt.year == ano]
            if mes:
                df_configurado = df_configurado[df_configurado['Data Emissão'].dt.month == mes]

            if 'Tipo Nota' in df_configurado.columns:
                df_entrada = df_configurado[df_configurado['Tipo Nota'] == 'Entrada'].copy()
                df_saida = df_configurado[df_configurado['Tipo Nota'] == 'Saída'].copy()

                df_estoque = gerar_estoque_fiscal(df_entrada, df_saida)

                st.sidebar.markdown(f"**🔹 Total Processado:** {len(df_configurado)} notas")
                st.sidebar.markdown(f"**📥 Entradas:** {len(df_entrada)}")
                st.sidebar.markdown(f"**📤 Saídas:** {len(df_saida)}")
                st.sidebar.markdown(f"**🚗 Vendidos:** {df_estoque[df_estoque['Situação'] == 'Vendido'].shape[0]}")

                abas = st.tabs(["📦 Estoque", "🕵️ Auditoria", "📈 KPIs e Resumo", "🧾 Apuração Fiscal"])

                with abas[0]:
                    st.subheader("📦 Estoque Fiscal")
                    with st.expander("🔽 Visualizar Dados"):
                        st.dataframe(df_estoque)
                    st.download_button("📥 Baixar Estoque", gerar_excel(df_estoque, "Estoque"), "Estoque.xlsx")

                with abas[1]:
                    st.subheader("🕵️ Relatório de Auditoria")
                    df_alertas = gerar_alertas_auditoria(df_entrada, df_saida)
                    if df_alertas.empty:
                        st.info("✅ Nenhuma inconsistência encontrada.")
                    else:
                        st.dataframe(df_alertas)
                        st.download_button("📥 Baixar Auditoria", gerar_excel(df_alertas, "Auditoria"), "Auditoria.xlsx")

                with abas[2]:
                    st.subheader("📊 KPIs")
                    kpis = gerar_kpis(df_estoque)
                    st.json(kpis)

                    st.subheader("📅 Resumo Mensal")
                    df_resumo = gerar_resumo_mensal(df_estoque)
                    st.dataframe(df_resumo)
                    st.download_button("📥 Baixar Resumo", gerar_excel(df_resumo, "Resumo_Mensal"), "Resumo_Mensal.xlsx")

                with abas[3]:
                    st.subheader("🧾 Apuração Fiscal")
                    df_apuracao, _ = calcular_apuracao(df_estoque)
                    if df_apuracao.empty:
                        st.info("ℹ️ Nenhuma venda registrada para apuração.")
                    else:
                        st.dataframe(df_apuracao)
                        st.download_button("📥 Baixar Apuração", gerar_excel(df_apuracao, "Apuracao"), "Apuracao_Fiscal.xlsx")
            else:
                st.error("❌ A coluna 'Tipo Nota' não foi gerada. Verifique a configuração e classificação.")
else:
    st.info("📂 Aguardando upload de arquivos XML ou ZIP.")
