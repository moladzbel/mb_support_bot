FROM python:3.10-alpine

ENV IS_DOCKER=True
WORKDIR /bot

ADD requirements.txt /bot/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

ADD alembic/ /bot/alembic/
ADD alembic.ini /bot/alembic.ini
ADD run.py /bot/run.py
ADD support_bot/ /bot/support_bot/

CMD ["python", "run.py"]
