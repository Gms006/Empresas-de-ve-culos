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
    gerar_alertas_auditoria,
    gerar_estoque_fiscal,
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


# ---------------------------------------------------------------------------
# Entrada de dados
# ---------------------------------------------------------------------------

def _carregar_empresas() -> dict[str, str]:
    """Carrega configuração das empresas do arquivo JSON."""
    path = Path("config/empresas_config.json")
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        st.error("Arquivo de configuração das empresas não encontrado.")
        return {}


def _upload_manual(files) -> list[str]:
    """Armazena arquivos enviados manualmente e extrai ZIPs."""
    upload_dir = Path(st.session_state.get("upload_dir", ""))
    if not upload_dir or not upload_dir.exists():
        upload_dir = Path(tempfile.mkdtemp(prefix="upload_"))
        st.session_state.upload_dir = str(upload_dir)
    upload_dir.mkdir(parents=True, exist_ok=True)

    paths: list[str] = []
    for f in files:
        dest = upload_dir / f.name
        with open(dest, "wb") as out:
            out.write(f.read())
        
        if f.name.lower().endswith(".zip"):
            try:
                with zipfile.ZipFile(dest, "r") as zf:
                    for name in zf.namelist():
                        if name.lower().endswith(".xml"):
                            extracted = upload_dir / Path(name).name
                            extracted.parent.mkdir(parents=True, exist_ok=True)
                            with open(extracted, "wb") as out_f:
                                out_f.write(zf.read(name))
                            paths.append(str(extracted))
            except Exception as exc:
                st.error(f"Erro ao extrair {f.name}: {exc}")
        else:
            paths.append(str(dest))
    return paths


# ---------------------------------------------------------------------------
# Processamento de dados
# ---------------------------------------------------------------------------

def _processar_arquivos(xml_paths: list[str], cnpj_empresa: str) -> pd.DataFrame:
    """Processa arquivos XML e retorna DataFrame configurado."""
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

    st.session_state.df_estoque = df_estoque
    st.session_state.df_alertas = df_alertas
    st.session_state.df_resumo = df_resumo
    st.session_state.kpis = kpis
    st.session_state.processado = True


def _exportar_excel(df: pd.DataFrame) -> bytes:
    """Gera um arquivo Excel em memória a partir do DataFrame informado."""
    with io.BytesIO() as buffer:
        with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:
            df.to_excel(writer, index=False)
        return buffer.getvalue()


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


def formatar_df_exibicao(df: pd.DataFrame) -> pd.DataFrame:
    """Formata DataFrame para exibição, convertendo valores monetários."""
    df_display = df.copy()
    
    # Colunas que devem ser formatadas como moeda
    colunas_moeda = [
        'Valor Total', 'Valor Venda', 'Valor Entrada', 'Valor Contábil (R$)',
        'ICMS', 'PIS', 'COFINS', 'Tributos Totais', 'Lucro Líquido Estimado',
        'valor_medio_compra', 'total_compra'
    ]
    
    for col in df_display.columns:
        if col in colunas_moeda and col in df_display.columns:
            try:
                df_display[col] = df_display[col].apply(
                    lambda x: formatar_moeda(x) if pd.notnull(x) else "R$ 0,00"
                )
            except:
                pass  # Se não conseguir formatar, mantém original
                
    return df_display


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
                    st.rerun()
                st.write("Filtros adicionais podem ir aqui")


