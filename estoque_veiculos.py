import xml.etree.ElementTree as ET

# Adicione esta linha para registrar o namespace
namespaces = {'nfe': 'http://www.portalfiscal.inf.br/nfe'}

def extrair_dados_xml(xml_path):
    try:
        tree = ET.parse(xml_path)
        root = tree.getroot()
        dados = {campo: None for campo in XPATH_CAMPOS.keys()}
        dados.update({campo: None for campo in REGEX_EXTRACAO.keys()})

        # Extração via XPath com namespaces
        for campo, path in XPATH_CAMPOS.items():
            elemento = root.find(path, namespaces)
            if elemento is not None and elemento.text:
                dados[campo] = elemento.text.strip()

        # Extração via Regex
        texto_xml = ET.tostring(root, encoding='unicode')
        for campo, padroes in REGEX_EXTRACAO.items():
            for padrao in padroes:
                match = re.search(padrao, texto_xml, re.IGNORECASE)
                if match:
                    dados[campo] = match.group(1).strip()
                    break

        # Validação
        if not validar_chassi(dados.get("Chassi")):
            dados["Chassi"] = None
        if not validar_placa(dados.get("Placa")):
            dados["Placa"] = None

        return dados

    except Exception as e:
        log.error(f"Erro ao processar {xml_path}: {e}")
        return {campo: None for campo in list(XPATH_CAMPOS.keys()) + list(REGEX_EXTRACAO.keys())}
