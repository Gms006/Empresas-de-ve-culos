import pandas as pd
import xml.etree.ElementTree as ET
import json
import re
import logging
import os
from datetime import datetime

# Configuração de Logs
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
log = logging.getLogger(__name__)

CONFIG_PATH = os.path.join(os.path.dirname(__file__), '..', 'config')

try:
    with open(os.path.join(CONFIG_PATH, 'extracao_config.json'), encoding='utf-8') as f:
        CONFIG_EXTRACAO = json.load(f)

    with open(os.path.join(CONFIG_PATH, 'layout_colunas.json'), encoding='utf-8') as f:
        LAYOUT_COLUNAS = json.load(f)
except Exception as e:
    log.error(f"Erro ao carregar arquivos de configuração: {e}")
    # Definir configurações padrão caso ocorra erro na leitura
    CONFIG_EXTRACAO = {
        "validadores": {
            "chassi": r'^[A-HJ-NPR-Z0-9]{17}$',
            "placa_mercosul": r'^[A-Z]{3}[0-9][A-Z][0-9]{2}$',
            "placa_antiga": r'^[A-Z]{3}[0-9]{4}$',
            "renavam": r'^\d{9,11}$'
        },
        "regex_extracao": {
            "Chassi": r'(?:CHASSI|CHAS|CH)\s*[:\-]?\s*([A-Z0-9]{17})',
            "Placa": r'(?:PLACA|PL)\s*[:\-]?\s*([A-Z0-9]{7})',
            "Renavam": r'(?:RENAVAM|REN|RNV)\s*[:\-]?\s*(\d{9,11})',
            "Ano Modelo": r'(?:ANO|ANO FAB|ANO DE FABRICAÇÃO)?\s*[:\-]?\s*(\d{4})(?:\/|\s*[\/\-,]\s*)(\d{4})',
            "Motor": r'(?:MOTOR|MOT)\s*[:\-]?\s*([A-Z0-9]+)',
            "Cor": r'(?:COR|COLOR)\s*[:\-]?\s*([A-Za-zÀ-ú\s]+?)(?:\s*[,\.]|$)',
            "Combustível": r'(?:COMBUSTÍVEL|COMB)\s*[:\-]?\s*([A-Za-zÀ-ú\s/]+?)(?:\s*[,\.]|$)',
            "Potência": r'(?:POTÊNCIA|POT)\s*[:\-]?\s*(\d+(?:\.\d+)?)',
            "Modelo": r'(?:MODELO|MOD)\s*[:\-]?\s*([A-Za-zÀ-ú0-9\s\.\-]+?)(?:\s*[,\.]|$)'
        }
    }
    LAYOUT_COLUNAS = {
        "Chassi": None, "Placa": None, "Renavam": None, "Ano Fabricação": None, 
        "Ano Modelo": None, "Motor": None, "Cor": None, "Combustível": None,
        "Potência": None, "Modelo": None
    }

# Validações aprimoradas
def validar_chassi(chassi):
    """Valida o formato do chassi."""
    if not chassi:
        return False
    chassi = str(chassi).strip().upper()
    return bool(re.fullmatch(CONFIG_EXTRACAO["validadores"]["chassi"], chassi))

def validar_placa(placa):
    """Valida o formato da placa (mercosul ou antiga)."""
    if not placa:
        return False
    placa = str(placa).strip().upper()
    return (
        bool(re.fullmatch(CONFIG_EXTRACAO["validadores"]["placa_mercosul"], placa)) or
        bool(re.fullmatch(CONFIG_EXTRACAO["validadores"]["placa_antiga"], placa))
    )

def validar_renavam(renavam):
    """Valida o formato do renavam."""
    if not renavam:
        return False
    renavam = str(renavam).strip()
    # Remove caracteres não numéricos
    renavam = re.sub(r'\D', '', renavam)
    return bool(re.fullmatch(CONFIG_EXTRACAO["validadores"].get("renavam", r'^\d{9,11}$'), renavam))

