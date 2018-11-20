import os
import sys
import json
import click
import datadog


CONTEXT_SETTINGS = dict(help_option_names=["-h", "-help", "--help"])
DEFAULT_STATE_FILENAME = ".mdstate.json"
ENV_DD_API_KEY = "DATADOG_API_KEY"
ENV_DD_APP_KEY = "DATADOG_APP_KEY"


def _abort(message, status=1):
    print(message)
    sys.exit(status)


def _read_state(file):
    if not os.path.exists(file):
        _abort("File {} does not exist".format(file), status=3)

    with open(file, "r") as statefile:
        try:
            return json.loads(statefile.read())
        except ValueError as ve:
            _abort(str(ve), status=4)


@click.group(context_settings=CONTEXT_SETTINGS)
@click.option("-state", default=DEFAULT_STATE_FILENAME, help="Path of the state file", show_default=True)
@click.option("-dd-api-key", default=os.environ.get(ENV_DD_API_KEY, ""), help="Datadog API Key")
@click.option("-dd-app-key", default=os.environ.get(ENV_DD_API_KEY, ""), help="Datadog APP Key")
@click.pass_context
def managercli(ctx, state, dd_api_key, dd_app_key):
    if not dd_api_key:
        _abort("Datadog API key was not provided", status=1)
    if not dd_app_key:
        _abort("Datadog App key was not provided", status=2)

    dd_options = {
        "api_key": dd_api_key,
        "app_key": dd_app_key
    }

    datadog.initialize(**dd_options)
    ctx.obj = {"statefile": state}


@managercli.command()
@click.option("-md-name", required=True, help="Name of the new Monitor Downtime (must be unique)")
@click.pass_context
def schedule(ctx, md_name):
    print("Schedule")


@managercli.command()
@click.option("-md-name", required=True, help="Name of the Monitor Downtime to cancel")
@click.pass_context
def cancel(ctx, md_name):
    state = _read_state(ctx.obj["statefile"])


if __name__ == "__main__":
    managercli()
