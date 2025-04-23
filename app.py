import streamlit as st
import pandas as pd
from io import BytesIO

# Configuração da página
st.set_page_config(page_title="Painel Fiscal de Veículos", layout="wide")

# Simulação de dados de estoque
# Substitua esta parte pelo carregamento real dos dados
df_estoque = pd.DataFrame({
    'Chassi': ['ABC123', 'DEF456', 'GHI789'],
    'Placa': ['XYZ-1234', 'UVW-5678', 'RST-9012'],
    'Modelo': ['Modelo A', 'Modelo B', 'Modelo C'],
    'Valor Total': [50000, 60000, 55000],
    'Data Emissão': ['2025-01-10', '2025-02-15', '2025-03-20'],
    'Data Saída': ['2025-01-15', '2025-02-20', '2025-03-25'],
    'CFOP': ['5101', '6101', '1101']
})

# Aba: Estoque Fiscal
st.title("📦 Estoque Fiscal")

# Exibição do DataFrame
st.dataframe(df_estoque, use_container_width=True)

# Criação do botão de download
def gerar_planilha_excel(df):
    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='Estoque Fiscal')
        writer.close()
    return buffer.getvalue()

excel_data = gerar_planilha_excel(df_estoque)

st.download_button(
    label="📥 Baixar Planilha Completa",
    data=excel_data,
    file_name="estoque_fiscal.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
)