# Classificação Entrada/Saída
def classificar_tipo_nota(emitente_cnpj, destinatario_cnpj, cnpj_empresa):
    """Classifica a nota como entrada ou saída com base nos CNPJs."""
    emitente = str(emitente_cnpj or "").replace('.', '').replace('/', '').replace('-', '').strip()
    destinatario = str(destinatario_cnpj or "").replace('.', '').replace('/', '').replace('-', '').strip()
    cnpj_empresa = str(cnpj_empresa or "").replace('.', '').replace('/', '').replace('-', '').strip()

    if destinatario == cnpj_empresa:
        return "Entrada"
    elif emitente == cnpj_empresa:
        return "Saída"
    else:
        log.warning(f"CNPJ não identificado como da empresa: Emitente={emitente}, Destinatário={destinatario}, Empresa={cnpj_empresa}")
        return "Indeterminado"

# Classificação Veículo x Consumo
def classificar_produto(row):
    """Classifica o produto como veículo ou consumo."""
    # Verifica se há dados de veículo
    if row.get('Chassi') or row.get('Placa') or row.get('Renavam'):
        return "Veículo"
    
    # Verifica se a descrição do produto indica um veículo
    produto = str(row.get('Produto') or "").lower()
    for termo in ['veículo', 'veiculo', 'automóvel', 'automovel', 'caminhão', 'caminhao', 'motocicleta', 'moto']:
        if termo in produto:
            return "Veículo"
    
    return "Consumo"

def limpar_texto(texto):
    """Remove caracteres especiais e espaços extras."""
    if not texto:
        return ""
    texto = str(texto).strip()
    texto = re.sub(r'\s+', ' ', texto)  # Remove espaços extras
    return texto

def formatar_data(data_str):
    """Formata a data para o padrão brasileiro."""
    if not data_str:
        return None
    try:
        # Tenta diferentes formatos de data que podem aparecer em XMLs de NFe
        for fmt in ['%Y-%m-%dT%H:%M:%S%z', '%Y-%m-%dT%H:%M:%S', '%Y-%m-%d']:
            try:
                # Remove a parte do fuso horário se existir
                data_str_limpa = re.sub(r'[-+]\d{2}:\d{2}$', '', data_str)
                data = datetime.strptime(data_str_limpa, fmt)
                return data.strftime('%d/%m/%Y')
            except ValueError:
                continue
    except Exception as e:
        log.warning(f"Erro ao formatar data '{data_str}': {e}")
    return data_str

# Função para encontrar informações adicionais com expressões regulares
def extrair_info_com_regex(texto_completo, campo):
    """Extrai informações usando regex em um texto."""
    if not texto_completo or not campo:
        return None
    
    padrao = CONFIG_EXTRACAO["regex_extracao"].get(campo)
    if not padrao:
        return None
    
    match = re.search(padrao, texto_completo, re.IGNORECASE)
    if not match:
        return None
    
    valor = match.group(1).strip() if match.groups() else None
    return valor

def normalizar_cnpj(cnpj):
    """Remove formatação do CNPJ e retorna apenas os números."""
    if not cnpj:
        return None
    return re.sub(r'\D', '', str(cnpj))

