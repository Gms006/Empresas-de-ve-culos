import os

import pandas as pd
import xml.etree.ElementTree as ET
import json
import re
import logging
from modules.configurador_planilha import configurar_planilha
from datetime import datetime
from typing import List, Dict, Any, Optional, Union

log = logging.getLogger(__name__)

# Caminhos de configuração
CONFIG_PATH = os.path.join(os.path.dirname(__file__), '..', 'config')

# Carregamento de configurações
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
        "xpath_campos": {
            "CFOP": ".//nfe:det/nfe:prod/nfe:CFOP",
            "Data Emissão": ".//nfe:ide/nfe:dhEmi",
            "Emitente Nome": ".//nfe:emit/nfe:xNome",
            "Emitente CNPJ": ".//nfe:emit/nfe:CNPJ",
            "Destinatário Nome": ".//nfe:dest/nfe:xNome",
            "Destinatário CNPJ": ".//nfe:dest/nfe:CNPJ",
            "Destinatário CPF": ".//nfe:dest/nfe:CPF",
            "Valor Total": ".//nfe:total/nfe:ICMSTot/nfe:vNF",
            "Produto": ".//nfe:det/nfe:prod/nfe:xProd",
            "Natureza Operação": ".//nfe:ide/nfe:natOp"
        },
        "regex_extracao": {
            "Chassi": r'(?:CHASSI|CHAS|CH)[\s:;.-]*([A-HJ-NPR-Z0-9]{17})',
            "Placa": r'(?:PLACA|PL)[\s:;.-]*([A-Z]{3}[0-9][A-Z0-9][0-9]{2})|(?:PLACA|PL)[\s:;.-]*([A-Z]{3}-?[0-9]{4})',
            "Renavam": r'(?:RENAVAM|REN|RENAV)[\s:;.-]*([0-9]{9,11})',
            "KM": r'(?:KM|QUILOMETRAGEM|HODOMETRO|HODÔMETRO)[\s:;.-]*([0-9]{1,7})',
            "Ano Modelo": r'(?:ANO[\s/]*MODELO|ANO[\s/]?FAB[\s/]?MOD)[\s:;.-]*([0-9]{4})[\s/.-]+([0-9]{4})|ANO[\s:;.-]*([0-9]{4})[\s/.-]+([0-9]{4})',
            "Cor": r'(?:COR|COLOR)[\s:;.-]*([A-Za-zÀ-ú\s]+?)(?:[\s,.;]|$)',
            "Motor": r'(?:MOTOR|MOT|N[º°\s]?\s*MOTOR)[\s:;.-]*([A-Z0-9]+)',
            "Combustível": r'(?:COMBUSTÍVEL|COMBUSTIVEL|COMB)[\s:;.-]*([A-Za-zÀ-ú\s/]+?)(?:[\s,.;]|$)',
            "Modelo": r'(?:MODELO|MOD)[\s:;.-]*([A-Za-zÀ-ú0-9\s\.-]+?)(?:[\s,.;]|$)',
            "Potência": r'(?:POTÊNCIA|POTENCIA|POT)[\s:;.-]*([0-9]+(?:[,.][0-9]+)?)'
        }
    }
    LAYOUT_COLUNAS = {
        "Tipo Nota": {"tipo": "str", "ordem": 1},
        "CFOP": {"tipo": "str", "ordem": 2},
        "Data Emissão": {"tipo": "date", "ordem": 3},
        "Valor Total": {"tipo": "float", "ordem": 4},
        "Emitente Nome": {"tipo": "str", "ordem": 5},
        "Destinatário Nome": {"tipo": "str", "ordem": 6},
        "Destinatário CNPJ": {"tipo": "str", "ordem": 7},
        "Destinatário CPF": {"tipo": "str", "ordem": 8},
        "Chassi": {"tipo": "str", "ordem": 9},
        "Placa": {"tipo": "str", "ordem": 10},
        "Renavam": {"tipo": "str", "ordem": 11},
        "KM": {"tipo": "int", "ordem": 12},
        "Ano Modelo": {"tipo": "int", "ordem": 13},
        "Ano Fabricação": {"tipo": "int", "ordem": 14},
        "Cor": {"tipo": "str", "ordem": 15},
        "Natureza Operação": {"tipo": "str", "ordem": 16},
        "CHAVE XML": {"tipo": "str", "ordem": 17}
    }


