FROM dtcooper/raspberrypi-os:python3.11

WORKDIR /app

COPY requirements.txt .
RUN pip install fastapi sqlalchemy boto3 python-dotenv uvicorn "pydantic[email]" rpi-lgpio

COPY . .

CMD ["python", "api.py"]