FROM openjdk:8-slim

# variables
ARG BASEDIR="/usr/src/app"
ARG LIBDIR=${BASEDIR}/lib
ARG PROJDIR="/tmp/mujava-testing"

RUN \
  apt-get update && apt-get install -y \
    ant \
    python3 && \
  rm -rf /var/lib/apt/lists/*;

WORKDIR ${BASEDIR}

VOLUME ${PROJDIR}
VOLUME ${BASEDIR}

CMD ["bash", "-c", "./mujava-runner.py tasks.ndjson > /usr/src/app/mutation-results.ndjson"]
