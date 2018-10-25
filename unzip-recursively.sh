#! /usr/bin/env bash

lookindir=$1

if [[ -z $lookindir ]]; then
  lookindir="."
fi

# web-cat submissions are downloaded in a certain format
# this unzips the jar and places the project in a top level
# directory with the same name as the jar file
find ${lookindir} -name "*.jar" |
  while read filename; do
    parentdir="$(dirname $filename)"
    newdirname=${lookindir}/"$(basename $filename)"
    newdirname=${newdirname%.*}

    unzip -o -d "${newdirname}" "$filename";
  done;
