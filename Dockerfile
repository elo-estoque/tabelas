# Usa a imagem oficial completa (Resolve dependências e arquitetura automaticamente)
FROM python:3.9

# Define o diretório de trabalho
WORKDIR /app

# Copia e instala as dependências
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copia o resto dos arquivos
COPY . .

# Expõe a porta correta
EXPOSE 8501

# Comando de execução (Usando CMD que é mais seguro contra erros de formato)
CMD ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]
