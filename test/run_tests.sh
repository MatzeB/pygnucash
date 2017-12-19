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

for i in *.test.sh; do
    echo -n "$i ... "
    NAME="$(basename $i .test.sh)"
    sh $i > /tmp/$NAME.out
    diff -u /tmp/$NAME.out $NAME.reference && echo "ok"
done
