# x86 architecture 
FROM     debian:jessie 
           
# arm (raspberry pi) architecture       
#FROM     resin/rpi-raspbian 

MAINTAINER Mort Canty "mort.canty@gmail.com"

RUN apt-get update && apt-get install -y --no-install-recommends \
    python \
    build-essential \
    make \
    gcc \
    g++ \
    python-dev \ 
    python-flask \
    python-numpy \
    python-scipy \
    python-gdal \
    libffi-dev \
    python-pip    

# package imported by auxil package (but not used)
RUN     apt-get install -y --no-install-recommends python-tk

# setup the prov_means library
COPY    prov_means.c /home/prov_means.c
WORKDIR /home
RUN     gcc -shared -Wall -g -o libprov_means.so -fPIC prov_means.c
RUN     cp libprov_means.so /usr/lib/libprov_means.so

# my auxil
COPY    dist/auxil-1.1.tar.gz /auxil-1.1.tar.gz
WORKDIR /
RUN     tar -xzvf auxil-1.1.tar.gz
WORKDIR /auxil-1.1
RUN     python setup.py install  
WORKDIR /
RUN     rm -rf auxil-1.1/
RUN     rm auxil-1.1.tar.gz

EXPOSE 5000

# server 
RUN     pip install --upgrade pip
RUN     pip install google-api-python-client
RUN     pip install pyCrypto
RUN     apt-get install -y libssl-dev
RUN     pip install earthengine-api
ADD     Crypto /home/Crypto
ADD     ee /home/ee
ADD     httplib2 /home/httplib2
ADD     oauth2client /home/oauth2client
ADD     static /home/static
ADD     templates /home/templates   
COPY    eeMad.py /home/eeMad.py
COPY    eeWishart.py /home/eeWishart.py
COPY    app.py /home/app.py

WORKDIR /home
CMD     /bin/bash

