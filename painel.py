"""Painel principal da aplicação Streamlit.

Este módulo concentra a interface do dashboard e o fluxo de carregamento
dos dados. Antes as ações de navegação e de processamento eram construídas
com HTML estático, o que impedia callbacks e travava a página. A nova
versão utiliza apenas componentes nativos do Streamlit e controla o estado
por ``st.session_state``.
"""

import io
import json
import os
import tempfile
import zipfile
from pathlib import Path

import pandas as pd
import streamlit as st

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


def _init_session() -> None:
    """Inicializa chaves do ``st.session_state`` com valores seguros."""
    defaults = {
        "processado": False,
        "df_configurado": pd.DataFrame(),
        "df_estoque": pd.DataFrame(),
        "df_alertas": pd.DataFrame(),
        "df_resumo": pd.DataFrame(),
        "kpis": {},
        "page": "Relatórios",
        "xml_paths": [],
        "cnpj_empresa": "",
        "filtro_ano": None,
        "filtro_mes": None,
    }
    for chave, valor in defaults.items():
        st.session_state.setdefault(chave, valor)


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
    """Executa todas as etapas de transformação dos dados."""
    df_config = _processar_arquivos(xml_paths, cnpj_empresa)
    if df_config.empty:
        st.session_state.processado = False
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


def _exportar_excel(df: pd.DataFrame) -> bytes:
    """Gera um arquivo Excel em memória a partir do DataFrame informado."""
    with io.BytesIO() as buffer:
        with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:
            df.to_excel(writer, index=False)
        return buffer.getvalue()


def render_topbar(logo: Path) -> None:
    """Renderiza a barra superior com navegação."""
    col_logo, col_nav = st.columns([3, 2])
    with col_logo:
        if logo.exists():
            st.image(str(logo), width=60)
        else:
            st.write("Logo não encontrada")
        st.markdown("**NETO CONTABILIDADE**\nVILECRDE")
    with col_nav:
        pagina = st.radio(
            "Navegação",
            ["Relatórios", "Mapa de Vendas"],
            horizontal=True,
            index=0 if st.session_state.page == "Relatórios" else 1,
        )
        st.session_state.page = pagina


