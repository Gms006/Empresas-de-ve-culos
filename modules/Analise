import pandas as pd
import numpy as np
import logging
import os
import yaml
from datetime import datetime
from dateutil.relativedelta import relativedelta
import json

# Configuração de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('apuracao_fiscal.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('apuracao_fiscal')

# Constantes e configurações
CONFIG_FILE = 'config_fiscal.yaml'

def carregar_configuracoes(arquivo=CONFIG_FILE):
    """Carrega configurações fiscais de arquivo externo."""
    try:
        if os.path.exists(arquivo):
            with open(arquivo, 'r', encoding='utf-8') as file:
                return yaml.safe_load(file)
        else:
            # Configurações padrão
            config_padrao = {
                'aliquotas': {
                    'icms': {
                        'revenda_veiculos': 0.19,
                        'revenda_pecas': 0.20,
                    },
                    'pis_cofins': 0.0365,  # Soma de PIS (0,65%) e COFINS (3%)
                    'irpj': {
                        'aliquota_base': 0.15,
                        'adicional': 0.10,
                        'limite_trimestral': 60000
                    },
                    'csll': 0.09,
                    'presuncao_lucro': {
                        'revenda_veiculos': 0.32,
                        'revenda_pecas': 0.38,
                        'servicos': 0.32
                    }
                },
                'regras_especificas': {
                    'icms_st_aliquota': 0.12,
                    'margem_valor_agregado': 0.30,
                    'considerar_icms_st': True
                }
            }
            # Salva configurações padrão
            with open(arquivo, 'w', encoding='utf-8') as file:
                yaml.dump(config_padrao, file, default_flow_style=False)
            logger.info(f"Arquivo de configuração criado: {arquivo}")
            return config_padrao
    except Exception as e:
        logger.error(f"Erro ao carregar configurações: {e}")
        raise

def validar_dados(df):
    """Valida e limpa o DataFrame de entrada."""
    if df is None or df.empty:
        raise ValueError("DataFrame vazio ou nulo fornecido")
    
    # Verificar colunas necessárias
    colunas_necessarias = [
        'Situação', 'Data Saída', 'Lucro', 'Valor Venda', 
        'Valor Custo', 'Tipo Veículo', 'CNPJ/CPF Cliente'
    ]
    
    colunas_faltantes = [col for col in colunas_necessarias if col not in df.columns]
    if colunas_faltantes:
        # Tentar mapear nomes de colunas semelhantes
        mapeamento_sugerido = {}
        for col_faltante in colunas_faltantes:
            if col_faltante == 'Data Saída' and 'Data Venda' in df.columns:
                mapeamento_sugerido['Data Venda'] = 'Data Saída'
            elif col_faltante == 'Valor Venda' and 'Preço Venda' in df.columns:
                mapeamento_sugerido['Preço Venda'] = 'Valor Venda'
            elif col_faltante == 'Tipo Veículo' and 'Categoria' in df.columns:
                mapeamento_sugerido['Categoria'] = 'Tipo Veículo'
        
        if mapeamento_sugerido:
            df = df.rename(columns=mapeamento_sugerido)
            colunas_faltantes = [col for col in colunas_necessarias if col not in df.columns]
            logger.info(f"Colunas mapeadas automaticamente: {mapeamento_sugerido}")
        
        if colunas_faltantes:
            raise ValueError(f"Colunas necessárias não encontradas: {', '.join(colunas_faltantes)}")
    
    # Converter e limpar dados
    df_limpo = df.copy()
    
    # Tratamento de datas
    if 'Data Saída' in df_limpo.columns:
        df_limpo['Data Saída'] = pd.to_datetime(df_limpo['Data Saída'], errors='coerce')
        # Identificar linhas com datas inválidas
        linhas_invalidas = df_limpo['Data Saída'].isna()
        if linhas_invalidas.any():
            logger.warning(f"Encontradas {linhas_invalidas.sum()} linhas com datas inválidas")
    
    # Tratamento de valores numéricos
    for coluna in ['Lucro', 'Valor Venda', 'Valor Custo']:
        if coluna in df_limpo.columns:
            df_limpo[coluna] = pd.to_numeric(df_limpo[coluna], errors='coerce').fillna(0)
    
    # Validar situação do veículo
    if 'Situação' in df_limpo.columns:
        situacoes_validas = ['Vendido', 'Em Estoque', 'Reservado']
        situacoes_invalidas = df_limpo[~df_limpo['Situação'].isin(situacoes_validas)]['Situação'].unique()
        if len(situacoes_invalidas) > 0:
            logger.warning(f"Encontradas situações não padrão: {', '.join(situacoes_invalidas)}")
    
    # Verificar se há lucro calculado corretamente
    if 'Lucro' in df_limpo.columns and 'Valor Venda' in df_limpo.columns and 'Valor Custo' in df_limpo.columns:
        # Calcular lucro esperado
        lucro_esperado = df_limpo['Valor Venda'] - df_limpo['Valor Custo']
        # Comparar com lucro informado
        diferenca = (df_limpo['Lucro'] - lucro_esperado).abs()
        if (diferenca > 0.1).any():  # Tolerância de 10 centavos para arredondamentos
            logger.warning(f"Encontradas {(diferenca > 0.1).sum()} linhas com lucro inconsistente")
            # Corrigir automaticamente
            df_limpo['Lucro'] = lucro_esperado
            logger.info("Lucro recalculado automaticamente")
    
    return df_limpo

