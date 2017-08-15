FROM python:3.5.4

ENV PROJ_DIR /root/Notify

COPY . $PROJ_DIR

RUN pip3 install -r $PROJ_DIR/deploy/requirements.txt

WORKDIR $PROJ_DIR

ENTRYPOINT ["python3", "run.py"]