import subprocess, os

def quick_cat(path) -> str:
    """Performs the CLI command "cat" and returns its output as a sanitised string."""
    # Check that the file exists
    if os.path.isfile(path):
        # Execute cat on the file
        response = subprocess.run(['cat', path], stdout=subprocess.PIPE)
        if response.returncode == 0:
            return response.stdout.decode('utf-8', 'ignore').strip()
    return None

def command_find(command:str, term:str) -> str:
    """Runs a CLI |command| and searches for a given |term| from its output.
    Returns the line of text containing the term, minus the term itself. Otherwise, it outputs None."""
    value = 'Unknown'
    # Run the custom command
    response = subprocess.run([command], stdout=subprocess.PIPE)
    if response.returncode == 0:
        sanitised = response.stdout.decode('utf-8', 'ignore')       
        for line in sanitised.split('\n'):
            if term in line:
                value = line.replace(term, '').strip()
                return value
        return value
    return None