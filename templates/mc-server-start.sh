#!/bin/bash

for props in 'banned-ips' 'banned-players' 'ops' 'whitelist'; do
    echo Merging ${props}...
    mcpropmerge.py ../../conf/${props}.json local.${props}.json > ${props}.json
done

# ISO 8601: YYYY-MM-DDTHH:mm:ssZ
date -u +"%Y-%m-%dT%H:%M:%SZ" >server-start

java -Xmx1024M -Xms1024M -Djava.net.preferIPv4Stack=true -jar minecraft_server.jar nogui
