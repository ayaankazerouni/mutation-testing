if [[ $1 ]]; then
  projdir=$1
else
  projdir=/tmp/mujava-testing
fi

./clone-projects.py tasks.ndjson && \
  docker build -t mujava-app . && \
    docker run \
    -v ${projdir}:${projdir} \
    -v $PWD:/usr/src/app \
    -it --rm mujava-app
