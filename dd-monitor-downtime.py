import os
import sys
import json
import click
import datadog
import logging


VERSION = "0.1.0"
CONTEXT_SETTINGS = dict(help_option_names=["-h", "-help", "--help"])
DEFAULT_STATE_FILENAME = ".mdstate.json"
CWD = os.getcwd()
DEFAULT_STATE_FILE = os.path.join(CWD, DEFAULT_STATE_FILENAME)
ENV_DD_API_KEY = "DATADOG_API_KEY"
ENV_DD_APP_KEY = "DATADOG_APP_KEY"
STATE_LOCK_FILENAME = ".ddmd.lock"

logging.basicConfig(level=logging.INFO,
                    datefmt="%Y-%m-%d %H:%M:%S%z", format='%(asctime)s [%(levelname)s]  %(message)s')


def _abort(message, status=1):
    logging.error(message)
    sys.exit(status)


def _success(message):
    logging.info(message)
    sys.exit(0)


def __init_datadog(api_key, app_key):
    if not api_key:
        _abort("Datadog API key was not provided", status=1)
    if not app_key:
        _abort("Datadog App key was not provided", status=2)

    dd_options = {
        "api_key": api_key,
        "app_key": app_key
    }

    datadog.initialize(**dd_options)


def _acquire_state_lock(target_dir):
    """
    Acquire write lock by creating a lock file in the same directory
    as the state.

    If a lock file already exists, this method waits indefinitely until
    it is able to acquire the lock. No timeout exists to maximize the
    likelihood of modifying the local state.

    :param target_dir: Directory where the state file resides
    :return: None
    """
    state_lock_file = os.path.join(target_dir, STATE_LOCK_FILENAME)

    # Wait for the other process to release state lock
    while os.path.exists(state_lock_file):
        pass

    try:
        open(state_lock_file, "w").close()
    except Exception as e:
        _abort("Failed to acquire state lock {}: {}".format(state_lock_file, str(e)), status=11)


def _release_state_lock(target_dir):
    """
    Release the write lock acquired to modify local state.

    If this method fails to delete the lock file, the process aborts
    immediately and the file must be deleted manually, otherwise all
    other instances of this script will be stuck indefinitely, waiting
    for the lock to be released.

    :param target_dir: Directory where the state file resides
    :return: None
    """
    state_lock_file = os.path.join(target_dir, STATE_LOCK_FILENAME)
    try:
        os.remove(os.path.join(state_lock_file))
    except Exception as e:
        _abort("Failed to delete state lock {}: {}".format(state_lock_file, str(e)), status=10)


def _read_state(file):
    """
    Read local state

    :param file: State file path
    :return: State object as python dict (Key: downtime name, Value: downtime datadog ID)
    """
    if not os.path.exists(file):
        _abort("File {} does not exist".format(file), status=3)

    with open(file, "r") as statefile:
        try:
            return json.loads(statefile.read())
        except ValueError as ve:
            _abort(str(ve), status=4)


def _write_state(file, action, key, value):
    """
    Modify local state to record the action taken in this process.
    The state is written to only if a new downtime is created or an
    existing one deleted.
    This method must release the acquired lock regardless of whether
    it fails or succeeds in performing the action.

    :param file: State file path
    :param action: The action to perform on a resource in the state (create or delete)
    :param key: Resource name
    :param value: Resource value (used when creating a new resource)
    :return: None
    """
    state_dir = os.path.dirname(file)

    # Do not proceed until write lock has been acquired
    _acquire_state_lock(state_dir)
    # Reading the state now guarantees that it can't be modified by
    # other instances of this script until this function releases the write lock.
    state = _read_state(file)

    if action == "delete" and key in state:
        # Ignore if key does not exist in state
        del state[key]
    elif action == "create":
        if key in state:
            _release_state_lock(state_dir)
            _abort("Key {} already exists in state file".format(key), status=8)
        state[key] = value

    with open(file, "w") as statefile:
        try:
            statefile.write(json.dumps(state, indent=4))
        except Exception as e:
            _release_state_lock(state_dir)
            _abort("Failed to write to state file: {}".format(str(e)), status=9)

    _release_state_lock(state_dir)


@click.group(context_settings=CONTEXT_SETTINGS)
@click.option("-state", default=DEFAULT_STATE_FILE, help="Path of the state file", show_default=True)
@click.option("-dd-api-key", default=os.getenv(ENV_DD_API_KEY, ""),
              help="Datadog API Key (env: {})".format(ENV_DD_API_KEY))
@click.option("-dd-app-key", default=os.getenv(ENV_DD_APP_KEY, ""),
              help="Datadog APP Key (env: {})".format(ENV_DD_APP_KEY))
@click.pass_context
def managercli(ctx, state, dd_api_key, dd_app_key):
    """
    Schedule and Cancel Datadog Monitor downtimes on demand
    """
    ctx.obj = {
        "statefile": state,
        "dd_api_key": dd_api_key,
        "dd_app_key": dd_app_key
    }


