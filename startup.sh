#!/bin/sh

echo "$(date): Staring plug in $(pwd), id=$(id)"

# trap docker SIGTERM and gracefully shutdown
trap_sigterm() {
    echo "$(date): SIGTERM received, running 'pkill plug.py'..."
    pkill plug.py
    sync
    sleep 1
}

# start with "&" + wait so we can trap 'docker stop' signal and shutdown gracefully
trap trap_sigterm SIGTERM

for J in /home/plug/*.json
do
   echo "$(date): Starting /home/plug/plug.py $J"
   /home/plug/plug.py $J &
done

wait