# Extração por Produto com Padronização aprimorada
def extrair_dados_xml(xml_path):
    """Extrai dados de um arquivo XML de NFe."""
    try:
        log.info(f"Processando XML: {xml_path}")
        tree = ET.parse(xml_path)
        root = tree.getroot()
        # Usar namespace dinâmico para maior compatibilidade
        namespaces = {'nfe': root.tag.split('}')[0].strip('{')} if '}' in root.tag else {}
        ns = namespaces
        
        # Log para debug das namespaces
        log.debug(f"Namespaces identificadas: {ns}")

        # Obter número da NF para referência em logs
        try:
            num_nf = root.findtext('.//nfe:ide/nfe:nNF', namespaces=ns) or "Desconhecido"
            log.info(f"Processando NF número: {num_nf}")
        except Exception as e:
            log.warning(f"Erro ao obter número da NF: {e}")
            num_nf = "Desconhecido"

        # Garantir campos do cabeçalho sempre preenchidos
        cabecalho = {
            'Número NF': num_nf,
            'Emitente Nome': root.findtext('.//nfe:emit/nfe:xNome', namespaces=ns) or 'Não informado',
            'Emitente CNPJ': normalizar_cnpj(root.findtext('.//nfe:emit/nfe:CNPJ', namespaces=ns)) or 'Não informado',
            'Destinatario Nome': root.findtext('.//nfe:dest/nfe:xNome', namespaces=ns) or 'Não informado',
            'Destinatario CNPJ': normalizar_cnpj(root.findtext('.//nfe:dest/nfe:CNPJ', namespaces=ns)) or 'Não informado',
            'CFOP': root.findtext('.//nfe:det/nfe:prod/nfe:CFOP', namespaces=ns),
            'Data Emissão': formatar_data(root.findtext('.//nfe:ide/nfe:dhEmi', namespaces=ns)),
            'Valor Total': root.findtext('.//nfe:total/nfe:ICMSTot/nfe:vNF', namespaces=ns)
        }

        log.debug(f"Cabeçalho extraído: {cabecalho}")

        registros = []
        campos_padrao = list(LAYOUT_COLUNAS.keys()) + ['Produto', 'XML Path']

        # Procura por itens (produtos) na NFe
        itens = root.findall('.//nfe:det', ns)
        log.info(f"Encontrados {len(itens)} itens na NF")

        for i, item in enumerate(itens, 1):
            dados = {col: None for col in campos_padrao}
            dados.update(cabecalho)
            dados['XML Path'] = xml_path
            
            # Extrair campos básicos do produto
            xProd = item.findtext('.//nfe:prod/nfe:xProd', namespaces=ns) or ""
            infAdProd = item.findtext('.//nfe:infAdProd', namespaces=ns) or ""
            
            # Também procurar em observações adicionais do produto e da NF
            obs_fisco = root.findtext('.//nfe:infAdic/nfe:infAdFisco', namespaces=ns) or ""
            obs_complementares = root.findtext('.//nfe:infAdic/nfe:infCpl', namespaces=ns) or ""
            
            # Concatenar todas as informações relevantes para busca
            produto_completo = f"{xProd} {infAdProd} {obs_fisco} {obs_complementares}".strip()
            
            dados['Produto'] = limpar_texto(xProd)
            dados['Item'] = i  # Número sequencial do item na NF
            
            log.debug(f"Processando item {i}: {dados['Produto'][:50]}...")

            # Procurar diretamente campos de veículo na estrutura XML
            try:
                # Verificar se há nó específico de veículo
                veiculo = item.find('.//nfe:veicProd', ns)
                if veiculo is not None:
                    dados['Chassi'] = veiculo.findtext('nfe:chassi', namespaces=ns)
                    dados['Renavam'] = veiculo.findtext('nfe:nrRENAVAM', namespaces=ns)
                    dados['Placa'] = veiculo.findtext('nfe:placa', namespaces=ns)
                    dados['Ano Fabricação'] = veiculo.findtext('nfe:anoFab', namespaces=ns)
                    dados['Ano Modelo'] = veiculo.findtext('nfe:anoMod', namespaces=ns)
                    dados['Combustível'] = veiculo.findtext('nfe:tpComb', namespaces=ns)
                    dados['Cor'] = veiculo.findtext('nfe:xCor', namespaces=ns)
                    dados['Potência'] = veiculo.findtext('nfe:potencia', namespaces=ns)
                    log.info(f"Dados de veículo encontrados no nó veicProd para item {i}")
            except Exception as e:
                log.warning(f"Erro ao buscar nó de veículo: {e}")

            # Aplicar regex para extrair informações não encontradas na estrutura XML
            for campo in CONFIG_EXTRACAO["regex_extracao"].keys():
                # Se já encontrou o valor na estrutura XML, não sobrescrever
                if campo in dados and dados[campo]:
                    continue

                if campo == "Ano Modelo":
                    anos = re.search(CONFIG_EXTRACAO["regex_extracao"][campo], produto_completo, re.IGNORECASE)
                    if anos:
                        dados["Ano Fabricação"] = anos.group(1)
                        dados["Ano Modelo"] = anos.group(2)
                        log.debug(f"Extraído Ano Fab/Modelo: {anos.group(1)}/{anos.group(2)}")
                else:
                    valor = extrair_info_com_regex(produto_completo, campo)
                    if valor:
                        dados[campo] = valor
                        log.debug(f"Extraído {campo}: {valor}")

            # Validações finais dos dados extraídos
            if dados.get("Chassi") and not validar_chassi(dados["Chassi"]):
                log.warning(f"Chassi inválido encontrado: {dados['Chassi']}")
                dados["Chassi"] = None
            
            if dados.get("Placa") and not validar_placa(dados["Placa"]):
                log.warning(f"Placa inválida encontrada: {dados['Placa']}")
                dados["Placa"] = None
            
            if dados.get("Renavam") and not validar_renavam(dados["Renavam"]):
                log.warning(f"Renavam inválido encontrado: {dados['Renavam']}")
                dados["Renavam"] = None

            # Adicionar identificação especial para veículos de maior valor (análise antifraude)
            try:
                valor_item = float(item.findtext('.//nfe:prod/nfe:vProd', namespaces=ns) or "0")
                dados["Valor Item"] = valor_item
                if valor_item > 50000:  # Veículos de alto valor
                    log.info(f"Item de alto valor detectado: R${valor_item:.2f}")
            except Exception as e:
                log.warning(f"Erro ao processar valor do item: {e}")
                dados["Valor Item"] = None

            registros.append(dados)

        log.info(f"Total de {len(registros)} registros extraídos do XML")
        return registros

    except ET.ParseError as e:
        log.error(f"Erro ao fazer parse do XML {xml_path}: {e}")
        return []
    except Exception as e:
        log.error(f"Erro ao processar {xml_path}: {e}")
        import traceback
        log.error(traceback.format_exc())
        return []

