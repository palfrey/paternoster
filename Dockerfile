FROM python:3.9.2
WORKDIR /app
COPY requirements.txt /app
RUN pip install -r requirements.txt
COPY . /app
CMD uwsgi debug-uwsgi.ini