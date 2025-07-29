import os
import io
import logging
import zipfile
from typing import Dict, List, Tuple
import json
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload, MediaIoBaseUpload

SCOPES = ['https://www.googleapis.com/auth/drive.readonly']
ROOT_FOLDER_ID = '1ADaMbXNPEX8ZIT7c1U_pWMsRygJFROZq'

log = logging.getLogger(__name__)


def get_drive_service() -> "googleapiclient.discovery.Resource":
    """Retorna o serviço do Google Drive utilizando ``GCP_SERVICE_ACCOUNT_JSON``.

    A variável de ambiente deve conter o JSON da chave de serviço. Erros de
    ausência ou formatação incorreta são relatados explicitamente.
    """
    raw_json = os.getenv("GCP_SERVICE_ACCOUNT_JSON")
    if not raw_json:
        raise EnvironmentError(
            "Variável GCP_SERVICE_ACCOUNT_JSON não definida"
        )
    try:
        service_account_info = json.loads(raw_json)
    except json.JSONDecodeError as exc:
        raise ValueError(
            "Conteúdo inválido em GCP_SERVICE_ACCOUNT_JSON"
        ) from exc

    creds = service_account.Credentials.from_service_account_info(
        service_account_info, scopes=SCOPES
    )
    return build("drive", "v3", credentials=creds)


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
    """Lista todos os arquivos dentro da pasta informada."""
    query = f"'{folder_id}' in parents and trashed=false"
    files: List[dict] = []
    page_token = None
    while True:
        results = (
            service.files()
            .list(
                q=query,
                fields="nextPageToken, files(id, name, mimeType, modifiedTime)",
                pageToken=page_token,
                pageSize=1000,
            )
            .execute()
        )
        files.extend(results.get("files", []))
        page_token = results.get("nextPageToken")
        if not page_token:
            break
    return files


def _download_files(service, folder_id: str, dest_dir: str) -> List[str]:
    """Baixa recursivamente todos os arquivos XML da pasta para ``dest_dir``."""
    os.makedirs(dest_dir, exist_ok=True)
    files = _list_files(service, folder_id)
    xml_paths: List[str] = []
    for f in files:
        if f['mimeType'] == 'application/vnd.google-apps.folder':
            # Descer em subpastas (ex: Entradas/2025/05-2025)
            sub_dir = os.path.join(dest_dir, f['name'])
            xml_paths.extend(_download_files(service, f['id'], sub_dir))
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

def _read_index(service, company_id: str) -> Tuple[Dict[str, Dict], str | None]:
    """Lê o arquivo ``index_arquivos.json`` da empresa."""
    query = (
        f"'{company_id}' in parents and "
        "name='index_arquivos.json' and trashed=false"
    )
    res = service.files().list(q=query, fields="files(id)").execute()
    files = res.get("files")
    if not files:
        return {}, None
    idx_id = files[0]["id"]
    request = service.files().get_media(fileId=idx_id)
    buf = io.BytesIO()
    downloader = MediaIoBaseDownload(buf, request)
    done = False
    while not done:
        _, done = downloader.next_chunk()
    buf.seek(0)
    return json.load(buf), idx_id


def _write_index(
    service, company_id: str, index: Dict[str, Dict], file_id: str | None
) -> str:
    """Grava ``index_arquivos.json`` na pasta da empresa."""
    media = MediaIoBaseUpload(
        io.BytesIO(json.dumps(index, ensure_ascii=False, indent=2).encode("utf-8")),
        mimetype="application/json",
        resumable=False,
    )
    if file_id:
        service.files().update(fileId=file_id, media_body=media).execute()
        return file_id
    meta = {"name": "index_arquivos.json", "parents": [company_id]}
    result = service.files().create(body=meta, media_body=media).execute()
    return result["id"]


def _infer_tipo_nota(service, file_id: str) -> str:
    """Obtém o campo ``tpNF`` do XML para definir Entrada ou Saída."""
    try:
        request = service.files().get_media(fileId=file_id)
        buf = io.BytesIO()
        downloader = MediaIoBaseDownload(buf, request)
        done = False
        while not done:
            _, done = downloader.next_chunk()
        buf.seek(0)
        import xml.etree.ElementTree as ET

        tree = ET.parse(buf)
        tp_elem = tree.find(
            ".//{http://www.portalfiscal.inf.br/nfe}tpNF"
        )
        if tp_elem is not None:
            if tp_elem.text == "0":
                return "Entrada"
            if tp_elem.text == "1":
                return "Saída"
    except Exception:
        log.exception("Erro ao inferir tipo de nota")
    return "Indefinido"


