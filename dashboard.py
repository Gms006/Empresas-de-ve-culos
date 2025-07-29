import streamlit as st
import pandas as pd
import numpy as np
from pathlib import Path

# Page config
st.set_page_config(page_title="Dashboard Neto Contabilidade", layout="wide")

# Load logo
logo_path = Path('config/logo.png')

# Custom CSS
st.markdown('''
<style>
body {
    background-color: #233143;
    color: #ffffff;
    font-family: "Montserrat", Arial, sans-serif;
}

/* Top Bar */
.top-bar {
    background-color: #1a2536;
    padding: 10px 25px;
    display: flex;
    align-items: center;
    justify-content: space-between;
}
.top-title {
    display: flex;
    flex-direction: column;
    margin-left: 15px;
}
.top-title h1 {
    margin: 0;
    font-size: 32px;
    font-weight: 700;
}
.top-title span.neto {
    color: #ffffff;
}
.top-title span.contab {
    color: #d1d5db;
}
.sub-title {
    font-size: 14px;
    color: #d1d5db;
    margin-top: -4px;
}
.nav-menu {
    display: flex;
    align-items: center;
    gap: 20px;
}
.nav-menu a {
    color: #ffffff;
    text-decoration: none;
    font-size: 16px;
}
.nav-menu button {
    background-color: #1f2937;
    border: none;
    padding: 6px 15px;
    border-radius: 5px;
    color: #ffffff;
    cursor: pointer;
}
.nav-menu button:hover {
    background-color: #374151;
}
.hamburger {
    width: 22px;
    height: 2px;
    background: #ffffff;
    position: relative;
}
.hamburger:before,
.hamburger:after {
    content: "";
    position: absolute;
    left: 0;
    width: 22px;
    height: 2px;
    background: #ffffff;
}
.hamburger:before { top: -6px; }
.hamburger:after { top: 6px; }

/* KPI Cards */
.kpi-card {
    background-color: #1a2536;
    border-radius: 8px;
    padding: 20px;
    box-shadow: 0 2px 4px rgba(0,0,0,0.3);
    color: #f1f1f1;
    text-align: center;
}
.kpi-title { font-size: 16px; color: #d1d5db; }
.kpi-value { font-size: 28px; color: #ffd700; margin-top: 5px; }

/* Sidebar */
.sidebar-title { color: #ffd700; font-size: 20px; margin-bottom: 10px; }

/* Tables */
.styled-table tbody tr:nth-child(even) {
    background-color: #2f4159;
}
.styled-table tbody tr:nth-child(odd) {
    background-color: #233143;
}
</style>
''', unsafe_allow_html=True)

# Top bar layout
with st.container():
    st.markdown(
        f"""
        <div class='top-bar'>
            <div style='display:flex;align-items:center;'>
                <img src='{logo_path.as_posix()}' style='height:60px;'>
                <div class='top-title'>
                    <h1><span class='neto'>NETO</span> <span class='contab'>CONTABILIDADE</span></h1>
                    <div class='sub-title'>VILECRDE</div>
                </div>
            </div>
            <div class='nav-menu'>
                <a href='#'>MAPA DE VENDAS</a>
                <button>Relatórios</button>
                <div class='hamburger'></div>
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )

# Sidebar filters
with st.sidebar:
    st.markdown("<div class='sidebar-title'>Filtros</div>", unsafe_allow_html=True)
    anos = [2024, 2025]
    meses = ["Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho"]
    ano = st.selectbox("Ano", anos)
    mes = st.selectbox("Mês", meses)

# Sample data
np.random.seed(1)
df_vendas = pd.DataFrame({
    'Produto': [f'Carro {i}' for i in range(1,6)],
    'Valor (R$)': np.random.randint(50000,150000,size=5)
})

df_estoque = pd.DataFrame({
    'Estoque (dias)': np.random.randint(30,200,size=5)
})

# KPIs values
total_entradas = df_vendas['Valor (R$)'].sum() * 1.1
total_saidas = df_vendas['Valor (R$)'].sum()
lucro = total_saidas - total_entradas
estoque_atual = df_estoque['Estoque (dias)'].mean()

# KPI cards
c1, c2, c3, c4 = st.columns(4)
with c1:
    st.markdown(f"<div class='kpi-card'><div class='kpi-title'>Total de Entradas</div><div class='kpi-value'>R$ {total_entradas:,.0f}</div></div>", unsafe_allow_html=True)
with c2:
    st.markdown(f"<div class='kpi-card'><div class='kpi-title'>Total de Saídas</div><div class='kpi-value'>R$ {total_saidas:,.0f}</div></div>", unsafe_allow_html=True)
with c3:
    st.markdown(f"<div class='kpi-card'><div class='kpi-title'>Lucro</div><div class='kpi-value'>R$ {lucro:,.0f}</div></div>", unsafe_allow_html=True)
with c4:
    st.markdown(f"<div class='kpi-card'><div class='kpi-title'>Estoque Atual ({mes}/{ano})</div><div class='kpi-value'>{estoque_atual:.0f} dias</div></div>", unsafe_allow_html=True)

# Central tables
c_left, c_right = st.columns([2,1])

with c_left:
    t1, t2 = st.columns(2)
    with t1:
        st.markdown("### Produtos Vendidos")
        st.table(df_vendas.style.set_table_attributes('class="styled-table"'))
    with t2:
        st.markdown("### Estoque Parado")
        st.table(df_estoque.style.set_table_attributes('class="styled-table"'))

with c_right:
    st.markdown("### Alertas Fiscais")
    num_alertas = int(df_estoque['Estoque (dias)'].iloc[0] / 10)
    st.markdown(f"<div class='kpi-card'><div class='kpi-title'>Alertas Fiscais</div><div class='kpi-value'>{num_alertas}</div></div>", unsafe_allow_html=True)
    st.table(df_estoque.head(3).style.set_table_attributes('class="styled-table"'))
