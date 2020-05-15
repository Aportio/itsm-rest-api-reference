# Dockerfile to create a test instance of the ITSM RESTful API reference implementation

FROM docker.io/library/python:3.6
LABEL Description="Aportio ITSM RESTful API reference implementation" \
      Vendor="Aportio" \
      Version="1.0"

ADD . /
RUN pip3 install -r requirements/deploy.txt
COPY db.json-example /db.json

EXPOSE 5000

ENTRYPOINT [ "python3" ]

CMD [ "run.py" ]