def render_sidebar(empresas: dict[str, str], nomes_empresas: list[str], logo: Path) -> str:
    """Renderiza a barra lateral com seleção de empresa e carregamento de dados."""
    with st.sidebar:
        if logo.exists():
            st.image(str(logo), width=100)
        
        empresa_nome = st.selectbox("Selecione a Empresa", [""] + nomes_empresas)
        
        if not empresa_nome:
            st.info("Selecione uma empresa para iniciar")
            return ""
            
        # Encontra o CNPJ da empresa selecionada
        chave = next(k for k, v in empresas.items() if v["nome"] == empresa_nome)
        st.session_state.cnpj_empresa = empresas[chave]["cnpj_emitentes"][0]
        st.markdown(f"**CNPJ:** {st.session_state.cnpj_empresa}")

        # Seleção do modo de carregamento
        modo = st.radio("Fonte dos XMLs", ["Google Drive", "Upload Manual"])
        
        if modo == "Google Drive":
            if st.button("Baixar XMLs do Drive"):
                with st.spinner("Baixando XMLs do Drive..."):
                    try:
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
                    except Exception as e:
                        st.error(f"Erro ao baixar XMLs: {e}")
        else:
            uploaded = st.file_uploader(
                "Envie XML ou ZIP", type=["xml", "zip"], accept_multiple_files=True
            )
            if uploaded and st.button("Carregar arquivos"):
                try:
                    paths = _upload_manual(uploaded)
                    st.session_state.xml_paths = paths
                    st.session_state.processado = False
                    st.session_state.erros_xml = []
                    st.success(f"{len(paths)} arquivos carregados.")
                except Exception as e:
                    st.error(f"Erro ao carregar arquivos: {e}")

        # Filtros de período (apenas se dados processados)
        if st.session_state.processado and not st.session_state.df_estoque.empty:
            anos, meses = obter_anos_meses_unicos(
                st.session_state.df_estoque, "Data Base"
            )
            st.session_state.filtro_ano = st.selectbox("Ano", anos)
            st.session_state.filtro_mes = st.selectbox(
                "Mês",
                meses,
                format_func=lambda m: [
                    "Jan", "Fev", "Mar", "Abr", "Mai", "Jun",
                    "Jul", "Ago", "Set", "Out", "Nov", "Dez"
                ][m - 1],
            )
    
    return empresa_nome


