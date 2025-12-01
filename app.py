import streamlit as st
import pandas as pd
import re
import io

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Sanitizador Elo Brindes", layout="wide", page_icon="🚚")

st.markdown("## 🚚 Sanitizador de Endereços (CEP Blindado)")

# --- FUNÇÕES DE LIMPEZA AVANÇADA ---

def extrair_cep_bruto(texto):
    if not isinstance(texto, str): return None
    texto_limpo = " ".join(texto.split()) # Remove espaços duplos e quebras de linha
    
    # ESTRATÉGIA 1 (PRIORIDADE): Procura a palavra "CEP" seguida de números
    # Ex: "CEP: 12.345-678" ou "CEP 12345678"
    match_com_palavra = re.search(r'(?:CEP|C\.E\.P)\s*[:.-]?\s*(\d{2}\.?\d{3}[- ]?\d{3})', texto_limpo, re.IGNORECASE)
    if match_com_palavra:
        return re.sub(r'\D', '', match_com_palavra.group(1)) # Retorna só números
        
    # ESTRATÉGIA 2 (VARREDURA): Procura qualquer formato de CEP solto ou colado
    # Aceita: 12.345-678, 12345-678, 12345678
    # O (?<!\d) garante que não pegue parte de um CNPJ ou telefone longo
    match_generico = re.search(r'(?<!\d)(\d{2}\.?\d{3}[- ]?\d{3})(?!\d)', texto_limpo)
    if match_generico:
        return re.sub(r'\D', '', match_generico.group(1))
        
    return None

def extrair_numero_inteligente(texto):
    if not isinstance(texto, str): return ""
    texto_upper = texto.upper().strip()
    
    # 1. PRIORIDADE: Procura S/N explicitamente
    if re.search(r'\b(S/N|SN|S\.N|SEM N|S-N)\b', texto_upper):
        return "S/N"

    # 2. Hífen duplo (Ex: RUA X - 188 - CENTRO)
    match_hifen = re.search(r'\s[-–]\s*(\d+)\s*(?:[-–]|$)', texto_upper)
    if match_hifen:
        return match_hifen.group(1)

    # 3. Padrão vírgula (Ex: Av X, 177)
    match_meio = re.search(r',\s*(\d+)\s*(?:-|,|;|/|AP|BL)', texto_upper)
    if match_meio:
        return match_meio.group(1)

    # 4. Prefixo "Nº"
    match_n = re.search(r'(?:nº|n|num)\.?\s*(\d+)', texto_upper, re.IGNORECASE)
    if match_n:
        return match_n.group(1)
    
    # 5. Número logo após vírgula
    match_virgula = re.search(r',\s*(\d+)', texto_upper)
    if match_virgula:
        return match_virgula.group(1)

    # 6. Última tentativa: Fim da linha
    match_fim = re.search(r'\s(\d+)$', texto_upper)
    if match_fim:
        return match_fim.group(1)
        
    return "" 

def gerar_status(cep, numero):
    status = []
    # SEU PEDIDO: Marcar bem visível quem não tem CEP
    if not cep:
        status.append("🔴 SEM CEP") 
    
    if not numero:
        status.append("⚠️ SEM NÚMERO")
    elif numero == "S/N":
        status.append("⚪ S/N")
        
    if not status:
        return "✅ OK"
    return " ".join(status)

def processar_planilha(df, col_endereco):
    df = df.copy()
    
    # Salva índice para reordenar no final
    df['_Index_Original'] = df.index
    
    # Extrações
    df['CEP_Final'] = df[col_endereco].apply(extrair_cep_bruto)
    df['Numero_Final'] = df[col_endereco].apply(extrair_numero_inteligente)
    
    # Limpa o Logradouro
    def limpar_texto(row):
        txt = str(row[col_endereco])
        cep = row['CEP_Final']
        
        # Remove CEP do texto (formatado ou limpo)
        if cep:
            txt = re.sub(rf'{cep[:5]}.?{cep[5:]}', '', txt) 
            txt = re.sub(rf'{cep}', '', txt)
            
        # Remove Número (exceto S/N)
        num = row['Numero_Final']
        if num and num != "S/N":
            txt = re.sub(rf'\b{num}\b', '', txt)
            
        # Limpezas extras
        txt = re.sub(r'\bCEP\b[:.]?', '', txt, flags=re.IGNORECASE) # Tira palavra CEP
        txt = re.sub(r'\s[-–]\s*$', '', txt) # Tira hifens soltos no final
        
        return txt.strip(' ,;-.')

    df['Logradouro_Final'] = df.apply(limpar_texto, axis=1)
    df['Bairro_Final'] = "" 
    
    # Gera Status
    df['STATUS_SISTEMA'] = df.apply(lambda x: gerar_status(x['CEP_Final'], x['Numero_Final']), axis=1)
    
    # Ordena: PROBLEMAS PRIMEIRO (para você corrigir rápido)
    df = df.sort_values(by=['STATUS_SISTEMA'], ascending=False)
    
    return df

