import json
from pathlib import Path

import pandas as pd
import streamlit as st
from datetime import date
from io import BytesIO


@st.cache_data
def _load_vendidos_data() -> pd.DataFrame:
    """Carrega dados de veículos vendidos.

    Os dados são lidos de ``dados/vendidos.csv``. Caso o arquivo não exista,
    retorna um ``DataFrame`` vazio com as colunas esperadas.
    """
    caminho = "dados/vendidos.csv"
    try:
        return pd.read_csv(
            caminho,
            parse_dates=["data_venda", "data_compra"],
            dtype={"empresa": str},
        )
    except FileNotFoundError:
        colunas = [
            "empresa",
            "data_compra",
            "data_venda",
            "chassi",
            "placa",
            "valor_compra",
            "valor_venda",
            "nota_compra",
            "nota_venda",
            "icms_compra",
            "icms_venda",
            "lucro_apurado",
        ]
        df = pd.DataFrame(columns=colunas)
        # garante que as colunas de data tenham tipo datetime para uso de ``.dt``
        df["data_venda"] = pd.to_datetime(df["data_venda"])
        df["data_compra"] = pd.to_datetime(df["data_compra"])
        return df


@st.cache_data
def _load_estoque_data() -> pd.DataFrame:
    """Carrega dados de veículos em estoque."""
    caminho = "dados/estoque.csv"
    try:
        return pd.read_csv(
            caminho, parse_dates=["data_compra"], dtype={"empresa": str}
        )
    except FileNotFoundError:
        colunas = [
            "empresa",
            "data_compra",
            "chassi",
            "placa",
            "valor_compra",
            "nota_compra",
            "icms_compra",
        ]
        df = pd.DataFrame(columns=colunas)
        df["data_compra"] = pd.to_datetime(df["data_compra"])
        return df


def _empresas_list() -> list[str]:
    """Lista empresas configuradas ou presentes nos dados."""

    empresas: set[str] = set()

    # Empresas definidas em arquivo de configuração
    path = Path("config/empresas_config.json")
    try:
        with open(path, encoding="utf-8") as f:
            empresas.update(json.load(f).keys())
    except FileNotFoundError:  # pragma: no cover - interface
        pass

    # Empresas já presentes nos CSVs
    df_v = _load_vendidos_data()
    df_e = _load_estoque_data()
    empresas.update(df_v.get("empresa", pd.Series()).dropna())
    empresas.update(df_e.get("empresa", pd.Series()).dropna())

    lista = sorted(empresas)
    return lista or [""]


def load_and_filter_vendidos(
    empresa: str,
    start_date,  # datetime.date
    end_date,  # datetime.date
    busca: str,
) -> pd.DataFrame:
    """Filtra os veículos vendidos por empresa, período e busca."""
    df = _load_vendidos_data().copy()
    if not df.empty:
        if empresa:
            df = df[df["empresa"] == empresa]
        df = df[
            (df["data_venda"] >= pd.to_datetime(start_date))
            & (df["data_venda"] <= pd.to_datetime(end_date))
        ]
        if busca:
            busca_lower = busca.lower()
            df = df[
                df["chassi"].str.lower().str.contains(busca_lower)
                | df["placa"].str.lower().str.contains(busca_lower)
            ]
    cols = [
        "data_venda",
        "chassi",
        "placa",
        "valor_compra",
        "valor_venda",
        "nota_compra",
        "nota_venda",
        "icms_compra",
        "icms_venda",
        "lucro_apurado",
    ]
    return df[cols] if not df.empty else pd.DataFrame(columns=cols)


def load_and_filter_estoque(empresa: str, busca: str) -> pd.DataFrame:
    """Retorna veículos em estoque filtrando por empresa e busca."""
    df = _load_estoque_data().copy()
    if not df.empty:
        if empresa:
            df = df[df["empresa"] == empresa]
        if busca:
            busca_lower = busca.lower()
            df = df[
                df["chassi"].str.lower().str.contains(busca_lower)
                | df["placa"].str.lower().str.contains(busca_lower)
            ]
    cols = [
        "data_compra",
        "chassi",
        "placa",
        "valor_compra",
        "nota_compra",
        "icms_compra",
    ]
    return df[cols] if not df.empty else pd.DataFrame(columns=cols)


def _df_to_excel(df: pd.DataFrame) -> bytes:
    """Converte ``DataFrame`` para bytes de um arquivo Excel."""
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False)
    return output.getvalue()


