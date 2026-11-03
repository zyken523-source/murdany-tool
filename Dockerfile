FROM python:3.9-slim
WORKDIR /app
COPY . .
RUN pip install -r requirements.txt
EXPOSE 7860
CMD ["uvicorn", "sipel:app", "--host", "0.0.0.0", "--port", "7860"]