def classificar_operacoes(df):
    """Classifica operações para aplicar alíquotas corretas."""
    df = df.copy()
    
    # Classificar tipo de veículo se existir a coluna
    if 'Tipo Veículo' in df.columns:
        # Padronizar nomes para minúsculo e sem acentos
        df['Tipo Veículo'] = df['Tipo Veículo'].str.lower().str.normalize('NFKD').str.encode('ascii', errors='ignore').str.decode('utf-8')
        
        # Criar categorias fiscais
        condicoes = [
            df['Tipo Veículo'].str.contains('caminhao|caminhão|truck|carreta|reboque'),
            df['Tipo Veículo'].str.contains('moto|motocicleta|scooter'),
            df['Tipo Veículo'].str.contains('onibus|ônibus|van|micro'),
            df['Tipo Veículo'].str.contains('importado|import')
        ]
        
        categorias = [
            'veiculos_pesados',
            'motocicletas',
            'transporte_coletivo',
            'importados'
        ]
        
        df['Categoria Fiscal'] = np.select(condicoes, categorias, default='veiculos_passeio')
    else:
        # Categoria padrão se não houver informação
        df['Categoria Fiscal'] = 'veiculos_passeio'
    
    # Classificar tipo de operação (interestadual ou interna)
    if 'UF Cliente' in df.columns and 'UF Empresa' in df.columns:
        df['Operação'] = np.where(df['UF Cliente'] == df['UF Empresa'], 'interna', 'interestadual')
    else:
        df['Operação'] = 'interna'  # Padrão
    
    return df

def calcular_icms_st(df, config):
    """Calcula ICMS-ST se aplicável."""
    if not config['regras_especificas']['considerar_icms_st']:
        return df
    
    df = df.copy()
    
    # Base de cálculo do ICMS-ST (valor da operação + IPI + frete + outras despesas + MVA)
    mva = config['regras_especificas']['margem_valor_agregado']
    
    # Verificar se tem coluna de valor de venda
    if 'Valor Venda' in df.columns:
        # Cálculo simplificado para demonstração
        df['Base ICMS-ST'] = df['Valor Venda'] * (1 + mva)
        
        # ICMS normal
        aliquota_icms = config['aliquotas']['icms']['revenda_veiculos']
        df['ICMS Normal'] = df['Valor Venda'] * aliquota_icms
        
        # ICMS-ST
        aliquota_st = config['regras_especificas']['icms_st_aliquota']
        df['ICMS-ST'] = (df['Base ICMS-ST'] * aliquota_st) - df['ICMS Normal']
        
        # Garantir que ICMS-ST não seja negativo
        df['ICMS-ST'] = df['ICMS-ST'].clip(lower=0)
    
    return df

