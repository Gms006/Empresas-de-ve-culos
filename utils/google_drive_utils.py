import os
import io
import logging
from typing import List, Tuple
import json
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload

SCOPES = ['https://www.googleapis.com/auth/drive.readonly']
ROOT_FOLDER_ID = '1ADaMbXNPEX8ZIT7c1U_pWMsRygJFROZq'

log = logging.getLogger(__name__)


def get_drive_service() -> 'googleapiclient.discovery.Resource':
    """Autentica e retorna o serviço do Google Drive usando variável de ambiente."""
    service_account_info = json.loads(os.environ['GCP_SERVICE_ACCOUNT_JSON'])
    creds = service_account.Credentials.from_service_account_info(
        service_account_info, scopes=SCOPES
    )
    return build('drive', 'v3', credentials=creds)


def _find_subfolder(service, parent_id: str, name: str) -> str | None:
    """Retorna o ID da subpasta com o nome fornecido."""
    query = (
        f"'{parent_id}' in parents and \
         mimeType='application/vnd.google-apps.folder' and \
         trashed=false"
    )
    results = service.files().list(q=query, fields='files(id, name)').execute()
    for f in results.get('files', []):
        if f['name'].lower() == name.lower():
            return f['id']
    return None


def _list_files(service, folder_id: str) -> List[dict]:
    """Lista arquivos dentro da pasta informada."""
    query = f"'{folder_id}' in parents and trashed=false"
    results = service.files().list(q=query, fields='files(id, name, mimeType)').execute()
    return results.get('files', [])


def _download_files(service, folder_id: str, dest_dir: str) -> List[str]:
    """Baixa todos os arquivos XML da pasta para ``dest_dir``."""
    os.makedirs(dest_dir, exist_ok=True)
    files = _list_files(service, folder_id)
    xml_paths: List[str] = []
    for f in files:
        if f['mimeType'] == 'application/vnd.google-apps.folder':
            continue
        if not f['name'].lower().endswith('.xml'):
            continue
        request = service.files().get_media(fileId=f['id'])
        path = os.path.join(dest_dir, f['name'])
        fh = io.FileIO(path, 'wb')
        downloader = MediaIoBaseDownload(fh, request)
        done = False
        while not done:
            _, done = downloader.next_chunk()
        xml_paths.append(path)
    return xml_paths


def baixar_xmls_empresa(company_name: str, tipo: str,
                        root_id: str = ROOT_FOLDER_ID,
                        dest_dir: str | None = None) -> Tuple[List[str], List[str]]:
    """Baixa XMLs de uma empresa no Google Drive.

    Retorna a lista de caminhos baixados e mensagens informativas.
    """
    if dest_dir is None:
        dest_dir = os.getcwd()

    service = get_drive_service()
    empresa_id = _find_subfolder(service, root_id, company_name)
    mensagens: List[str] = []
    if not empresa_id:
        mensagens.append(f'Empresa {company_name} não encontrada no Drive.')
        return [], mensagens

    xml_paths: List[str] = []
    tipos_map = []
    tipo_lower = tipo.lower()
    if tipo_lower in ('entradas', 'ambas'):
        tipos_map.append('Entradas')
    if tipo_lower in ('saídas', 'saidas', 'ambas'):
        tipos_map.append('Saidas')

    for pasta in tipos_map:
        pasta_id = _find_subfolder(service, empresa_id, pasta)
        if not pasta_id:
            mensagens.append(f'Subpasta {pasta} não encontrada para {company_name}.')
            continue
        baixados = _download_files(service, pasta_id, dest_dir)
        if not baixados:
            mensagens.append(f'Nenhum XML em {pasta} para {company_name}.')
        xml_paths.extend(baixados)

    return xml_paths, mensagens
