FROM openjdk:8

# variables
ARG BASEDIR="/usr/src/mujava"
ARG LIBDIR=${BASEDIR}/lib

# classpath  
WORKDIR ${BASEDIR}
ENV CLASSPATH ${LIBDIR}/mujava.jar:${LIBDIR}/openjava.jar:${LIBDIR}/commons-io-2.4.jar:${LIBDIR}/junit-4.12.jar:${LIBDIR}/tools.jar
RUN apt-get update && apt-get install -y \
  ant \
  python3 \
  && rm -rf /var/lib/apt/lists/*;

COPY . ${BASEDIR}

#CMD [ "python3", "setup_mujava.py" ]
CMD ["bash"]
