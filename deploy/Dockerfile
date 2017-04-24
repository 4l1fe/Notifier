FROM ubuntu:16.04

ENV PROJ_DIR /root/Notify
COPY deploy/requirements.txt /root/requirements.txt

RUN apt-get update && \
    apt-get install -y \
            build-essential \
            libssl-dev \
            libffi-dev \
            wget && \
    wget https://www.python.org/ftp/python/3.5.3/Python-3.5.3.tar.xz && \
    tar xf Python-3.5.3.tar.xz && \
    cd Python-3.5.3 && \
    ./configure && \
    make && \
    make install && \
    rm -rf Python-3.5.3.tar.xz Python-3.5.3 && \
    apt-get install -y python3-dev \
                       python3-pip && \
    pip3 install -r /root/requirements.txt && \
    rm -rf /var/lib/apt/lists/* && \
    apt-get autoremove -y

COPY . $PROJ_DIR

WORKDIR $PROJ_DIR

ENTRYPOINT ["python3", "run.py"]