import streamlit as st
import pandas as pd
import re
import io

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Sanitizador Elo Brindes", layout="wide", page_icon="🚚")

st.markdown("## 🚚 Sanitizador de Endereços (Layout Personalizado)")

# --- FUNÇÕES DE EXTRAÇÃO (O ROBÔ BLINDADO) ---

def extrair_cep_bruto(texto):
    if not isinstance(texto, str): return None
    texto_limpo = " ".join(texto.split())
    
    # 1. Procura CEP com palavra chave
    match_com_palavra = re.search(r'(?:CEP|C\.E\.P)\s*[:.-]?\s*(\d{2}\.?\d{3}[- ]?\d{3})', texto_limpo, re.IGNORECASE)
    if match_com_palavra:
        return re.sub(r'\D', '', match_com_palavra.group(1))
        
    # 2. Procura CEP solto
    match_generico = re.search(r'(?<!\d)(\d{2}\.?\d{3}[- ]?\d{3})(?!\d)', texto_limpo)
    if match_generico:
        return re.sub(r'\D', '', match_generico.group(1))
    return None

def extrair_numero_inteligente(texto):
    if not isinstance(texto, str): return ""
    texto_upper = texto.upper().strip()
    
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
    
    # 2. Mapeia as colunas originais para as colunas padrão
    # Se o usuário não selecionou uma coluna (None), cria em branco
    df['Nome_Final'] = df[col_map['nome']] if col_map['nome'] else ""
    df['Cidade_Final'] = df[col_map['cidade']] if col_map['cidade'] else ""
    df['UF_Final'] = df[col_map['uf']] if col_map['uf'] else ""
    df['Regiao_Final'] = df[col_map['regiao']] if col_map['regiao'] else ""
    df['Bairro_Final'] = df[col_map['bairro']] if col_map['bairro'] else "" # Tenta pegar do original se tiver
    
    col_endereco = col_map['endereco']
    
    # 3. Extrações do Robô
    df['CEP_Final'] = df[col_endereco].apply(extrair_cep_bruto)
    df['Numero_Final'] = df[col_endereco].apply(extrair_numero_inteligente)
    
    # 4. Limpeza do Logradouro
    def limpar_texto(row):
        txt = str(row[col_endereco])
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
    
    # 5. Colunas Extras (Em branco para preencher)
    df['Complemento_Final'] = ""
    df['Aos_Cuidados_Final'] = ""
    
    # 6. Status
    df['STATUS_SISTEMA'] = df.apply(lambda x: gerar_status(x['CEP_Final'], x['Numero_Final']), axis=1)
    
    # Ordena por erro para facilitar a edição
    df = df.sort_values(by=['STATUS_SISTEMA'], ascending=False)
    
    return df

# --- INTERFACE ---

uploaded_file = st.file_uploader("📂 Importar Planilha (.xlsx)", type=['xlsx'])

