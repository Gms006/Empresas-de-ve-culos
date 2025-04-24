import streamlit as st
import pandas as pd
import zipfile
import tempfile
import os
import json
import time
from io import BytesIO
from concurrent.futures import ThreadPoolExecutor
import matplotlib.pyplot as plt
import seaborn as sns

# Importações dos módulos
from modules.estoque_veiculos import processar_xmls
from modules.configurador_planilha import configurar_planilha
from modules.transformadores_veiculos import (
    gerar_estoque_fiscal,
    gerar_alertas_auditoria,
    gerar_kpis,
    gerar_resumo_mensal
)
from modules.apuracao_fiscal import calcular_apuracao
from modules.Analise import sua_funcao_principal
# Utilidades
from utils.filtros_utils import obter_anos_meses_unicos, aplicar_filtro_periodo
from utils.formatador_utils import formatar_moeda, formatar_percentual

# Configuração da página
st.set_page_config(
    page_title="Painel Fiscal de Veículos", 
    layout="wide",
    initial_sidebar_state="expanded"
)

# Estilo personalizado
st.markdown("""
<style>
    .main-header {
        font-size: 32px;
        font-weight: bold;
        color: #1E3A8A;
        margin-bottom: 20px;
    }
    .sub-header {
        font-size: 24px;
        font-weight: bold;
        color: #2563EB;
        margin-top: 15px;
        margin-bottom: 10px;
    }
    .card {
        padding: 20px;
        border-radius: 10px;
        background-color: #F3F4F6;
        margin-bottom: 20px;
    }
    .info-card {
        padding: 15px;
        border-radius: 8px;
        background-color: #E0F2FE;
        border-left: 4px solid #0284C7;
        margin-bottom: 15px;
    }
    .warning-card {
        padding: 15px;
        border-radius: 8px;
        background-color: #FEF3C7;
        border-left: 4px solid #D97706;
        margin-bottom: 15px;
    }
    .success-card {
        padding: 15px;
        border-radius: 8px;
        background-color: #D1FAE5;
        border-left: 4px solid #059669;
        margin-bottom: 15px;
    }
</style>
""", unsafe_allow_html=True)

# Título principal
st.markdown('<div class="main-header">🚗 Painel Fiscal de Veículos</div>', unsafe_allow_html=True)

# Inicialização de estado da sessão
if 'dados_processados' not in st.session_state:
    st.session_state.dados_processados = False
if 'df_configurado' not in st.session_state:
    st.session_state.df_configurado = None
if 'df_estoque' not in st.session_state:
    st.session_state.df_estoque = None
if 'df_alertas' not in st.session_state:
    st.session_state.df_alertas = None
if 'df_resumo' not in st.session_state:
    st.session_state.df_resumo = None
if 'df_apuracao' not in st.session_state:
    st.session_state.df_apuracao = None
if 'kpis' not in st.session_state:
    st.session_state.kpis = None

# Configuração da sidebar
with st.sidebar:
    st.markdown('<div class="sub-header">⚙️ Configurações</div>', unsafe_allow_html=True)

    # 🔹 Seleção da Empresa
    try:
        with open('config/empresas_config.json', encoding='utf-8') as f:
            empresas = json.load(f)
    except Exception as e:
        st.error(f"Erro ao carregar configuração de empresas: {e}")
        empresas = {}

    opcoes_empresas = {v['nome']: k for k, v in empresas.items()}
    
    if not opcoes_empresas:
        st.warning("Nenhuma empresa configurada. Por favor, adicione empresas ao arquivo config/empresas_config.json")
        empresa_selecionada_nome = None
        chave_empresa = None
        cnpj_empresa = None
    else:
        empresa_selecionada_nome = st.selectbox("🏢 Selecione a Empresa", options=opcoes_empresas.keys())
        chave_empresa = opcoes_empresas[empresa_selecionada_nome]
        cnpj_empresa = empresas[chave_empresa]['cnpj_emitentes'][0]
        st.markdown(f"**CNPJ Selecionado:** `{cnpj_empresa}`")

    # Botão para limpar dados
    if st.session_state.dados_processados:
        if st.button("🗑️ Limpar Dados Processados"):
            st.session_state.dados_processados = False
            st.session_state.df_configurado = None
            st.session_state.df_estoque = None
            st.session_state.df_alertas = None
            st.session_state.df_resumo = None
            st.session_state.df_apuracao = None
            st.session_state.kpis = None
            st.success("Dados limpos com sucesso!")
            st.experimental_rerun()

    # Sobre o projeto
    st.markdown("---")
    st.markdown("### 📌 Sobre")
    st.markdown("""
    Esta aplicação analisa XMLs de notas fiscais para geração de:
    
    - Controle de estoque fiscal
    - Análise de entrada/saída
    - Cálculo tributário
    - Relatórios gerenciais
    """)

