FROM ubuntu:18.04

# variables
ARG BASEDIR="/usr/src/app"
ARG CLONEDIR="/tmp/mutation-testing"
ARG PROJDIR
ARG TASKFILE

# Install java, ant, python3, and pip
RUN \
  apt-get update && apt-get install -y \
    default-jdk \
    ant \
    python3 \
    python3-pip

# Python dependencies
RUN \
  python3 -m pip install pandas && \
  rm -rf /var/lib/apt/lists/*;

VOLUME ${CLONEDIR}

# directory containing source code and dependencies 
VOLUME ${BASEDIR}

# directory that will contain projects prepared for PIT testing
WORKDIR ${BASEDIR}

CMD ["bash", "-c", "./pit-runner.py tasks.ndjson -l -m all > /usr/src/app/mutation-results.ndjson"]
