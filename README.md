# datadog-monitor-downtime
This is a commandline utility that helps schedule and cancel Monitor Downtimes on Datadog.

It is designed to be used to suppress alerts during planned outages. For example, a deployment job in a CI server like Jenkins could invoke this application to setup a monitor downtime before killing a Tomcat process. Once the deployment is successful and tomcat has restarted, the utility can be invoked again to delete the monitor downtime.

## Usage
```bash
export DATADOG_API_KEY=xxxxxxxxxxxxx
export DATADOG_APP_KEY=xxxxxxxxxxxxxxxxxxxxxxxx

python dd-monitor-downtime.py -state ./mdstate.json schedule -scope "app:wordpress" -monitor-id 1897212 -md-name "wordpress-167"
```