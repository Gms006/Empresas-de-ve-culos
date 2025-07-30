import streamlit as st
import pandas as pd
import json
import os
import zipfile
import tempfile
from pathlib import Path

from modules.estoque_veiculos import processar_xmls
from modules.configurador_planilha import configurar_planilha
from modules.transformadores_veiculos import (
    gerar_estoque_fiscal,
    gerar_alertas_auditoria,
    gerar_kpis,
    gerar_resumo_mensal,
)
from utils.google_drive_utils import criar_servico_drive, baixar_xmls_empresa_zip, ROOT_FOLDER_ID
from utils.filtros_utils import obter_anos_meses_unicos, aplicar_filtro_periodo
from utils.formatador_utils import formatar_moeda
from utils.interface_utils import formatar_df_exibicao


def _init_session():
    if "processado" not in st.session_state:
        st.session_state.processado = False
        st.session_state.df_configurado = pd.DataFrame()
        st.session_state.df_estoque = pd.DataFrame()
        st.session_state.df_alertas = pd.DataFrame()
        st.session_state.df_resumo = pd.DataFrame()
        st.session_state.kpis = {}


def _carregar_empresas():
    path = Path("config/empresas_config.json")
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _processar_arquivos(xml_paths, cnpj_empresa):
    if not xml_paths:
        return pd.DataFrame()
    df = processar_xmls(xml_paths, cnpj_empresa)
    return configurar_planilha(df)


def _executar_pipeline(xml_paths, cnpj_empresa):
    df_config = _processar_arquivos(xml_paths, cnpj_empresa)
    if df_config.empty:
        st.warning("Nenhum dado processado.")
        return

    df_entrada = df_config[df_config["Tipo Nota"] == "Entrada"].copy()
    df_saida = df_config[df_config["Tipo Nota"] == "Saída"].copy()

    df_estoque = gerar_estoque_fiscal(df_entrada, df_saida)
    df_alertas = gerar_alertas_auditoria(df_entrada, df_saida)
    df_resumo = gerar_resumo_mensal(df_estoque)
    kpis = gerar_kpis(df_estoque)

    st.session_state.df_configurado = df_config
    st.session_state.df_estoque = df_estoque
    st.session_state.df_alertas = df_alertas
    st.session_state.df_resumo = df_resumo
    st.session_state.kpis = kpis
    st.session_state.processado = True


def _upload_manual(files):
    with tempfile.TemporaryDirectory() as tmpdir:
        paths = []
        for f in files:
            dest = os.path.join(tmpdir, f.name)
            with open(dest, "wb") as out:
                out.write(f.read())
            if f.name.lower().endswith(".zip"):
                try:
                    with zipfile.ZipFile(dest, "r") as zf:
                        for name in zf.namelist():
                            if name.lower().endswith(".xml"):
                                zf.extract(name, tmpdir)
                                paths.append(os.path.join(tmpdir, name))
                except Exception as exc:
                    st.error(f"Erro ao extrair {f.name}: {exc}")
            else:
                paths.append(dest)
        return paths


