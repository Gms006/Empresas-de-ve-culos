import pandas as pd
from pages import painel


def test_render_relatorios_uses_fiscal_generator(monkeypatch):
    calls = {"count": 0}

    def fake_generator(df, buffer, codigo_por_chassi=None):
        calls["count"] += 1
        assert "Valor Produtos" in df.columns

    monkeypatch.setattr(painel, "gerar_relatorio_fiscal_excel", fake_generator)
    monkeypatch.setattr(painel, "_mostrar_kpis", lambda k: None)
    monkeypatch.setattr(painel.st, "subheader", lambda *a, **k: None)
    monkeypatch.setattr(painel.st, "dataframe", lambda *a, **k: None)
    monkeypatch.setattr(painel.st, "download_button", lambda *a, **k: None)

    painel.st.session_state.df_estoque = pd.DataFrame({
        "Situação": ["Vendido"],
        "Chave": ["1"],
        "Produto": ["Carro"],
        "Valor Entrada": [100.0],
        "Valor Venda": [200.0],
        "Lucro": [100.0],
        "ICMS Valor_saida": [0.0],
        "ICMS Valor_entrada": [0.0],
    })
    painel.st.session_state.kpis = {}
    painel.st.session_state.df_resumo = pd.DataFrame()
    painel.st.session_state.df_alertas = pd.DataFrame()

    painel.render_relatorios()

    assert calls["count"] == 1