def calcular_tributos(df, config, periodo=None):
    """Calcula tributos com base nas configurações fornecidas."""
    df = df.copy()
    
    # Filtrar por período se especificado
    if periodo:
        if isinstance(periodo, tuple) and len(periodo) == 2:
            inicio, fim = periodo
            df = df[(df['Data Saída'] >= inicio) & (df['Data Saída'] <= fim)]
        else:
            logger.warning("Formato de período inválido. Usando todos os dados.")
    
    # Filtrar apenas veículos vendidos
    df_vendidos = df[df["Situação"] == "Vendido"].copy()
    
    if df_vendidos.empty:
        logger.warning("Nenhum veículo vendido encontrado no período")
        return pd.DataFrame(), df_vendidos
    
    # Adicionar trimestre para cálculos do IRPJ/CSLL
    df_vendidos["Trimestre"] = df_vendidos["Data Saída"].dt.to_period("Q")
    df_vendidos["Trimestre_Texto"] = df_vendidos["Trimestre"].dt.strftime("%Y-T%q")
    
    # Adicionar mês para cálculos mensais como PIS/COFINS
    df_vendidos["Mês"] = df_vendidos["Data Saída"].dt.to_period("M")
    df_vendidos["Mês_Texto"] = df_vendidos["Data Saída"].dt.strftime("%Y-%m")
    
    # Alíquotas base
    aliquota_pis_cofins = config['aliquotas']['pis_cofins']
    
    # Calcular tributos por linha
    # PIS/COFINS - mensal - regime não-cumulativo para revenda
    df_vendidos["PIS/COFINS"] = df_vendidos["Lucro"] * aliquota_pis_cofins
    
    # Aplicar alíquotas específicas por categoria de veículo para ICMS
    df_vendidos["ICMS"] = df_vendidos["Lucro"] * config['aliquotas']['icms']['revenda_veiculos']
    
    # Base de cálculo para IRPJ/CSLL - varia conforme atividade
    df_vendidos["Base IRPJ/CSLL"] = df_vendidos["Lucro"] * config['aliquotas']['presuncao_lucro']['revenda_veiculos']
    
    # IRPJ/CSLL - trimestral
    aliquota_irpj = config['aliquotas']['irpj']['aliquota_base']
    aliquota_csll = config['aliquotas']['csll']
    
    df_vendidos["IRPJ"] = df_vendidos["Base IRPJ/CSLL"] * aliquota_irpj
    df_vendidos["CSLL"] = df_vendidos["Base IRPJ/CSLL"] * aliquota_csll
    
    # Adicional de IRPJ será calculado após agrupamento por trimestre
    df_vendidos["Adicional IRPJ"] = 0.0
    
    # Somar tributos
    colunas_tributos = ["ICMS", "PIS/COFINS", "IRPJ", "CSLL"]
    if "ICMS-ST" in df_vendidos.columns:
        colunas_tributos.append("ICMS-ST")
    
    df_vendidos["Total Tributos"] = df_vendidos[colunas_tributos].sum(axis=1)
    df_vendidos["Lucro Líquido"] = df_vendidos["Lucro"] - df_vendidos["Total Tributos"]
    
    # Agrupar por Trimestre para IRPJ/CSLL
    resumo_trimestral = df_vendidos.groupby("Trimestre_Texto").agg({
        "Lucro": "sum",
        "Base IRPJ/CSLL": "sum",
        "IRPJ": "sum",
        "CSLL": "sum",
        "Total Tributos": "sum",
        "Lucro Líquido": "sum"
    }).reset_index()
    
    # Calcular adicional IRPJ (10% sobre o valor que exceder R$ 60.000 por trimestre)
    limite_trimestral = config['aliquotas']['irpj']['limite_trimestral']
    aliquota_adicional = config['aliquotas']['irpj']['adicional']
    
    resumo_trimestral["Adicional IRPJ"] = resumo_trimestral["Base IRPJ/CSLL"].apply(
        lambda base: max(0, (base - limite_trimestral) * aliquota_adicional)
    )
    
    # Atualizar totais após adicional
    resumo_trimestral["Total Tributos"] += resumo_trimestral["Adicional IRPJ"]
    resumo_trimestral["Lucro Líquido"] -= resumo_trimestral["Adicional IRPJ"]
    
    # Agrupar por Mês para outros tributos
    resumo_mensal = df_vendidos.groupby("Mês_Texto").agg({
        "Lucro": "sum",
        "ICMS": "sum",
        "PIS/COFINS": "sum",
        "Total Tributos": "sum",
        "Lucro Líquido": "sum"
    }).reset_index()
    
    # Adicionar ICMS-ST se existir
    if "ICMS-ST" in df_vendidos.columns:
        resumo_mensal["ICMS-ST"] = df_vendidos.groupby("Mês_Texto")["ICMS-ST"].sum().values
    
    # Calcular totais gerais
    total_geral = {
        "Lucro": df_vendidos["Lucro"].sum(),
        "ICMS": df_vendidos["ICMS"].sum(),
        "PIS/COFINS": df_vendidos["PIS/COFINS"].sum(),
        "Base IRPJ/CSLL": df_vendidos["Base IRPJ/CSLL"].sum(),
        "IRPJ": df_vendidos["IRPJ"].sum(),
        "CSLL": df_vendidos["CSLL"].sum(),
        "Adicional IRPJ": resumo_trimestral["Adicional IRPJ"].sum(),
        "Total Tributos": df_vendidos["Total Tributos"].sum() + resumo_trimestral["Adicional IRPJ"].sum(),
        "Lucro Líquido": df_vendidos["Lucro Líquido"].sum() - resumo_trimestral["Adicional IRPJ"].sum()
    }
    
    if "ICMS-ST" in df_vendidos.columns:
        total_geral["ICMS-ST"] = df_vendidos["ICMS-ST"].sum()
    
    return {
        'resumo_trimestral': resumo_trimestral,
        'resumo_mensal': resumo_mensal,
        'total_geral': total_geral,
        'detalhamento': df_vendidos
    }

