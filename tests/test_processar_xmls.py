import os
import sys
import pandas as pd

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, ROOT)

import modules.estoque_veiculos as ev


def test_processar_xmls_uses_configurador(monkeypatch):
    called = {"called": False}

    def fake_extrair(_):
        return [{
            "Emitente CNPJ/CPF": "111",
            "Destinatário CNPJ/CPF": "222",
            "CFOP": "1102",
            "Chassi": "ABCDEFGH123456789",
            "Data Emissão": pd.Timestamp("2023-01-01")
        }]

    def fake_config(df):
        called["called"] = True
        assert isinstance(df, pd.DataFrame)
        # Mimic creation of missing columns
        for col in ["Placa", "Renavam"]:
            if col not in df.columns:
                df[col] = None
        return df

    monkeypatch.setattr(ev, "extrair_dados_xml", lambda path: fake_extrair(path))
    monkeypatch.setattr(ev, "configurar_planilha", fake_config)

    df = ev.processar_xmls(["file.xml"], "111")
    assert called["called"]
    assert not df.empty


def test_processar_xmls_filters_columns(tmp_path):
    xml_content = '''<?xml version="1.0" encoding="UTF-8"?>
    <NFe xmlns="http://www.portalfiscal.inf.br/nfe">
        <infNFe Id="NFe000" versao="4.00">
            <ide>
                <nNF>1</nNF>
                <dhEmi>2023-01-01T12:00:00-03:00</dhEmi>
                <tpNF>1</tpNF>
            </ide>
            <emit>
                <CNPJ>12345678000199</CNPJ>
                <xNome>Emitente</xNome>
            </emit>
            <dest>
                <CNPJ>98765432000188</CNPJ>
                <xNome>Destinatario</xNome>
            </dest>
            <det nItem="1">
                <prod>
                    <xProd>CARRO XYZ</xProd>
                    <CFOP>5102</CFOP>
                    <vProd>1000.00</vProd>
                </prod>
                <imposto>
                    <ICMS>
                        <ICMS00>
                            <vICMS>180.00</vICMS>
                        </ICMS00>
                    </ICMS>
                </imposto>
            </det>
        </infNFe>
    </NFe>'''
    xml_file = tmp_path / "nota.xml"
    xml_file.write_text(xml_content, encoding="utf-8")
    df = ev.processar_xmls([str(xml_file)], "12345678000199")
    expected_cols = [
        "Tipo Nota",
        "CFOP",
        "Data Emissão",
        "Emitente CNPJ/CPF",
        "Destinatário CNPJ/CPF",
        "Chassi",
        "Placa",
        "Produto",
        "Valor Total",
        "Renavam",
        "KM",
        "Ano Modelo",
        "Ano Fabricação",
        "Cor",
        "ICMS Alíquota",
        "ICMS Valor",
        "ICMS Base",
        "CST ICMS",
        "Redução BC",
        "Modalidade BC",
        "Natureza Operação",
        "CHAVE XML",
        "Empresa CNPJ",
        "Tipo Produto",
        "Mês Emissão",
        "Alerta Auditoria",
    ]
    assert list(df.columns) == expected_cols

