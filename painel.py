"""Alias para o painel localizado em ``pages/painel.py``."""

import sys
from pages import painel as _painel

# Torna este módulo um alias direto do painel real
sys.modules[__name__] = _painel

if __name__ == "__main__":  # pragma: no cover
    _painel.main()
