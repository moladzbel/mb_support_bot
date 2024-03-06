FROM python:3.10-alpine

ENV IS_DOCKER=True

ADD requirements.txt /requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

WORKDIR /code
CMD ["sh", "-c", "./run.py migrate; ./run.py"]
