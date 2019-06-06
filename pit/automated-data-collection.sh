#Automation lines for a whole semester's project
#for projdir in /home/mutant/DATA/submissions/p1 \
#	/home/mutant/DATA/submissions/p2 \
#	/home/mutant/DATA/submissions/p3 \
#	/home/mutant/DATA/submissions/p4
#do
#	[ -d $projdir ] && echo "Directory $projdir exists."	
#done

inputdir=$1 #Full path to original folder
outputdirname=$2 #path starting in outputs; such as fall2018/p1

#Sanity check; change the directory to parent of pit/
cd ~/code/forked/mutation-testing
./write_tasks.py $1 -n 2 > pit/tasks.ndjson

#Change directory to pit/ and run docker container
cd pit/
./run-docker.sh

#Handling outputs generated
mkdir -p $2
cd /tmp/mutation-testing/
find . -name 'mutations.csv' -exec cp --parents \{\} $2 \;
cp ~/code/forked/mutation-testing/pit/mutation-results.ndjson $2

tar -czvf $2.tar.gz $2
rm -rf $2
