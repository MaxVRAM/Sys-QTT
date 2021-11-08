from sys import stdout

class clr:
    RESET = '\033[0m' #LIGHT GREY
    # Normal
    OK = '\033[0;32;48m' #GREEN
    WARNING = '\033[0;33;48m' #YELLOW
    FAIL = '\033[0;31;48m' #RED
    HLIGHT = '\033[0;37;48m' #WHITE
    NOTICE = '\033[0;34;48m' #BLUE
    DARK = '\033[0;30;48m' #DARK GREY
    # Coloured BG
    C_OK = '\033[0;37;42m' #GREEN
    C_WARNING = '\033[0;37;43m' #YELLOW
    C_FAIL = '\033[0;37;41m' #RED
    C_HLIGHT = '\033[0;30;47m' #WHITE
    C_NOTICE = '\033[0;37;44m' #BLUE
    # Bright
    B_OK = '\033[1;32;48m' #GREEN
    B_WARNING = '\033[1;33;48m' #YELLOW
    B_FAIL = '\033[1;31;48m' #RED
    B_HLT = '\033[1;37;48m' #WHITE
    B_NOTICE = '\033[1;34;48m' #BLUE
    B_DARK = '\033[1;30;48m' #DARK GREY

def c_print(message = '', **kwargs):
    if message is None or message == '':
        print()
    else:    
        dressing = ''
        if 'tab' in kwargs and type(kwargs['tab']) == int:
            for x in range(kwargs['tab']):
                dressing = f'    {dressing}'
        if 'status' in kwargs and type(kwargs['status']) is not None:
            if kwargs['status'] == 'info':
                dressing = f'{dressing}{clr.B_DARK}[{clr.B_HLT}i{clr.B_DARK}]{clr.RESET} '
            if kwargs['status'] == 'wait':
                dressing = f'{dressing}{clr.B_DARK}[{clr.B_HLT}•{clr.B_DARK}]{clr.RESET} '
            elif kwargs['status'] == 'ok':
                dressing = f'{dressing}{clr.B_DARK}[{clr.B_OK}✓{clr.B_DARK}]{clr.RESET} '
            elif kwargs['status'] == 'warning':
                dressing = f'{dressing}{clr.B_DARK}[{clr.B_WARNING}!{clr.B_DARK}]{clr.RESET} '
            elif kwargs['status'] == 'fail':
                dressing = f'{dressing}{clr.B_DARK}[{clr.B_FAIL}✗{clr.B_DARK}]{clr.RESET} '
        else:
            dressing = f'{dressing}{clr.HLIGHT}'
        print(f'{dressing}{message}{clr.RESET}')
    stdout.flush()

def c_title(message:str, subject:str, status:str):
    TITLE = 'Sys-QTT'
    string_length = len(TITLE + message + subject) + 2
    string_end = ''.join(['-' for _ in range(string_length)])
    print()
    c_print(string_end, tab=1)
    c_print(f'{clr.B_HLT}{TITLE}{clr.RESET} {message} {getattr(clr, status)}{subject}', tab=1)
    c_print(string_end, tab=1)
    print()