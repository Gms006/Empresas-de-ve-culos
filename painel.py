
"""Streamlit dashboard reproducing the approved layout"""
import streamlit as st
import pandas as pd
import numpy as np
from pathlib import Path


def load_data():
    np.random.seed(42)
    months = list(range(1, 13))
    years = [2024, 2025]
    vendas = []
    for year in years:
        for month in months:
            for prod in range(1, 6):
                vendas.append({
                    "Produto": f"Carro {prod}",
                    "Valor": np.random.randint(50000, 150000),
                    "Ano": year,
                    "Mes": month,
                })
    df_vendas = pd.DataFrame(vendas)

    estoque = []
    for year in years:
        for month in months:
            for prod in range(1, 6):
                estoque.append({
                    "Produto": f"Carro {prod}",
                    "Estoque (dias)": np.random.randint(30, 200),
                    "Ano": year,
                    "Mes": month,
                })
    df_estoque = pd.DataFrame(estoque)
    return df_vendas, df_estoque


def main():
    st.set_page_config(
        page_title="Dashboard Neto Contabilidade",
        layout="wide",
    )

    logo_path = Path("config/logo.png")
    df_vendas, df_estoque = load_data()

    st.markdown(
        """
        <style>
            body {background-color:#233143; color:#ffffff; font-family:Montserrat, Arial, sans-serif;}
            .top-bar {background-color:#1a2536; padding:10px 25px; display:flex; align-items:center; justify-content:space-between;}
            .top-title{display:flex; flex-direction:column; margin-left:15px;}
            .top-title h1{margin:0; font-size:32px; font-weight:700;}
            .top-title span.neto{color:#ffffff;}
            .top-title span.contab{color:#d1d5db;}
            .sub-title{font-size:14px; color:#d1d5db; margin-top:-4px;}
            .nav-menu{display:flex; align-items:center; gap:20px;}
            .nav-menu a{color:#ffffff; text-decoration:none; font-size:16px;}
            .nav-menu button{background-color:#1f2937; border:none; padding:6px 15px; border-radius:5px; color:#ffffff; cursor:pointer;}
            .nav-menu button:hover{background-color:#374151;}
            .hamburger{width:22px; height:2px; background:#ffffff; position:relative;}
            .hamburger:before,.hamburger:after{content:""; position:absolute; left:0; width:22px; height:2px; background:#ffffff;}
            .hamburger:before{top:-6px;} .hamburger:after{top:6px;}
            .kpi-card{background-color:#1a2536; border-radius:8px; padding:20px; box-shadow:0 2px 4px rgba(0,0,0,0.3); color:#f1f1f1; text-align:center;}
            .kpi-title{font-size:16px; color:#d1d5db;}
            .kpi-value{font-size:28px; color:#ffd700; margin-top:5px;}
            .sidebar-title{color:#ffd700; font-size:20px; margin-bottom:10px;}
            .styled-table tbody tr:nth-child(even){background-color:#2f4159;}
            .styled-table tbody tr:nth-child(odd){background-color:#233143;}
            .alert-card{background-color:#1a2536; border-radius:8px; padding:20px; text-align:center; color:#f1f1f1;}
            .alert-title{font-size:16px; color:#d1d5db; margin-bottom:10px;}
            .alert-badge{display:inline-block; width:60px; height:60px; line-height:60px; border-radius:50%; background-color:#ffd700; color:#1a2536; font-size:24px; font-weight:bold;}
        </style>
        """,
        unsafe_allow_html=True,
    )

    # Sidebar filters
    with st.sidebar:
        st.image(logo_path, use_column_width=False)
        st.markdown("<div class='sidebar-title'>Filtros</div>", unsafe_allow_html=True)
        anos = sorted(df_vendas["Ano"].unique())
        meses_num = sorted(df_vendas["Mes"].unique())
        mes_labels = [
            "Janeiro",
            "Fevereiro",
            "Março",
            "Abril",
            "Maio",
            "Junho",
            "Julho",
            "Agosto",
            "Setembro",
            "Outubro",
            "Novembro",
            "Dezembro",
        ]
        ano = st.selectbox("Ano", anos)
        mes = st.selectbox("Mês", meses_num, format_func=lambda x: mes_labels[x-1])

    vendas_filtrado = df_vendas[(df_vendas["Ano"] == ano) & (df_vendas["Mes"] == mes)]
    estoque_filtrado = df_estoque[(df_estoque["Ano"] == ano) & (df_estoque["Mes"] == mes)]

    total_saidas = vendas_filtrado["Valor"].sum()
    total_entradas = total_saidas * 0.9
    lucro = total_saidas - total_entradas
    estoque_atual = estoque_filtrado["Estoque (dias)"].mean()

    # Top bar
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
            unsafe_allow_html=True,
        )

    # KPI cards
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.markdown(
            f"<div class='kpi-card'><div class='kpi-title'>Total de Entradas</div><div class='kpi-value'>R$ {total_entradas:,.0f}</div></div>",
            unsafe_allow_html=True,
        )
    with c2:
        st.markdown(
            f"<div class='kpi-card'><div class='kpi-title'>Total de Saídas</div><div class='kpi-value'>R$ {total_saidas:,.0f}</div></div>",
            unsafe_allow_html=True,
        )
    with c3:
        st.markdown(
            f"<div class='kpi-card'><div class='kpi-title'>Lucro</div><div class='kpi-value'>R$ {lucro:,.0f}</div></div>",
            unsafe_allow_html=True,
        )
    with c4:
        st.markdown(
            f"<div class='kpi-card'><div class='kpi-title'>Estoque Atual ({mes_labels[mes-1]}/{ano})</div><div class='kpi-value'>{estoque_atual:.0f} dias</div></div>",
            unsafe_allow_html=True,
        )

    c_left, c_right = st.columns([2, 1])

    with c_left:
        t1, t2 = st.columns(2)
        with t1:
            st.markdown("### Produtos Vendidos")
            st.table(
                vendas_filtrado[["Produto", "Valor"]]
                .rename(columns={"Valor": "Valor (R$)"})
                .style.set_table_attributes('class="styled-table"')
            )
        with t2:
            st.markdown("### Estoque Parado")
            st.table(
                estoque_filtrado[["Produto", "Estoque (dias)"]]
                .style.set_table_attributes('class="styled-table"')
            )

    with c_right:
        st.markdown("### Alertas Fiscais")
        num_alertas = int((estoque_filtrado["Estoque (dias)"] > 150).sum())
        st.markdown(
            f"<div class='alert-card'><div class='alert-title'>Alertas Fiscais</div><div class='alert-badge'>{num_alertas}</div></div>",
            unsafe_allow_html=True,
        )
        alertas = estoque_filtrado[estoque_filtrado["Estoque (dias)"] > 150].copy()
        alertas.rename(columns={"Estoque (dias)": "DDV"}, inplace=True)
        st.table(
            alertas[["Produto", "DDV"]]
            .rename(columns={"Produto": "Estoque Parado"})
            .style.set_table_attributes('class="styled-table"')
        )

if __name__ == "__main__":
    main()