# Pré-compilar as expressões regulares para melhor performance
REGEX_COMPILADOS = {}
try:
    for campo, padrao in CONFIG_EXTRACAO["regex_extracao"].items():
        REGEX_COMPILADOS[campo] = re.compile(padrao, re.IGNORECASE)
    log.info("Expressões regulares compiladas com sucesso")
except Exception as e:
    log.error(f"Erro ao compilar expressões regulares: {e}")
    REGEX_COMPILADOS = {}

# Funções de validação
def validar_chassi(chassi: Optional[str]) -> bool:
    """Valida o formato do chassi."""
    if not chassi:
        return False
    chassi = re.sub(r"\W", "", str(chassi)).upper()
    pattern = re.compile(CONFIG_EXTRACAO["validadores"]["chassi"])
    return bool(pattern.fullmatch(chassi))

def validar_placa(placa: Optional[str]) -> bool:
    """Valida o formato da placa (mercosul ou antiga)."""
    if not placa:
        return False
    placa = str(placa).strip().upper()
    placa_sem_hifen = placa.replace('-', '')
    
    # Validar formato Mercosul
    pattern_mercosul = re.compile(CONFIG_EXTRACAO["validadores"]["placa_mercosul"])
    if pattern_mercosul.fullmatch(placa_sem_hifen):
        return True
    
    # Validar formato antigo
    pattern_antigo = re.compile(CONFIG_EXTRACAO["validadores"]["placa_antiga"].replace('-', ''))
    if pattern_antigo.fullmatch(placa_sem_hifen):
        return True
    
    return False

def validar_renavam(renavam: Optional[str]) -> bool:
    """Valida o formato do renavam."""
    if not renavam:
        return False
    renavam = str(renavam).strip()
    # Remove caracteres não numéricos
    renavam = re.sub(r'\D', '', renavam)
    pattern = re.compile(CONFIG_EXTRACAO["validadores"].get("renavam", r'^\d{9,11}$'))
    return bool(pattern.fullmatch(renavam))

def classificar_tipo_nota(
    emitente_cnpj: Optional[str],
    destinatario_cnpj: Optional[str],
    cnpj_empresa: Union[str, List[str], None],
    cfop: Optional[str],
) -> str:
    """Classifica a nota como ``Entrada``, ``Saída`` ou ``Indefinido``.

    A análise do CFOP tem prioridade. Caso o CFOP não esteja presente ou não
    permita determinar o tipo da nota, a classificação por CNPJ é utilizada
    como fallback.
    """

    # ------------------------------------------------------------------
    # Prioridade 1: Analisar CFOP
    # ------------------------------------------------------------------
    cfop_str = ""
    if cfop is not None:
        try:
            cfop_str = re.sub(r"\D", "", str(cfop))
            # Normalizar para 4 dígitos caso venha como float (e.g., 1102.0)
            if len(cfop_str) > 4:
                cfop_str = cfop_str[:4]
            cfop_str = cfop_str.strip()
        except Exception:
            cfop_str = ""

    if cfop_str:
        primeiro_digito = cfop_str[0]
        if primeiro_digito in {"1", "2"}:
            return "Entrada"
        if primeiro_digito in {"5", "6"}:
            return "Saída"
        return "Indefinido"

    # ------------------------------------------------------------------
    # Prioridade 2: Fallback utilizando CNPJ
    # ------------------------------------------------------------------
    emitente = normalizar_cnpj(emitente_cnpj)
    destinatario = normalizar_cnpj(destinatario_cnpj)

    if isinstance(cnpj_empresa, (list, tuple, set)):
        cnpjs_empresa = {normalizar_cnpj(c) for c in cnpj_empresa if normalizar_cnpj(c)}
    elif cnpj_empresa:
        cnpjs_empresa = {normalizar_cnpj(cnpj_empresa)}
    else:
        cnpjs_empresa = set()

    if destinatario and destinatario in cnpjs_empresa:
        return "Entrada"
    if emitente and emitente in cnpjs_empresa:
        return "Saída"

    return "Indefinido"

