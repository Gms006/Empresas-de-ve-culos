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
from st_aggrid import AgGrid, GridOptionsBuilder, DataReturnMode, GridUpdateMode

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
        "download_dir": "",
        "upload_dir": "",
        "erros_xml": [],
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
    st.session_state["erros_xml"] = []
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
    """Armazena arquivos enviados manualmente em diretório persistente."""
    upload_dir = Path(st.session_state.get("upload_dir", ""))
    if not upload_dir or not upload_dir.exists():
        upload_dir = Path(tempfile.mkdtemp(prefix="upload_"))
        st.session_state.upload_dir = str(upload_dir)
    upload_dir.mkdir(parents=True, exist_ok=True)

    paths = []
    for f in files:
        dest = upload_dir / f.name
        with open(dest, "wb") as out:
            out.write(f.read())
        if f.name.lower().endswith(".zip"):
            try:
                with zipfile.ZipFile(dest, "r") as zf:
                    for name in zf.namelist():
                        if name.lower().endswith(".xml"):
                            extracted = upload_dir / name
                            extracted.parent.mkdir(parents=True, exist_ok=True)
                            with open(extracted, "wb") as out_f:
                                out_f.write(zf.read(name))
                            paths.append(str(extracted))
            except Exception as exc:
                st.error(f"Erro ao extrair {f.name}: {exc}")
        else:
            paths.append(str(dest))
    return paths


def _exportar_excel(df: pd.DataFrame) -> bytes:
    """Gera um arquivo Excel em memória a partir do DataFrame informado."""
    with io.BytesIO() as buffer:
        with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:
            df.to_excel(writer, index=False)
        return buffer.getvalue()


def mostrar_grid_selecionavel(
    df: pd.DataFrame, key: str, selection_mode: str = "single"
):
    """Exibe ``df`` em um grid interativo permitindo seleção de linhas."""
    if df is None or df.empty:
        st.write("Nenhum dado para exibir.")
        return None

    gb = GridOptionsBuilder.from_dataframe(df)
    gb.configure_pagination(paginationAutoPageSize=True)
    gb.configure_side_bar()
    gb.configure_selection(selection_mode, use_checkbox=True)
    gb.configure_default_column(resizable=True, sortable=True, filter=True)
    grid_options = gb.build()

    grid_response = AgGrid(
        df,
        gridOptions=grid_options,
        data_return_mode=DataReturnMode.FILTERED_AND_SORTED,
        update_mode=GridUpdateMode.MODEL_CHANGED,
        fit_columns_on_grid_load=True,
        enable_enterprise_modules=False,
        theme="dark",
        key=key,
        allow_unsafe_jscode=True,
    )
    return grid_response


def apurar_tributos_por_venda(df_vendas: pd.DataFrame) -> pd.DataFrame:
    """Aplica alíquotas básicas de tributos sobre o valor de venda."""
    df = df_vendas.copy()
    valor = pd.to_numeric(df.get("Valor Total"), errors="coerce").fillna(0.0)
    df["Valor Total"] = valor
    df["ICMS"] = valor * 0.18
    df["PIS"] = valor * 0.0165
    df["COFINS"] = valor * 0.076
    df["Tributos Totais"] = df[["ICMS", "PIS", "COFINS"]].sum(axis=1)
    return df


