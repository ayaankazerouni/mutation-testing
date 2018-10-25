# positional params put here later
PARAMS=""

# default values
PROJECTDIR=~/Developer/student-projects/testsubmissions
TASKFILE=tasks.json
SKIP_TASKS=false
SKIP_RUN=false

while (( "$#" )); do
  case "$1" in
    -t)
      SKIP_TASKS=true
      shift
      ;;
    -r)
      SKIP_RUN=true
      shift
      ;;
    -h|--help)
      echo "Positional arguments (should be in this relative order):"
      echo -e "\tPROJECTDIR: The directory containing submissions to be mutated."
      echo -e "\t\tDefaults to ${PROJECTDIR}"
      echo -e "\tTASKFILE: The file to which tasks for GNU Parallel should be written."
      echo -e "\t\tDefaults to ${TASKFILE}"
      echo "Options:"
      echo -e "\t-t: Skip generating a task file? Use this if you already have tasks written to a file."
      echo -e "\t-r: Skip mutation testing? Convenient to only write tasks."
      exit 0
      ;;
    --) # end arugment parsing
      shift
      break
      ;;
    *) # preserve positionals
      PARAMS="$PARAMS $1"
      shift
      ;;
  esac
done

eval set -- "$PARAMS" 

if [[ -n "$1" ]]; then
  PROJECTDIR=$1
fi

if [[ -n "$2" ]]; then
  TASKFILE=$2
fi 

if [ "$SKIP_TASKS" = false ] ; then 
  rm -f ${TASKFILE}
  find  ${PROJECTDIR} -maxdepth 1 -type d | while read line; do
    if [[ $line != $PROJECTDIR ]]; then
      echo "{ \"projectPath\": \"$line\", \"task\": \"pit\" }" >> $TASKFILE
    fi
  done
  echo "Wrote tasks from ${PROJECTDIR} to ${TASKFILE}."
fi

if [ "$SKIP_RUN" = false ] ; then
  echo "Starting mutation testing. This might take a while."
  parallel --progress --arg-file tasks.json --pipepart --cat ./run-mutation-test.js {} > /tmp/mutation-results.json
  echo "Run summary in /tmp/mutation-results.json. PITest reports in /tmp/mutation-testing/. Use ./aggregrate_results.py to translate PIT reports to coverage data."
fi 
