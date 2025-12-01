import streamlit as st
import pandas as pd
import re
import io

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Sanitizador Elo Brindes", layout="wide", page_icon="🚚")

st.markdown("## 🚚 Sanitizador de Endereços (Modo Turbo)")

# --- FUNÇÕES DE LIMPEZA AVANÇADA ---

def extrair_cep_bruto(texto):
    if not isinstance(texto, str): return None
    
    # 1. Limpeza prévia: Tira espaços duplos
    texto_limpo = " ".join(texto.split())
    
    # 2. REGEX "ASPIRADOR DE PÓ"
    # Procura: 2 digitos + (ponto opcional) + 3 digitos + (traco ou espaco opcional) + 3 digitos
    # Ex: 12.345-678 | 12345 678 | 12345678 | CEP: 12345-678
    match = re.search(r'(?<!\d)\d{2}\.?\d{3}[- ]?\d{3}(?!\d)', texto_limpo)
    
    if match:
        # Retorna apenas os números (12345678)
        return re.sub(r'\D', '', match.group(0))
    return None

def extrair_numero_inteligente(texto):
    if not isinstance(texto, str): return ""
    texto_upper = texto.upper().strip()
    
    # 1. Procura S/N explicitamente
    if re.search(r'\b(S/N|SN|S\.N|SEM N|S-N)\b', texto_upper):
        return "S/N"

    # 2. Estratégia "Sanduíche": Número entre vírgulas ou traços (O mais comum no seu caso)
    # Ex: "Av Brasilia, 177 - 1 Piso" -> Pega o 177
    match_meio = re.search(r',\s*(\d+)\s*(?:-|,|;|/|AP|BL)', texto_upper)
    if match_meio:
        return match_meio.group(1)

    # 3. Procura "Nº 123"
    match_n = re.search(r'(?:nº|n|num)\.?\s*(\d+)', texto_upper, re.IGNORECASE)
    if match_n:
        return match_n.group(1)
    
    # 4. Número logo após vírgula (Rua X, 123)
    match_virgula = re.search(r',\s*(\d+)', texto_upper)
    if match_virgula:
        return match_virgula.group(1)

    # 5. Última tentativa: Número no fim da linha
    match_fim = re.search(r'\s(\d+)$', texto_upper)
    if match_fim:
        return match_fim.group(1)
        
    return "" 

def gerar_status(cep, numero):
    status = []
    if not cep:
        status.append("🔴 CEP?") # Vermelho pra chamar atenção
    
    if not numero:
        status.append("⚠️ NÚMERO?")
    elif numero == "S/N":
        status.append("⚪ S/N")
        
    if not status:
        return "✅ OK"
    return " ".join(status)

def processar_planilha(df, col_endereco):
    df = df.copy()
    
    # Extrações
    df['CEP_Final'] = df[col_endereco].apply(extrair_cep_bruto)
    df['Numero_Final'] = df[col_endereco].apply(extrair_numero_inteligente)
    
    # Limpa o logradouro
    def limpar_texto(row):
        txt = str(row[col_endereco])
        # Remove CEP encontrado do texto original (para limpar)
        cep = row['CEP_Final']
        if cep:
            # Tenta remover formatos variados do CEP no texto
            txt = re.sub(rf'{cep[:5]}.?{cep[5:]}', '', txt) # 12345-678
            txt = re.sub(rf'{cep}', '', txt) # 12345678
            
        # Remove Número encontrado (se não for S/N)
        num = row['Numero_Final']
        if num and num != "S/N":
            txt = re.sub(rf'\b{num}\b', '', txt)
            
        # Remove a palavra "CEP" solta
        txt = re.sub(r'\bCEP\b:?', '', txt, flags=re.IGNORECASE)
        
        return txt.strip(' ,;-.')

    df['Logradouro_Final'] = df.apply(limpar_texto, axis=1)
    df['Bairro_Final'] = "" 
    
    # Gera Status
    df['STATUS_SISTEMA'] = df.apply(lambda x: gerar_status(x['CEP_Final'], x['Numero_Final']), axis=1)
    
    # Ordena: Problemas primeiro
    df = df.sort_values(by=['STATUS_SISTEMA'], ascending=False)
    
    return df

# --- INTERFACE ---

uploaded_file = st.file_uploader("📂 Importar Planilha (.xlsx)", type=['xlsx'])

if uploaded_file:
    try:
        df = pd.read_excel(uploaded_file)
        
        # Identificar coluna
        colunas = list(df.columns)
        index_padrao = 0
        for i, col in enumerate(colunas):
            if "endereço" in col.lower() or "endereco" in col.lower():
                index_padrao = i
                break
        
        st.info("👇 Selecione a coluna do endereço bagunçado:")
        col_alvo = st.selectbox("", colunas, index=index_padrao)

        if st.button("🚀 Processar Agora"):
            with st.spinner('Lendo e separando dados...'):
                df_processado = processar_planilha(df, col_alvo)
            
            st.success("Processamento concluído!")
            
            # --- TABELA DE EDIÇÃO (LARGURA CORRIGIDA) ---
            column_config = {
                "STATUS_SISTEMA": st.column_config.TextColumn(
                    "⚠️ Status",
                    width="medium", # Força tamanho médio
                    disabled=True
                ),
                col_alvo: st.column_config.TextColumn(
                    "Endereço Original (Bloqueado)", 
                    width="large", # Força tamanho GRANDE
                    disabled=True
                ),
                "Logradouro_Final": st.column_config.TextColumn("Rua/Logradouro", width="large"),
                "Numero_Final": st.column_config.TextColumn("Número", width="small"),
                "CEP_Final": st.column_config.TextColumn("CEP", width="medium"),
                "Bairro_Final": st.column_config.TextColumn("Bairro", width="medium"),
            }
            
            # Reorganizar colunas para mostrar o importante primeiro
            cols_order = ["STATUS_SISTEMA", col_alvo, "Logradouro_Final", "Numero_Final", "CEP_Final", "Bairro_Final"]
            cols_rest = [c for c in df.columns if c not in cols_order]
            
            edited_df = st.data_editor(
                df_processado[cols_order + cols_rest],
                column_config=column_config,
                num_rows="dynamic",
                use_container_width=True, # Tenta usar a tela toda
                height=700
            )

            # --- DOWNLOAD ---
            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
                edited_df.to_excel(writer, index=False, sheet_name='Envio')
                
            st.download_button(
                label="✅ Baixar Planilha Pronta",
                data=buffer,
                file_name="Enderecos_Corrigidos.xlsx",
                mime="application/vnd.ms-excel",
                type="primary"
            )

    except Exception as e:
        st.error(f"Erro no arquivo: {e}")
