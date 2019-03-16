mkdir lib

curl -o lib/junit.jar http://central.maven.org/maven2/junit/junit/4.12/junit-4.12.jar
curl -o lib/pitest.jar http://central.maven.org/maven2/org/pitest/pitest/1.4.6/pitest-1.4.6.jar
curl -o lib/pitest-entry.jar http://central.maven.org/maven2/org/pitest/pitest-entry/1.4.6/pitest-entry-1.4.6.jar
curl -o lib/pitest-ant.jar http://central.maven.org/maven2/org/pitest/pitest-ant/1.4.6/pitest-ant-1.4.6.jar

echo -e "\n\nstudent.jar not downloaded! Download it manually from the following link\nhttp://sourceforge.net/projects/web-cat/files/Student%20Library/4.14/student.jar/download"