def classificar_produto(row: Dict[str, Any]) -> str:
    """Classifica o item como veículo apenas se houver chassi."""

    chassi = row.get("Chassi")
    if chassi is not None and str(chassi).strip():
        return "Veículo"

    return "Consumo"

def limpar_texto(texto: Optional[str]) -> str:
    """Remove caracteres especiais e espaços extras."""
    if not texto:
        return ""
    texto = str(texto).strip()
    texto = re.sub(r'\s+', ' ', texto)  # Remove espaços extras
    return texto

def formatar_data(data_str: Optional[str]) -> Optional[datetime]:
    """Converte strings de data em objetos ``datetime``.

    Manter as datas como ``datetime`` evita conversões repetidas durante as
    agregações mensais.
    """
    if not data_str:
        return None
    try:
        for fmt in ["%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"]:
            try:
                data_str_limpa = re.sub(r"[-+]\d{2}:\d{2}$", "", data_str)
                return datetime.strptime(data_str_limpa, fmt)
            except ValueError:
                continue
    except Exception as e:
        log.warning(f"Erro ao converter data '{data_str}': {e}")
    return None

def extrair_placa(texto_completo: str) -> Optional[str]:
    """Extrai a placa de veículo usando regex."""
    if not texto_completo:
        return None

    # Usar regex pré-compilado se disponível
    if 'Placa' in REGEX_COMPILADOS:
        match = REGEX_COMPILADOS['Placa'].search(texto_completo)
        if match:
            # Verificar qual dos grupos capturou algo (formato mercosul ou antigo)
            for grupo in match.groups():
                if grupo:
                    placa = grupo.strip().upper()
                    if validar_placa(placa):
                        return placa
    else:
        # Fallback para regex não compilado
        padrao = CONFIG_EXTRACAO["regex_extracao"]["Placa"]
        match = re.search(padrao, texto_completo, re.IGNORECASE)
        if match:
            # Pegar o primeiro grupo não vazio
            for grupo in match.groups():
                if grupo:
                    placa = grupo.strip().upper()
                    if validar_placa(placa):
                        return placa

    return None

def extrair_info_com_regex(texto_completo: str, campo: str) -> Optional[str]:
    """Extrai informações usando regex em um texto."""
    if not texto_completo or not campo:
        return None
    
    # Caso especial para Placa que tem um padrão mais complexo
    if campo == "Placa":
        return extrair_placa(texto_completo)
    
    # Usar regex pré-compilado se disponível
    if campo in REGEX_COMPILADOS:
        match = REGEX_COMPILADOS[campo].search(texto_completo)
    else:
        # Fallback para regex não compilado
        padrao = CONFIG_EXTRACAO["regex_extracao"].get(campo)
        if not padrao:
            return None
        match = re.search(padrao, texto_completo, re.IGNORECASE)
    
    if not match:
        return None
    
    # Para o caso de Ano Modelo que tem dois formatos possíveis
    if campo == "Ano Modelo" and match.groups():
        # Verifica qual formato foi usado
        if match.group(1) and match.group(2):  # Formato principal
            return match.group(2)  # Retorna o ano modelo
        elif match.group(3) and match.group(4):  # Formato alternativo
            return match.group(4)  # Retorna o ano modelo
    
    # Para campos normais
    if match.groups():
        valor = match.group(1)
        if valor:
            return valor.strip()
    
    return None

def normalizar_cnpj(cnpj: Optional[str]) -> Optional[str]:
    """Remove formatação do CNPJ e retorna apenas os números."""
    if not cnpj:
        return None
    return re.sub(r'\D', '', str(cnpj))

