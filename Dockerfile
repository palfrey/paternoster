FROM python:3.11
WORKDIR /app
RUN wget https://raw.githubusercontent.com/vishnubob/wait-for-it/81b1373f17855a4dc21156cfe1694c31d7d1792e/wait-for-it.sh -O /usr/bin/wait-for-it && chmod +x /usr/bin/wait-for-it
COPY requirements.txt /app
RUN pip install -r requirements.txt
COPY . /app
CMD uwsgi debug-uwsgi.ini