def gerar_relatorio_fiscal(resultados, periodo, formato='excel'):
    """Gera relatórios fiscais em diferentes formatos."""
    today = datetime.now().strftime('%Y%m%d')
    
    if isinstance(periodo, tuple) and len(periodo) == 2:
        inicio, fim = periodo
        periodo_str = f"{inicio.strftime('%Y%m%d')}_a_{fim.strftime('%Y%m%d')}"
    else:
        periodo_str = 'completo'
    
    nome_base = f"relatorio_fiscal_{periodo_str}_{today}"
    
    # Extrair DataFrames dos resultados
    resumo_trimestral = resultados.get('resumo_trimestral', pd.DataFrame())
    resumo_mensal = resultados.get('resumo_mensal', pd.DataFrame())
    detalhamento = resultados.get('detalhamento', pd.DataFrame())
    total_geral = resultados.get('total_geral', {})
    
    # Formatar valores para visualização
    for df in [resumo_trimestral, resumo_mensal, detalhamento]:
        if not df.empty:
            for coluna in df.select_dtypes(include=['float64']).columns:
                df[coluna] = df[coluna].round(2)
    
    # Excel (formato padrão e mais completo)
    if formato.lower() in ['excel', 'xlsx', 'xls']:
        arquivo = f"{nome_base}.xlsx"
        with pd.ExcelWriter(arquivo, engine='openpyxl') as writer:
            resumo_trimestral.to_excel(writer, sheet_name='Resumo Trimestral', index=False)
            resumo_mensal.to_excel(writer, sheet_name='Resumo Mensal', index=False)
            
            # Total geral como uma linha
            pd.DataFrame([total_geral]).to_excel(writer, sheet_name='Total Geral', index=False)
            
            # Detalhamento completo
            if not detalhamento.empty:
                colunas_detalhamento = [
                    'Data Saída', 'Trimestre_Texto', 'Mês_Texto', 'Lucro',
                    'ICMS', 'PIS/COFINS', 'Base IRPJ/CSLL', 'IRPJ', 'CSLL',
                    'Total Tributos', 'Lucro Líquido'
                ]
                
                # Adicionar ICMS-ST se existir
                if 'ICMS-ST' in detalhamento.columns:
                    colunas_detalhamento.insert(colunas_detalhamento.index('ICMS') + 1, 'ICMS-ST')
                
                # Filtrar e ordenar colunas
                detalhamento_export = detalhamento[
                    [col for col in colunas_detalhamento if col in detalhamento.columns]
                ]
                detalhamento_export.to_excel(writer, sheet_name='Detalhamento', index=False)
        
        logger.info(f"Relatório Excel gerado: {arquivo}")
        return arquivo
    
    # CSV (formato simples, apenas resumos)
    elif formato.lower() == 'csv':
        arquivo_trimestral = f"{nome_base}_trimestral.csv"
        arquivo_mensal = f"{nome_base}_mensal.csv"
        
        resumo_trimestral.to_csv(arquivo_trimestral, index=False)
        resumo_mensal.to_csv(arquivo_mensal, index=False)
        
        logger.info(f"Relatórios CSV gerados: {arquivo_trimestral}, {arquivo_mensal}")
        return [arquivo_trimestral, arquivo_mensal]
    
    # JSON (formato para integração com outros sistemas)
    elif formato.lower() == 'json':
        arquivo = f"{nome_base}.json"
        
        # Preparar dicionário para JSON
        dados_json = {
            'resumo_trimestral': resumo_trimestral.to_dict(orient='records'),
            'resumo_mensal': resumo_mensal.to_dict(orient='records'),
            'total_geral': total_geral
        }
        
        with open(arquivo, 'w', encoding='utf-8') as f:
            json.dump(dados_json, f, ensure_ascii=False, indent=4)
        
        logger.info(f"Relatório JSON gerado: {arquivo}")
        return arquivo
    
    else:
        logger.error(f"Formato de relatório não suportado: {formato}")
        raise ValueError(f"Formato '{formato}' não suportado. Use 'excel', 'csv' ou 'json'.")

