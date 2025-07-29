import os
import sys
import tempfile

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, ROOT)

from modules.estoque_veiculos import extrair_dados_xml

def test_extrair_icms_e_chave(tmp_path):
    xml_content = '''<?xml version="1.0" encoding="UTF-8"?>
<NFe xmlns="http://www.portalfiscal.inf.br/nfe">
    <infNFe Id="NFe12345678901234567890123456789012345678901234" versao="4.00">
        <ide>
            <nNF>1</nNF>
            <dhEmi>2023-01-01T12:00:00-03:00</dhEmi>
            <tpNF>1</tpNF>
        </ide>
        <emit>
            <CNPJ>12345678000199</CNPJ>
            <xNome>Empresa Emitente</xNome>
        </emit>
        <dest>
            <CNPJ>98765432000188</CNPJ>
            <xNome>Empresa Dest</xNome>
        </dest>
        <total>
            <ICMSTot>
                <vNF>1000.00</vNF>
            </ICMSTot>
        </total>
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

    registros = extrair_dados_xml(str(xml_file))
    assert len(registros) == 1
    registro = registros[0]
    assert float(registro["ICMS Valor"]) == 180.00
    assert registro["CHAVE XML"] == "NFe12345678901234567890123456789012345678901234"


def test_chassi_extraido_de_xprod(tmp_path):
    xml_content = '''<?xml version="1.0" encoding="UTF-8"?>
<NFe xmlns="http://www.portalfiscal.inf.br/nfe">
    <infNFe Id="NFe000" versao="4.00">
        <ide>
            <nNF>1</nNF>
            <dhEmi>2023-01-01T12:00:00-03:00</dhEmi>
        </ide>
        <emit>
            <CNPJ>12345678000199</CNPJ>
        </emit>
        <dest>
            <CNPJ>98765432000188</CNPJ>
        </dest>
        <det nItem="1">
            <prod>
                <xProd>BMW/X1 S20I ACTIVEFLEX 98M50AA00L4A92818</xProd>
            </prod>
        </det>
    </infNFe>
</NFe>'''
    xml_file = tmp_path / "nota_chassi.xml"
    xml_file.write_text(xml_content, encoding="utf-8")

    registros = extrair_dados_xml(str(xml_file))
    assert registros[0]["Chassi"] == "98M50AA00L4A92818"
