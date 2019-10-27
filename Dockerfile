FROM python:3.6-stretch
ADD sources/sources.list /etc/apt/
RUN apt-get update
RUN apt-get install -y curl git wget zip unzip
RUN cat /etc/os-release
WORKDIR /usr/local
RUN git clone https://github.com/eclogue/eclogue.git
WORKDIR /usr/local/eclogue
RUN pip install pipenv
ENV PIPENV_VENV_IN_PROJECT 1
ENV ENV docker
RUN git checkout develop
RUN pipenv update
RUN pipenv run python manage.py migrate bootstrap
ENTRYPOINT pipenv run python manage.py start