def analise_mensal_saidas(df, ano=None, mes=None):
    """Análise específica de saídas mensais."""
    df = df.copy()
    
    # Filtrar apenas veículos vendidos
    df_vendidos = df[df["Situação"] == "Vendido"].copy()
    
    if df_vendidos.empty:
        logger.warning("Nenhum veículo vendido encontrado")
        return pd.DataFrame()
    
    # Garantir que a coluna de data está correta
    df_vendidos["Data Saída"] = pd.to_datetime(df_vendidos["Data Saída"], errors="coerce")
    
    # Filtrar por ano e mês se especificados
    if ano and mes:
        df_vendidos = df_vendidos[
            (df_vendidos["Data Saída"].dt.year == ano) & 
            (df_vendidos["Data Saída"].dt.month == mes)
        ]
    
    # Adicionar mês para agrupamento
    df_vendidos["Mês"] = df_vendidos["Data Saída"].dt.to_period("M")
    df_vendidos["Mês_Texto"] = df_vendidos["Data Saída"].dt.strftime("%Y-%m")
    
    # Análise por tipo de veículo se disponível
    if "Tipo Veículo" in df_vendidos.columns:
        analise_tipo = df_vendidos.groupby(["Mês_Texto", "Tipo Veículo"]).agg({
            "Lucro": ["sum", "mean", "count"],
            "Valor Venda": ["sum", "mean"],
            "Valor Custo": ["sum", "mean"]
        })
        
        # Achatar hierarquia para facilitar visualização
        analise_tipo.columns = [f"{col[0]}_{col[1]}" for col in analise_tipo.columns]
        analise_tipo = analise_tipo.reset_index()
        
        # Calcular margem média
        analise_tipo["Margem_Media"] = (analise_tipo["Lucro_sum"] / analise_tipo["Valor Venda_sum"] * 100).round(2)
        
        return analise_tipo
    
    # Análise básica se não houver tipo de veículo
    analise_basica = df_vendidos.groupby("Mês_Texto").agg({
        "Lucro": ["sum", "mean", "count"],
        "Valor Venda": ["sum", "mean"],
        "Valor Custo": ["sum", "mean"]
    })
    
    # Achatar hierarquia
    analise_basica.columns = [f"{col[0]}_{col[1]}" for col in analise_basica.columns]
    analise_basica = analise_basica.reset_index()
    
    # Calcular margem média
    analise_basica["Margem_Media"] = (analise_basica["Lucro_sum"] / analise_basica["Valor Venda_sum"] * 100).round(2)
    
    return analise_basica

def analisar_estoque(df):
    """Analisa veículos em estoque e métricas relacionadas."""
    df = df.copy()
    
    # Filtrar veículos em estoque
    df_estoque = df[df["Situação"] == "Em Estoque"].copy()
    
    if df_estoque.empty:
        logger.warning("Nenhum veículo em estoque encontrado")
        return pd.DataFrame()
    
    # Calcular idade do estoque
    hoje = pd.Timestamp('today')
    if "Data Entrada" in df_estoque.columns:
        df_estoque["Data Entrada"] = pd.to_datetime(df_estoque["Data Entrada"], errors="coerce")
        df_estoque["Dias em Estoque"] = (hoje - df_estoque["Data Entrada"]).dt.days
    
    # Resumo por tipo de veículo se disponível
    if "Tipo Veículo" in df_estoque.columns:
        resumo_estoque = df_estoque.groupby("Tipo Veículo").agg({
            "Valor Custo": ["sum", "mean", "count"],
            "Dias em Estoque": ["mean", "max", "min"] if "Dias em Estoque" in df_estoque.columns else []
        })
        
        # Achatar hierarquia
        if not resumo_estoque.empty:
            resumo_estoque.columns = [f"{col[0]}_{col[1]}" for col in resumo_estoque.columns]
            resumo_estoque = resumo_estoque.reset_index()
            
            # Renomear contagem para "Quantidade"
            if "Valor Custo_count" in resumo_estoque.columns:
                resumo_estoque = resumo_estoque.rename(columns={"Valor Custo_count": "Quantidade"})
        
        return resumo_estoque
    
    # Resumo básico se não houver tipo de veículo
    resumo_basico = {
        "Total Veículos": len(df_estoque),
        "Valor Total Estoque": df_estoque["Valor Custo"].sum(),
        "Valor Médio Unitário": df_estoque["Valor Custo"].mean()
    }
    
    if "Dias em Estoque" in df_estoque.columns:
        resumo_basico.update({
            "Média Dias em Estoque": df_estoque["Dias em Estoque"].mean(),
            "Máximo Dias em Estoque": df_estoque["Dias em Estoque"].max(),
            "Mínimo Dias em Estoque": df_estoque["Dias em Estoque"].min()
        })
    
    return pd.DataFrame([resumo_basico])

