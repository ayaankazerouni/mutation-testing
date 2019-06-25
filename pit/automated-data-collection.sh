inputdir=$1 #Full path to original folder
outputdirname=$2 #path starting in outputs; such as fall2018/p1

#Sanity check; change the directory to parent of pit/
cd ~/code/forked/mutation-testing
#./write_tasks.py $1 -n 4 > pit/tasks.ndjson
./write_tasks.py $1 > pit/tasks.ndjson

#Change directory to pit/ and run docker container
cd pit/
./run-docker.sh

#Handling outputs generated
mkdir -p $2
cd /tmp/mutation-testing/
find . -name 'mutations.csv' -exec cp --parents \{\} $2 \;

mv ~/code/forked/mutation-testing/pit/mutation-results.ndjson $2
mv ~/code/forked/mutation-testing/pit/.log-pit $2/log-pit.txt

tar -czvf $2.tar.gz -C $2 ./
rm -rf $2
