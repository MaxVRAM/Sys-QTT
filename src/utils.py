import subprocess

def quick_cat(arg):
    output = subprocess.run(['cat', arg], capture_output=True)
    return output.stdout.decode('utf-8').rstrip() if output.returncode == 0 else None