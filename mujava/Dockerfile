FROM openjdk:8

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
ENV CLASSPATH ${LIBDIR}/mujava.jar:${LIBDIR}/openjava.jar:${LIBDIR}/commons-io.jar:${LIBDIR}/junit.jar:${LIBDIR}/tools.jar

VOLUME ${PROJDIR}

COPY . ${BASEDIR}

# CMD [ "python3", "mujava_runner.py" ]
CMD ["bash"]
