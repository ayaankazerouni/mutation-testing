FROM openjdk:8

# variables
ARG BASEDIR="/usr/src/mujava"
ARG LIBDIR=${BASEDIR}/lib

# classpath  
WORKDIR ${BASEDIR}
RUN apt-get update && apt-get install -y \
  ant \
  python3 \
  && rm -rf /var/lib/apt/lists/*;
ENV CLASSPATH ${LIBDIR}/mujava.jar:${LIBDIR}/openjava.jar:${LIBDIR}/commons-io.jar:${LIBDIR}/junit.jar:${LIBDIR}/tools.jar

COPY . ${BASEDIR}

# CMD [ "python3", "setup_mujava.py" ]
CMD ["bash"]
