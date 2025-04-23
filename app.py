app.py
```python
import streamlit as st
import pandas as pd
import zipfile
import tempfile
import os
import json
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

# 🔹 Seleção da Empresa
with open('config/empresas_config.json', encoding='utf-8') as f:
    empresas = json.load(f)

opcoes_empresas = {v['nome']: k for k, v in empresas.items()}
empresa_selecionada_nome = st.sidebar.selectbox("🏢 Selecione a Empresa", options=opcoes_empresas.keys())
chave_empresa = opcoes_empresas[empresa_selecionada_nome]
cnpj_empresa = empresas[chave_empresa]['cnpj_emitentes'][0]
st.sidebar.markdown(f"**CNPJ Selecionado:** `{cnpj_empresa}`")

# Função utilitária para gerar Excel
def gerar_excel(df, nome_abas="Relatorio"):
    output = BytesIO()
    df_export = df.copy()

    for col in df_export.columns:
        if pd.api.types.is_datetime64_any_dtype(df_export[col]):
            df_export[col] = df_export[col].dt.strftime('%d/%m/%Y').fillna('')
        elif df_export[col].dtype == 'O':
            df_export[col] = df_export[col].apply(lambda x: str(x) if pd.notnull(x) else '')

    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df_export.to_excel(writer, index=False, sheet_name=nome_abas[:31])
    output.seek(0)
    return output

# Upload de arquivos XML ou ZIP
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

        # Processar XMLs com base no CNPJ da empresa
        df_extraido = processar_xmls(xml_paths, cnpj_empresa)

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

            if 'Tipo Nota' in df_configurado.columns:
                df_entrada = df_configurado[df_configurado['Tipo Nota'] == 'Entrada'].copy()
                df_saida = df_configurado[df_configurado['Tipo Nota'] == 'Saída'].copy()

                df_estoque = gerar_estoque_fiscal(df_entrada, df_saida)

                abas = st.tabs(["📦 Estoque", "🕵️ Auditoria", "📈 KPIs e Resumo", "🧾 Apuração Fiscal"])

                with abas[0]:
                    st.subheader("📦 Estoque Fiscal")
                    st.dataframe(df_estoque)
                    st.download_button("📥 Baixar Estoque", gerar_excel(df_estoque, "Estoque"), "Estoque.xlsx")

                with abas[1]:
                    st.subheader("🕵️ Relatório de Auditoria")
                    df_alertas = gerar_alertas_auditoria(df_entrada, df_saida)
                    st.dataframe(df_alertas)
                    st.download_button("📥 Baixar Auditoria", gerar_excel(df_alertas, "Auditoria"), "Auditoria.xlsx")

                with abas[2]:
                    st.subheader("📊 KPIs")
                    kpis = gerar_kpis(df_estoque)
                    st.json(kpis)

                    st.subheader("📅 Resumo Mensal")
                    df_resumo = gerar_resumo_mensal(df_estoque)
                    st.dataframe(df_resumo)
                    st.download_button("📥 Baixar Resumo", gerar_excel(df_resumo, "Resumo"), "Resumo_Mensal.xlsx")

                with abas[3]:
                    st.subheader("🧾 Apuração Fiscal")
                    df_apuracao, _ = calcular_apuracao(df_estoque)
                    st.dataframe(df_apuracao)
                    st.download_button("📥 Baixar Apuração", gerar_excel(df_apuracao, "Apuracao"), "Apuracao_Fiscal.xlsx")
            else:
                st.error("❌ A coluna 'Tipo Nota' não foi gerada. Verifique a configuração e classificação.")
else:
    st.info("📂 Aguardando upload de arquivos XML ou ZIP.")
