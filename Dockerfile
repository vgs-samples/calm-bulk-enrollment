FROM python:3.9.9-slim
ADD . /app
WORKDIR /app
RUN pip install --upgrade pip && pip install -r requirements.txt

CMD ["python", "main.py"]