def montar_relatorio_vendas_compras(st_session) -> pd.DataFrame:
    """Relaciona vendas com compras repetidas por chassi."""
    df_config = st_session.df_configurado
    vendas = df_config[df_config["Tipo Nota"] == "Saída"].copy()
    entradas = df_config[df_config["Tipo Nota"] == "Entrada"].copy()

    vendas = aplicar_filtro_periodo(
        vendas, "Data Emissão", st_session.get("filtro_ano"), st_session.get("filtro_mes")
    )
    entradas = aplicar_filtro_periodo(
        entradas, "Data Emissão", st_session.get("filtro_ano"), st_session.get("filtro_mes")
    )

    for df in (vendas, entradas):
        if "Chassi" in df.columns:
            df["Chassi_norm"] = (
                df["Chassi"].astype(str).str.replace(r"\W", "", regex=True).str.upper()
            )
        else:
            df["Chassi_norm"] = ""

    compras_agrupadas = (
        entradas.groupby("Chassi_norm")
        .agg(
            vezes_comprado=("Chassi_norm", "count"),
            valor_medio_compra=("Valor Total", "mean"),
            total_compra=("Valor Total", "sum"),
        )
        .reset_index()
        .rename(columns={"Chassi_norm": "Chassi"})
    )

    vendas_tributos = apurar_tributos_por_venda(vendas)
    vendas_tributos = vendas_tributos.rename(
        columns={"Chassi_norm": "Chassi", "Valor Total": "Valor Venda"}
    )

    rel = vendas_tributos.merge(compras_agrupadas, on="Chassi", how="left")
    rel["Lucro Líquido Estimado"] = (
        rel["Valor Venda"]
        - rel.get("total_compra", 0).fillna(0)
        - rel.get("Tributos Totais", 0).fillna(0)
    )
    return rel


