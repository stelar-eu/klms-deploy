FROM python:3.11

RUN mkdir /app
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY k8sexec.py .
CMD [ "python", "k8sexec.py" ]
