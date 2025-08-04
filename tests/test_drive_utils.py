from pathlib import Path

import utils.drive_utils as du


def test_baixar_xmls_empresa_zip(monkeypatch, tmp_path):
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
        Path(destino).write_bytes(b"")
        # Simula que o site extraiu o ZIP criando um XML na pasta destino
        xml_path = Path(destino).parent / "nfe1.xml"
        xml_path.write_text("<xml />", encoding="utf-8")

    monkeypatch.setattr(du, "_buscar_subpasta_id", fake_buscar_subpasta_id)
    monkeypatch.setattr(du, "listar_arquivos", fake_listar_arquivos)
    monkeypatch.setattr(du, "baixar_arquivo", fake_baixar_arquivo)

    xmls = du.baixar_xmls_empresa_zip(None, "root", "Empresa", tmp_path)
    assert xmls == [str(tmp_path / "nfe1.xml")]
