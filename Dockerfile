FROM python:3.12

WORKDIR /app

COPY requirements/requirements.txt /app/

RUN pip install --no-cache-dir -r requirements.txt

RUN apt-get update && apt-get install -y python3-tk

RUN apt-get update && apt-get install -y xauth x11-apps

COPY app/ /app/

CMD ["python", "main.py"]

