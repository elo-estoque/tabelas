import streamlit as st
import pandas as pd
import re
import io

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="🚚 ELO-Normalizador Automático de Endereços", layout="wide", page_icon="🚚")

st.markdown("## 🚚 ELO-Normalizador Automático de Endereços (CEP + Layout Final) 🚚 ")

# --- FUNÇÕES DE EXTRAÇÃO (O ROBÔ BLINDADO 3.4) ---

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

    # 4. PROCURA 3 (PADRÃO): 8 dígitos SOLTOS
    match_8_digitos = re.search(r'(?<!\d)(\d{8})(?!\d)', texto_limpo)
    if match_8_digitos:
        return match_8_digitos.group(1)
        
    # 5. PROCURA 4 (SALVA VIDAS - CORREÇÃO DO EXCEL): 7 dígitos soltos
    match_7_digitos = re.search(r'(?<!\d)(\d{7})(?!\d)', texto_limpo)
    if match_7_digitos:
        return "0" + match_7_digitos.group(1)
        
    return None

def extrair_numero_inteligente(texto):
    if not isinstance(texto, str): return ""
    
    # LIMPEZA CRÍTICA: Remove aspas e converte para MAIÚSCULO (Resolve o problema de 'apto' vs 'APTO')
    texto_upper = texto.upper().replace('"', '').strip()

    # --- VACINA ANTI-COMPLEMENTO (TURBINADA) ---
    # Remove qualquer combinação de termos que indicam complemento seguido de número.
    # Ex: "Apt 102", "Cs 3", "Lt 45B", "Sala 10"
    
    lista_proibida = [
        r'APTO', r'APT', r'AP', r'APARTAMENTO', r'APART',  # Apartamentos
        r'LOTE', r'LT', r'LOT',                            # Lotes
        r'CASA', r'CS', r'CN',                             # Casas
        r'BLOCO', r'BL',                                   # Blocos
        r'SALA', r'SL', r'CJ', r'CONJUNTO',                # Salas/Conjuntos
        r'LOJA', r'LJ',                                    # Lojas
        r'ANDAR', r'AND',                                  # Andares
        r'UNIDADE', r'UNID',                               # Unidades
        r'FRENTE', r'FD', r'FUNDOS', r'FDS',               # Fundos/Frente
        r'QD', r'QUADRA',                                  # Quadras
        r'BOX', r'GARAGEM',                                # Box
        r'KM'                                              # Quilometragem (Rodovias)
    ]
    
    # Cria o regex gigante: (?:APTO|APT|...)\.?\s*\d+[A-Z]?
    regex_proibidos = r'\b(?:' + '|'.join(lista_proibida) + r')\.?\s*\d+[A-Z]?\b'
    
    # Aplica a vacina: Apaga esses termos do texto que o robô lê
    texto_upper = re.sub(regex_proibidos, '', texto_upper, flags=re.IGNORECASE)

    # --- TRAVA DE SEGURANÇA (CEP) ---
    # 1. Remove CEPs formatados (81280-430)
    texto_upper = re.sub(r'\b\d{5}[-.]?\d{3}\b', '', texto_upper)
    
    # 2. Remove qualquer sequência gigante (7+ dígitos)
    texto_limpo_numeros = re.sub(r'\d{7,}', '', texto_upper)

    # Função auxiliar: Só aceita se tiver até 6 dígitos
    def eh_valido(n):
        return len(n) <= 6

    # --- BUSCAS PADRÃO ---

    # 1. Procura S/N explícito
    if re.search(r'\b(S/N|SN|S\.N|SEM N|S-N)\b', texto_limpo_numeros): return "S/N"
    
    # 2. Padrão: Número seguido de VÍRGULA (Ex: Rua Tal 57, Ap 22)
    match_antes_virgula = re.search(r'\b(\d+)\s*,', texto_limpo_numeros)
    if match_antes_virgula and eh_valido(match_antes_virgula.group(1)): return match_antes_virgula.group(1)

    # 3. Padrão: Rua Tal, 123 - Bairro
    match_hifen = re.search(r'\s[-–]\s*(\d+)\s*(?:[-–]|$)', texto_limpo_numeros)
    if match_hifen and eh_valido(match_hifen.group(1)): return match_hifen.group(1)

    # 4. Padrão: Rua Tal, 123, Bairro
    match_meio = re.search(r',\s*(\d+)\s*(?:-|,|;|/|AP|BL)', texto_limpo_numeros)
    if match_meio and eh_valido(match_meio.group(1)): return match_meio.group(1)

    # 5. Padrão: Rua Tal nº 123
    match_n = re.search(r'(?:nº|n|num)\.?\s*(\d+)', texto_limpo_numeros, re.IGNORECASE)
    if match_n and eh_valido(match_n.group(1)): return match_n.group(1)
    
    # 6. Padrão simples: Vírgula e numero
    match_virgula = re.search(r',\s*(\d+)', texto_limpo_numeros)
    if match_virgula and eh_valido(match_virgula.group(1)): return match_virgula.group(1)

    # 7. Padrão final de linha: Rua Tal 123
    match_fim = re.search(r'\s(\d+)$', texto_limpo_numeros)
    if match_fim and eh_valido(match_fim.group(1)): return match_fim.group(1)
    
    # --- BUSCA DE VARREDURA (Último Recurso) ---
    numeros_soltos = re.findall(r'\d+', texto_limpo_numeros)
    for n in numeros_soltos:
        if eh_valido(n):
            return n
        
    return "" 

