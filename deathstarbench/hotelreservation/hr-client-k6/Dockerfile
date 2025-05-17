FROM python:3.7.11-slim-buster
RUN apt-get -y update && \
    apt-get -y upgrade && \
    apt-get install -y gnupg dirmngr && \
    gpg -k && \
    gpg --no-default-keyring --keyring /usr/share/keyrings/k6-archive-keyring.gpg --keyserver hkp://keyserver.ubuntu.com:80 --recv-keys C5AD17C747E3415A3642D57D77C6C491D6AC1D69 && \
    echo "deb [signed-by=/usr/share/keyrings/k6-archive-keyring.gpg] https://dl.k6.io/deb stable main" | tee /etc/apt/sources.list.d/k6.list && \
    DEBIAN_FRONTEND=noninteractive TZ=America/Los_Angeles apt-get -y install tzdata && \
    apt-get -y update && \
    apt-get -y upgrade && \
    apt-get -y install dnsutils git vim python3 python3-aiohttp k6 iputils-ping lynx build-essential gcc bash curl nano && \
    pip install kubernetes
COPY driver /driver/
