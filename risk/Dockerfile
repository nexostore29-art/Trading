FROM python:3.11-slim
WORKDIR /trading
RUN pip install --no-cache-dir requests==2.32.* ccxt==4.5.*
COPY risk /trading/risk
CMD ["python", "risk/watchdog.py"]
