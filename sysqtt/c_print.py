from sys import stdout


class col:
    RESET = '\033[0m'  # LIGHT GREY
    # Normal
    OK = '\033[0;32;48m'  # GREEN
    WARNING = '\033[0;33;48m'  # YELLOW
    FAIL = '\033[0;31;48m'  # RED
    HLIGHT = '\033[0;37;48m'  # WHITE
    NOTICE = '\033[0;34;48m'  # BLUE
    DARK = '\033[0;30;48m'  # DARK GREY
    # Coloured BG
    C_OK = '\033[0;37;42m'  # GREEN
    C_WARNING = '\033[0;37;43m'  # YELLOW
    C_FAIL = '\033[0;37;41m'  # RED
    C_HLIGHT = '\033[0;30;47m'  # WHITE
    C_NOTICE = '\033[0;37;44m'  # BLUE
    # Bright
    B_OK = '\033[1;32;48m'  # GREEN
    B_WARNING = '\033[1;33;48m'  # YELLOW
    B_FAIL = '\033[1;31;48m'  # RED
    B_HLT = '\033[1;37;48m'  # WHITE
    B_NOTICE = '\033[1;34;48m'  # BLUE
    B_DARK = '\033[1;30;48m'  # DARK GREY


def c_print(message='', **kwargs):
    if message is None or message == '':
        print()
        stdout.flush()
        return
    dressing = ''
    if 'tab' in kwargs and type(kwargs['tab']) == int:
        for x in range(kwargs['tab']):
            dressing = f'    {dressing}'
    if 'status' in kwargs and type(kwargs['status']) is not None:
        if kwargs['status'] == 'info':
            dressing = f'{dressing}{col.B_DARK}[{col.B_HLT}i{col.B_DARK}]{col.RESET} '
        if kwargs['status'] == 'wait':
            dressing = f'{dressing}{col.B_DARK}[{col.B_HLT}•{col.B_DARK}]{col.RESET} '
        elif kwargs['status'] == 'ok':
            dressing = f'{dressing}{col.B_DARK}[{col.B_OK}✓{col.B_DARK}]{col.RESET} '
        elif kwargs['status'] == 'warning':
            dressing = f'{dressing}{col.B_DARK}[{col.B_WARNING}!{col.B_DARK}]{col.RESET} '
        elif kwargs['status'] == 'fail':
            dressing = f'{dressing}{col.B_DARK}[{col.B_FAIL}✗{col.B_DARK}]{col.RESET} '
    else:
        dressing = f'{dressing}{col.HLIGHT}'
    print(f'{dressing}{message}{col.RESET}')
    stdout.flush()


def c_title(message: str, subject: str, status: str):
    TITLE = 'Sys-QTT'
    string_length = len(TITLE + message + subject) + 2
    string_end = ''.join(['-' for _ in range(string_length)])
    print()
    c_print(string_end, tab=1)
    c_print(f'{col.B_HLT}{TITLE}{col.RESET} {message} \
        {getattr(col, status)}{subject}', tab=1)
    c_print(string_end, tab=1)
    print()