def _link_painel() -> None:
    """Adiciona link para o painel de importação, ignorando falhas.

    Quando a aplicação é executada fora do comando ``streamlit run`` o registro
    de páginas não está disponível e ``st.sidebar.page_link`` levanta
    ``KeyError``. Para evitar que a interface quebre nesses cenários o erro é
    simplesmente ignorado.
    """

    try:  # pragma: no cover - depende de execução via Streamlit
        st.sidebar.page_link("pages/painel.py", label="Importar notas via Drive")
    except KeyError:
        pass


def show_home() -> None:
    st.set_page_config(layout="wide", page_title="Home - Emp. de Veículos")

    st.sidebar.title("Filtros")
    _link_painel()
    empresas_list = _empresas_list()
    empresa = st.sidebar.selectbox("Empresa", empresas_list)
    mes_inicio, mes_fim = st.sidebar.slider("Mês", 1, 12, (1, 12))

    df_v = _load_vendidos_data().copy()
    if empresa:
        df_v = df_v[df_v["empresa"] == empresa]
    df_v = df_v[df_v["data_venda"].dt.month.between(mes_inicio, mes_fim)]

    df_e = _load_estoque_data().copy()
    if empresa:
        df_e = df_e[df_e["empresa"] == empresa]

    qtd_vend = len(df_v)
    total_compra = df_v["valor_compra"].sum()
    total_venda = df_v["valor_venda"].sum()
    lucro = total_venda - total_compra
    icms_debito = df_v["icms_venda"].sum()
    icms_credito = df_v["icms_compra"].sum()
    qtd_estoque = len(df_e)

    c1, c2, c3, c4, c5, c6, c7 = st.columns(7)
    c1.metric("Qtd. Vendidos", f"{qtd_vend:.0f}")
    c2.metric("Total Compra", f"R$ {total_compra:,.2f}")
    c3.metric("Total Venda", f"R$ {total_venda:,.2f}")
    c4.metric("Lucro Apurado", f"R$ {lucro:,.2f}")
    c5.metric("ICMS Débito", f"R$ {icms_debito:,.2f}")
    c6.metric("ICMS Crédito", f"R$ {icms_credito:,.2f}")
    c7.metric("Estoque Atual", f"{qtd_estoque}")
    c7.write("🚗")


def show_reports() -> None:
    st.set_page_config(layout="wide", page_title="Relatórios - Emp. de Veículos")

    st.sidebar.title("Filtros")
    _link_painel()
    empresas_list = _empresas_list()
    empresa = st.sidebar.selectbox("Empresa", empresas_list)
    data_ini = date.today().replace(month=1, day=1)
    data_fim = date.today()
    start_date, end_date = st.sidebar.date_input("Período", [data_ini, data_fim])
    busca = st.sidebar.text_input("Buscar chassi ou placa")

    tab1, tab2 = st.tabs(["Carros Vendidos", "Carros em Estoque"])

    with tab1:
        st.header("📋 Carros Vendidos")
        df = load_and_filter_vendidos(empresa, start_date, end_date, busca)
        st.download_button(
            "📥 Exportar Excel",
            _df_to_excel(df),
            file_name="relatorio_vendidos.xlsx",
            mime=(
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            ),
        )
        st.dataframe(df, use_container_width=True)
        st.markdown("### 📊 Lucro por Mês")
        if not df.empty:
            lucro_por_mes = (
                df.set_index("data_venda").resample("M")["lucro_apurado"].sum()
            )
        else:
            lucro_por_mes = pd.Series(dtype="float")
        st.bar_chart(lucro_por_mes)

    with tab2:
        st.header("🚗 Carros em Estoque")
        df_estoque = load_and_filter_estoque(empresa, busca)
        qtd_estoque = len(df_estoque)
        avg_compra = df_estoque["valor_compra"].mean()
        m1, m2 = st.columns(2)
        m1.metric("Qtd. em Estoque", f"{qtd_estoque}")
        m2.metric("Média Compra", f"R$ {avg_compra:,.2f}")
        st.download_button(
            "📥 Exportar Excel",
            _df_to_excel(df_estoque),
            file_name="relatorio_estoque.xlsx",
            mime=(
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            ),
        )
        st.dataframe(df_estoque, use_container_width=True)


def main() -> None:
    page = st.sidebar.radio("Ir para:", ["Home", "Relatórios"])
    if page == "Home":
        show_home()
    else:
        show_reports()


if __name__ == "__main__":
    main()
