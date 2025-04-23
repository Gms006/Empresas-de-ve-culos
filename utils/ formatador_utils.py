
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
