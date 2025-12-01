import streamlit as st
import pandas as pd
import re
import io
import unicodedata

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="🚚 ELO-Normalizador Automático de Endereços", layout="wide", page_icon="🚚")

st.markdown("## 🚚 ELO-Normalizador Automático de Endereços (CEP + Layout Final) 🚚 ")

# --- FUNÇÕES DE EXTRAÇÃO (O ROBÔ BLINDADO) ---

def remover_acentos(txt):
    if not isinstance(txt, str): return str(txt)
    return unicodedata.normalize('NFKD', txt).encode('ASCII', 'ignore').decode('ASCII')

def extrair_cep_bruto(texto):
    if not isinstance(texto, str): return None
    
    # 1. LIMPEZA INICIAL
    texto_limpo = texto.replace('"', '').replace("'", "").strip()
    
    # 2. PROCURA 1: Padrão Formatado (Com traço, ponto ou espaço)
    match_formatado = re.search(r'\b\d{2}[. ]?\d{3}-\d{3}\b', texto_limpo)
    if match_formatado:
         return re.sub(r'\D', '', match_formatado.group(0))
    
    # 3. PROCURA 2: Palavra "CEP" seguida de números
    match_palavra = re.search(r'(?:CEP|C\.E\.P).{0,5}?(\d{8})', re.sub(r'[-.]', '', texto_limpo), re.IGNORECASE)
    if match_palavra:
        return match_palavra.group(1)
        
    # 4. PROCURA 3: 8 dígitos soltos (Com verificação de borda para não pegar pedaço de telefone)
    match_8_digitos = re.search(r'(?<!\d)(\d{8})(?!\d)', texto_limpo)
    if match_8_digitos:
        return match_8_digitos.group(1)
        
    # 5. PROCURA 4: 7 dígitos (Erro comum de digitação, assume zero à esquerda)
    match_7_digitos = re.search(r'(?<!\d)(\d{7})(?!\d)', texto_limpo)
    if match_7_digitos:
        return "0" + match_7_digitos.group(1)
        
    return None

def formatar_cep(cep_bruto):
    if not cep_bruto or len(cep_bruto) != 8:
        return ""
    return f"{cep_bruto[:5]}-{cep_bruto[5:]}"

def extrair_uf(texto):
    if not isinstance(texto, str): return ''
    # Procura por UF no final da string ou isolada (ex: /SP, - SP, ou SP no fim)
    match = re.search(r'\b([A-Z]{2})\b$', texto.strip())
    if match:
        return match.group(1)
    return ''

def classificar_regiao(uf):
    sul = ['RS', 'SC', 'PR']
    sudeste = ['SP', 'RJ', 'MG', 'ES']
    centro_oeste = ['MT', 'MS', 'GO', 'DF']
    nordeste = ['BA', 'PI', 'MA', 'CE', 'RN', 'PB', 'PE', 'AL', 'SE']
    norte = ['AC', 'RO', 'AM', 'RR', 'PA', 'AP', 'TO']
    
    uf = str(uf).upper().strip()
    if uf in sul: return 'Sul'
    if uf in sudeste: return 'Sudeste'
    if uf in centro_oeste: return 'Centro-Oeste'
    if uf in nordeste: return 'Nordeste'
    if uf in norte: return 'Norte'
    return ''