@managercli.command(short_help="Initialize state")
@click.option("-statefile", default=DEFAULT_STATE_FILE, show_default=True, help="Path of the state file")
def init(statefile):
    """
    Initialize state

    This command must be run before using other functionality of
    the application. If the state file is lost or corrupted, the
    application cannot track the downtimes created by it.

    It is recommended that the state file be periodically backed up
    and only this application should write to it.

    By default, this command creates an empty state file in
    the process's current working directory.
    """
    try:
        sf = open(statefile, "w")
        sf.write(json.dumps({}, indent=4))
        sf.close()
    except Exception as e:
        _abort("Failed to initialize state at {}: {}".format(statefile, str(e)), status=14)

    _success("Created {}".format(statefile))


@managercli.command(short_help="Get version")
def version():
    """
    Get version information
    """
    print("datadog-monitor-downtime v{}".format(VERSION))


@managercli.command(short_help="Schedule a downtime")
@click.option("-md-name", required=True, help="Name of the new downtime (must be unique)")
@click.option("-scope", required=True, help="Comma-separated list of scopes to which the downtime applies")
@click.option("-monitor-tags", help="Comma-separated list of monitor tags")
@click.option("-monitor-id", help="Single monitor to which the downtime applies")
@click.option("-start", help="POSIX timestamp to start the downtime at")
@click.option("-end", help="POSIX timestamp to end the downtime at")
@click.option("-message", help="Message to include with notifications for this downtime")
@click.option("-timezone", default="UTC", help="Timezone for the downtime")
@click.option("-recur-type", help="Type of recurrence of the downtime")
@click.option("-recur-period", type=int, help="How often to repeat the downtime")
@click.option("-recur-weekdays", help="List of week days to repeat downtime on")
@click.option("-recur-until-occurrences", help="Number of times the downtime is rescheduled")
@click.option("-recur-until-date", help="Date at which the downtime recurrence should end as a POSIX timestamp")
@click.pass_context
def schedule(ctx, md_name, scope, monitor_tags, monitor_id, start, end,
             message, timezone, recur_type, recur_period, recur_weekdays, recur_until_occurrences, recur_until_date):
    """
    Schedule a downtime

    Doc:

    API reference: https://docs.datadoghq.com/api/?lang=python#schedule-monitor-downtime
    """
    __init_datadog(api_key=ctx.obj["dd_api_key"], app_key=ctx.obj["dd_app_key"])

    state = _read_state(ctx.obj["statefile"])
    if md_name in state:
        _abort("Downtime {} already exists in state".format(md_name), status=12)

    recur_obj = None

    # Create recurrence object only if its mandatory values are provided
    if recur_type and recur_period:
        recur_obj = {
            "type": recur_type,
            "period": int(recur_period),
            "until_occurrences": recur_until_occurrences,
            "until_date": int(recur_until_date),
            "week_days": int(recur_weekdays)
        }

    try:
        res = datadog.api.Downtime.create(
            scope=scope,
            monitor_tags=monitor_tags,
            monitor_id=int(monitor_id),
            start=int(start),
            end=int(end),
            message=message,
            timezone=timezone,
            recurrence=recur_obj
        )
    except Exception as e:
        _abort("Failed to schedule Downtime {}: {}".format(md_name, str(e)), status=13)

    try:
        _write_state(file=ctx.obj["statefile"], action="create", key=md_name, value=res["id"])
    except Exception as e:
        _abort(
            "Successfully scheduler downtime {} (ID {}) but failed to update local state: {}".format(md_name, res["id"], str(e)),
            status=14
        )

    _success("Scheduled downtime {} (ID {}) successfully".format(md_name, res["id"]))


@managercli.command(short_help="Cancel a scheduled downtime")
@click.option("-md-name", required=True, help="Name of the Monitor Downtime to cancel")
@click.pass_context
def cancel(ctx, md_name):
    """
    Cancel a downtime managed by this application

    Doc:

    API reference: https://docs.datadoghq.com/api/?lang=python#cancel-monitor-downtime
    """
    __init_datadog(api_key=ctx.obj["dd_api_key"], app_key=ctx.obj["dd_app_key"])

    state = _read_state(ctx.obj["statefile"])
    if md_name not in state:
        _abort("Downtime {} does not exist in state".format(md_name), status=5)

    try:
        md_id = int(state[md_name])
        datadog.api.Downtime.delete(md_id)
    except Exception as e:
        _abort("Failed to cancel Monitor downtime {}: {}".format(md_name, str(e)), status=6)

    try:
        _write_state(file=ctx.obj["statefile"], action="delete", key=md_name)
    except Exception as e:
        _abort(
            "Successfully cancelled Monitor downtime {} (ID {}) but failed to update local state: {}".format(md_name, md_id, str(e)),
            status=7
        )

    _success("Cancelled Monitor downtime {} (ID {}) successfully".format(md_name, md_id))


if __name__ == "__main__":
    managercli()