def extrair_dados_xml(xml_path: str) -> List[Dict[str, Any]]:
    """Extrai dados de um arquivo XML de NFe."""
    try:
        log.info(f"Processando XML: {xml_path}")
        tree = ET.parse(xml_path)
        root = tree.getroot()
        
        # Detectar namespace automaticamente
        ns_match = re.match(r'\{(.+?)\}', root.tag)
        ns_uri = ns_match.group(1) if ns_match else ''
        ns = {'nfe': ns_uri} if ns_uri else {}
        
        # Log para debug do namespace
        log.debug(f"Namespace detectado: {ns}")

        # Obter número da NF para referência em logs
        try:
            xpath_num_nf = CONFIG_EXTRACAO.get("xpath_campos", {}).get("Número NF", ".//nfe:ide/nfe:nNF")
            num_nf = root.findtext(xpath_num_nf, namespaces=ns) or "Desconhecido"
            log.info(f"Processando NF número: {num_nf}")
        except Exception as e:
            log.warning(f"Erro ao obter número da NF: {e}")
            num_nf = "Desconhecido"

        # Chave de acesso do XML
        chave_xml = ""
        try:
            inf_nfe = root.find('.//nfe:infNFe', namespaces=ns)
            if inf_nfe is not None:
                chave_xml = inf_nfe.attrib.get('Id', '')
        except Exception:
            chave_xml = ""

        # Extrair dados dos campos XPath do cabeçalho da nota
        xpath_campos = CONFIG_EXTRACAO.get("xpath_campos", {})
        
        # Garantir campos do cabeçalho sempre preenchidos
        data_emissao = formatar_data(
            root.findtext(
                xpath_campos.get('Data Emissão', './/nfe:ide/nfe:dhEmi'),
                namespaces=ns,
            )
        )

        cabecalho = {
            'Número NF': num_nf,
            'CHAVE XML': chave_xml,
            'Emitente Nome': root.findtext(
                xpath_campos.get('Emitente Nome', './/nfe:emit/nfe:xNome'),
                namespaces=ns,
            )
            or 'Não informado',
            'Emitente CNPJ': normalizar_cnpj(
                root.findtext(
                    xpath_campos.get('Emitente CNPJ', './/nfe:emit/nfe:CNPJ'),
                    namespaces=ns,
                )
            )
            or 'Não informado',
            'Destinatário Nome': root.findtext(
                xpath_campos.get('Destinatário Nome', './/nfe:dest/nfe:xNome'),
                namespaces=ns,
            )
            or 'Não informado',
            'Destinatário CNPJ': normalizar_cnpj(
                root.findtext(
                    xpath_campos.get('Destinatário CNPJ', './/nfe:dest/nfe:CNPJ'),
                    namespaces=ns,
                )
            ),
            'Destinatário CPF': normalizar_cnpj(
                root.findtext(
                    xpath_campos.get('Destinatário CPF', './/nfe:dest/nfe:CPF'),
                    namespaces=ns,
                )
            ),
            'CFOP': root.findtext(
                xpath_campos.get('CFOP', './/nfe:det/nfe:prod/nfe:CFOP'),
                namespaces=ns,
            ),
            'Data Emissão': data_emissao,
            'Mês Emissão': data_emissao.strftime('%m/%Y') if data_emissao else None,
            'Valor Total': root.findtext(
                xpath_campos.get('Valor Total', './/nfe:total/nfe:ICMSTot/nfe:vNF'),
                namespaces=ns,
            ),
            'Natureza Operação': root.findtext(
                xpath_campos.get('Natureza Operação', './/nfe:ide/nfe:natOp'),
                namespaces=ns,
            ),
        }
        log.debug(f"Cabeçalho extraído: {cabecalho}")

        registros = []
        # Campos padrão baseados nas chaves do LAYOUT_COLUNAS + campos adicionais
        campos_padrao = list(LAYOUT_COLUNAS.keys()) + ['Produto', 'XML Path', 'Item', 'Valor Item']

        # Procura por itens (produtos) na NFe
        itens = root.findall('.//nfe:det', ns)
        log.info(f"Encontrados {len(itens)} itens na NF")

        # Extrair informações adicionais gerais da nota
        obs_fisco = root.findtext('.//nfe:infAdic/nfe:infAdFisco', namespaces=ns) or ""
        obs_complementares = root.findtext('.//nfe:infAdic/nfe:infCpl', namespaces=ns) or ""
        infos_gerais = f"{obs_fisco} {obs_complementares}".strip()
        
        for i, item in enumerate(itens, 1):
            dados = {col: None for col in campos_padrao}
            dados.update(cabecalho)
            dados['XML Path'] = xml_path
            dados['Item'] = i
            dados['CFOP'] = item.findtext('.//nfe:prod/nfe:CFOP', namespaces=ns) or cabecalho.get('CFOP')
            
            # Extrair campos básicos do produto
            xProd = item.findtext('.//nfe:prod/nfe:xProd', namespaces=ns) or ""
            infAdProd = item.findtext('.//nfe:infAdProd', namespaces=ns) or ""
            
            # Concatenar todas as informações relevantes para busca
            produto_completo = f"{xProd} {infAdProd} {infos_gerais}".strip()
            
            dados['Produto'] = limpar_texto(xProd)

            log.debug(f"Processando item {i}: {dados['Produto'][:50]}...")

            # Valor do ICMS do item
            try:
                icms_text = item.findtext(
                    xpath_campos.get('ICMS', './/nfe:imposto/nfe:ICMS//nfe:vICMS'),
                    namespaces=ns,
                )
                dados['ICMS'] = float(icms_text) if icms_text is not None else None
            except Exception as e:
                log.warning(f"Erro ao processar ICMS do item: {e}")

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
                    anos = extrair_info_com_regex(produto_completo, campo)
                    # Se encontrou ano modelo, tenta extrair também ano fabricação
                    if anos:
                        match = REGEX_COMPILADOS.get(campo, re.compile(CONFIG_EXTRACAO["regex_extracao"][campo], re.IGNORECASE)).search(produto_completo)
                        if match:
                            # Verifica qual formato foi usado
                            if match.group(1) and match.group(2):  # Formato principal
                                dados["Ano Fabricação"] = match.group(1)
                                dados["Ano Modelo"] = match.group(2)
                            elif match.group(3) and match.group(4):  # Formato alternativo
                                dados["Ano Fabricação"] = match.group(3)
                                dados["Ano Modelo"] = match.group(4)
                            log.debug(f"Extraído Ano Fab/Modelo: {dados.get('Ano Fabricação')}/{dados.get('Ano Modelo')}")
                else:
                    valor = extrair_info_com_regex(produto_completo, campo)
                    if valor:
                        dados[campo] = valor
                        log.debug(f"Extraído {campo}: {valor}")

            # Validações finais dos dados extraídos
            if dados.get("Chassi"):
                if validar_chassi(dados["Chassi"]):
                    dados["Chassi"] = dados["Chassi"].upper()
                else:
                    log.warning(f"Chassi inválido encontrado: {dados['Chassi']}")
                    dados["Chassi"] = None
            
            if dados.get("Placa"):
                if validar_placa(dados["Placa"]):
                    dados["Placa"] = dados["Placa"].upper()
                else:
                    log.warning(f"Placa inválida encontrada: {dados['Placa']}")
                    dados["Placa"] = None
            
            if dados.get("Renavam"):
                if validar_renavam(dados["Renavam"]):
                    dados["Renavam"] = re.sub(r'\D', '', dados["Renavam"])
                else:
                    log.warning(f"Renavam inválido encontrado: {dados['Renavam']}")
                    dados["Renavam"] = None

            # Adicionar valor do item
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

