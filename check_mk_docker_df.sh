#!/bin/bash
###
#
#   check_mk_docker_df  : check_mk plugin which will gather filesystem usage for all running containers.
#
#   Version      Author          Description      
#     0.1        Nigel Heaney    Initial version

BLACKLIST="#"

CONFFILE='/etc/check_mk/check_mk_docker_df.conf'
if [ ! -e $CONFFILE ]; then 
    touch $CONFFILE
    echo "#Add container names or ID's to blacklist if you want them to be excluded from omd monitoring." > $CONFFILE
    echo '#e.g This is a regex string so BLACKLIST="stg-proxy|redis|test|536ff129ce47" would exclude all of container which contain any of these.' >> $CONFFILE
    echo 'BLACKLIST="#"' >> $CONFFILE
fi    

#Source the config file so we can override defaults.
source $CONFFILE

echo "<<<df>>>"
for c in $(docker ps --format "{{.Names}}" | egrep -v $BLACKLIST) ; do docker exec $c df -kTPB 1024| grep -E '\/docker-' | sed "s/$/_container_$c/g";done

