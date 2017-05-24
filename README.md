# check_mk
My collection of check_mk plugins

## check_mk_docker.py
This will allow you to monitor several aspects of docker and optionally individual containers which can track cpu,memory,disk and if a particular container is up or not.

The default is to perform summary check and via config file you can extent to monitor specific containers.  This condif file is in /etc/check_mk/check_mk_docker.conf.

This plugin is designed to be run as a local check.


## check_mk_docker_df.sh
This plugin will connect to each continer and grab filesystem usage. There is a config file which can be used to exclude or blacklist containers from this check.  Note the check relies on the df command being available.


## check_mk_apt
This check is designed to highlight missing patches based on the security or risk to the server and report back how many critical, high, medium and low security updates are required.  Currently I have only configured and tested for ubuntu 14.0x (trusty) edition as this was the scope during development but can easily be extended.

This is designed to be run as a local check and is relatively slow so to protect check_mk_agent from taking too long, set this up as a
 cached check say every 24 hours.


## check_mk_yum
This check is designed to utilise the yum security plugin and will report back on missing patches based on security or risk tot he server. Will trigger an alert after 10 critical updates missing.  This has been tested on Redhat 5,6,7 and Centos 5,6,7.  Everything else is not supported.

Now Centos do no not support errata nor do they publish errata so this will not with Centos out of the box.  This requires that you are using something like Spacewalk with errata published or use another method which I setup so I could publish errata to local repos. See centos-errata repo for this.

This is designed to be run as a local check and is relatively slow so to protect check_mk_agent from taking too long, set this up as a cached check say every 24 hours.


