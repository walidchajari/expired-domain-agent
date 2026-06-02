FROM mcr.microsoft.com/playwright/python:v1.52.0

WORKDIR /app

ENV PLAYWRIGHT_BROWSERS_PATH=/ms-playwright

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p data reports

CMD ["python", "run.py"]
