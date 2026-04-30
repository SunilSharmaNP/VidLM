FROM mysterysd/wzmlx:latest

WORKDIR /usr/src/app
RUN chmod 777 /usr/src/app

# Update pip + setuptools, then install requirements.
# (The base image does NOT ship `uv`, so use plain pip3.)
RUN pip3 install --upgrade pip setuptools setuptools-scm

COPY requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt

COPY . .

CMD ["bash", "start.sh"]
