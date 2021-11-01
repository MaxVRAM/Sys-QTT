import subprocess, os

def quick_cat(path, **kwargs):
    """Performs the CLI command "cat" and returns its output as a sanitised string."""
    # Force typecast if kwarg supplied
    ret_type = str if 'ret_type' not in kwargs else kwargs['ret_type']
    # Check that the file exists
    if os.path.isfile(path):
        # Execute cat on the file
        response = subprocess.run(['cat', path], stdout=subprocess.PIPE)
        if response.returncode == 0:
            value = response.stdout.decode('utf-8', 'ignore').strip()
            # String float needs to be converted to float before truncated to int
            return int(float(value)) if ret_type is int else ret_type(value)
    return None

def command_find(command:str, term:str, **kwargs):
    """Runs a CLI |command| and searches for a given |term| from its output.
    Returns the line of text containing the term, minus the term itself. Otherwise, it outputs None."""
    # Force typecast if kwarg supplied
    ret_type = str if 'ret_type' not in kwargs else kwargs['ret_type']
    # Run the custom command
    response = subprocess.run([command], stdout=subprocess.PIPE)
    if response.returncode == 0:
        sanitised = response.stdout.decode('utf-8', 'ignore')       
        for line in sanitised.split('\n'):
            if term in line:
                value = line.replace(term, '').strip()
                # String float needs to be converted to float before truncated to int
                return int(float(value)) if ret_type is int else ret_type(value)
        return None
    return None