def processar_xmls(xml_paths: List[str], cnpj_empresa: Union[str, List[str]]) -> pd.DataFrame:
    """Processa múltiplos arquivos XML e retorna um DataFrame consolidado."""
    todos_registros = []
    total_xmls = len(xml_paths)
    log.info(f"Iniciando processamento de {total_xmls} arquivos XML")
    
    # Usar paralelismo para processamento mais rápido com muitos arquivos XML
    use_parallel = total_xmls > 10
    
    if use_parallel:
        try:
            # Importação condicional para não depender desta lib se não for usada
            from concurrent.futures import ProcessPoolExecutor
            import multiprocessing
            
            max_workers = min(multiprocessing.cpu_count(), 8)  # Limitar a 8 workers
            log.info(f"Usando processamento paralelo com {max_workers} workers")
            
            with ProcessPoolExecutor(max_workers=max_workers) as executor:
                results = list(executor.map(extrair_dados_xml, xml_paths))
                
            for registros in results:
                if registros:
                    todos_registros.extend(registros)
                    
        except Exception as e:
            log.warning(f"Erro no processamento paralelo: {e}. Usando processamento sequencial.")
            use_parallel = False
    
    # Processamento sequencial como fallback ou opção principal
    if not use_parallel:
        for i, xml_path in enumerate(xml_paths, 1):
            log.info(f"Processando arquivo {i}/{total_xmls}: {xml_path}")
            registros = extrair_dados_xml(xml_path)
            if registros:
                todos_registros.extend(registros)
                log.info(f"Extraídos {len(registros)} registros do arquivo {i}")
            else:
                log.warning(f"Nenhum registro extraído do XML: {xml_path}")

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
    if isinstance(cnpj_empresa, (list, tuple, set)):
        cnpj_list = [normalizar_cnpj(c) for c in cnpj_empresa]
        empresa_padrao = cnpj_list[0] if cnpj_list else None
    else:
        empresa_padrao = normalizar_cnpj(cnpj_empresa)

    df['Empresa CNPJ'] = empresa_padrao

    df['Tipo Nota'] = df.apply(
        lambda row: classificar_tipo_nota(
            row['Emitente CNPJ'],
            row['Destinatário CNPJ'],
            cnpj_empresa,
            row.get('CFOP'),
        ),
        axis=1,
    )
    df['Tipo Produto'] = df.apply(classificar_produto, axis=1)

    # Aplicar configuração de layout e tipagem
    df = configurar_planilha(df)

    # Reordenar colunas conforme especificado
    ordenadas = sorted(LAYOUT_COLUNAS.items(), key=lambda x: x[1]['ordem'])
    base_cols = [c for c, _ in ordenadas]
    extras = ["Empresa CNPJ", "Tipo Produto", "Mês Emissão"]
    nova_ordem = [
        "Tipo Nota",
        *[c for c in base_cols if c not in {"Tipo Nota", "Natureza Operação", "CHAVE XML"}],
        *extras,
        "Natureza Operação",
        "CHAVE XML",
    ]
    df = df.reindex(columns=nova_ordem)

    # Estatísticas para validação
    veiculos = df[df['Tipo Produto'] == 'Veículo'].shape[0]
    consumo = df[df['Tipo Produto'] == 'Consumo'].shape[0]
    com_chassi = df[df['Chassi'].notna()].shape[0]
    com_placa = df[df['Placa'].notna()].shape[0]
    com_renavam = df[df['Renavam'].notna()].shape[0]
    
    log.info(f"Estatísticas finais: {veiculos} veículos, {consumo} itens de consumo")
    log.info(f"Dados de identificação: {com_chassi} com chassi, {com_placa} com placa, {com_renavam} com renavam")

    return df
  
