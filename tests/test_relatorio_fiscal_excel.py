import os
import sys
import pandas as pd

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, ROOT)

from modules.relatorio_fiscal_excel import gerar_relatorio_fiscal_excel


def test_gerar_relatorio_fiscal_excel(tmp_path):
    df = pd.DataFrame(
        {
            "CPF/CNPJ": ["99.999.999/0001-01"],
            "Razão Social": ["Exemplo de Cliente"],
            "UF": ["SC"],
            "Município": ["Criciúma"],
            "Endereço": ["Rua X"],
            "Número Documento": ["123"],
            "Série": ["1"],
            "Data": ["2024-01-01"],
            "Situação": [0],
            "CFOP": ["5102"],
            "Valor Produtos": [100000.0],
            "Valor Descontos": [0.0],
            "Valor Contábil": [100000.0],
            "Lucro": [20000.0],
            "Chassi": ["ABC123"],
        }
    )

    saida = tmp_path / "relatorio.xlsx"
    codigo_mapa = {"ABC123": "COD123"}
    result = gerar_relatorio_fiscal_excel(df, saida, codigo_por_chassi=codigo_mapa)

    assert saida.exists(), "Arquivo Excel não foi criado"
    assert result.loc[0, "Base de Calculo ICMS"] == 5000.0
    assert result.loc[0, "Valor ICMS"] == 5000.0 * 0.19
    assert result.loc[0, "Base de Calculo PIS/COFINS"] == 20000.0
    assert result.loc[0, "Valor PIS"] == 20000.0 * 0.0065
    assert result.loc[0, "Valor COFINS"] == 20000.0 * 0.03
    assert result.loc[0, "Acumulador"] == 3
    assert result.loc[0, "Código do Item"] == "COD123"


def test_extracao_dados_basicos_xml(tmp_path):
    xml_content = '''<?xml version="1.0" encoding="UTF-8"?>
    <NFe xmlns="http://www.portalfiscal.inf.br/nfe">
      <infNFe Id="NFe0001" versao="4.00">
        <ide>
          <nNF>1234</nNF>
          <serie>1</serie>
          <dhEmi>2024-01-01T00:00:00-03:00</dhEmi>
        </ide>
        <dest>
          <CNPJ>99999999000101</CNPJ>
          <xNome>Cliente Teste</xNome>
          <enderDest>
            <UF>SC</UF>
            <xMun>Criciúma</xMun>
            <xLgr>Rua Exemplo</xLgr>
            <nro>1234</nro>
          </enderDest>
        </dest>
        <det nItem="1">
          <prod>
            <CFOP>5101</CFOP>
            <vProd>1000.00</vProd>
          </prod>
        </det>
      </infNFe>
    </NFe>'''

    xml_file = tmp_path / "nota.xml"
    xml_file.write_text(xml_content, encoding="utf-8")

    df = pd.DataFrame({
        "Valor Produtos": [1000.0],
        "XML Path": [str(xml_file)],
    })

    saida = tmp_path / "relatorio.xlsx"
    result = gerar_relatorio_fiscal_excel(df, saida)

    row = result.iloc[0]
    assert row["CPF/CNPJ"] == "99.999.999/0001-01"
    assert row["Razão Social"] == "Cliente Teste"
    assert row["UF"] == "SC"
    assert row["Município"] == "Criciúma"
    assert row["Endereço"] == "Rua Exemplo 1234"
    assert row["Número Documento"] == "1234"
    assert row["Série"] == "1"
    assert row["Data"] == "2024-01-01"
    assert row["CFOP"] == "5101"
