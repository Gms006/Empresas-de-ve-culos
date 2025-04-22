
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
from filtros_utils import obter_anos_meses_unicos, aplicar_filtro_periodo
from formatador_utils import formatar_moeda, formatar_percentual

# === CARREGAR FORMATO PARA FORMATAR EXIBIÇÃO E EXPORTAÇÃO ===
with open("formato_colunas.json", "r", encoding="utf-8") as f:
    formato = json.load(f)

# === FORMATADOR PARA EXIBIÇÃO NO SITE ===
def formatar_df_exibicao(df):
    df = df.copy()
    for col in df.columns:
        if any(key in col for key in formato.get("moeda", [])):
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0.0)
            df[col] = df[col].apply(formatar_moeda)
        elif any(key in col for key in formato.get("percentual", [])):
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0.0)
            df[col] = df[col].apply(formatar_percentual)
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
            df_apuracao, df_detalhado = calcular_apuracao(df_estoque)

    st.success("✅ Arquivos processados com sucesso!")

    # === INTERFACE ===
    aba = st.sidebar.radio("Escolha o relatório", ["📦 Estoque", "🕵️ Auditoria", "📈 KPIs e Resumo", "🧾 Apuração Fiscal"])

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
        col1.metric("Total Vendido (R$)", formatar_moeda(kpis["Total Vendido (R$)"]))
        col2.metric("Lucro Total (R$)", formatar_moeda(kpis["Lucro Total (R$)"]))
        col3.metric("Estoque Atual (R$)", formatar_moeda(kpis["Estoque Atual (R$)"]))

        exibir_tabela("📄 Resumo Mensal", df_resumo)

    elif aba == "🧾 Apuração Fiscal":
        st.subheader("🧾 Apuração Tributária Trimestral")
        exibir_tabela("📃 Apuração Resumida por Trimestre", df_apuracao)
        with st.expander("📋 Ver Detalhamento por Veículo"):
            exibir_tabela("Detalhamento Fiscal de Vendas", df_detalhado)
