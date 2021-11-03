import subprocess, os, pytz
from datetime import datetime as dt

UTC = pytz.utc
TIMEZONE = None

def set_timezone(tz):
    global TIMEZONE
    TIMEZONE = pytz.timezone(tz)

def utc_from_ts(timestamp: float) -> dt:
    """Return a UTC time from a timestamp."""
    return UTC.localize(dt.utcfromtimestamp(timestamp))

def as_local(input_dt: dt) -> dt:
    """Convert a UTC datetime object to local time zone."""
    if input_dt.tzinfo is None:
        input_dt = UTC.localize(input_dt)
    if input_dt.tzinfo == TIMEZONE:
        return input_dt
    return input_dt.astimezone(TIMEZONE)




def search(input: str, term: str) -> str:
    for line in input.split('\n'):
        if term in line:
            value = line.replace(term, '').strip()
            # String float needs to be converted to float before truncated to int
            return value

def quick_command(command:str, **kwargs):
    """Runs a CLI command and returns its output.
    Optional kwarg "args" as a list to add arguments to the command.
    Also kwargs 'ret_type' to typecast the return value,
    and 'term' to search and return value after term string."""
    # Force typecast if kwarg supplied
    ret_type = str if 'ret_type' not in kwargs else kwargs['ret_type']
    term = None if 'term' not in kwargs else kwargs['term']
    args = [command] if 'args' not in kwargs else [command, *kwargs['args']]
    # Run the custom command
    response = subprocess.run(args, stdout=subprocess.PIPE)
    if response.returncode == 0:
        value = response.stdout.decode('utf-8', 'ignore')
        value = search(value, term) if term is not None else value
        if value is not None:
            # String float needs to be converted to float before truncated to int
            return int(float(value)) if ret_type is int else ret_type(value)
    return None

def quick_cat(path, **kwargs):
    """Performs the CLI command "cat" and returns its output as a sanitised string.
    Accepts kwargs 'ret_type' to typecast the return value.
    And 'term' to search and return value after term string."""
    kwargs = {} if kwargs is None else kwargs
    if 'args' not in kwargs:
        kwargs['args'] = [path]
    else:
        kwargs['args'] = [path]
    #print('input kwargs: ' + kwargs['kwargs'])
    # Check that the file exists
    if os.path.isfile(path):
        return quick_command('cat', **kwargs)
    return None