def processar_apuracao_completa(arquivo_excel, periodo=None, gerar_relatorio=True, formato_relatorio='excel'):
    """Função principal que processa todos os dados e gera apuração completa."""
    try:
        # Carregar dados
        logger.info(f"Carregando dados do arquivo: {arquivo_excel}")
        df_estoque = pd.read_excel(arquivo_excel)
        
        # Carregar configurações
        config = carregar_configuracoes()
        
        # Validar e limpar dados
        logger.info("Validando e limpando dados")
        df_limpo = validar_dados(df_estoque)
        
        # Classificar operações
        logger.info("Classificando operações")
        df_classificado = classificar_operacoes(df_limpo)
        
        # Calcular ICMS-ST se aplicável
        logger.info("Calculando ICMS-ST")
        df_com_st = calcular_icms_st(df_classificado, config)
        
        # Definir período se não especificado
        if not periodo:
            # Usar mês atual como padrão
            hoje = datetime.now()
            inicio_mes = datetime(hoje.year, hoje.month, 1)
            fim_mes = inicio_mes + relativedelta(months=1, days=-1)
            periodo = (inicio_mes, fim_mes)
            logger.info(f"Usando período padrão: {inicio_mes.strftime('%d/%m/%Y')} a {fim_mes.strftime('%d/%m/%Y')}")
        
        # Calcular tributos
        logger.info("Calculando tributos")
        resultados_tributos = calcular_tributos(df_com_st, config, periodo)
        
        # Análise de saídas mensais
        logger.info("Analisando saídas mensais")
        if periodo and isinstance(periodo, tuple) and len(periodo) == 2:
            inicio, fim = periodo
            analise_saidas = analise_mensal_saidas(df_com_st, ano=inicio.year, mes=inicio.month)
        else:
            analise_saidas = analise_mensal_saidas(df_com_st)
        
        # Análise de estoque
        logger.info("Analisando estoque")
        analise_estoque = analisar_estoque(df_com_st)
        
        # Gerar relatório se solicitado
        if gerar_relatorio:
            logger.info(f"Gerando relatório no formato: {formato_relatorio}")
            caminho_relatorio = gerar_relatorio_fiscal(resultados_tributos, periodo, formato_relatorio)
            logger.info(f"Relatório gerado com sucesso: {caminho_relatorio}")
        
        # Compilar resultados completos
        resultados_completos = {
            'tributos': resultados_tributos,
            'analise_saidas': analise_saidas,
            'analise_estoque': analise_estoque
        }
        
        return resultados_completos
    
    except Exception as e:
        logger.error(f"Erro ao processar apuração: {str(e)}", exc_info=True)
        raise

def gerar_dashboards(resultados):
    """Gera visualizações e dashboards para análise gerencial."""
    try:
        import matplotlib.pyplot as plt
        import seaborn as sns
        
        # Criar pasta para visualizações se não existir
        pasta_visualizacoes = 'visualizacoes'
        if not os.path.exists(pasta_visualizacoes):
            os.makedirs(pasta_visualizacoes)
        
        # Extrair dados
        resumo_trimestral = resultados['tributos'].get('resumo_trimestral', pd.DataFrame())
        resumo_mensal = resultados['tributos'].get('resumo_mensal', pd.DataFrame())
        analise_saidas = resultados.get('analise_saidas', pd.DataFrame())
        
        # Lista para armazenar caminhos dos gráficos gerados
        graficos_gerados = []
        
        # Configurar estilo
        plt.style.use('ggplot')
        
        # 1. Gráfico de Evolução da Lucratividade
        if not resumo_mensal.empty and 'Mês_Texto' in resumo_mensal.columns and 'Lucro' in resumo_mensal.columns:
            plt.figure(figsize=(12, 6))
            plt.plot(resumo_mensal['Mês_Texto'], resumo_mensal['Lucro'], marker='o', linewidth=2)
            plt.fill_between(resumo_mensal['Mês_Texto'], resumo_mensal['Lucro'], alpha=0.3)
            plt.grid(True, linestyle='--', alpha=0.7)
            plt.title('Evolução da Lucratividade Mensal', fontsize=15)
            plt.xlabel('Mês')
            plt.ylabel('Lucro (R$)')
            plt.xticks(rotation=45)
            plt.tight_layout()
            
            caminho_grafico = os.path.join(pasta_visualizacoes, 'evolucao_lucratividade_mensal.png')
            plt.savefig(caminho_grafico, dpi=300)
            plt.close()
            graficos_gerados.append(caminho_grafico)
        
        # 2. Gráfico da Distribuição de Tributos por Trimestre
        if not resumo_trimestral.empty:
            colunas_tributos = ['ICMS', 'PIS/COFINS', 'IRPJ', 'CSLL', 'Adicional IRPJ']
            colunas_presentes = [col for col in colunas_tributos if col in resumo_trimestral.columns]
            
            if colunas_presentes:
                plt.figure(figsize=(12, 8))
                
                # Criar gráfico de barras empilhadas
                bottom = np.zeros(len(resumo_trimestral))
                
                for col in colunas_presentes:
                    plt.bar(resumo_trimestral['Trimestre_Texto'], resumo_trimestral[col], bottom=bottom, label=col)
                    bottom += resumo_trimestral[col].values
                
                plt.title('Composição de Tributos por Trimestre', fontsize=15)
                plt.xlabel('Trimestre')
                plt.ylabel('Valor (R$)')
                plt.legend(loc='upper left', bbox_to_anchor=(1, 1))
                plt.xticks(rotation=45)
                plt.grid(True, linestyle='--', alpha=0.3)
                plt.tight_layout()
                
                caminho_grafico = os.path.join(pasta_visualizacoes, 'composicao_tributos_trimestral.png')
                plt.savefig(caminho_grafico, dpi=300)
                plt.close()
                graficos_gerados.append(caminho_grafico)
        
        # 3. Gráfico de Margem Média por Tipo de Veículo
        if not analise_saidas.empty and 'Tipo Veículo' in analise_saidas.columns and 'Margem_Media' in analise_saidas.columns:
            plt.figure(figsize=(10, 8))
            
            # Agrupamento por tipo de veículo
            margem_por_tipo = analise_saidas.groupby('Tipo Veículo')['Margem_Media'].mean().sort_values(ascending=False)
            
            sns.barplot(x=margem_por_tipo.values, y=margem_por_tipo.index)
            plt.title('Margem Média por Tipo de Veículo', fontsize=15)
            plt.xlabel('Margem (%)')
            plt.grid(True, linestyle='--', alpha=0.7)
            plt.tight_layout()
            
            caminho_grafico = os.path.join(pasta_visualizacoes, 'margem_por_tipo_veiculo.png')
            plt.savefig(caminho_grafico, dpi=300)
            plt.close()
            graficos_gerados.append(caminho_grafico)
        
        # 4. Gráfico de Lucro Líquido vs. Tributos
        if not resumo_mensal.empty and 'Mês_Texto' in resumo_mensal.columns:
            if 'Lucro Líquido' in resumo_mensal.columns and 'Total Tributos' in resumo_mensal.columns:
                plt.figure(figsize=(12, 6))
                
                x = np.arange(len(resumo_mensal))
                largura = 0.35
                
                plt.bar(x - largura/2, resumo_mensal['Lucro Líquido'], largura, label='Lucro Líquido')
                plt.bar(x + largura/2, resumo_mensal['Total Tributos'], largura, label='Total Tributos')
                
                plt.xlabel('Mês')
                plt.ylabel('Valor (R$)')
                plt.title('Lucro Líquido vs. Total de Tributos', fontsize=15)
                plt.xticks(x, resumo_mensal['Mês_Texto'], rotation=45)
                plt.legend()
                plt.grid(True, linestyle='--', alpha=0.3)
                plt.tight_layout()
                
                caminho_grafico = os.path.join(pasta_visualizacoes, 'lucro_vs_tributos.png')
                plt.savefig(caminho_grafico, dpi=300)
                plt.close()
                graficos_gerados.append(caminho_grafico)
        
        return graficos_gerados
    
    except ImportError as e:
        logger.warning(f"Não foi possível gerar visualizações. Bibliotecas necessárias não encontradas: {str(e)}")
        return []
    except Exception as e:
        logger.error(f"Erro ao gerar dashboards: {str(e)}", exc_info=True)
        return []

