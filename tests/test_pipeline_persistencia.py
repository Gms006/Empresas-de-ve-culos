import pandas as pd
import streamlit as st
import painel


def _df_exemplo():
    return pd.DataFrame(
        {
            "Tipo Nota": ["Entrada", "Saída"],
            "Chassi": ["ABC", "ABC"],
            "Placa": ["AAA1234", "AAA1234"],
            "CFOP": ["1102", "5102"],
            "Valor Total": [100, 200],
            "Data Emissão": ["2023-01-01", "2023-01-02"],
            "Tipo Produto": ["Veículo", "Veículo"],
            "Alerta Auditoria": ["", ""],
            "Empresa CNPJ": ["123", "123"],
            "ICMS Valor": [0, 0],
        }
    )


def test_df_configurado_persistido(monkeypatch):
    df = _df_exemplo()
    monkeypatch.setattr(painel, "_processar_arquivos", lambda *args, **kwargs: df)
    st.session_state.clear()
    painel._init_session()
    painel._executar_pipeline(["x.xml"], "123")
    assert "df_configurado" in st.session_state
    assert not st.session_state.df_configurado.empty
