"""Utilidades para integração com o Google Drive."""

from __future__ import annotations

import os
from typing import List, Optional

from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaIoBaseDownload


def criar_servico_drive(caminho_chave: str):
    """Cria um serviço de acesso ao Google Drive.

    Parameters
    ----------
    caminho_chave: str
        Caminho para o arquivo JSON de chave de serviço do Google.

    Returns
    -------
    googleapiclient.discovery.Resource
        Instância do serviço configurado para acesso somente leitura.
    """

    scopes = ["https://www.googleapis.com/auth/drive.readonly"]
    creds = Credentials.from_service_account_file(caminho_chave, scopes=scopes)
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


def baixar_xmls_da_pasta(service, pasta_id: str, destino: str) -> List[str]:
    """Baixa todos os arquivos XML de ``pasta_id`` para ``destino``."""

    arquivos = listar_arquivos(service, pasta_id)
    caminhos = []
    for arquivo in arquivos:
        if arquivo["name"].lower().endswith(".xml"):
            caminho_destino = os.path.join(destino, arquivo["name"])
            baixar_arquivo(service, arquivo["id"], caminho_destino)
            caminhos.append(caminho_destino)
    return caminhos


def baixar_xmls_empresa(
    service,
    pasta_principal_id: str,
    nome_empresa: str,
    destino: str,
) -> List[str]:
    """Baixa o ZIP mais recente da empresa e extrai todos os XMLs."""

    empresa_id = _buscar_subpasta_id(service, pasta_principal_id, nome_empresa)
    if not empresa_id:
        raise FileNotFoundError(
            f"Pasta da empresa '{nome_empresa}' não encontrada no Drive"
        )

    compactadas_id = _buscar_subpasta_id(service, empresa_id, "NFs Compactadas")
    if not compactadas_id:
        return []

    arquivos = listar_arquivos(service, compactadas_id)
    zips = [a for a in arquivos if a["name"].lower().endswith(".zip")]
    if not zips:
        return []

    zips.sort(key=lambda a: a.get("modifiedTime", ""), reverse=True)
    info_zip = zips[0]
    zip_path = os.path.join(destino, info_zip["name"])

    baixar_arquivo(service, info_zip["id"], zip_path)

    import zipfile

    xmls: List[str] = []
    with zipfile.ZipFile(zip_path, "r") as zf:
        for name in zf.namelist():
            if name.lower().endswith(".xml"):
                zf.extract(name, destino)
                xmls.append(os.path.join(destino, name))
    return xmls
