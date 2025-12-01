FROM python:3.9-slim

WORKDIR /app

# Instala as dependências
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copia o código do app
COPY . .

# Expõe a porta do Streamlit
EXPOSE 8501

# Comando para rodar
ENTRYPOINT ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]
