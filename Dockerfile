FROM tiangolo/uvicorn-gunicorn-fastapi:python3.12


COPY ./requirements.txt /tmp/
RUN pip install -U pip &&        pip install -r /tmp/requirements.txt
COPY ./ /app
WORKDIR /app
RUN pip install .
ENV APP_MODULE=splash_userservice.api:app
# CMD ["uvicorn", "splash_userservice.api:app", "--host", "0.0.0.0", "--port", "80"]