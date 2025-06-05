
import streamlit as st
import pandas as pd
import io
import json

# Usar importações relativas para funcionar quando ``utils`` é um pacote
from .filtros_utils import obter_anos_meses_unicos, aplicar_filtro_periodo
from .formatador_utils import (
    formatar_moeda,
    formatar_percentual,
    formatar_data_curta,
)

# Carregar configurações de formatação se existirem
try:
    with open("formato_colunas.json", "r", encoding="utf-8") as f:
        formato = json.load(f)
except FileNotFoundError:
    # Formato básico caso o arquivo não esteja disponível
    formato = {
        "moeda": ["Valor", "Lucro"],
        "percentual": ["%"],
        "inteiro": [],
        "texto": [],
    }

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
        elif any(p in col for p in ["Data", "Mês", "Trimestre"]):
            df[col] = df[col].apply(formatar_data_curta)
    return df

def criar_aba_padrao(titulo, df, coluna_data=None):
    st.subheader(titulo)
    
    # Aplicar filtro por período
    if coluna_data:
        anos, meses = obter_anos_meses_unicos(df, coluna_data)
        ano = st.sidebar.selectbox(f"Ano ({titulo})", [None] + anos, key=f"ano_{titulo}")
        mes = st.sidebar.selectbox(f"Mês ({titulo})", [None] + meses, key=f"mes_{titulo}")
        df = aplicar_filtro_periodo(df, coluna_data, ano, mes)

    df_formatado = formatar_df_exibicao(df)
    st.dataframe(df_formatado, use_container_width=True)

    # Exportação Excel individual
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:
        df_temp = df.copy()
        for col in df_temp.columns:
            if any(key in col for key in formato.get("moeda", [])):
                df_temp[col] = pd.to_numeric(df_temp[col], errors='coerce')
            elif any(key in col for key in formato.get("percentual", [])):
                df_temp[col] = pd.to_numeric(df_temp[col], errors='coerce')
            elif col in formato.get("inteiro", []):
                df_temp[col] = pd.to_numeric(df_temp[col], errors='coerce').fillna(0).astype(int)
            elif any(p in col for p in ["Data", "Mês", "Trimestre"]):
                df_temp[col] = pd.to_datetime(df_temp[col], errors='coerce').dt.strftime("%d/%m/%Y")

        df_temp.to_excel(writer, sheet_name=titulo[:31], index=False)
        worksheet = writer.sheets[titulo[:31]]
        for i, col in enumerate(df_temp.columns):
            if any(key in col for key in formato.get("moeda", [])):
                worksheet.set_column(i, i, 14, writer.book.add_format({"num_format": "R$ #,##0.00"}))
            elif any(key in col for key in formato.get("percentual", [])):
                worksheet.set_column(i, i, 12, writer.book.add_format({"num_format": "0.00%"}))
            elif any(key in col for key in formato.get("texto", [])):
                worksheet.set_column(i, i, 20, writer.book.add_format({"num_format": "@"}))
            elif col in formato.get("inteiro", []):
                worksheet.set_column(i, i, 10, writer.book.add_format({"num_format": "0"}))
            else:
                worksheet.set_column(i, i, 18)

    st.download_button(
        label=f"📥 Baixar {titulo}.xlsx",
        data=buffer.getvalue(),
        file_name=f"{titulo}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
