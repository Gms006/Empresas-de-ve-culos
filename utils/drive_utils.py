"""Utilidades para integração com o Google Drive."""

from __future__ import annotations

import os
import logging
from typing import List, Optional

import json
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaIoBaseDownload


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

    query = (
        f"'{parent_id}' in parents and "
        "mimeType='application/vnd.google-apps.folder' and "
        f"name='{nome}' and trashed=false"
    )
    res = service.files().list(q=query, fields="files(id,name)").execute()
    arquivos = res.get("files", [])
    if arquivos:
        return arquivos[0]["id"]
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


def baixar_xmls_empresa_zip(
    service,
    pasta_principal_id: str,
    nome_empresa: str,
    destino: str,
) -> List[str]:
    """Baixa o arquivo ``*.zip`` da pasta da empresa e retorna os XMLs extraídos."""
    empresa_id = _buscar_subpasta_id(service, pasta_principal_id, nome_empresa)
    if not empresa_id:
        raise FileNotFoundError(
            f"Pasta da empresa '{nome_empresa}' não encontrada no Drive"
        )

    arquivos = listar_arquivos(service, empresa_id)
    arquivos_zip = [a for a in arquivos if a["name"].lower().endswith(".zip")]
    if not arquivos_zip:
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

    logging.info("Arquivo ZIP escolhido: %s", alvo["name"])
    os.makedirs(destino, exist_ok=True)
    zip_path = os.path.join(destino, "empresa.zip")
    baixar_arquivo(service, alvo["id"], zip_path)
    try:
        import zipfile

        with zipfile.ZipFile(zip_path) as zf:
            zf.extractall(destino)
    except zipfile.BadZipFile as exc:
        raise ValueError(
            f"Arquivo ZIP inválido para a empresa '{nome_empresa}'",
        ) from exc

    xmls = [
        os.path.join(root, f)
        for root, _, files in os.walk(destino)
        for f in files
        if f.lower().endswith(".xml")
    ]
    if not xmls:
        logging.warning("Nenhum XML encontrado após a extração em %s", destino)
        raise FileNotFoundError(f"Nenhum XML encontrado em {destino}")
    return xmls
