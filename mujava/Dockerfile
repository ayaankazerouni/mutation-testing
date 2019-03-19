FROM openjdk:8-slim

# variables
ARG BASEDIR="/usr/src/app"
ARG LIBDIR=${BASEDIR}/lib
ARG PROJDIR="/tmp/mujava-testing"

# classpath  
WORKDIR ${BASEDIR}
RUN apt-get update && apt-get install -y \
  ant \
  python3 \
  && rm -rf /var/lib/apt/lists/*;

VOLUME ${PROJDIR}
VOLUME ${BASEDIR}

# CMD [ "python3", "mujava_runner.py" ]
CMD ["bash"]