def render_main_content(empresa_nome: str):
    """Renderiza o conteúdo principal da aplicação."""
    # Verificação de arquivos carregados
    if st.session_state.xml_paths:
        st.markdown("**Status dos XMLs carregados:**")
        existentes = [p for p in st.session_state.xml_paths if Path(p).exists()]
        faltando = [p for p in st.session_state.xml_paths if not Path(p).exists()]
        
        if existentes:
            st.success(f"✅ {len(existentes)} arquivos válidos encontrados")
        if faltando:
            st.warning(f"⚠️ {len(faltando)} arquivos não encontrados (podem ter expirado)")

    # Processamento de dados
    if not st.session_state.processado:
        if not st.session_state.xml_paths:
            st.info("📁 Carregue os arquivos XML na barra lateral para começar.")
            return
            
        st.info("⏳ Dados não processados. Clique no botão abaixo para processar.")
        if st.button("🔄 Carregar / Reprocessar XMLs", type="primary"):
            with st.spinner("Processando XMLs..."):
                try:
                    _executar_pipeline(
                        st.session_state.xml_paths, st.session_state.cnpj_empresa
                    )
                    if st.session_state.processado:
                        st.success("✅ Dados carregados com sucesso!")
                        st.rerun()
                    else:
                        st.error("❌ Falha no processamento dos dados.")
                except Exception as e:
                    st.error(f"❌ Erro durante processamento: {e}")
                    
        # Exibir erros se houver
        if st.session_state.get("erros_xml"):
            with st.expander("⚠️ Ver erros de processamento", expanded=False):
                for erro in st.session_state["erros_xml"][:10]:
                    st.text(erro)
                if len(st.session_state["erros_xml"]) > 10:
                    st.text(f"... e mais {len(st.session_state['erros_xml']) - 10} erros")
        return

    # Aplicar filtros
    df_filtrado = aplicar_filtro_periodo(
        st.session_state.df_estoque,
        "Data Base",
        st.session_state.get("filtro_ano"),
        st.session_state.get("filtro_mes"),
    )

    if df_filtrado.empty:
        st.warning("📊 Não há dados para o período selecionado.")
        return

    # KPIs
    kpis = gerar_kpis(df_filtrado)
    c1, c2, c3 = st.columns(3)
    c1.metric("💰 Total Vendido", formatar_moeda(kpis.get("Total Vendido (R$)", 0)))
    c2.metric("📈 Lucro Total", formatar_moeda(kpis.get("Lucro Total (R$)", 0)))
    c3.metric("📦 Estoque Atual", formatar_moeda(kpis.get("Estoque Atual (R$)", 0)))

    # Navegação entre páginas
    page = st.session_state.page

    if page == "Relatórios":
        st.markdown("### 📊 Carros Vendidos x Comprados Repetidos")
        try:
            rel_vendas = montar_relatorio_vendas_compras(st.session_state)
            if not rel_vendas.empty:
                st.dataframe(formatar_df_exibicao(rel_vendas), use_container_width=True)
                st.download_button(
                    "📥 Exportar relatório de vendas-compras",
                    data=_exportar_excel(rel_vendas),
                    file_name="vendas_compras_relatorio.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                )
            else:
                st.info("📋 Nenhum dado de vendas-compras disponível para o período selecionado.")
        except Exception as e:
            st.error(f"❌ Erro ao gerar relatório: {e}")

    elif page == "Mapa de Vendas":
        st.markdown("### 🗺️ Mapa de Vendas")
        st.info("🚧 Funcionalidade em desenvolvimento.")

    elif page == "Estoque Fiscal":
        st.markdown("### 📦 Estoque Fiscal")
        try:
            estoque = df_filtrado.copy()
            
            # Calcular dias em estoque
            if "Data Emissão_entrada" in estoque.columns:
                estoque["Dias em Estoque"] = (
                    pd.to_datetime(estoque["Data Saída"], errors="coerce").fillna(pd.Timestamp.today())
                    - pd.to_datetime(estoque["Data Emissão_entrada"], errors="coerce")
                ).dt.days
            
            estoque["Situação"] = estoque["Situação"].fillna("Desconhecido")
            
            # Selecionar colunas para exibição
            cols_exibir = [
                c for c in [
                    "Chassi_entrada", "Valor Entrada", "Situação", 
                    "Data Emissão_entrada", "Data Saída", "Dias em Estoque"
                ] if c in estoque.columns
            ]
            
            if cols_exibir:
                display = estoque[cols_exibir].rename(columns={
                    "Chassi_entrada": "Chassi",
                    "Valor Entrada": "Valor Contábil (R$)",
                    "Data Emissão_entrada": "Data Entrada",
                })
                
                st.dataframe(formatar_df_exibicao(display), use_container_width=True)
                st.download_button(
                    "📥 Exportar estoque fiscal",
                    data=_exportar_excel(display),
                    file_name="estoque_fiscal.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                )
            else:
                st.info("📋 Nenhuma coluna de estoque disponível para exibição.")
        except Exception as e:
            st.error(f"❌ Erro ao processar estoque fiscal: {e}")


def main():
    """Função principal da aplicação."""
    st.set_page_config(
        page_title="Dashboard Neto Contabilidade", 
        layout="wide",
        initial_sidebar_state="expanded"
    )
    
    # Inicializar sessão
    _init_session()
    
    # Carregar configurações
    empresas = _carregar_empresas()
    if not empresas:
        st.error("❌ Não foi possível carregar a configuração das empresas.")
        st.stop()
        
    nomes_empresas = [v["nome"] for v in empresas.values()]
    LOGO = Path("config/logo.png")
    
    # Renderizar topbar
    render_topbar(LOGO)
    
    # Renderizar sidebar e obter empresa selecionada
    empresa_nome = render_sidebar(empresas, nomes_empresas, LOGO)
    
    # Renderizar conteúdo principal apenas se empresa selecionada
    if empresa_nome:
        render_main_content(empresa_nome)
    else:
        st.markdown("### 👋 Bem-vindo ao Dashboard Neto Contabilidade")
        st.info("📌 Selecione uma empresa na barra lateral para começar a análise.")


if __name__ == "__main__":
    main()
