from pathlib import Path
import logging

import pytest
import utils.drive_utils as du


def test_baixar_xmls_empresa_zip(monkeypatch, tmp_path, caplog):
    def fake_buscar_subpasta_id(service, parent_id, nome):
        assert parent_id == "root"
        assert nome == "Empresa"
        return "id_empresa"

    def fake_listar_arquivos(service, pasta_id):
        assert pasta_id == "id_empresa"
        return [{"name": "qualquer.zip", "id": "zip1"}]

    def fake_baixar_arquivo(service, file_id, destino):
        assert file_id == "zip1"
        Path(destino).parent.mkdir(parents=True, exist_ok=True)
        import zipfile

        with zipfile.ZipFile(destino, "w") as zf:
            zf.writestr("sub/nfe1.xml", "<xml />")
    monkeypatch.setattr(du, "_buscar_subpasta_id", fake_buscar_subpasta_id)
    monkeypatch.setattr(du, "listar_arquivos", fake_listar_arquivos)
    monkeypatch.setattr(du, "baixar_arquivo", fake_baixar_arquivo)

    with caplog.at_level(logging.INFO):
        xmls = du.baixar_xmls_empresa_zip(None, "root", "Empresa", tmp_path)
    assert xmls == [str(tmp_path / "sub" / "nfe1.xml")]
    assert any("qualquer.zip" in r.message for r in caplog.records)


def test_multiplos_zips_sem_config(monkeypatch, tmp_path):
    def fake_buscar_subpasta_id(service, parent_id, nome):
        return "id_empresa"

    def fake_listar_arquivos(service, pasta_id):
        return [
            {"name": "a.zip", "id": "a"},
            {"name": "b.zip", "id": "b"},
        ]

    monkeypatch.setattr(du, "_buscar_subpasta_id", fake_buscar_subpasta_id)
    monkeypatch.setattr(du, "listar_arquivos", fake_listar_arquivos)

    with pytest.raises(RuntimeError):
        du.baixar_xmls_empresa_zip(None, "root", "Empresa", tmp_path)


def test_multiplos_zips_com_config(monkeypatch, tmp_path):
    def fake_buscar_subpasta_id(service, parent_id, nome):
        return "id_empresa"

    def fake_listar_arquivos(service, pasta_id):
        return [
            {"name": "a.zip", "id": "a"},
            {"name": "b.zip", "id": "b"},
        ]

    def fake_baixar_arquivo(service, file_id, destino):
        assert file_id == "b"
        Path(destino).parent.mkdir(parents=True, exist_ok=True)
        import zipfile

        with zipfile.ZipFile(destino, "w") as zf:
            zf.writestr("nfe.xml", "<xml />")

    monkeypatch.setattr(du, "_buscar_subpasta_id", fake_buscar_subpasta_id)
    monkeypatch.setattr(du, "listar_arquivos", fake_listar_arquivos)
    monkeypatch.setattr(du, "baixar_arquivo", fake_baixar_arquivo)
    monkeypatch.setenv("NOME_ARQUIVO_ZIP", "b.zip")

    xmls = du.baixar_xmls_empresa_zip(None, "root", "Empresa", tmp_path)
    assert xmls == [str(tmp_path / "nfe.xml")]
