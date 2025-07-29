# Painel Fiscal de Veículos

Este projeto contém uma aplicação [Streamlit](https://streamlit.io/) para análise de notas fiscais de veículos. A partir dos arquivos XML das NFe é possível gerar relatórios de estoque, auditoria, KPIs e apuração fiscal.

## Integração com Google Drive

Os XMLs podem ser importados automaticamente de uma pasta no Google Drive. Para habilitar esta funcionalidade:

1. Salve o arquivo de chave do serviço Google no caminho `Chave_Veiculos.json`.
2. Confirme que suas empresas e respectivos CNPJs estão definidos em `config/empresas_config.json`.
3. Defina a variável de ambiente `GCP_SERVICE_ACCOUNT_JSON` com o conteúdo do JSON de serviço.
4. Execute a aplicação com `streamlit run app.py` e selecione:
   - A empresa desejada
   - O tipo de nota (Entradas, Saídas ou Ambas)
   - A opção **Google Drive** como origem
5. Clique em **"Buscar XMLs do Drive"** para iniciar o download e processamento.

O ID da pasta principal do Drive é `1ADaMbXNPEX8ZIT7c1U_pWMsRygJFROZq`. Dentro dela cada empresa possui as subpastas `Entradas` e `Saidas` contendo os XMLs.

O upload manual de arquivos continua disponível selecionando a opção *Upload Manual*.