if uploaded_file:
    try:
        df = pd.read_excel(uploaded_file)
        cols = list(df.columns)
        
        st.write("### ⚙️ Mapeamento de Colunas")
        st.info("O sistema tentou adivinhar as colunas. Corrija se necessário:")
        
        col1, col2, col3 = st.columns(3)
        
        # Funcao auxiliar para achar coluna pelo nome aproximado
        def achar_col(termos):
            for i, c in enumerate(cols):
                if any(t in c.lower() for t in termos): return i
            return 0 # Default

        with col1:
            c_end = st.selectbox("Endereço Completo *", cols, index=achar_col(['endereço', 'endereco']))
            c_nome = st.selectbox("Nome (Clube/Loja)", ["(Criar em Branco)"] + cols, index=achar_col(['nome', 'clube', 'loja']) + 1)
        
        with col2:
            c_cidade = st.selectbox("Cidade", ["(Criar em Branco)"] + cols, index=achar_col(['cidade', 'city']) + 1)
            c_uf = st.selectbox("UF (Estado)", ["(Criar em Branco)"] + cols, index=achar_col(['uf', 'estado']) + 1)
            
        with col3:
            c_regiao = st.selectbox("Região", ["(Criar em Branco)"] + cols, index=achar_col(['regiao', 'região']) + 1)
            c_bairro = st.selectbox("Bairro (Se existir)", ["(Criar em Branco)"] + cols, index=achar_col(['bairro']) + 1)

        # Mapa de colunas selecionadas
        col_map = {
            'endereco': c_end,
            'nome': c_nome if c_nome != "(Criar em Branco)" else None,
            'cidade': c_cidade if c_cidade != "(Criar em Branco)" else None,
            'uf': c_uf if c_uf != "(Criar em Branco)" else None,
            'regiao': c_regiao if c_regiao != "(Criar em Branco)" else None,
            'bairro': c_bairro if c_bairro != "(Criar em Branco)" else None,
        }

        if st.button("🚀 Gerar Planilha Organizada"):
            with st.spinner('Organizando colunas e gerando IDs...'):
                df_processado = processar_planilha(df, col_map)
            
            st.success("Tudo pronto! Verifique e baixe.")
            
            # --- DEFINIÇÃO DA ORDEM FINAL ---
            # Essa é a lista que define a ordem exata das colunas na tela e no download
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
            
            # Configuração visual da tabela
            column_config = {
                "STATUS_SISTEMA": st.column_config.TextColumn("⚠️ Status", width="medium", disabled=True),
                "ID_Personalizado": st.column_config.TextColumn("ID", width="small", disabled=True),
                c_end: st.column_config.TextColumn("Endereço Original", width="large", disabled=True),
                "Nome_Final": st.column_config.TextColumn("Nome (Clube)", width="medium"),
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
            
            # Mostra STATUS primeiro para edição, depois segue a ordem pedida
            cols_to_show = ["STATUS_SISTEMA"] + ordem_final_colunas
            
            edited_df = st.data_editor(
                df_processado[cols_to_show],
                column_config=column_config,
                num_rows="dynamic",
                use_container_width=True,
                height=700
            )

            # --- DOWNLOAD ---
            st.write("---")
            st.subheader("💾 Baixar Planilha Final")
            
            col1, col2 = st.columns(2)
            
            # Botão 1: Baixa com Erros no topo (Status incluso)
            buffer1 = io.BytesIO()
            with pd.ExcelWriter(buffer1, engine='xlsxwriter') as writer:
                edited_df.to_excel(writer, index=False, sheet_name='Triagem')
            with col1:
                st.download_button("⬇️ Baixar Tabela de Triagem (Com Status)", buffer1, "Triagem.xlsx")

            # Botão 2: Baixa LIMPO e na ORDEM DO ID (Perfeito para importação)
            buffer2 = io.BytesIO()
            with pd.ExcelWriter(buffer2, engine='xlsxwriter') as writer:
                # 1. Reordena pelo ID (extraindo o numero do texto "ID_1")
                df_final = edited_df.copy()
                # Cria coluna temporaria de numero para ordenar
                df_final['__sort_id'] = df_final['ID_Personalizado'].apply(lambda x: int(x.split('_')[1]))
                df_final = df_final.sort_values('__sort_id')
                
                # 2. Seleciona APENAS as colunas pedidas na ordem pedida (sem status)
                df_final = df_final[ordem_final_colunas]
                
                # 3. Renomeia para ficar bonito no Excel final
                df_final.columns = [
                    "ID", "Endereço Original", "Nome (Clube)", "CEP", "Logradouro", 
                    "N°", "Complemento", "Bairro", "Cidade", "UF", "Região", "Aos Cuidados"
                ]
                
                df_final.to_excel(writer, index=False, sheet_name='Envio')
                
            with col2:
                st.download_button(
                    label="✅ Baixar Planilha FINAL (Ordem Correta ID_1...)",
                    data=buffer2,
                    file_name="Lote_Final_Correios.xlsx",
                    mime="application/vnd.ms-excel",
                    type="primary"
                )

    except Exception as e:
        st.error(f"Erro ao processar: {e}")
