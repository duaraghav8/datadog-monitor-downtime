# datadog-monitor-downtime
This is a commandline utility that helps schedule and cancel [monitor downtimes](https://docs.datadoghq.com/monitors/downtimes/) on [Datadog](https://www.datadoghq.com/). It is designed to be used to suppress alerts during planned outages.

For example, a deployment job in a CI server like Jenkins could invoke this tool to setup a monitor downtime before killing a Tomcat process that is being monitored for health. Once the deployment is successful and tomcat has restarted, the tool can be invoked again to delete the downtime and resume Tomcat's monitoring.

## Installation
This is a stand-alone script and can be placed and run from anywhere on disk. The following Python dependencies must be installed on the system before running the script:

- [datadogpy](https://github.com/DataDog/datadogpy) >= 0.24.0
- [click](https://click.palletsprojects.com/en/7.x/) >= 7.0

## Usage
Any downtimes managed by this script are tracked in its **local state** - a JSON file kept on disk. State initialization must be performed before using this script to manage downtimes. Multiple instances of this script can run simultaneously and operate on a shared state.

It is highly recommended that the state file be continuously backed up. If it is lost, the script cannot track the downtimes created by it.

The CLI is intended to be invoked using Python 2.7.

To get help on the tool's usage, run:
```bash
python dd-monitor-downtime.py -help
```

For help on a specific command, run:
```bash
python dd-monitor-downtime.py [command] -help
```

To get version information, use `python dd-monitor-downtime.py version`. While reporting issues, the output of this command must be included in the description.

### Initialization
The `init` command must be used to initialize state. By default, the state file is created in the process's current working directory as `.mdstate.json`. This can be changed using `-statefile`.

```bash
python dd-monitor-downtime.py init
python dd-monitor-downtime.py init -statefile /opt/downtime-manager/state.json
```

When running the script with a downtime management command, it will try to load the state from the default path as described above. The `-state` option can be used to specify the file from which to load the state.

```bash
python dd-monitor-downtime.py [command] [args]
python dd-monitor-downtime.py -state /opt/downtime-manager/state.json [command] [args]
```

### Datadog credentials
The commands described below are the downtime management commands and require Datadog credentials. These can be supplied either via commandline or environment. Commandline arguments have precedence over environment variables.

| CLI option    | Environment variable | Description             |
|---------------|----------------------|-------------------------|
| `-dd-api-key` | `DATADOG_API_KEY`    | Datadog account API key |
| `-dd-app-key` | `DATADOG_APP_KEY`    | Datadog account APP key |

Below is an example of how to supply datadog credentials through the commandline.
```bash
python dd-monitor-downtime.py -dd-api-key "xxxxxxx" -dd-app-key "xxxxxxx" [command] [args]
```

### Scheduling a downtime
The `schedule` command must be used to schedule a new downtime. The user must supply a name for this new downtime using `-md-name`. This name must be unique across the local state being used by the script. For example, in build systems, the combination of job name and build number can guarantee a unique name (eg- `wordpress-178`).

Command help
```bash
python dd-monitor-downtime.py schedule -help
```

Examples

1. Create downtime on dev environment for ElasticSearch cluster, assuming that `env` and `service` are valid scopes in the user's account.
```bash
python dd-monitor-downtime.py schedule -md-name "es-dev" -scope "env:dev,service:elasticsearch"
```

2. Schedule a downtime for a specific time in future
```bash
python dd-monitor-downtime.py schedule -md-name "all-apps" -scope "env:prod" -start "1543600009" -end "1543603609" -timezone "UTC"
```

3. Create downtime for a specific monitor
```bash
python dd-monitor-downtime.py schedule -md-name "java-apps" -scope "env:stage" -monitor-id "7376587"
```

4. Create a recurring downtime
```bash
python dd-monitor-downtime.py schedule -md-name "everything" -scope "env:prod" -recur-type days -recur-period 3 -recur-weekdays "Mon,Fri"
```

Note that if the `end` option is supplied, the downtime will delete itself from Datadog at the specified time. Despite this, the `cancel` command must be run with this downtime's name so that the script also removes it from local state and frees the name for re-use.

See Scheduling a downtime on [Datadog docs](https://docs.datadoghq.com/monitors/downtimes/) and its [API reference](https://docs.datadoghq.com/api/?lang=python#schedule-monitor-downtime) for detailed descriptions of all the options.

### Cancelling a downtime
To cancel a downtime managed by this script, the `cancel` command can be used and the unique downtime name must be supplied using `-md-name`.

```bash
python dd-monitor-downtime.py cancel -md-name "video-stream"
```

The above example deletes the downtime from Datadog as well as from local state and frees the name `video-stream` for re-use.

## Notes
This script internally uses [datadogpy](https://github.com/DataDog/datadogpy) to communicate with Datadog. This library produces a log `No agent or invalid configuration file found` if the script is run on a machine that doesn't have Datadog agent installed. This log can be safely ignored if the intention is to run the tool from such a machine. The tool itself doesn't require datadog agent to be present on the host.