def main():
    st.set_page_config(page_title="Dashboard Neto Contabilidade", layout="wide")
    _init_session()

    LOGO = Path("config/logo.png")

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

    empresas = _carregar_empresas()
    nomes_empresas = [v["nome"] for v in empresas.values()]

    with st.sidebar:
        st.image(LOGO, width=100)
        empresa_nome = st.selectbox("Empresa", [""] + nomes_empresas)
        if not empresa_nome:
            st.info("Selecione a empresa para iniciar")
            return
        chave = next(k for k, v in empresas.items() if v["nome"] == empresa_nome)
        cnpj_empresa = empresas[chave]["cnpj_emitentes"][0]
        st.markdown(f"**CNPJ:** {cnpj_empresa}")

        modo = st.radio("Fonte dos XMLs", ["Google Drive", "Upload Manual"])
        if modo == "Google Drive":
            if st.button("Buscar XMLs do Drive"):
                with st.spinner("Baixando XMLs do Drive..."):
                    service = criar_servico_drive()
                    with tempfile.TemporaryDirectory() as tmpdir:
                        xmls = baixar_xmls_empresa_zip(service, ROOT_FOLDER_ID, empresa_nome, tmpdir)
                        _executar_pipeline(xmls, cnpj_empresa)
        else:
            uploaded = st.file_uploader("Envie XML ou ZIP", type=["xml", "zip"], accept_multiple_files=True)
            if uploaded:
                paths = _upload_manual(uploaded)
                _executar_pipeline(paths, cnpj_empresa)

        if st.session_state.processado:
            anos, meses = obter_anos_meses_unicos(st.session_state.df_estoque, "Data Base")
            ano = st.selectbox("Ano", anos)
            mes = st.selectbox("Mês", meses, format_func=lambda m: ["Jan","Fev","Mar","Abr","Mai","Jun","Jul","Ago","Set","Out","Nov","Dez"][m-1])
            st.session_state.filtro_ano = ano
            st.session_state.filtro_mes = mes

    # Top bar
    with st.container():
        st.markdown(
            """
            <div class='top-bar'>
                <div style='display:flex;align-items:center;'>
            """,
            unsafe_allow_html=True,
        )
        st.image(LOGO, width=60)
        st.markdown(
            """
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

    if not st.session_state.processado:
        st.warning("Nenhum dado carregado. Importe os XMLs para visualizar o painel.")
        return

    df_filtrado = aplicar_filtro_periodo(
        st.session_state.df_estoque,
        "Data Base",
        st.session_state.get("filtro_ano"),
        st.session_state.get("filtro_mes"),
    )
    kpis = gerar_kpis(df_filtrado)

    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown(
            f"<div class='kpi-card'><div class='kpi-title'>Total Vendido</div><div class='kpi-value'>{formatar_moeda(kpis['Total Vendido (R$)'])}</div></div>",
            unsafe_allow_html=True,
        )
    with c2:
        st.markdown(
            f"<div class='kpi-card'><div class='kpi-title'>Lucro Total</div><div class='kpi-value'>{formatar_moeda(kpis['Lucro Total (R$)'])}</div></div>",
            unsafe_allow_html=True,
        )
    with c3:
        st.markdown(
            f"<div class='kpi-card'><div class='kpi-title'>Estoque Atual (R$)</div><div class='kpi-value'>{formatar_moeda(kpis['Estoque Atual (R$)'])}</div></div>",
            unsafe_allow_html=True,
        )

    vendas = st.session_state.df_configurado[st.session_state.df_configurado["Tipo Nota"] == "Saída"].copy()
    vendas = aplicar_filtro_periodo(vendas, "Data Emissão", st.session_state.get("filtro_ano"), st.session_state.get("filtro_mes"))
    vendas_tab = vendas[["Produto", "Valor Total"]].rename(columns={"Valor Total": "Valor (R$)"})

    estoque_parado = df_filtrado[df_filtrado["Situação"] == "Em Estoque"].copy()
    if "Data Emissão_entrada" in estoque_parado.columns:
        estoque_parado["Estoque (dias)"] = (
            pd.Timestamp.today() - pd.to_datetime(estoque_parado["Data Emissão_entrada"], errors="coerce")
        ).dt.days
    estoque_tab = estoque_parado[["Chassi_entrada", "Estoque (dias)"]].rename(columns={"Chassi_entrada": "Estoque"})

    c_left, c_right = st.columns([2, 1])
    with c_left:
        t1, t2 = st.columns(2)
        with t1:
            st.markdown("### Produtos Vendidos")
            st.table(vendas_tab.style.set_table_attributes('class="styled-table"'))
        with t2:
            st.markdown("### Estoque Parado")
            st.table(estoque_tab.style.set_table_attributes('class="styled-table"'))
    with c_right:
        st.markdown("### Alertas Fiscais")
        num_alertas = len(st.session_state.df_alertas)
        st.markdown(
            f"<div class='alert-card'><div class='alert-title'>Alertas Fiscais</div><div class='alert-badge'>{num_alertas}</div></div>",
            unsafe_allow_html=True,
        )
        if not st.session_state.df_alertas.empty:
            cols_desejadas = ["Estoque Parado", "DDV"]
            cols_existentes = [c for c in cols_desejadas if c in st.session_state.df_alertas.columns]
            if cols_existentes:
                alertas_tab = st.session_state.df_alertas[cols_existentes]
            else:
                alertas_tab = st.session_state.df_alertas
            st.table(alertas_tab.style.set_table_attributes('class="styled-table"'))
        else:
            st.write("Nenhum alerta fiscal encontrado.")


if __name__ == "__main__":
    main()
