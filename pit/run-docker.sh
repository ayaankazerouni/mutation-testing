clonedir=/tmp/mutation-testing
container="pit-runner"
datadir=$1

[[ -z "$datadir" ]] && echo 'Missing data directory' && exit 1

[[ -d $datadir ]] && \
  mkdir -p ${clonedir} && \
  docker build \
    --build-arg CLONEDIR=$clonedir \
    --build-arg DATADIR=$datadir \
    -t $container . && \
  docker run \
    -v ${clonedir}:${clonedir} \
    -v $PWD:/usr/src/app \
    -v ${datadir}:/usr/src/app/datadir \
    -it --rm $container