def main():
    st.set_page_config(page_title="Dashboard Neto Contabilidade", layout="wide")
    _init_session()

    LOGO = Path("config/logo.png")

    empresas = _carregar_empresas()
    nomes_empresas = [v["nome"] for v in empresas.values()]

    with st.sidebar:
        if LOGO.exists():
            st.image(str(LOGO), width=100)
        empresa_nome = st.selectbox("Empresa", [""] + nomes_empresas)
        if empresa_nome:
            chave = next(k for k, v in empresas.items() if v["nome"] == empresa_nome)
            st.session_state.cnpj_empresa = empresas[chave]["cnpj_emitentes"][0]
            st.markdown(f"**CNPJ:** {st.session_state.cnpj_empresa}")

            modo = st.radio("Fonte dos XMLs", ["Google Drive", "Upload Manual"])
            if modo == "Google Drive":
                if st.button("Baixar XMLs do Drive"):
                    with st.spinner("Baixando XMLs do Drive..."):
                        service = criar_servico_drive()
                        with tempfile.TemporaryDirectory() as tmpdir:
                            xmls = baixar_xmls_empresa_zip(
                                service, ROOT_FOLDER_ID, empresa_nome, tmpdir
                            )
                    st.session_state.xml_paths = xmls
                    st.session_state.processado = False
                    st.success(f"{len(xmls)} arquivos obtidos.")
            else:
                uploaded = st.file_uploader(
                    "Envie XML ou ZIP", type=["xml", "zip"], accept_multiple_files=True
                )
                if uploaded and st.button("Carregar arquivos"):
                    paths = _upload_manual(uploaded)
                    st.session_state.xml_paths = paths
                    st.session_state.processado = False
                    st.success(f"{len(paths)} arquivos carregados.")

            if st.session_state.processado and not st.session_state.df_estoque.empty:
                anos, meses = obter_anos_meses_unicos(
                    st.session_state.df_estoque, "Data Base"
                )
                st.session_state.filtro_ano = st.selectbox("Ano", anos)
                st.session_state.filtro_mes = st.selectbox(
                    "Mês",
                    meses,
                    format_func=lambda m: [
                        "Jan",
                        "Fev",
                        "Mar",
                        "Abr",
                        "Mai",
                        "Jun",
                        "Jul",
                        "Ago",
                        "Set",
                        "Out",
                        "Nov",
                        "Dez",
                    ][m - 1],
                )
        else:
            st.info("Selecione a empresa para iniciar")

    render_topbar(LOGO)

    if not empresa_nome:
        st.stop()

    if not st.session_state.processado:
        st.info("Nenhum dado processado.")
        if st.session_state.xml_paths:
            if st.button("Carregar / Reprocessar XMLs"):
                with st.spinner("Processando XMLs..."):
                    _executar_pipeline(
                        st.session_state.xml_paths, st.session_state.cnpj_empresa
                    )
                if st.session_state.processado:
                    st.success("Dados carregados com sucesso.")
        else:
            st.warning("Carregue os arquivos na barra lateral.")
        return

    # Navegação entre páginas
    if st.session_state.page == "Mapa de Vendas":
        st.write("Mapa de Vendas em construção.")
        return

    df_filtrado = aplicar_filtro_periodo(
        st.session_state.df_estoque,
        "Data Base",
        st.session_state.get("filtro_ano"),
        st.session_state.get("filtro_mes"),
    )

    if df_filtrado.empty:
        st.warning("Não há dados para o período selecionado.")
        return

    kpis = gerar_kpis(df_filtrado)

    c1, c2, c3 = st.columns(3)
    c1.metric("Total Vendido", formatar_moeda(kpis.get("Total Vendido (R$)", 0)))
    c2.metric("Lucro Total", formatar_moeda(kpis.get("Lucro Total (R$)", 0)))
    c3.metric(
        "Estoque Atual (R$)",
        formatar_moeda(kpis.get("Estoque Atual (R$)", 0)),
    )

    st.download_button(
        "Exportar relatório de estoque",
        data=_exportar_excel(df_filtrado),
        file_name="relatorio_estoque.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )

    vendas = st.session_state.df_configurado[
        st.session_state.df_configurado["Tipo Nota"] == "Saída"
    ].copy()
    vendas = aplicar_filtro_periodo(
        vendas, "Data Emissão", st.session_state.get("filtro_ano"), st.session_state.get("filtro_mes")
    )
    vendas_tab = vendas[["Produto", "Valor Total"]].rename(
        columns={"Valor Total": "Valor (R$)"}
    )

    estoque_parado = df_filtrado[df_filtrado["Situação"] == "Em Estoque"].copy()
    if "Data Emissão_entrada" in estoque_parado.columns and not estoque_parado.empty:
        estoque_parado["Estoque (dias)"] = (
            pd.Timestamp.today()
            - pd.to_datetime(estoque_parado["Data Emissão_entrada"], errors="coerce")
        ).dt.days
    estoque_tab = estoque_parado[["Chassi_entrada", "Estoque (dias)"]].rename(
        columns={"Chassi_entrada": "Estoque"}
    )

    c_left, c_right = st.columns([2, 1])
    with c_left:
        t1, t2 = st.columns(2)
        with t1:
            st.markdown("### Produtos Vendidos")
            st.dataframe(formatar_df_exibicao(vendas_tab), use_container_width=True)
        with t2:
            st.markdown("### Estoque Parado")
            st.dataframe(formatar_df_exibicao(estoque_tab), use_container_width=True)
    with c_right:
        st.markdown("### Alertas Fiscais")
        num_alertas = len(st.session_state.df_alertas)
        st.write(f"Total de alertas: {num_alertas}")
        if not st.session_state.df_alertas.empty:
            desired = ["Estoque Parado", "DDV"]
            existing = [c for c in desired if c in st.session_state.df_alertas.columns]
            tabela = (
                st.session_state.df_alertas[existing]
                if existing
                else st.session_state.df_alertas
            )
            st.dataframe(formatar_df_exibicao(tabela), use_container_width=True)
        else:
            st.write("Nenhum alerta fiscal encontrado.")


if __name__ == "__main__":
    main()
