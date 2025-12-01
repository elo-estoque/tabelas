import streamlit as st
import pandas as pd
import re
import io

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Sanitizador Elo Brindes", layout="wide", page_icon="🚚")

st.markdown("## 🚚 Sanitizador de Endereços (CEP + Layout Final)")

# --- FUNÇÕES DE EXTRAÇÃO (O ROBÔ BLINDADO) ---

def extrair_cep_bruto(texto):
    if not isinstance(texto, str): return None
    
    # 1. LIMPEZA DE LIXO (O Pulo do Gato para seu erro)
    # Remove aspas, aspas simples e espaços das pontas
    texto_limpo = texto.replace('"', '').replace("'", "").strip()
    
    # 2. PROCURA 1: Padrão Formatado (Com traço)
    # Ex: 12.345-678 ou 12345-678
    match_formatado = re.search(r'\d{2}\.?\d{3}-\d{3}', texto_limpo)
    if match_formatado:
         return re.sub(r'\D', '', match_formatado.group(0))
    
    # 3. PROCURA 2: Palavra "CEP" seguida de números
    match_palavra = re.search(r'(?:CEP|C\.E\.P).{0,5}?(\d{8})', re.sub(r'[-.]', '', texto_limpo), re.IGNORECASE)
    if match_palavra:
        return match_palavra.group(1)

    # 4. PROCURA 3 (NUCLEAR): Qualquer sequência de 8 dígitos SOLTOS
    # Procura por exatos 8 digitos que não sejam parte de um numero maior (tipo CNPJ)
    # O regex abaixo procura 8 digitos isolados ou no fim da linha
    match_8_digitos = re.search(r'(?<!\d)(\d{8})(?!\d)', texto_limpo)
    if match_8_digitos:
        return match_8_digitos.group(1)
        
    return None

def extrair_numero_inteligente(texto):
    if not isinstance(texto, str): return ""
    texto_upper = texto.upper().replace('"', '').strip() # Limpa aspas aqui tb
    
    if re.search(r'\b(S/N|SN|S\.N|SEM N|S-N)\b', texto_upper): return "S/N"
    
    match_hifen = re.search(r'\s[-–]\s*(\d+)\s*(?:[-–]|$)', texto_upper)
    if match_hifen: return match_hifen.group(1)

    match_meio = re.search(r',\s*(\d+)\s*(?:-|,|;|/|AP|BL)', texto_upper)
    if match_meio: return match_meio.group(1)

    match_n = re.search(r'(?:nº|n|num)\.?\s*(\d+)', texto_upper, re.IGNORECASE)
    if match_n: return match_n.group(1)
    
    match_virgula = re.search(r',\s*(\d+)', texto_upper)
    if match_virgula: return match_virgula.group(1)

    match_fim = re.search(r'\s(\d+)$', texto_upper)
    if match_fim: return match_fim.group(1)
        
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
    
    # 1. Cria ID Sequencial (ID_1, ID_2...)
    df['ID_Personalizado'] = [f'ID_{i+1}' for i in range(len(df))]
    
    # 2. Mapeia colunas
    df['Nome_Final'] = df[col_map['nome']] if col_map['nome'] else ""
    df['Cidade_Final'] = df[col_map['cidade']] if col_map['cidade'] else ""
    df['UF_Final'] = df[col_map['uf']] if col_map['uf'] else ""
    df['Regiao_Final'] = df[col_map['regiao']] if col_map['regiao'] else ""
    df['Bairro_Final'] = df[col_map['bairro']] if col_map['bairro'] else "" 
    
    col_endereco = col_map['endereco']
    
    # 3. Extrações
    df['CEP_Final'] = df[col_endereco].apply(extrair_cep_bruto)
    df['Numero_Final'] = df[col_endereco].apply(extrair_numero_inteligente)
    
    # 4. Limpeza do Logradouro
    def limpar_texto(row):
        txt = str(row[col_endereco]).replace('"', '').replace("'", "") # Tira aspas
        cep = row['CEP_Final']
        num = row['Numero_Final']
        
        if cep:
            txt = re.sub(rf'{cep[:5]}.?{cep[5:]}', '', txt) 
            txt = re.sub(rf'{cep}', '', txt)
            
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
    
    # Ordena por erro
    df = df.sort_values(by=['STATUS_SISTEMA'], ascending=False)
    
    return df

# --- INTERFACE ---

uploaded_file = st.file_uploader("📂 Importar Planilha (.xlsx)", type=['xlsx'])

if uploaded_file:
    try:
        df = pd.read_excel(uploaded_file)
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
            with st.spinner('Lendo dados...'):
                df_processado = processar_planilha(df, col_map)
            
            st.success("Feito!")
            
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