# Função para facilitar o processamento direto de um diretório
def processar_diretorio(diretorio: str, cnpj_empresa: Union[str, List[str]], extensao: str = ".xml") -> pd.DataFrame:
    """Processa todos os arquivos XML em um diretório."""
    if not os.path.isdir(diretorio):
        log.error(f"Diretório não encontrado: {diretorio}")
        return pd.DataFrame()
    
    # Encontrar todos os arquivos XML no diretório
    xml_paths = [os.path.join(diretorio, f) for f in os.listdir(diretorio) 
                 if f.lower().endswith(extensao.lower())]
    
    if not xml_paths:
        log.warning(f"Nenhum arquivo {extensao} encontrado no diretório {diretorio}")
        return pd.DataFrame()
    
    log.info(f"Encontrados {len(xml_paths)} arquivos {extensao} no diretório {diretorio}")
    return processar_xmls(xml_paths, cnpj_empresa)

# Função para exportar para Excel com formatação
def exportar_para_excel(df: pd.DataFrame, caminho_saida: str) -> bool:
    """Exporta o DataFrame para um arquivo Excel formatado."""
    if df.empty:
        log.error("DataFrame vazio, não é possível exportar para Excel")
        return False
    
    try:
        # Importar apenas se necessário
        import xlsxwriter
        
        log.info(f"Exportando dados para Excel: {caminho_saida}")
        
        # Criar diretório de saída se não existir
        diretorio_saida = os.path.dirname(caminho_saida)
        if diretorio_saida and not os.path.exists(diretorio_saida):
            os.makedirs(diretorio_saida)
        
        # Configurar o writer com opções
        writer = pd.ExcelWriter(
            caminho_saida,
            engine='xlsxwriter',
            engine_kwargs={'options': {'strings_to_numbers': True}}
        )
        
        # Exportar DataFrame
        df.to_excel(writer, sheet_name='Dados Extraídos', index=False)
        
        # Acessar o workbook e a planilha
        workbook = writer.book
        worksheet = writer.sheets['Dados Extraídos']
        
        # Definir formatos
        formato_cabecalho = workbook.add_format({
            'bold': True,
            'text_wrap': True,
            'valign': 'top',
            'fg_color': '#D7E4BC',
            'border': 1
        })
        
        formato_veiculo = workbook.add_format({
            'bg_color': '#E0F7FA',
            'valign': 'top'
        })
        
        
        formato_numero = workbook.add_format({
            'num_format': '#,##0.00',
            'valign': 'top'
        })
        
        formato_data = workbook.add_format({
            'num_format': 'dd/mm/yyyy',
            'valign': 'top'
        })
        
        # Aplicar formato ao cabeçalho
        for col_num, value in enumerate(df.columns.values):
            worksheet.write(0, col_num, value, formato_cabecalho)
        
        # Definir a largura das colunas baseada no conteúdo
        for i, coluna in enumerate(df.columns):
            max_len = max(
                df[coluna].astype(str).apply(len).max(),
                len(str(coluna))
            )
            worksheet.set_column(i, i, max_len + 2)
        
        # Aplicar formatação condicional para veículos se a coluna existir
        if 'Tipo Produto' in df.columns:
            from xlsxwriter.utility import xl_col_to_name
            col_idx = df.columns.get_loc('Tipo Produto')
            col_letter = xl_col_to_name(col_idx)
            worksheet.conditional_format(
                1,
                0,
                len(df) + 1,
                len(df.columns) - 1,
                {
                    'type': 'formula',
                    'criteria': f'=${col_letter}2="Veículo"',
                    'format': formato_veiculo,
                },
            )
        
        # Configurar filtros
        worksheet.autofilter(0, 0, len(df), len(df.columns) - 1)
        
        # Congelar primeira linha
        worksheet.freeze_panes(1, 0)
        
        # Fechar o writer e salvar o arquivo
        writer.close()
        log.info(f"Arquivo Excel salvo com sucesso: {caminho_saida}")
        return True
        
    except Exception as e:
        log.error(f"Erro ao exportar para Excel: {e}")
        import traceback
        log.error(traceback.format_exc())
        return False

