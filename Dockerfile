FROM python:3.6-stretch
ADD sources/sources.list /etc/apt/
RUN apt-get update
RUN apt-get install -y curl git wget zip unzip
RUN cat /etc/os-release
WORKDIR /usr/local
RUN git clone https://github.com/eclogue/eclogue.git
WORKDIR /usr/local/eclogue
RUN pip install pipenv -i http://mirrors.aliyun.com/pypi/simple
ENV PIPENV_VENV_IN_PROJECT 1
RUN git checkout develop && git pull origin develop
RUN pipenv update -v
COPY config/development.yaml config/
RUN pipenv run python manage.py migrate bootstrap --username=admin --password=eclogue
EXPOSE 5000
ENTRYPOINT pipenv run python manage.py start
