# 1. Escolhe a imagem base (Python leve)
FROM python:3.11-slim

# 2. Define o diretório de trabalho
WORKDIR /app

# 3. Define a variável de ambiente para a porta
ENV PORT 8000

# 4. Instala dependências do sistema operacional necessárias
RUN apt-get update && apt-get install -y gcc libffi-dev

# 5. Instala as bibliotecas Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 6. Copia o código da API
COPY . .

# 7. O COMANDO CORRETO (AQUI ESTAVA O ERRO)
# Não use "gunicorn" puro. Use "uvicorn" para garantir compatibilidade com FastAPI.
CMD ["uvicorn", "normalizador_api:app", "--host", "0.0.0.0", "--port", "8000"]