def gerar_status(cep, numero):
    status = []
    if not cep: status.append("🔴 CEP?") 
    if not numero: status.append("⚠️ NÚMERO?")
    elif numero == "S/N": status.append("⚪ S/N")
    
    if not status: return "✅ OK"
    return " ".join(status)

# --- PROCESSAMENTO ---

def processar_planilha(df, col_map):
    df = df.copy()
    
    # 1. Cria ID Sequencial
    df['ID_Personalizado'] = [f'ID_{i+1}' for i in range(len(df))]
    
    # 2. Mapeia colunas simples
    df['Nome_Final'] = df[col_map['nome']] if col_map['nome'] else ""
    df['Cidade_Final'] = df[col_map['cidade']] if col_map['cidade'] else ""
    df['UF_Final'] = df[col_map['uf']] if col_map['uf'] else ""
    df['Regiao_Final'] = df[col_map['regiao']] if col_map['regiao'] else ""
    df['Bairro_Final'] = df[col_map['bairro']] if col_map['bairro'] else "" 
    
    col_endereco = col_map['endereco']
    
    # 3. Extrações (CEP e Número)
    # Garante que a coluna de endereço seja string antes de processar
    df[col_endereco] = df[col_endereco].astype(str)
    
    df['CEP_Final'] = df[col_endereco].apply(extrair_cep_bruto)
    df['Numero_Final'] = df[col_endereco].apply(extrair_numero_inteligente)
    
    # 4. Limpeza do Logradouro (Remove o que já achamos)
    def limpar_texto(row):
        txt = str(row[col_endereco]).replace('"', '').replace("'", "")
        cep = row['CEP_Final']
        num = row['Numero_Final']
        
        # Se achou CEP, remove ele do texto para limpar
        if cep:
            # Tenta remover formato formatado e formato limpo
            txt = re.sub(rf'{cep[:5]}.?{cep[5:]}', '', txt) 
            txt = re.sub(rf'{cep}', '', txt)
            # Remove CEP de 7 digitos se foi o caso
            if cep.startswith('0'):
                cep_sem_zero = cep[1:]
                txt = re.sub(rf'{cep_sem_zero}', '', txt)
            
        if num and num != "S/N":
            txt = re.sub(rf'\b{num}\b', '', txt)
            
        txt = re.sub(r'\bCEP\b[:.]?', '', txt, flags=re.IGNORECASE)
        txt = re.sub(r'\s[-–]\s*$', '', txt)
        return txt.strip(' ,;-.')

    df['Logradouro_Final'] = df.apply(limpar_texto, axis=1)
    
    # 5. Colunas Extras
    df['Complemento_Final'] = ""
    df['Aos_Cuidados_Final'] = ""
    
    # 6. Status
    df['STATUS_SISTEMA'] = df.apply(lambda x: gerar_status(x['CEP_Final'], x['Numero_Final']), axis=1)
    
    # Ordena colocando os erros primeiro
    df = df.sort_values(by=['STATUS_SISTEMA'], ascending=False)
    
    return df

# --- INTERFACE ---

uploaded_file = st.file_uploader("📂 Importar Planilha (.xlsx)", type=['xlsx'])

