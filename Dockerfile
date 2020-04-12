FROM python:3.6-stretch
ADD storage/sources /etc/apt/
RUN apt-get update
RUN apt-get install -y curl git wget zip unzip
RUN cat /etc/os-release
WORKDIR /usr/local
RUN git clone https://github.com/eclogue/eclogue.git
WORKDIR /usr/local/eclogue
RUN pip install pipenv -i https://pypi.tuna.tsinghua.edu.cn/simple
ENV PIPENV_VENV_IN_PROJECT 1
RUN git pull origin master
RUN pipenv update -v
COPY .env .env
COPY config/docker.yaml config/docker.yaml
ENV ENV docker
EXPOSE 5000
ENTRYPOINT ["pipenv", "run", "python", "manage.py"]
CMD ["start"]