def atualizar_index_empresa(service, company_id: str) -> Dict[str, Dict]:
    """Atualiza ou cria o ``index_arquivos.json`` para a empresa."""
    index, idx_id = _read_index(service, company_id)
    arquivos = _scan_xmls(service, company_id)

    atual: Dict[str, Dict] = {}
    for arq in arquivos:
        file_id = arq["id"]
        info = index.get(file_id, {})
        if info.get("modificado") != arq.get("modifiedTime"):
            tipo = info.get("tipo")
            if not tipo or info.get("modificado") != arq.get("modifiedTime"):
                tipo = _infer_tipo_nota(service, file_id)
            atual[file_id] = {
                "nome": arq["name"],
                "caminho": arq["path"],
                "modificado": arq.get("modifiedTime"),
                "tipo": tipo,
            }
        else:
            atual[file_id] = info

    changed = index != atual
    if changed:
        _write_index(service, company_id, atual, idx_id)
    return atual


def _scan_xmls(service, folder_id: str, prefix: str = "") -> List[Dict[str, str]]:
    """Retorna metadados de todos os XMLs abaixo de ``folder_id``."""
    entries: List[Dict[str, str]] = []
    files = _list_files(service, folder_id)
    for f in files:
        if f["mimeType"] == "application/vnd.google-apps.folder":
            new_prefix = os.path.join(prefix, f["name"])
            entries.extend(_scan_xmls(service, f["id"], new_prefix))
            continue
        if f["name"].lower().endswith(".xml"):
            entries.append(
                {
                    "id": f["id"],
                    "name": f["name"],
                    "path": os.path.join(prefix, f["name"]),
                    "modifiedTime": f.get("modifiedTime"),
                }
            )
    return entries
def baixar_xmls_empresa(
    company_name: str,
    root_id: str = ROOT_FOLDER_ID,
    dest_dir: str | None = None,
) -> Tuple[List[str], List[str]]:
    """Baixa o ZIP de XMLs da empresa, extrai e retorna os caminhos."""

    if dest_dir is None:
        dest_dir = os.getcwd()

    service = get_drive_service()
    mensagens: List[str] = []

    empresa_id = _find_subfolder(service, root_id, company_name)
    if not empresa_id:
        mensagens.append(f"Empresa {company_name} não encontrada no Drive.")
        return [], mensagens

    compactadas_id = _find_subfolder(service, empresa_id, "NFs Compactadas")
    if not compactadas_id:
        mensagens.append("Subpasta 'NFs Compactadas' não encontrada.")
        return [], mensagens

    arquivos = _list_files(service, compactadas_id)
    zips = [f for f in arquivos if f["name"].lower().endswith(".zip")]
    if not zips:
        mensagens.append("Nenhum arquivo ZIP localizado em 'NFs Compactadas'.")
        return [], mensagens

    zips.sort(key=lambda f: f.get("modifiedTime", ""), reverse=True)
    zip_info = zips[0]
    zip_path = os.path.join(dest_dir, zip_info["name"])

    os.makedirs(dest_dir, exist_ok=True)
    mensagens.append(f"Baixando {zip_info['name']} do Drive...")
    request = service.files().get_media(fileId=zip_info["id"])
    with io.FileIO(zip_path, "wb") as fh:
        downloader = MediaIoBaseDownload(fh, request)
        done = False
        while not done:
            _, done = downloader.next_chunk()

    mensagens.append("Extraindo XMLs...")
    xml_paths: List[str] = []
    try:
        with zipfile.ZipFile(zip_path, "r") as zf:
            for name in zf.namelist():
                if name.lower().endswith(".xml"):
                    zf.extract(name, dest_dir)
                    xml_paths.append(os.path.join(dest_dir, name))
    except Exception as exc:
        mensagens.append(f"Erro ao extrair ZIP: {exc}")
        return [], mensagens

    mensagens.append(f"{len(xml_paths)} XMLs extraídos do ZIP.")
    return xml_paths, mensagens
