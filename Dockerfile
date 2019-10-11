FROM python:3.7-slim

COPY slack.py /usr/local/bin/
RUN mkdir -p /opt/resource
RUN ln -s /usr/local/bin/slack.py /opt/resource/check
RUN ln -s /usr/local/bin/slack.py /opt/resource/in
RUN ln -s /usr/local/bin/slack.py /opt/resource/out
