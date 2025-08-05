"""Utilidades para integração com o Google Drive."""

from __future__ import annotations

import os
import logging
import zipfile
import unicodedata
from pathlib import Path
from typing import List, Optional

import json
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaIoBaseDownload


log = logging.getLogger(__name__)


def criar_servico_drive():
    """Cria um serviço de acesso ao Google Drive usando ``GCP_SERVICE_ACCOUNT_JSON``.

    A variável de ambiente deve conter o JSON completo da chave de serviço.
    """

    scopes = ["https://www.googleapis.com/auth/drive.readonly"]
    raw_json = os.getenv("GCP_SERVICE_ACCOUNT_JSON")
    if not raw_json:
        raise EnvironmentError(
            "Variável GCP_SERVICE_ACCOUNT_JSON não definida"
        )
    try:
        info = json.loads(raw_json)
    except json.JSONDecodeError as exc:
        raise ValueError(
            "Conteúdo inválido em GCP_SERVICE_ACCOUNT_JSON"
        ) from exc

    creds = Credentials.from_service_account_info(info, scopes=scopes)
    return build("drive", "v3", credentials=creds)


def _buscar_subpasta_id(service, parent_id: str, nome: str) -> Optional[str]:
    """Retorna o ID de uma subpasta de ``parent_id`` com o ``nome`` informado."""

    def _normalizar(texto: str) -> str:
        texto_norm = unicodedata.normalize("NFD", texto)
        texto_sem_acento = "".join(
            c for c in texto_norm if unicodedata.category(c) != "Mn"
        )
        return texto_sem_acento.casefold()

    query = (
        f"'{parent_id}' in parents and "
        "mimeType='application/vnd.google-apps.folder' and "
        "trashed=false"
    )
    res = service.files().list(q=query, fields="files(id,name)").execute()
    for f in res.get("files", []):
        if _normalizar(f["name"]) == _normalizar(nome):
            return f["id"]
    return None


def listar_arquivos(service, pasta_id: str) -> List[dict]:
    """Lista arquivos (não pastas) dentro da pasta especificada."""

    query = (
        f"'{pasta_id}' in parents and mimeType!='application/vnd.google-apps.folder' "
        "and trashed=false"
    )
    arquivos = []
    page_token = None
    while True:
        res = (
            service.files()
            .list(
                q=query,
                fields="nextPageToken, files(id,name,modifiedTime)",
                pageToken=page_token,
            )
            .execute()
        )
        arquivos.extend(res.get("files", []))
        page_token = res.get("nextPageToken")
        if not page_token:
            break
    return arquivos


def baixar_arquivo(service, file_id: str, destino: str) -> None:
    """Baixa um único arquivo do Google Drive."""

    request = service.files().get_media(fileId=file_id)
    os.makedirs(os.path.dirname(destino), exist_ok=True)
    with open(destino, "wb") as f:
        downloader = MediaIoBaseDownload(f, request)
        done = False
        while not done:
            try:
                status, done = downloader.next_chunk()
            except HttpError:
                break


def safe_extract_all(zf: zipfile.ZipFile, dest: str) -> None:
    """Extrai os arquivos do ZIP em ``dest`` com verificação contra path traversal."""
    dest_abs = os.path.abspath(dest)
    for member in zf.namelist():
        member_path = os.path.abspath(os.path.join(dest, member))
        if not member_path.startswith(dest_abs):
            raise Exception(f"Arquivo malicioso: {member}")
        zf.extract(member, dest)


def baixar_xmls_empresa_zip(
    service,
    pasta_principal_id: str,
    nome_empresa: str,
    destino: str,
) -> List[str]:
    """Baixa o arquivo ``*.zip`` da pasta da empresa e retorna os XMLs extraídos."""

    log.info(
        "Buscando pasta da empresa '%s' em '%s'", nome_empresa, pasta_principal_id
    )
    empresa_id = _buscar_subpasta_id(service, pasta_principal_id, nome_empresa)
    if not empresa_id:
        log.error("Pasta da empresa '%s' não encontrada", nome_empresa)
        raise FileNotFoundError(
            f"Pasta da empresa '{nome_empresa}' não encontrada no Drive"
        )
    log.info("Pasta da empresa encontrada: %s", empresa_id)

    arquivos = listar_arquivos(service, empresa_id)
    arquivos_zip = [a for a in arquivos if a["name"].lower().endswith(".zip")]
    if not arquivos_zip:
        log.warning("Nenhum arquivo ZIP encontrado para '%s'", nome_empresa)
        return []

    zip_config = os.getenv("NOME_ARQUIVO_ZIP")
    if len(arquivos_zip) > 1:
        if zip_config:
            alvo = next((a for a in arquivos_zip if a["name"] == zip_config), None)
            if not alvo:
                logging.warning(
                    "Nenhum ZIP corresponde ao nome configurado '%s' para a empresa '%s'",
                    zip_config,
                    nome_empresa,
                )
                raise FileNotFoundError(
                    f"Arquivo ZIP '{zip_config}' não encontrado para a empresa '{nome_empresa}'",
                )
        else:
            nomes = [a["name"] for a in arquivos_zip]
            logging.warning(
                "Múltiplos arquivos ZIP encontrados para a empresa '%s': %s",
                nome_empresa,
                nomes,
            )
            raise RuntimeError(
                "Configure NOME_ARQUIVO_ZIP para selecionar o arquivo desejado.",
            )
    else:
        alvo = arquivos_zip[0]

    log.info("Arquivo ZIP escolhido: %s (id=%s)", alvo["name"], alvo["id"])
    os.makedirs(destino, exist_ok=True)
    zip_path = os.path.join(destino, alvo["name"])
    baixar_arquivo(service, alvo["id"], zip_path)
    log.info("Download concluído: %s", zip_path)
    zip_dest = os.path.join(destino, Path(alvo["name"]).stem)
    try:
        with zipfile.ZipFile(zip_path) as zf:
            log.info("Conteúdo do ZIP: %s", zf.namelist())
            safe_extract_all(zf, zip_dest)
    except zipfile.BadZipFile as exc:
        log.exception(
            "Falha ao processar ZIP para a empresa '%s'", nome_empresa
        )
        raise

    xmls = sorted(
        [
            os.path.join(root, f)
            for root, _, files in os.walk(zip_dest)
            for f in files
            if f.lower().endswith(".xml")
        ]
    )
    if not xmls:
        log.error("Nenhum XML encontrado em %s", destino)
        raise FileNotFoundError(f"Nenhum XML encontrado em {destino}")
    log.info("XMLs extraídos: %s", [os.path.basename(x) for x in xmls])
    return xmls
