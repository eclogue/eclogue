FROM python:3.7.4-stretch
ADD sources/sources.list /etc/apt/
RUN apt-get update
RUN apt-get install -y curl git wget zip unzip
RUN cat /etc/os-release
WORKDIR /usr/local
RUN git clone https://github.com/eclogue/eclogue.git
WORKDIR /usr/local/eclogue
RUN pip install pipenv
ENV PIPENV_VENV_IN_PROJECT 1
RUN pipenv install
RUN pipen run python manage.py migrate bootstrap
ENTRYPOINT pipenv run python manage.py start