def exportar_para_sistema_contabil(resultados, sistema='dominio'):
    """Exporta dados para formatos compatíveis com sistemas contábeis."""
    sistemas_suportados = ['dominio', 'fortes', 'sage', 'cont_matic', 'generic']
    
    if sistema.lower() not in sistemas_suportados:
        logger.warning(f"Sistema contábil '{sistema}' não suportado. Usando formato genérico.")
        sistema = 'generic'
    
    # Obter data atual para o nome do arquivo
    hoje = datetime.now().strftime('%Y%m%d')
    
    # Extrair resumo mensal dos resultados
    resumo_mensal = resultados['tributos'].get('resumo_mensal', pd.DataFrame())
    
    if resumo_mensal.empty:
        logger.warning("Sem dados mensais para exportar")
        return None
    
    # Preparar diretório de exportação
    dir_exportacao = 'exportacao_contabil'
    if not os.path.exists(dir_exportacao):
        os.makedirs(dir_exportacao)
    
    # Configurações específicas por sistema
    if sistema.lower() == 'dominio':
        # Formato específico para o sistema Domínio
        arquivo = os.path.join(dir_exportacao, f'dominio_apuracao_{hoje}.csv')
        
        # Preparar colunas conforme layout do Domínio
        df_export = resumo_mensal.copy()
        
        # Formatação de colunas
        df_export['DATA'] = pd.to_datetime(df_export['Mês_Texto'] + '-01').dt.strftime('%d/%m/%Y')
        df_export['VALOR_VENDA'] = df_export['Lucro'] + df_export['Total Tributos']
        df_export['LUCRO'] = df_export['Lucro']
        df_export['ICMS'] = df_export['ICMS'] if 'ICMS' in df_export.columns else 0
        df_export['PIS_COFINS'] = df_export['PIS/COFINS'] if 'PIS/COFINS' in df_export.columns else 0
        
        # Selecionar e renomear colunas para o padrão do sistema
        colunas_export = ['DATA', 'VALOR_VENDA', 'LUCRO', 'ICMS', 'PIS_COFINS']
        df_export = df_export[colunas_export]
        
        # Exportar CSV com separador ponto-e-vírgula (padrão brasileiro)
        df_export.to_csv(arquivo, sep=';', index=False, decimal=',')
        
    elif sistema.lower() == 'fortes':
        # Formato para o sistema Fortes
        arquivo = os.path.join(dir_exportacao, f'fortes_apuracao_{hoje}.csv')
        
        # Preparar dados
        df_export = resumo_mensal.copy()
        
        # Formatar conforme layout do Fortes
        df_export['COMPETENCIA'] = pd.to_datetime(df_export['Mês_Texto'] + '-01').dt.strftime('%m/%Y')
        df_export['RECEITA_BRUTA'] = df_export['Lucro'] + df_export['Total Tributos'] 
        df_export['LUCRO_PRESUMIDO'] = df_export['Base IRPJ/CSLL'] if 'Base IRPJ/CSLL' in df_export.columns else 0
        df_export['ICMS_APURADO'] = df_export['ICMS'] if 'ICMS' in df_export.columns else 0
        df_export['PIS_APURADO'] = df_export['PIS/COFINS'] * 0.178 if 'PIS/COFINS' in df_export.columns else 0  # Aproximação
        df_export['COFINS_APURADO'] = df_export['PIS/COFINS'] * 0.822 if 'PIS/COFINS' in df_export.columns else 0  # Aproximação
        
        # Exportar
        colunas_export = ['COMPETENCIA', 'RECEITA_BRUTA', 'LUCRO_PRESUMIDO', 'ICMS_APURADO', 'PIS_APURADO', 'COFINS_APURADO']
        df_export[colunas_export].to_csv(arquivo, sep=';', index=False, decimal=',')
        
    else:
        # Formato genérico (CSV padrão)
        arquivo = os.path.join(dir_exportacao, f'apuracao_contabil_{hoje}.csv')
        
        # Exportar dados mensais completos
        resumo_mensal.to_csv(arquivo, index=False)
    
    logger.info(f"Dados exportados para sistema contábil {sistema}: {arquivo}")
    return arquivo

