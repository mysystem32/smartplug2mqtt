IP=$(hostname -i)
HOST=$(hostname -s)
DATA=$HOME/docker/$HOST

docker run -d --restart=unless-stopped \
       --name=plug --hostname=plug \
       --net=bridge2 \
       -v $PWD/:/home/plug/ \
       ads/plug

sleep 2
docker logs plug
