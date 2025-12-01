FROM python:3.9-slim

# 1. Instala compiladores (Resolve o erro do Pandas e erro de arquitetura)
RUN apt-get update && apt-get install -y \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 2. Copia e instala as bibliotecas
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 3. Copia o resto do código
COPY . .

# 4. Configura a porta
EXPOSE 8501

# 5. Comando de inicialização
ENTRYPOINT ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]