def extrair_numero_inteligente(texto):
    if not isinstance(texto, str): return ""
    
    texto_upper = texto.upper().replace('"', '').strip()
    
    # --- LISTA DE PALAVRAS PROIBIDAS (A LÓGICA ROBUSTA) ---
    # Removemos estas palavras e o que vem depois delas para não confundir "APTO 44" com o número da casa
    lista_proibida = [
        r'APTO', r'APT', r'AP', r'APARTAMENTO', r'APART', 
        r'LOTE', r'LT', r'LOT',
        r'CASA', r'CS', r'CN', 
        r'BLOCO', r'BL', 
        r'SALA', r'SL', 
        r'CJ', r'CONJUNTO',
        r'LOJA', r'LJ', 
        r'ANDAR', r'AND', 
        r'UNIDADE', r'UNID', 
        r'FRENTE', r'FD', 
        r'FUNDOS', r'FDS', 
        r'QD', r'QUADRA', 
        r'BOX', 
        r'GARAGEM', 
        r'KM'
    ]
    
    # Regex agressivo para limpar complementos
    regex_proibidos = r'\b(?:' + '|'.join(lista_proibida) + r')\.?\s*\d+[A-Z]?\b'
    texto_upper = re.sub(regex_proibidos, '', texto_upper, flags=re.IGNORECASE)
    
    # Remove CEPs do texto para não confundir
    texto_upper = re.sub(r'\b\d{5}[-.]?\d{3}\b', '', texto_upper)
    
    # Remove sequências numéricas muito longas (telefones, CNPJ)
    texto_limpo_numeros = re.sub(r'\d{7,}', '', texto_upper)
    
    # Função auxiliar para validar se parece um número de casa
    def eh_valido(n):
        return len(n) <= 6 # Números de casa raramente têm mais de 6 dígitos
    
    # 1. Busca explícita por "S/N"
    if re.search(r'\b(S/N|SN|S\.N|SEM N|S-N)\b', texto_limpo_numeros):
        return "S/N"
    
    # 2. Busca número antes de vírgula (Padrão: Rua Tal, 123)
    match_antes_virgula = re.search(r'\b(\d+)\s*,', texto_limpo_numeros)
    if match_antes_virgula and eh_valido(match_antes_virgula.group(1)):
        return match_antes_virgula.group(1)
    
    # 3. Busca número entre hifens ou no fim com hifen (Rua Tal - 123)
    match_hifen = re.search(r'\s[-–]\s*(\d+)\s*(?:[-–]|$)', texto_limpo_numeros)
    if match_hifen and eh_valido(match_hifen.group(1)):
        return match_hifen.group(1)
        
    # 4. Busca número após vírgula e antes de complementos comuns
    match_meio = re.search(r',\s*(\d+)\s*(?:-|,|;|/|AP|BL)', texto_limpo_numeros)
    if match_meio and eh_valido(match_meio.group(1)):
        return match_meio.group(1)
    
    # 5. Busca explícita por "Nº 123"
    match_n = re.search(r'(?:nº|n|num)\.?\s*(\d+)', texto_limpo_numeros, re.IGNORECASE)
    if match_n and eh_valido(match_n.group(1)):
        return match_n.group(1)
    
    # 6. Busca genérica após vírgula
    match_virgula = re.search(r',\s*(\d+)', texto_limpo_numeros)
    if match_virgula and eh_valido(match_virgula.group(1)):
        return match_virgula.group(1)
    
    # 7. Último recurso: Número no final da string
    match_fim = re.search(r'\s(\d+)$', texto_limpo_numeros)
    if match_fim and eh_valido(match_fim.group(1)):
        return match_fim.group(1)
    
    # 8. Desespero: Pega o primeiro número solto que encontrar
    numeros_soltos = re.findall(r'\d+', texto_limpo_numeros)
    for n in numeros_soltos:
        if eh_valido(n): return n
        
    return ""

def gerar_status(cep, numero):
    status = []
    if not cep: status.append("FALTA CEP") 
    if not numero: status.append("FALTA NÚMERO")
    elif numero == "S/N": status.append("S/N (Manual)")
    
    if not status: return "OK"
    return " ".join(status)

# --- PROCESSAMENTO DO DATAFRAME ---

def processar_planilha(df, col_endereco, col_nome, col_ac):
    df = df.copy()
    
    # Normaliza a coluna de endereço para string
    df['Endereço Original'] = df[col_endereco].astype(str).replace('nan', '')
    
    # 1. Extração de CEP (Blindada)
    df['CEP_Bruto'] = df['Endereço Original'].apply(extrair_cep_bruto)
    df['CEP_Final'] = df['CEP_Bruto'].apply(formatar_cep)
    
    # 2. Extração de Número (Inteligente)
    df['Numero_Final'] = df['Endereço Original'].apply(extrair_numero_inteligente)
    
    # 3. Limpeza do Logradouro
    def limpar_logradouro(row):
        txt = str(row['Endereço Original']).replace('"', '').replace("'", "")
        cep = row['CEP_Bruto']
        num = row['Numero_Final']
        
        # Remove o CEP do texto para não atrapalhar
        if cep:
            txt = re.sub(rf'{cep[:5]}.?{cep[5:]}', '', txt) 
            txt = re.sub(rf'{cep}', '', txt)
            if cep.startswith('0'):
                txt = re.sub(rf'{cep[1:]}', '', txt)
            
        # Remove o número encontrado do texto
        if num and num != "S/N":
            txt = re.sub(rf'\b{num}\b', '', txt)
            
        # Limpezas gerais
        txt = re.sub(r'\bCEP\b[:.]?', '', txt, flags=re.IGNORECASE)
        txt = re.sub(r'\s[-–]\s*$', '', txt) # Hifens no final
        
        # Tenta remover a UF do final se ela existir
        match_uf = re.search(r'\b([A-Z]{2})\b$', txt.strip())
        if match_uf:
            txt = re.sub(r'\b[A-Z]{2}\b$', '', txt)
            
        return txt.strip(' ,;/-')

    df['Logradouro_Final'] = df.apply(limpar_logradouro, axis=1)
    
    # 4. Geografia: Bairro, Cidade, UF
    def separar_geo(texto_orig):
        uf = extrair_uf(texto_orig)
        cidade = ''
        bairro = ''
        
        if uf:
            # Tenta quebrar por vírgulas ou traços
            partes = re.split(r'[,-/]', texto_orig)
            partes = [p.strip() for p in partes if p.strip()]
            
            # Se a última parte for a UF, remove
            if partes and partes[-1].upper() == uf:
                partes.pop()
                
            # Assume: ... Bairro, Cidade, UF
            if partes:
                cidade = partes[-1] 
            if len(partes) > 1:
                bairro = partes[-2]
                
        return pd.Series([bairro, cidade, uf])

    df[['Bairro_Final', 'Cidade_Final', 'UF_Final']] = df['Endereço Original'].apply(separar_geo)
    
    # 5. Região
    df['Regiao_Final'] = df['UF_Final'].apply(classificar_regiao)
    
    # 6. Complemento (Deixamos vazio por padrão pois é arriscado inferir sem base de dados)
    df['Complemento_Final'] = ''
    
    # 7. Colunas de Nome e A/C
    df['Nome_Final'] = df[col_nome] if col_nome else ''
    df['AC_Final'] = df[col_ac] if col_ac else ''
    
    # 8. Status para validação visual (opcional)
    df['Status_Sistema'] = df.apply(lambda x: gerar_status(x['CEP_Final'], x['Numero_Final']), axis=1)
    
    # ==========================================================
    # ORGANIZAÇÃO FINAL (AQUI ESTÁ A MUDANÇA SOLICITADA)
    # ==========================================================
    
    # Geração de IDs: ID_0, ID_1...
    df['ID'] = [f'ID_{i}' for i in range(len(df))]
    
    # Definição Exata das Colunas e Ordem
    colunas_ordenadas = [
        'ID', 
        'Nome_Final',       # Nome (Clube)
        'CEP_Final',        # CEP
        'Logradouro_Final', # Logradouro
        'Numero_Final',     # N°
        'Complemento_Final',# Complemento
        'Bairro_Final',     # Bairro
        'Cidade_Final',     # Cidade
        'UF_Final',         # UF
        'Regiao_Final',     # Região
        'AC_Final',         # Aos cuidados
        'Endereço Original' # Endereço Original (NO FINAL)
    ]
    
    # Seleciona e Renomeia
    df_export = df[colunas_ordenadas].copy()
    
    df_export.columns = [
        'ID',
        'Nome (Clube)',
        'CEP',
        'Logradouro',
        'N°',
        'Complemento',
        'Bairro',
        'Cidade',
        'UF',
        'Região',
        'Aos cuidados',
        'Endereço Original'
    ]
    
    return df_export