# Função utilitária para gerar Excel
def gerar_excel(df, nome_abas="Relatorio"):
    output = BytesIO()
    df_export = df.copy()

    # Conversão segura de tipos de dados
    for col in df_export.columns:
        if pd.api.types.is_datetime64_any_dtype(df_export[col]):
            df_export[col] = df_export[col].dt.strftime('%d/%m/%Y').fillna('')
        elif df_export[col].dtype == 'object':  # Usando object em vez de 'O'
            df_export[col] = df_export[col].apply(lambda x: str(x) if pd.notnull(x) else '')
        elif df_export[col].name.lower().startswith(('valor', 'lucro', 'total')):
            # Formatar colunas monetárias
            df_export[col] = pd.to_numeric(df_export[col], errors='coerce').fillna(0)

    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df_export.to_excel(writer, index=False, sheet_name=nome_abas[:31])
        
        # Formatar colunas
        workbook = writer.book
        worksheet = writer.sheets[nome_abas[:31]]
        
        # Formato monetário
        formato_moeda = workbook.add_format({'num_format': 'R$ #,##0.00'})
        
        # Aplicar formatos por tipo de coluna
        for i, col in enumerate(df_export.columns):
            col_lower = col.lower()
            if any(termo in col_lower for termo in ['valor', 'lucro', 'total']):
                worksheet.set_column(i, i, 15, formato_moeda)
            elif 'data' in col_lower:
                worksheet.set_column(i, i, 12)
            else:
                worksheet.set_column(i, i, 18)
        
    output.seek(0)
    return output

# Função para processar os arquivos com feedback de progresso
def processar_arquivos(xml_paths, cnpj_empresa):
    total_arquivos = len(xml_paths)
    progresso = st.progress(0)
    status_text = st.empty()
    
    if total_arquivos > 0:
        # Processar em lotes para melhorar desempenho com muitos arquivos
        resultados = []
        
        # Criar lotes de 100 arquivos para processamento
        lote_size = min(100, total_arquivos)
        for i in range(0, total_arquivos, lote_size):
            lote = xml_paths[i:i+lote_size]
            
            # Processar lote de arquivos
            with ThreadPoolExecutor() as executor:
                lote_resultados = processar_xmls(lote, cnpj_empresa)
                resultados.append(lote_resultados)
                
            # Atualizar progresso
            progresso.progress(min((i+lote_size)/total_arquivos, 1.0))
            status_text.text(f"Processando {min(i+lote_size, total_arquivos)} de {total_arquivos} arquivos...")
            time.sleep(0.1)  # Pequena pausa para atualização visual
        
        # Consolidar resultados
        df_final = pd.concat(resultados, ignore_index=True) if resultados else pd.DataFrame()
        
        status_text.text("Processamento concluído!")
        progresso.progress(1.0)
        time.sleep(1)
        status_text.empty()
        progresso.empty()
        
        return df_final
    else:
        status_text.text("Nenhum arquivo para processar")
        time.sleep(1)
        status_text.empty()
        progresso.empty()
        return pd.DataFrame()

