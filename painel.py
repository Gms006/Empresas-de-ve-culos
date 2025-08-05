"""Painel principal Streamlit para análise de notas fiscais de veículos."""

from __future__ import annotations

import io
import json
import tempfile
from pathlib import Path
import zipfile
import logging

import pandas as pd
import streamlit as st

from modules.estoque_veiculos import processar_xmls
from modules.configurador_planilha import configurar_planilha
from utils.validacao_utils import validar_campos_obrigatorios
from modules.transformadores_veiculos import (
    gerar_alertas_auditoria,
    gerar_estoque_fiscal,
    gerar_kpis,
    gerar_resumo_mensal,
)
from utils.google_drive_utils import (
    ROOT_FOLDER_ID,
    baixar_xmls_empresa_zip,
    criar_servico_drive,
)
from googleapiclient.errors import HttpError


# Configuração de logging
log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Estado da aplicação
# ---------------------------------------------------------------------------

def _init_session() -> None:
    """Inicializa chaves do ``st.session_state`` com valores padrão."""
    defaults = {
        "processado": False,
        "df_estoque": pd.DataFrame(),
        "df_alertas": pd.DataFrame(),
        "df_resumo": pd.DataFrame(),
        "kpis": {},
        "xml_paths": [],
        "cnpj_empresa": "",
        "erros_xml": [],
        "download_dir": "",
        "upload_dir": "",
    }
    for chave, valor in defaults.items():
        st.session_state.setdefault(chave, valor)


# ---------------------------------------------------------------------------
# Entrada de dados
# ---------------------------------------------------------------------------

def _carregar_empresas() -> dict[str, str]:
    path = Path("config/empresas_config.json")
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        st.error("Arquivo de configuração das empresas não encontrado.")
        return {}

# ---------------------------------------------------------------------------
# Processamento de dados
# ---------------------------------------------------------------------------

def _upload_manual(files) -> list[str]:
    """Armazena arquivos enviados manualmente e extrai ZIPs."""
    upload_dir = Path(st.session_state.get("upload_dir", tempfile.mkdtemp(prefix="upload_")))
    upload_dir.mkdir(parents=True, exist_ok=True)
    st.session_state.upload_dir = str(upload_dir)

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
                            extracted = upload_dir / name
                            extracted.parent.mkdir(parents=True, exist_ok=True)
                            with open(extracted, "wb") as out_f:
                                out_f.write(zf.read(name))
                            paths.append(str(extracted))
            except zipfile.BadZipFile as exc:  # pragma: no cover - apenas log
                st.error(f"Erro ao extrair {f.name}: {exc}")
        else:
            paths.append(str(dest))
    return paths


# ---------------------------------------------------------------------------
# Processamento de dados
# ---------------------------------------------------------------------------

def _processar_arquivos(xml_paths: list[str], cnpj_empresa: str) -> pd.DataFrame:
    if not xml_paths:
        return pd.DataFrame()
    df = processar_xmls(xml_paths, cnpj_empresa)
    df = configurar_planilha(df)
    validar_campos_obrigatorios(df)
    return df


def _executar_pipeline(xml_paths: list[str], cnpj_empresa: str) -> None:
    st.session_state["erros_xml"] = []
    df_config = _processar_arquivos(xml_paths, cnpj_empresa)
    st.session_state.df_configurado = df_config
    
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


# ---------------------------------------------------------------------------
# UI helpers
# ---------------------------------------------------------------------------

def _exportar_excel(df: pd.DataFrame) -> bytes:
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:
        df.to_excel(writer, index=False)
    return buffer.getvalue()