def render_topbar(logo: Path) -> None:
    """Renderiza a barra superior com navegação e ações rápidas."""
    cols = st.columns([1, 6, 4])
    with cols[0]:
        if logo.exists():
            st.image(str(logo), width=50)
        else:
            st.markdown("**NETO CONTABILIDADE**")
    with cols[1]:
        st.markdown(
            "<h1 style='margin:0;'>NETO <span style='color:#d1d5db;'>CONTABILIDADE</span></h1>",
            unsafe_allow_html=True,
        )
        st.markdown(
            "<div style='font-size:12px;color:#d1d5db;'>VILECRDE</div>",
            unsafe_allow_html=True,
        )
    with cols[2]:
        paginas = ["Relatórios", "Mapa de Vendas", "Estoque Fiscal"]
        current = st.session_state.get("page", "Relatórios")
        idx = paginas.index(current) if current in paginas else 0
        pagina = st.radio(
            "Navegação",
            paginas,
            horizontal=True,
            index=idx,
            label_visibility="collapsed",
        )
        st.session_state.page = pagina

        if st.button("☰", key="hamburger"):
            with st.expander("Ações rápidas", expanded=True):
                if st.button("Reprocessar XMLs"):
                    st.session_state.processado = False
                    st.experimental_rerun()
                st.write("Filtros adicionais podem ir aqui")


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
                        download_dir = Path(st.session_state.get("download_dir", ""))
                        if not download_dir or not download_dir.exists():
                            download_dir = Path(tempfile.mkdtemp(prefix="xmls_"))
                            st.session_state.download_dir = str(download_dir)
                        download_dir.mkdir(parents=True, exist_ok=True)

                        xmls = baixar_xmls_empresa_zip(
                            service, ROOT_FOLDER_ID, empresa_nome, download_dir
                        )
                    st.session_state.xml_paths = xmls
                    st.session_state.processado = False
                    st.session_state.erros_xml = []
                    st.success(f"{len(xmls)} arquivos obtidos.")
            else:
                uploaded = st.file_uploader(
                    "Envie XML ou ZIP", type=["xml", "zip"], accept_multiple_files=True
                )
                if uploaded and st.button("Carregar arquivos"):
                    paths = _upload_manual(uploaded)
                    st.session_state.xml_paths = paths
                    st.session_state.processado = False
                    st.session_state.erros_xml = []
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

    if st.session_state.xml_paths:
        st.markdown("**Verificando existência dos XMLs carregados:**")
        existentes = [p for p in st.session_state.xml_paths if Path(p).exists()]
        faltando = [p for p in st.session_state.xml_paths if not Path(p).exists()]
        st.write(
            f"Existem {len(existentes)} arquivos válidos e {len(faltando)} ausentes."
        )
        if faltando:
            st.warning(
                "Alguns caminhos não existem mais; isso indica que foram carregados de uma pasta temporária expirou."
            )
            for p in faltando[:5]:
                st.text(p)

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
                    if st.session_state.get("erros_xml"):
                        st.warning(
                            "Alguns XMLs falharam ao serem processados. Veja detalhes abaixo:"
                        )
                        for e in st.session_state["erros_xml"][:10]:
                            st.text(e)
                        if len(st.session_state["erros_xml"]) > 10:
                            st.text(
                                f"... e mais {len(st.session_state['erros_xml']) - 10} erros"
                            )
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
    c3.metric("Estoque Atual (R$)", formatar_moeda(kpis.get("Estoque Atual (R$)", 0)))

    page = st.session_state.page

    if page == "Relatórios":
        # Produtos vendidos
        st.markdown("### Produtos Vendidos")
        vendas = st.session_state.df_configurado[
            st.session_state.df_configurado["Tipo Nota"] == "Saída"
        ].copy()
        vendas = aplicar_filtro_periodo(
            vendas,
            "Data Emissão",
            st.session_state.get("filtro_ano"),
            st.session_state.get("filtro_mes"),
        )
        vendas_tab = vendas[["Produto", "Valor Total"]].rename(
            columns={"Valor Total": "Valor (R$)"}
        )
        grid_vendas = mostrar_grid_selecionavel(vendas_tab, key="grid_vendas")
        if grid_vendas:
            st.download_button(
                "Exportar Vendas",
                data=_exportar_excel(vendas_tab),
                file_name="vendas_detalhado.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )

        # Estoque parado
        st.markdown("### Estoque Parado")
        estoque_parado = df_filtrado[df_filtrado["Situação"] == "Em Estoque"].copy()
        if "Data Emissão_entrada" in estoque_parado.columns and not estoque_parado.empty:
            estoque_parado["Estoque (dias)"] = (
                pd.Timestamp.today()
                - pd.to_datetime(estoque_parado["Data Emissão_entrada"], errors="coerce")
            ).dt.days
        estoque_exibir = estoque_parado[
            ["Chave", "Valor Entrada", "Estoque (dias)", "Situação"]
        ].rename(
            columns={"Chave": "Chassi/Chave", "Valor Entrada": "Valor Contábil (R$)"}
        )
        grid_estoque = mostrar_grid_selecionavel(estoque_exibir, key="grid_estoque")
        if grid_estoque:
            st.download_button(
                "Exportar Estoque Fiscal",
                data=_exportar_excel(estoque_exibir),
                file_name="estoque_fiscal.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )

        # Alertas fiscais
        st.markdown("### Alertas Fiscais")
        if not st.session_state.df_alertas.empty:
            desired = ["Estoque Parado", "DDV"]
            existing = [c for c in desired if c in st.session_state.df_alertas.columns]
            tabela_alertas = (
                st.session_state.df_alertas[existing]
                if existing
                else st.session_state.df_alertas
            )
            grid_alertas = mostrar_grid_selecionavel(tabela_alertas, key="grid_alertas")
            if grid_alertas:
                st.download_button(
                    "Exportar Alertas Fiscais",
                    data=_exportar_excel(tabela_alertas),
                    file_name="alertas_fiscais.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                )
        else:
            st.write("Nenhum alerta fiscal encontrado.")

    elif page == "Estoque Fiscal":
        st.markdown("## Estoque Fiscal")
        estoque = df_filtrado.copy()
        if "Data Emissão_entrada" in estoque.columns:
            estoque["Dias em Estoque"] = (
                pd.to_datetime(estoque["Data Saída"], errors="coerce").fillna(pd.Timestamp.today())
                - pd.to_datetime(estoque["Data Emissão_entrada"], errors="coerce")
            ).dt.days
        estoque["Situação"] = estoque["Situação"].fillna("Desconhecido")
        cols_exibir = [
            c
            for c in [
                "Chassi_entrada",
                "Valor Entrada",
                "Situação",
                "Data Emissão_entrada",
                "Data Saída",
                "Dias em Estoque",
            ]
            if c in estoque.columns
        ]
        display = estoque[cols_exibir].rename(
            columns={
                "Chassi_entrada": "Chassi",
                "Valor Entrada": "Valor Contábil (R$)",
                "Data Emissão_entrada": "Data Entrada",
            }
        )
        mostrar_grid_selecionavel(display, key="grid_estoque_fiscal")
        st.download_button(
            "Exportar estoque fiscal",
            data=_exportar_excel(display),
            file_name="estoque_fiscal.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )


if __name__ == "__main__":
    main()
