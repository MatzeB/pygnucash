#!/bin/bash
unset LANG
unset LC_COLLATE
unset LC_CTYPE
unset LC_MESSAGES
unset LC_MONETARY
unset LC_NUMERIC
unset LC_TIME
unset LC_ALL
export LANG=C

mkdir -p Inputs/gen
for i in Inputs/*.sql; do
    NAME="$(basename $i .sql)"
    OUTPUT="Inputs/gen/$NAME.gnucash"
    echo "GEN $OUTPUT : $i"
    rm -f "$OUTPUT"
    sqlite3 "$OUTPUT" ".read $i"
done

for i in *.test.sh; do
    echo -n "$i ... "
    NAME="$(basename $i .test.sh)"
    sh $i > /tmp/$NAME.out
    diff -u /tmp/$NAME.out $NAME.reference && echo "ok"
done
