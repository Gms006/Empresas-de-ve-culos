
def formatar_moeda(valor):
    try:
        return "R$ {:,.2f}".format(valor).replace(",", "X").replace(".", ",").replace("X", ".")
    except:
        return valor

def formatar_percentual(valor):
    try:
        return "{:.2f}%".format(valor)
    except:
        return valor

def formatar_data_curta(valor):
    """Formata datas no padrão brasileiro ``dd/mm/aaaa``."""
    import pandas as pd

    try:
        dt = pd.to_datetime(valor, errors="coerce")
        if pd.isna(dt):
            return ""
        return dt.strftime("%d/%m/%Y")
    except Exception:
        return valor
