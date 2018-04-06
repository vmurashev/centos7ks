FROM centos:centos7
RUN mkdir /root/centos7build
RUN yum -y install make deltarpm createrepo livecd-tools