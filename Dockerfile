FROM mcr.microsoft.com/playwright/python:v1.52.0

WORKDIR /app

ENV PLAYWRIGHT_BROWSERS_PATH=/ms-playwright

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
# Pre-download wordfreq language data
RUN python -c "import wordfreq; wordfreq.top_n_list('en', 100)" 2>/dev/null || true

COPY . .

RUN mkdir -p data reports

CMD ["python", "run.py"]