# --- INTERFACE ---

uploaded_file = st.file_uploader("📂 Importar Planilha (.xlsx)", type=['xlsx'])

if uploaded_file:
    try:
        df = pd.read_excel(uploaded_file)
        
        # Adivinha a coluna
        colunas = list(df.columns)
        index_padrao = 0
        for i, col in enumerate(colunas):
            if "endereço" in col.lower() or "endereco" in col.lower():
                index_padrao = i
                break
        
        st.info("👇 Confirme a coluna do Endereço Completo:")
        col_alvo = st.selectbox("", colunas, index=index_padrao)

        if st.button("🚀 Processar"):
            with st.spinner('O Robô está separando CEPs e Números...'):
                df_processado = processar_planilha(df, col_alvo)
            
            st.success("Feito! Linhas com ERRO aparecem no topo.")
            
            # --- TABELA DE EDIÇÃO ---
            column_config = {
                "STATUS_SISTEMA": st.column_config.TextColumn("⚠️ Alertas", width="medium", disabled=True),
                col_alvo: st.column_config.TextColumn("Endereço Original (Bloqueado)", width="large", disabled=True),
                "Logradouro_Final": st.column_config.TextColumn("Rua/Logradouro", width="large"),
                "Numero_Final": st.column_config.TextColumn("Número", width="small"),
                "CEP_Final": st.column_config.TextColumn("CEP", width="medium"),
                "Bairro_Final": st.column_config.TextColumn("Bairro", width="medium"),
                "_Index_Original": st.column_config.Column(hidden=True)
            }
            
            # Mostra o Status primeiro
            cols_order = ["STATUS_SISTEMA", col_alvo, "Logradouro_Final", "Numero_Final", "CEP_Final", "Bairro_Final"]
            cols_rest = [c for c in df.columns if c not in cols_order and c != "_Index_Original"]
            
            edited_df = st.data_editor(
                df_processado[cols_order + cols_rest + ["_Index_Original"]],
                column_config=column_config,
                num_rows="dynamic",
                use_container_width=True,
                height=700
            )

            # --- BOTÕES DE DOWNLOAD ---
            st.write("---")
            st.subheader("💾 Exportar")
            
            col1, col2 = st.columns(2)
            
            # BOTÃO 1: Baixa igual está na tela (Erros no topo)
            buffer1 = io.BytesIO()
            with pd.ExcelWriter(buffer1, engine='xlsxwriter') as writer:
                df_export1 = edited_df.drop(columns=['_Index_Original'])
                df_export1.to_excel(writer, index=False, sheet_name='Triagem')
                
            with col1:
                st.download_button(
                    label="⬇️ Baixar Planilha de TRIAGEM (Erros no Topo)",
                    data=buffer1,
                    file_name="Enderecos_Triagem.xlsx",
                    mime="application/vnd.ms-excel",
                )

            # BOTÃO 2: Baixa na ordem original (Para sistema Correios)
            buffer2 = io.BytesIO()
            with pd.ExcelWriter(buffer2, engine='xlsxwriter') as writer:
                # Reordena usando o ID salvo
                df_export2 = edited_df.sort_values(by='_Index_Original')
                df_export2 = df_export2.drop(columns=['_Index_Original'])
                df_export2.to_excel(writer, index=False, sheet_name='Envio')
                
            with col2:
                st.download_button(
                    label="✅ Baixar Planilha FINAL (Ordem Original)",
                    data=buffer2,
                    file_name="Lote_Correios_Final.xlsx",
                    mime="application/vnd.ms-excel",
                    type="primary"
                )

    except Exception as e:
        st.error(f"Erro ao processar: {e}")
