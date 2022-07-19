#!/usr/bin/env bash

files=$(ls | grep "results" | tr "\n" " ")

for file in $files
do
  nb_nodes=$(echo $file | awk 'BEGIN { FS="_" } { print $3; }')
  cat $file | awk -v nb=$nb_nodes 'BEGIN {FS=","; OFS=","} NR==1 {print $0,"nb_nodes"} NR>1 {print $0,nb}' > tmp
  cat tmp > $file 
done

rm tmp
