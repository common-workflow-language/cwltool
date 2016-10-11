FROM commonworkflowlanguage/cwltool_module
MAINTAINER peter.amstutz@curoverse.com

# Based on https://github.com/jpetazzo/dind

# Let's start with some basic stuff.
RUN DEBIAN_FRONTEND=noninteractive apt-get install -qy --no-install-recommends \
    apt-transport-https \
    ca-certificates \
    curl \
    lxc \
    iptables

# Install Docker from Docker Inc. repositories.
RUN curl -sSL https://get.docker.com/ | sh

# Install the magic wrapper.
ADD ./wrapdocker /usr/local/bin/wrapdocker
RUN chmod +x /usr/local/bin/wrapdocker

VOLUME /var/lib/docker
ENTRYPOINT ["wrapdocker", "cwltool"]
