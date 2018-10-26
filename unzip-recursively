#! /usr/bin/env bash

lookindir=$1

if [[ -z $lookindir ]]; then
  lookindir="."
fi

find ${lookindir} -name "*.jar" -o -name "*.zip" | # finds jars or zips recursively
  while read filename; do
    # filename is usually something.[jar|zip], two level deep
    parentdir=$(dirname $(dirname $filename)) # this will be the PID folder
    if [ $parentdir != "lib" ] # don't want to unzip external libs
    then
      # unzip the file into newdirname
      unzip -o -d "${parentdir}" "$filename";
    fi
  done;
