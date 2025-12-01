import streamlit as st
import pandas as pd
import re
import io

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Sanitizador Elo Brindes", layout="wide", page_icon="🚚")

st.markdown("## 🚚 Sanitizador de Endereços (Inteligente)")

# --- FUNÇÕES DE LIMPEZA AVANÇADA ---

def extrair_cep(texto):
    # Procura CEP (XXXXX-XXX ou XXXXXXXX)
    match = re.search(r'\b\d{5}-?\d{3}\b', str(texto))
    return match.group(0).replace('-', '') if match else None

def extrair_numero_inteligente(texto):
    if not isinstance(texto, str): return ""
    texto = texto.upper().strip()
    
    # 1. Prioridade: Procura "S/N" ou "SEM NUMERO"
    if re.search(r'\b(S/N|SN|S\.N|SEM N|S-N)\b', texto):
        return "S/N"

    # 2. Prioridade: Procura número entre vírgulas ou hífens (O SEU CASO)
    # Ex: "Av Brasilia, 177 - 1 Piso" -> Pega o 177
    # Explicação regex: Procura virgula, espaço, digitos, espaço, e depois traço ou virgula
    match_meio = re.search(r',\s*(\d+)\s*(?:-|,|;)', texto)
    if match_meio:
        return match_meio.group(1)

    # 3. Prioridade: Procura "nº 123"
    match_n = re.search(r'(?:nº|n|num)\.?\s*(\d+)', texto)
    if match_n:
        return match_n.group(1)
    
    # 4. Prioridade: Número solto logo após uma vírgula (Ex: Rua X, 123)
    match_virgula = re.search(r',\s*(\d+)', texto)
    if match_virgula:
        return match_virgula.group(1)

    # 5. Última tentativa: Número no final da string
    match_fim = re.search(r'\s(\d+)$', texto)
    if match_fim:
        return match_fim.group(1)
        
    return "" # Não achou nada

def gerar_status(cep, numero):
    status = []
    # Lógica de aviso
    if not cep:
        status.append("🟢 SEM CEP") # Seu pedido: Verde para sem CEP
    
    if not numero:
        status.append("⚠️ SEM NÚMERO")
    elif numero == "S/N":
        status.append("⚪ S/N")
        
    if not status:
        return "✅ OK"
    return " | ".join(status)

def processar_planilha(df, col_endereco):
    df = df.copy()
    
    # Extrações
    df['CEP_Final'] = df[col_endereco].apply(extrair_cep)
    df['Numero_Final'] = df[col_endereco].apply(extrair_numero_inteligente)
    
    # Limpa o logradouro (Tenta tirar o CEP e o número do texto original para ficar limpo)
    def limpar_texto(row):
        txt = str(row[col_endereco])
        # Remove CEP
        if row['CEP_Final']:
            txt = txt.replace(row['CEP_Final'], '').replace(row['CEP_Final'][:5]+'-'+row['CEP_Final'][5:], '')
        # Remove Número (se achou)
        if row['Numero_Final'] and row['Numero_Final'] != "S/N":
            # Remove apenas se o número estiver isolado para não apagar parte de outra coisa
            txt = re.sub(rf'\b{row["Numero_Final"]}\b', '', txt)
        return txt.strip(' ,;-')

    df['Logradouro_Final'] = df.apply(limpar_texto, axis=1)
    df['Bairro_Final'] = "" # Bairro é difícil pegar sem API, deixa pro humano ou API futura
    
    # Gera Coluna de Status Visual
    df['STATUS_SISTEMA'] = df.apply(lambda x: gerar_status(x['CEP_Final'], x['Numero_Final']), axis=1)
    
    # Ordena: Quem tem problema aparece primeiro!
    df = df.sort_values(by=['STATUS_SISTEMA'], ascending=False)
    
    return df

# --- INTERFACE ---

uploaded_file = st.file_uploader("📂 Arraste o Excel aqui", type=['xlsx', 'csv'])

if uploaded_file:
    try:
        if uploaded_file.name.endswith('.csv'):
            df = pd.read_csv(uploaded_file)
        else:
            df = pd.read_excel(uploaded_file)
            
        st.write("### 1. Identifique a coluna do Endereço Completo")
        
        # Tenta achar a coluna sozinho
        colunas = list(df.columns)
        index_padrao = 0
        for i, col in enumerate(colunas):
            if "endereço" in col.lower() or "endereco" in col.lower():
                index_padrao = i
                break
        
        col_alvo = st.selectbox("Selecione a coluna:", colunas, index=index_padrao)

        if st.button("🚀 Processar Endereços"):
            with st.spinner('O Robô está lendo...'):
                df_processado = processar_planilha(df, col_alvo)
            
            st.success("Pronto! Edite abaixo. (Linhas com problemas aparecem no topo)")
            
            # --- TABELA EDITÁVEL ---
            column_config = {
                "STATUS_SISTEMA": st.column_config.TextColumn(
                    "⚠️ Avisos do Robô",
                    help="Verde: Sem CEP | Cinza: S/N | Amarelo: Falta Número",
                    width="medium",
                    disabled=True
                ),
                col_alvo: st.column_config.TextColumn("Endereço Original (Bloqueado)", disabled=True, width="large"),
                "Logradouro_Final": st.column_config.TextColumn("Rua/Logradouro", width="large"),
                "Numero_Final": st.column_config.TextColumn("Número", width="small"),
                "CEP_Final": st.column_config.TextColumn("CEP", width="medium"),
                "Bairro_Final": st.column_config.TextColumn("Bairro", width="medium"),
            }
            
            # Colunas que queremos mostrar primeiro
            cols_order = ["STATUS_SISTEMA", col_alvo, "Logradouro_Final", "Numero_Final", "CEP_Final", "Bairro_Final"]
            # Adiciona o resto das colunas originais no fim, caso precise
            cols_extra = [c for c in df.columns if c not in cols_order]
            
            edited_df = st.data_editor(
                df_processado[cols_order + cols_extra],
                column_config=column_config,
                num_rows="dynamic",
                use_container_width=True,
                height=800
            )

            # --- DOWNLOAD ---
            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
                edited_df.to_excel(writer, index=False, sheet_name='Envio')
                
            st.download_button(
                label="💾 Baixar Planilha Pronta",
                data=buffer,
                file_name="Enderecos_Corrigidos.xlsx",
                mime="application/vnd.ms-excel",
                type="primary"
            )

    except Exception as e:
        st.error(f"Erro: {e}")