# Função para criar gráficos
def criar_grafico_resumo(df_resumo):
    fig, ax = plt.subplots(figsize=(10, 5))
    
    # Configurar data para plotagem
    df_temp = df_resumo.copy()
    if 'Mês' in df_temp.columns:
        df_temp['Mês'] = pd.to_datetime(df_temp['Mês']).dt.strftime('%b/%Y')
    
    # Plotar gráfico de barras
    sns.set_style('whitegrid')
    ax = sns.barplot(x='Mês', y='Lucro', data=df_temp, color='#1F77B4')
    
    # Adicionar linha de tendência
    ax2 = ax.twinx()
    sns.lineplot(x=range(len(df_temp)), y='Valor Venda', data=df_temp, 
                 marker='o', color='#FF7F0E', ax=ax2)
    
    # Configurações do gráfico
    ax.set_title('Resumo Mensal de Vendas e Lucro', fontsize=16)
    ax.set_xlabel('Período', fontsize=12)
    ax.set_ylabel('Lucro (R$)', fontsize=12)
    ax2.set_ylabel('Valor de Venda (R$)', fontsize=12)
    
    ax.tick_params(axis='x', rotation=45)
    
    # Ajustar layout
    plt.tight_layout()
    return fig

# Upload de arquivos XML ou ZIP
upload_area = st.container()
with upload_area:
    st.markdown('<div class="sub-header">📤 Upload de Arquivos</div>', unsafe_allow_html=True)
    
    if not cnpj_empresa:
        st.warning("Selecione uma empresa antes de fazer upload de arquivos")
        st.stop()
    
    uploaded_files = st.file_uploader("Envie seus XMLs ou ZIP", type=["xml", "zip"], accept_multiple_files=True)

    if uploaded_files:
        with st.spinner("Processando arquivos..."):
            with tempfile.TemporaryDirectory() as tmpdir:
                xml_paths = []

                # Processar os arquivos enviados
                for file in uploaded_files:
                    filepath = os.path.join(tmpdir, file.name)
                    with open(filepath, "wb") as f:
                        f.write(file.read())

                    if file.name.lower().endswith(".zip"):
                        try:
                            with zipfile.ZipFile(filepath, "r") as zip_ref:
                                zip_ref.extractall(tmpdir)
                                xml_paths += [os.path.join(tmpdir, name) for name in zip_ref.namelist() if name.lower().endswith(".xml")]
                        except Exception as e:
                            st.error(f"Erro ao extrair arquivo ZIP {file.name}: {e}")
                    elif file.name.lower().endswith(".xml"):
                        xml_paths.append(filepath)

                # Processar os XMLs
                if xml_paths:
                    df_extraido = processar_arquivos(xml_paths, cnpj_empresa)

                    if df_extraido.empty:
                        st.warning("⚠️ Nenhum dado extraído dos XMLs. Verifique os arquivos enviados.")
                    else:
                        try:
                            # Configurar planilha
                            df_configurado = configurar_planilha(df_extraido)
                            st.session_state.df_configurado = df_configurado
                            
                            # Processar dados
                            if 'Tipo Nota' in df_configurado.columns:
                                df_entrada = df_configurado[df_configurado['Tipo Nota'] == 'Entrada'].copy()
                                df_saida = df_configurado[df_configurado['Tipo Nota'] == 'Saída'].copy()
                                
                                with st.spinner("Gerando relatórios..."):
                                    # Estoque fiscal
                                    df_estoque = gerar_estoque_fiscal(df_entrada, df_saida)
                                    st.session_state.df_estoque = df_estoque
                                    
                                    # Alertas de auditoria
                                    df_alertas = gerar_alertas_auditoria(df_entrada, df_saida)
                                    st.session_state.df_alertas = df_alertas
                                    
                                    # KPIs
                                    kpis = gerar_kpis(df_estoque)
                                    st.session_state.kpis = kpis
                                    
                                    # Resumo mensal
                                    df_resumo = gerar_resumo_mensal(df_estoque)
                                    st.session_state.df_resumo = df_resumo
                                    
                                    # Apuração fiscal
                                    df_apuracao, _ = calcular_apuracao(df_estoque)
                                    st.session_state.df_apuracao = df_apuracao
                                    
                                    # Marcar dados como processados
                                    st.session_state.dados_processados = True
                                    
                                    st.success("✅ XMLs processados com sucesso!")
                            else:
                                st.error("❌ A coluna 'Tipo Nota' não foi gerada. Verifique a configuração e classificação.")
                        except Exception as e:
                            st.error(f"Erro ao processar dados: {e}")
                else:
                    st.warning("⚠️ Nenhum arquivo XML encontrado nos arquivos enviados.")