# Exemplo de uso
if __name__ == "__main__":
    import argparse
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    parser = argparse.ArgumentParser(description="Extração de dados de Notas Fiscais Eletrônicas (XML)")
    parser.add_argument("--dir", type=str, help="Diretório contendo arquivos XML")
    parser.add_argument("--xml", type=str, nargs="+", help="Caminhos de arquivos XML específicos")
    parser.add_argument("--cnpj", type=str, required=True, help="CNPJ da empresa para classificação da nota")
    parser.add_argument("--saida", type=str, default="resultado_extracao.xlsx", help="Caminho do arquivo de saída Excel")
    parser.add_argument("--debug", action="store_true", help="Ativar modo debug (logs detalhados)")
    
    args = parser.parse_args()
    
    # Configurar nível de log baseado no argumento debug
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
        log.info("Modo DEBUG ativado")
    
    # Determinar quais arquivos processar
    xml_paths = []
    if args.xml:
        xml_paths = args.xml
    elif args.dir:
        xml_paths = [os.path.join(args.dir, f) for f in os.listdir(args.dir) if f.lower().endswith('.xml')]
    
    if not xml_paths:
        log.error("Nenhum arquivo XML especificado. Use --dir ou --xml")
        parser.print_help()
        exit(1)
    
    # Processar XMLs
    df = processar_xmls(xml_paths, args.cnpj)
    
    # Exportar resultado
    if not df.empty:
        log.info(f"Processamento concluído com {len(df)} registros extraídos")
        exportar_para_excel(df, args.saida)
    else:
        log.error("Nenhum dado extraído dos XMLs")
