import subprocess
import sh

def quick_cat(arg):
    output = subprocess.run(['cat', arg], capture_output=True)
    return output.stdout.decode('utf-8', errors='strict').strip() if output.returncode == 0 else None

def command_find(command, term):
    value = 'Unknown'
    try:
        proc = subprocess.run(command, capture_output=True)
        output = proc.stdout.decode('utf-8', errors='strict').strip()
        for line in output.split('\n'):
            if term in line:
                value = line.replace(term, '').strip()
                return value
        return value
    except Exception as e:
        print(f'error: {e}')
        return value