def main(arquivo_excel, periodo=None, gerar_visualizacoes=True, exportar_contabil=False, sistema_contabil='generic'):
    """Função principal que executa o fluxo completo."""
    try:
        # Processar apuração fiscal
        logger.info("Iniciando processamento de apuração fiscal")
        resultados = processar_apuracao_completa(arquivo_excel, periodo)
        
        # Gerar visualizações se solicitado
        if gerar_visualizacoes:
            logger.info("Gerando visualizações e dashboards")
            graficos = gerar_dashboards(resultados)
            if graficos:
                logger.info(f"Visualizações geradas: {len(graficos)} gráficos")
            else:
                logger.warning("Não foi possível gerar visualizações")
        
        # Exportar para sistema contábil se solicitado
        if exportar_contabil:
            logger.info(f"Exportando dados para sistema contábil: {sistema_contabil}")
            arquivo_exportacao = exportar_para_sistema_contabil(resultados, sistema_contabil)
            if arquivo_exportacao:
                logger.info(f"Dados exportados para: {arquivo_exportacao}")
        
        logger.info("Processamento concluído com sucesso!")
        return resultados
    
    except Exception as e:
        logger.error(f"Erro no processamento principal: {str(e)}", exc_info=True)
        raise

# Exemplo de uso
if __name__ == "__main__":
    # Configurar nome do arquivo de dados
    arquivo_dados = "estoque_veiculos.xlsx"
    
    # Definir período (opcional)
    # Para período específico:
    # inicio = datetime(2025, 1, 1)
    # fim = datetime(2025, 3, 31)
    # periodo = (inicio, fim)
    
    # Para usar o período atual:
    periodo = None
    
    # Executar processamento
    try:
        resultados = main(
            arquivo_excel=arquivo_dados,
            periodo=periodo,
            gerar_visualizacoes=True,
            exportar_contabil=True,
            sistema_contabil='dominio'
        )
        
        print("Processamento concluído com sucesso!")
        
        # Exibir resumo dos resultados
        total_geral = resultados['tributos'].get('total_geral', {})
        if total_geral:
            print("\nResumo dos resultados:")
            print(f"Total de Lucro: R$ {total_geral.get('Lucro', 0):.2f}")
            print(f"Total de Tributos: R$ {total_geral.get('Total Tributos', 0):.2f}")
            print(f"Lucro Líquido: R$ {total_geral.get('Lucro Líquido', 0):.2f}")
            
    except FileNotFoundError:
        print(f"Erro: Arquivo {arquivo_dados} não encontrado.")
        print("Certifique-se de que o arquivo Excel com os dados de estoque existe no diretório.")
    except Exception as e:
        print(f"Erro durante o processamento: {str(e)}")
        import traceback
        traceback.print_exc()
