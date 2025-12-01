import streamlit as st
import pandas as pd
import re
import io
import requests

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Sanitizador de Endereços", layout="wide")

st.markdown("## 📦 Sanitizador de Endereços (Padrão Correios)")
st.info("Suba a planilha, verifique os dados e baixe o arquivo pronto para gerar etiquetas.")

# --- FUNÇÕES DE LIMPEZA ---

def extrair_cep(texto):
    # Procura CEP no formato XXXXX-XXX ou XXXXXXXX
    match = re.search(r'\b\d{5}-?\d{3}\b', str(texto))
    return match.group(0).replace('-', '') if match else ""

def tentar_extrair_numero(texto):
    # Tenta pegar números isolados no fim da string ou após vírgula
    # Ex: "Rua tal, 123" -> 123
    if not isinstance(texto, str): return ""
    match = re.search(r'(?:,|^)\s*(\d+\w?)\s*$', texto) # Padrão simples
    if match:
        return match.group(1)
    
    # Tentativa 2: Procura "n 123" ou "num 123"
    match_n = re.search(r'(?:nº|n|num)\.?\s*(\d+)', texto, re.IGNORECASE)
    if match_n:
        return match_n.group(1)
        
    return ""

def limpar_logradouro(texto, numero_encontrado):
    # Remove o número do texto original para deixar só a rua
    if not isinstance(texto, str): return ""
    novo_texto = texto
    if numero_encontrado:
        novo_texto = novo_texto.replace(numero_encontrado, '').strip()
    
    # Remove sufixos comuns de fim de linha
    novo_texto = re.sub(r'[, -]+$', '', novo_texto)
    return novo_texto

def processar_planilha(df, col_endereco):
    df = df.copy()
    
    # 1. Garante que as colunas existam
    df['CEP_Estimado'] = df[col_endereco].apply(extrair_cep)
    df['Numero_Estimado'] = df[col_endereco].apply(tentar_extrair_numero)
    
    # Tenta limpar o logradouro removendo o número
    df['Logradouro_Estimado'] = df.apply(
        lambda row: limpar_logradouro(row[col_endereco], row['Numero_Estimado']), axis=1
    )
    
    df['Bairro_Estimado'] = "" 
    df['Complemento_Estimado'] = ""
    
    return df

# --- INTERFACE ---

uploaded_file = st.file_uploader("Arraste seu Excel aqui (.xlsx)", type=['xlsx'])

if uploaded_file:
    # Ler arquivo
    try:
        df = pd.read_excel(uploaded_file)
        
        # Seleção da coluna de endereço
        colunas = list(df.columns)
        st.write("### 1. Selecione a coluna que tem o endereço completo:")
        
        # Tenta adivinhar qual é a coluna de endereço (se tiver "endereço" no nome)
        index_padrao = 0
        for i, col in enumerate(colunas):
            if "endereço" in col.lower() or "endereco" in col.lower():
                index_padrao = i
                break
                
        col_alvo = st.selectbox("Coluna de Endereço:", colunas, index=index_padrao)

        if st.button("Processar Dados"):
            with st.spinner('Processando endereços...'):
                df_processado = processar_planilha(df, col_alvo)
            
            st.success("Processamento concluído! Valide os dados abaixo.")
            st.warning("⚠️ A coluna 'Endereço Original' está bloqueada para manter a integridade.")

            # --- CONFIGURAÇÃO DA TABELA EDITÁVEL ---
            column_config = {
                col_alvo: st.column_config.TextColumn(
                    "Endereço Original (Bloqueado)",
                    disabled=True, # <--- BLOQUEIO DE SEGURANÇA
                    width="medium"
                ),
                "Logradouro_Estimado": st.column_config.TextColumn("Logradouro (Rua/Av)", required=True),
                "Numero_Estimado": st.column_config.TextColumn("Número", required=True),
                "Bairro_Estimado": st.column_config.TextColumn("Bairro"),
                "CEP_Estimado": st.column_config.TextColumn("CEP", required=True),
                "Complemento_Estimado": st.column_config.TextColumn("Complemento"),
            }

            # Mostra a tabela para edição
            edited_df = st.data_editor(
                df_processado,
                column_config=column_config,
                num_rows="dynamic",
                use_container_width=True,
                height=600
            )

            # --- EXPORTAÇÃO ---
            st.write("### 3. Finalizar")
            
            # Botão de Download
            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
                edited_df.to_excel(writer, index=False, sheet_name='Etiquetas')
                
            st.download_button(
                label="⬇️ Baixar Planilha para Importação (Lote)",
                data=buffer,
                file_name="Lote_Correios_Pronto.xlsx",
                mime="application/vnd.ms-excel",
                type="primary"
            )

    except Exception as e:
        st.error(f"Erro ao ler arquivo: {e}")