def sidebar(empresas: dict[str, str]) -> str | None:
    with st.sidebar:
        st.header("Configurações")
        empresa = st.selectbox("Empresa", ["-"] + list(empresas.keys()))
        if empresa and empresa != "-":
            cnpj = empresas[empresa]
            log.info("Empresa selecionada: %s", empresa)
        else:
            cnpj = None

        origem = st.radio("Origem dos XMLs", ["Upload Manual", "Google Drive"], key="origem")

        xml_paths: list[str] = []
        if origem == "Upload Manual":
            files = st.file_uploader(
                "Envie arquivos XML ou ZIP", type=["xml", "zip"], accept_multiple_files=True
            )
            if files:
                xml_paths = _upload_manual(files)
        else:
            if st.button("Buscar XMLs do Drive") and empresa:
                try:
                    log.info("Iniciando download dos XMLs para %s", empresa)
                    service = criar_servico_drive()
                    download_dir = tempfile.mkdtemp(prefix="download_")
                    xml_paths = baixar_xmls_empresa_zip(
                        service, ROOT_FOLDER_ID, empresa, download_dir
                    )
                    log.info(
                        "Arquivos XML baixados: %s",
                        [Path(p).name for p in xml_paths],
                    )
                    st.session_state.download_dir = download_dir
                except FileNotFoundError as exc:
                    log.error("Arquivo ou pasta não encontrada: %s", exc)
                    st.warning(str(exc))
                except zipfile.BadZipFile as exc:
                    log.error("ZIP inválido para %s: %s", empresa, exc)
                    st.warning(f"Arquivo ZIP inválido: {exc}")
                except HttpError as exc:  # pragma: no cover - depende do ambiente
                    log.error("Falha ao acessar Drive: %s", exc)
                    st.warning(f"Falha ao acessar Drive: {exc}")
        st.session_state.xml_paths = xml_paths
        st.session_state.cnpj_empresa = cnpj or ""
        return cnpj


def _mostrar_kpis(kpis: dict[str, float]) -> None:
    cols = st.columns(len(kpis))
    for col, (nome, valor) in zip(cols, kpis.items()):
        col.metric(nome, f"R$ {valor:,.2f}" if "R$" in nome else f"{valor:,.2f}")


def render_relatorios() -> None:
    df = st.session_state.df_estoque
    kpis = st.session_state.kpis
    _mostrar_kpis(kpis)

    vendidos = df[df["Situação"] == "Vendido"].copy()
    estoque = df[df["Situação"] == "Em Estoque"].copy()

    st.subheader("Veículos Vendidos")
    st.dataframe(vendidos[
        [
            col
            for col in [
                "Chave",
                "Produto", "Valor Entrada", "Valor Venda", "Lucro",
                "ICMS Valor_saida", "ICMS Valor_entrada"
            ]
            if col in vendidos.columns
        ]
    ])
    st.download_button(
        "Exportar Vendas",
        data=_exportar_excel(vendidos),
        file_name="vendas.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )

    st.subheader("Veículos em Estoque")
    st.dataframe(estoque[
        [
            col
            for col in [
                "Chave",
                "Produto", "Valor Entrada", "Data Emissão_entrada", "Data Saída"
            ]
            if col in estoque.columns
        ]
    ])
    st.download_button(
        "Exportar Estoque",
        data=_exportar_excel(estoque),
        file_name="estoque.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )

    st.subheader("Resumo Financeiro Mensal")
    st.dataframe(st.session_state.df_resumo)
    st.download_button(
        "Exportar Resumo",
        data=_exportar_excel(st.session_state.df_resumo),
        file_name="resumo_mensal.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )

    if not st.session_state.df_alertas.empty:
        st.subheader("Alertas Fiscais")
        st.dataframe(st.session_state.df_alertas)

# ---------------------------------------------------------------------------
# Ponto de entrada
# ---------------------------------------------------------------------------
def main() -> None:
    st.set_page_config(page_title="Painel Fiscal", layout="wide")
    _init_session()
    empresas = _carregar_empresas()
    cnpj = sidebar(empresas)
    if cnpj and st.session_state.xml_paths and st.button("Processar XMLs"):
        _executar_pipeline(st.session_state.xml_paths, cnpj)
    if st.session_state.processado:
        render_relatorios()
    else:
        st.info("Nenhum dado processado ainda.")


if __name__ == "__main__":  # pragma: no cover - entrada do Streamlit
    main()
