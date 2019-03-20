if [[ $1 ]]; then
  projdir=$1
else
  projdir=/tmp/mujava-testing
fi

if [[ $2 ]]; then
  taskfile=$2
else
  taskfile='tasks.ndjson'
fi

docker build -t mujava-app . && \
  docker run \
  -v ${projdir}:${projdir} \
  -v $PWD:/usr/src/app \
  -it --rm mujava-app