# Renderizar resultados se houver dados processados
if st.session_state.dados_processados:
    # Mostrar KPIs em cards
    st.markdown('<div class="sub-header">📊 Indicadores Principais</div>', unsafe_allow_html=True)
    
    kpi_cols = st.columns(3)
    with kpi_cols[0]:
        st.markdown(f"""
        <div class="card">
            <h3>Total Vendido</h3>
            <h2>{formatar_moeda(st.session_state.kpis["Total Vendido (R$)"])}</h2>
        </div>
        """, unsafe_allow_html=True)
    
    with kpi_cols[1]:
        st.markdown(f"""
        <div class="card">
            <h3>Lucro Total</h3>
            <h2>{formatar_moeda(st.session_state.kpis["Lucro Total (R$)"])}</h2>
        </div>
        """, unsafe_allow_html=True)
    
    with kpi_cols[2]:
        st.markdown(f"""
        <div class="card">
            <h3>Estoque Atual</h3>
            <h2>{formatar_moeda(st.session_state.kpis["Estoque Atual (R$)"])}</h2>
        </div>
        """, unsafe_allow_html=True)
    
    # Tabs para diferentes relatórios
    abas = st.tabs([
        "📦 Estoque", 
        "🕵️ Auditoria", 
        "📈 KPIs e Resumo", 
        "🧾 Apuração Fiscal",
        "📊 Análise Avançada"  # Nova aba
    ])
    
    with abas[0]:
        st.markdown('<div class="sub-header">📦 Estoque Fiscal</div>', unsafe_allow_html=True)
        
        # Filtros de data para estoque
        if 'Data Emissão_entrada' in st.session_state.df_estoque.columns:
            filtro_cols = st.columns(3)
            with filtro_cols[0]:
                anos_disponiveis = sorted(pd.to_datetime(
                    st.session_state.df_estoque['Data Emissão_entrada']).dt.year.unique().tolist())
                ano_selecionado = st.selectbox("Ano", [None] + anos_disponiveis, key="estoque_ano")
            
            with filtro_cols[1]:
                meses_disponiveis = list(range(1, 13))
                mes_selecionado = st.selectbox("Mês", [None] + meses_disponiveis, key="estoque_mes")
                
            with filtro_cols[2]:
                situacao_opcoes = ['Todos', 'Em Estoque', 'Vendido']
                situacao_selecionada = st.selectbox("Situação", situacao_opcoes, key="estoque_situacao")
            
            # Aplicar filtros
            df_estoque_filtrado = st.session_state.df_estoque.copy()
            
            if ano_selecionado:
                df_estoque_filtrado = df_estoque_filtrado[
                    pd.to_datetime(df_estoque_filtrado['Data Emissão_entrada']).dt.year == ano_selecionado]
            
            if mes_selecionado:
                df_estoque_filtrado = df_estoque_filtrado[
                    pd.to_datetime(df_estoque_filtrado['Data Emissão_entrada']).dt.month == mes_selecionado]
                
            if situacao_selecionada != 'Todos':
                df_estoque_filtrado = df_estoque_filtrado[df_estoque_filtrado['Situação'] == situacao_selecionada]
        else:
            df_estoque_filtrado = st.session_state.df_estoque
        
        # Mostrar tabela de estoque
        st.dataframe(df_estoque_filtrado, use_container_width=True)
        
        # Botão para download
        st.download_button(
            label="📥 Baixar Estoque",
            data=gerar_excel(df_estoque_filtrado, "Estoque"),
            file_name="Estoque.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
    
    with abas[1]:
        st.markdown('<div class="sub-header">🕵️ Relatório de Auditoria</div>', unsafe_allow_html=True)
        
        if not st.session_state.df_alertas.empty:
            st.dataframe(st.session_state.df_alertas, use_container_width=True)
            
            # Mostrar alertas críticos
            alertas_criticos = st.session_state.df_alertas.shape[0]
            st.markdown(f"""
            <div class="warning-card">
                <h3>⚠️ {alertas_criticos} alertas identificados</h3>
                <p>Verifique possíveis inconsistências nos dados fiscais.</p>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.markdown("""
            <div class="success-card">
                <h3>✅ Sem alertas de auditoria</h3>
                <p>Os dados fiscais analisados não apresentam inconsistências.</p>
            </div>
            """, unsafe_allow_html=True)
        
        st.download_button(
            label="📥 Baixar Relatório de Auditoria",
            data=gerar_excel(st.session_state.df_alertas, "Auditoria"),
            file_name="Auditoria.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
    
    with abas[2]:
        st.markdown('<div class="sub-header">📊 KPIs e Resumo Mensal</div>', unsafe_allow_html=True)
        
        # Mostrar gráfico de resumo mensal
        if not st.session_state.df_resumo.empty:
            grafico = criar_grafico_resumo(st.session_state.df_resumo)
            st.pyplot(grafico)
            
            # Mostrar tabela de resumo mensal
            st.markdown("### 📅 Resumo Mensal")
            st.dataframe(st.session_state.df_resumo, use_container_width=True)
            
            st.download_button(
                label="📥 Baixar Resumo Mensal",
                data=gerar_excel(st.session_state.df_resumo, "Resumo"),
                file_name="Resumo_Mensal.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
        else:
            st.info("Sem dados de resumo mensal para mostrar.")
    
    with abas[3]:
        st.markdown('<div class="sub-header">🧾 Apuração Fiscal</div>', unsafe_allow_html=True)
        
        if not st.session_state.df_apuracao.empty:
            # Mostrar tabela de apuração fiscal
            st.dataframe(st.session_state.df_apuracao, use_container_width=True)
            
            # Explicação do cálculo
            st.markdown("""
            <div class="info-card">
                <h3>📝 Como funciona o cálculo fiscal</h3>
                <p>A apuração fiscal é calculada com base nos seguintes parâmetros:</p>
                <ul>
                    <li>ICMS Presumido: 19% sobre o lucro</li>
                    <li>PIS/COFINS Presumido: 3,65% sobre o lucro</li>
                    <li>Base IRPJ/CSLL: 32% sobre o lucro</li>
                    <li>IRPJ: 15% sobre a base</li>
                    <li>Adicional IRPJ: 10% sobre o que exceder R$ 60.000 por trimestre</li>
                    <li>CSLL: 9% sobre a base</li>
                </ul>
            </div>
            """, unsafe_allow_html=True)
            
            st.download_button(
                label="📥 Baixar Apuração Fiscal",
                data=gerar_excel(st.session_state.df_apuracao, "Apuracao"),
                file_name="Apuracao_Fiscal.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
        else:
            st.info("Sem dados de apuração fiscal para mostrar.")
    
    with abas[4]:
        st.markdown('<div class="sub-header">📊 Análise Personalizada de Dados</div>', unsafe_allow_html=True)
        if st.button("Gerar Análise"):
            try:
                resultado_analise = sua_funcao_principal(st.session_state.df_configurado)
                st.dataframe(resultado_analise, use_container_width=True)
            except Exception as e:
                st.error(f"Erro ao executar análise avançada: {e}")

    # Download de todos os dados
    st.markdown('<div class="sub-header">📥 Baixar Dados Completos</div>', unsafe_allow_html=True)
    
    st.download_button(
        label="📥 Baixar Planilha Completa",
        data=gerar_excel(st.session_state.df_configurado, "Extracao_Completa"),
        file_name="Extracao_Completa.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
else:
    # Mostrar mensagem inicial
    st.markdown("""
    <div class="info-card">
        <h3>👋 Bem-vindo ao Painel Fiscal de Veículos</h3>
        <p>Para começar, selecione uma empresa e faça upload dos arquivos XML das notas fiscais.</p>
        <p>O sistema irá processar os dados e gerar relatórios de estoque, auditoria, KPIs e apuração fiscal.</p>
    </div>
    """, unsafe_allow_html=True)