# --- FUNÇÃO DE DOWNLOAD EXCEL ---
def convert_df(df):
    output = io.BytesIO()
    # Usa xlsxwriter para garantir compatibilidade
    writer = pd.ExcelWriter(output, engine='xlsxwriter')
    df.to_excel(writer, index=False, sheet_name='Sheet1')
    writer.close()
    processed_data = output.getvalue()
    return processed_data

# --- INTERFACE STREAMLIT ---

uploaded_file = st.file_uploader("Escolha um arquivo Excel (.xlsx) ou CSV", type=['xlsx', 'csv'])

if uploaded_file is not None:
    try:
        # Leitura
        if uploaded_file.name.endswith('.csv'):
            try:
                df = pd.read_csv(uploaded_file, encoding='utf-8', sep=';')
                if len(df.columns) < 2:
                    uploaded_file.seek(0)
                    df = pd.read_csv(uploaded_file, encoding='utf-8', sep=',')
            except:
                uploaded_file.seek(0)
                df = pd.read_csv(uploaded_file, encoding='latin1', sep=';')
        else:
            df = pd.read_excel(uploaded_file)
            
        st.write("### Pré-visualização dos dados originais:")
        st.dataframe(df.head())
        
        # Seletores de Coluna
        cols = df.columns.tolist()
        c1, c2, c3 = st.columns(3)
        col_endereco = c1.selectbox("Selecione a coluna de ENDEREÇO COMPLETO:", cols, index=0)
        col_nome = c2.selectbox("Coluna de Nome (Destinatário):", [None] + cols, index=1 if len(cols)>1 else 0)
        col_ac = c3.selectbox("Coluna A/C (Departamento):", [None] + cols, index=len(cols)-1 if len(cols)>2 else 0)
        
        # Botão de Processar
        if st.button("Processar e Normalizar"):
            with st.spinner('A IA está analisando os endereços com o Robô 3.4...'):
                
                # CHAMA O PROCESSAMENTO
                df_processado = processar_planilha(df, col_endereco, col_nome, col_ac)
                
                st.success(f"Processamento concluído! {len(df_processado)} endereços processados.")
                
                st.write("### Dados Normalizados (Layout Final):")
                st.dataframe(df_processado)
                
                # --- BOTÕES DE DOWNLOAD ---
                csv = df_processado.to_csv(index=False).encode('utf-8-sig')
                excel_data = convert_df(df_processado)
                
                c_down1, c_down2 = st.columns(2)
                
                c_down1.download_button(
                    label="📥 Baixar em CSV (UTF-8)",
                    data=csv,
                    file_name='enderecos_normalizados_correios.csv',
                    mime='text/csv',
                )
                
                c_down2.download_button(
                    label="📥 Baixar em Excel (.xlsx)",
                    data=excel_data,
                    file_name='enderecos_normalizados_correios.xlsx',
                    mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                )
                
    except Exception as e:
        st.error(f"Erro ao ler o arquivo: {e}")
