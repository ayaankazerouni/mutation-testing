#! /usr/bin/env bash

lookindir=$1

if [[ -z $lookindir ]]; then
  lookindir="."
fi

find ${lookindir} -name "*.jar" |
  while read filename; do
    parentdir="$(dirname $filename)"
    newdirname=${lookindir}/"$(basename $filename)"
    newdirname=${newdirname%.*}

    unzip -o -d "${newdirname}" "$filename";
  done;
