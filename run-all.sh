taskFile="tasks.json"
project_dir="/home/ayaan/Developer/student-projects/fall-2016-repos/"
skip_tasks=false
skip_run=false

while getopts ":tr" opt; do
  case $opt in
    t)
      skip_tasks=true
      ;;
    r)
      skip_run=true
      ;;
    \?)
      echo "invalid option -$OPTARG" >&2
      ;;
  esac
done

if [ "$skip_tasks" = false ] ; then 
  rm -f ${taskFile}
  find  ${project_dir} -maxdepth 1 -type d | while read line; do
    if [[ $line != $project_dir ]]; then
      echo "{ \"projectPath\": \"$line\", \"task\": \"pit\" }" >> $taskFile
    fi
  done
  echo "Wrote tasks from ${project_dir} to ${taskFile}."
fi

if [ "$skip_run" = false ] ; then
  # ./lib/distributed-map.pl \
  #   --cluster clusters.json \
  #   --workScript /home/ayaan/Developer/mutation-testing/run-mutation-test.js \
  #   --taskFile $taskFile \
  #   --env 'PATH=/home/ayaan/.nvm/versions/node/v8.9.4/bin/node:$PATH'
  echo "Starting parallel mutation testing. This might take a while."
  parallel --arg-file tasks.json --pipepart --cat ./run-mutation-test.js {} > /tmp/mutation-results.json
fi 
