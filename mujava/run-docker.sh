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

echo -e "Need sudo access to clean up from previous run.\nsudo rm -rf ${projdir}\n"
sudo rm -rf ${projdir}

./clone-projects.py ${taskfile} && \
  docker build -t mujava-app . && \
  docker run \
  -v ${projdir}:${projdir} \
  -v $PWD:/usr/src/app \
  -it --rm mujava-app
