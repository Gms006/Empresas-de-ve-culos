# Painel Fiscal de Veículos

Este projeto contém uma aplicação [Streamlit](https://streamlit.io/) para análise de notas fiscais de veículos. A partir dos arquivos XML das NFe é possível gerar relatórios de estoque, auditoria, KPIs e apuração fiscal.

## Integração com Google Drive

Os XMLs podem ser importados automaticamente de uma pasta no Google Drive. Para habilitar esta funcionalidade:

1. Defina a variável de ambiente `GCP_SERVICE_ACCOUNT_JSON` com o **JSON completo** da chave de serviço do Google (não um caminho de arquivo).
2. Confirme que suas empresas e respectivos CNPJs estão definidos em `config/empresas_config.json`.
3. Execute a aplicação com `streamlit run app.py` e selecione:
   - A empresa desejada
   - A opção **Google Drive** (ou *Upload Manual*) como origem
4. Clique em **"Buscar XMLs do Drive"** para iniciar o download e processamento.

O ID da pasta principal do Drive é `1ADaMbXNPEX8ZIT7c1U_pWMsRygJFROZq`. Dentro dela cada empresa possui uma subpasta chamada `NFs Compactadas` contendo um único arquivo ZIP com todos os XMLs da empresa. O sistema baixa automaticamente esse arquivo, extrai os XMLs e processa tudo de uma vez.

O upload manual de arquivos continua disponível selecionando a opção *Upload Manual*.