if uploaded_file:
    try:
        df = pd.read_excel(uploaded_file)
        # Converte tudo para string para evitar erros de leitura
        df = df.astype(str).replace('nan', '')
        cols = list(df.columns)
        
        st.write("### ⚙️ Mapeamento de Colunas")
        st.info("Confirme as colunas abaixo:")
        
        col1, col2, col3 = st.columns(3)
        
        def achar_col(termos):
            for i, c in enumerate(cols):
                if any(t in c.lower() for t in termos): return i
            return 0 

        with col1:
            c_end = st.selectbox("Endereço Completo *", cols, index=achar_col(['endereço', 'endereco']))
            c_nome = st.selectbox("Nome (Clube/Loja)", ["(Criar em Branco)"] + cols, index=achar_col(['nome', 'clube', 'loja']) + 1)
        
        with col2:
            c_cidade = st.selectbox("Cidade", ["(Criar em Branco)"] + cols, index=achar_col(['cidade', 'city']) + 1)
            c_uf = st.selectbox("UF (Estado)", ["(Criar em Branco)"] + cols, index=achar_col(['uf', 'estado']) + 1)
            
        with col3:
            c_regiao = st.selectbox("Região", ["(Criar em Branco)"] + cols, index=achar_col(['regiao', 'região']) + 1)
            c_bairro = st.selectbox("Bairro (Se existir)", ["(Criar em Branco)"] + cols, index=achar_col(['bairro']) + 1)

        col_map = {
            'endereco': c_end,
            'nome': c_nome if c_nome != "(Criar em Branco)" else None,
            'cidade': c_cidade if c_cidade != "(Criar em Branco)" else None,
            'uf': c_uf if c_uf != "(Criar em Branco)" else None,
            'regiao': c_regiao if c_regiao != "(Criar em Branco)" else None,
            'bairro': c_bairro if c_bairro != "(Criar em Branco)" else None,
        }

        if st.button("🚀 Processar"):
            with st.spinner('O Robô está trabalhando...'):
                df_processado = processar_planilha(df, col_map)
            
            st.success("Processamento concluído!")
            
            # ORDEM FINAL PEDIDA
            ordem_final_colunas = [
                "ID_Personalizado",
                c_end, # Endereço Original
                "Nome_Final",
                "CEP_Final",
                "Logradouro_Final",
                "Numero_Final",
                "Complemento_Final",
                "Bairro_Final",
                "Cidade_Final",
                "UF_Final",
                "Regiao_Final",
                "Aos_Cuidados_Final"
            ]
            
            column_config = {
                "STATUS_SISTEMA": st.column_config.TextColumn("⚠️ Status", width="medium", disabled=True),
                "ID_Personalizado": st.column_config.TextColumn("ID", width="small", disabled=True),
                c_end: st.column_config.TextColumn("Endereço Original", width="large", disabled=True),
                "Nome_Final": st.column_config.TextColumn("Nome", width="medium"),
                "CEP_Final": st.column_config.TextColumn("CEP", width="medium"),
                "Logradouro_Final": st.column_config.TextColumn("Logradouro", width="large"),
                "Numero_Final": st.column_config.TextColumn("N°", width="small"),
                "Complemento_Final": st.column_config.TextColumn("Complemento", width="medium"),
                "Bairro_Final": st.column_config.TextColumn("Bairro", width="medium"),
                "Cidade_Final": st.column_config.TextColumn("Cidade", width="medium"),
                "UF_Final": st.column_config.TextColumn("UF", width="small"),
                "Regiao_Final": st.column_config.TextColumn("Região", width="medium"),
                "Aos_Cuidados_Final": st.column_config.TextColumn("Aos Cuidados", width="medium"),
            }
            
            cols_to_show = ["STATUS_SISTEMA"] + ordem_final_colunas
            
            edited_df = st.data_editor(
                df_processado[cols_to_show],
                column_config=column_config,
                num_rows="dynamic",
                use_container_width=True,
                height=700
            )

            # DOWNLOAD
            st.write("---")
            st.subheader("💾 Exportar")
            
            col1, col2 = st.columns(2)
            
            # Botão 1: Triagem
            buffer1 = io.BytesIO()
            with pd.ExcelWriter(buffer1, engine='xlsxwriter') as writer:
                edited_df.to_excel(writer, index=False, sheet_name='Triagem')
            with col1:
                st.download_button("⬇️ Baixar Triagem (Erros no topo)", buffer1, "Triagem.xlsx")

            # Botão 2: Final
            buffer2 = io.BytesIO()
            with pd.ExcelWriter(buffer2, engine='xlsxwriter') as writer:
                # Reordena por ID numérico
                df_final = edited_df.copy()
                df_final['__sort_id'] = df_final['ID_Personalizado'].apply(lambda x: int(x.split('_')[1]))
                df_final = df_final.sort_values('__sort_id')
                df_final = df_final[ordem_final_colunas]
                df_final.columns = [
                    "ID", "Endereço Original", "Nome (Clube)", "CEP", "Logradouro", 
                    "N°", "Complemento", "Bairro", "Cidade", "UF", "Região", "Aos Cuidados"
                ]
                df_final.to_excel(writer, index=False, sheet_name='Envio')
                
            with col2:
                st.download_button(
                    label="✅ Baixar FINAL (Ordem ID Correta)",
                    data=buffer2,
                    file_name="Lote_Final.xlsx",
                    mime="application/vnd.ms-excel",
                    type="primary"
                )

    except Exception as e:
        st.error(f"Erro ao processar: {e}")
