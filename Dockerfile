FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .

RUN pip install --upgrade pip

RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Copy and set permissions on entrypoint script
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENV DJANGO_SETTINGS_MODULE=insighta_backend.settings
#ENV SECRET_KEY=dummy-secret-key-for-build

ENTRYPOINT ["/entrypoint.sh"]

#RUN python manage.py collectstatic --noinput

EXPOSE 8000

CMD ["gunicorn", "insighta_backend.wsgi:application", "--bind", "0.0.0.0:8000"]