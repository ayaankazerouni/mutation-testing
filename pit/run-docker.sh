clonedir=/tmp/mutation-testing
taskfile=tasks.ndjson
container="pit-runner"

key="$1"
case $key in
  -t|--tasks)
    taskfile="$2"
    shift 2
    ;;
esac

[[ -z "$taskfile" ]] && echo 'Missing task file argument (-t|--tasks)' && exit 1

[[ -f $taskfile ]] && \
  ../clone-projects.py $taskfile -p &&
  docker build \
    --build-arg TASKFILE=$taskfile \
    --build-arg CLONEDIR=$clonedir \
    --build-arg UID=$(echo UID) \
    -t $container . && \
  docker run \
    -v ${clonedir}:${clonedir} \
    -v $PWD:/usr/src/app \
    -it --rm $container