# Processar XMLs com Validação
def processar_xmls(xml_paths, cnpj_empresa):
    """Processa múltiplos arquivos XML e retorna um DataFrame consolidado."""
    todos_registros = []
    total_xmls = len(xml_paths)
    log.info(f"Iniciando processamento de {total_xmls} arquivos XML")
    
    for i, p in enumerate(xml_paths, 1):
        log.info(f"Processando arquivo {i}/{total_xmls}: {p}")
        registros = extrair_dados_xml(p)
        if registros:
            todos_registros.extend(registros)
            log.info(f"Extraídos {len(registros)} registros do arquivo {i}")
        else:
            log.warning(f"Nenhum registro extraído do XML: {p}")

    if not todos_registros:
        log.error("Nenhum dado extraído de nenhum XML.")
        return pd.DataFrame()

    log.info(f"Total de {len(todos_registros)} registros extraídos de todos os XMLs")
    df = pd.DataFrame(todos_registros)

    if df.empty:
        log.error("DataFrame vazio após consolidação.")
        return df

    # Classificação e ajustes finais
    log.info("Aplicando classificações e ajustes finais ao DataFrame")
    df['Tipo Nota'] = df.apply(lambda row: classificar_tipo_nota(row['Emitente CNPJ'], row['Destinatario CNPJ'], cnpj_empresa), axis=1)
    df['Tipo Produto'] = df.apply(classificar_produto, axis=1)
    
    # Estatísticas para validação
    veiculos = df[df['Tipo Produto'] == 'Veículo'].shape[0]
    consumo = df[df['Tipo Produto'] == 'Consumo'].shape[0]
    com_chassi = df[df['Chassi'].notna()].shape[0]
    com_placa = df[df['Placa'].notna()].shape[0]
    com_renavam = df[df['Renavam'].notna()].shape[0]
    
    log.info(f"Estatísticas finais: {veiculos} veículos, {consumo} itens de consumo")
    log.info(f"Dados de identificação: {com_chassi} com chassi, {com_placa} com placa, {com_renavam} com renavam")
    
    return df
