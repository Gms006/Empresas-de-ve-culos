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
            "Emitente CNPJ": "111",
            "Destinatario CNPJ": "222",
            "CFOP": "1102",
            "Chassi": "ABCDEFGH123456789",
            "Data Emissão": pd.Timestamp("2023-01-01")
        }]

    def fake_config(df):
        called["called"] = True
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

