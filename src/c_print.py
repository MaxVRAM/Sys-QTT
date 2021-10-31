from sys import stdout

class text_color:
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
    B_HLIGHT = '\033[1;37;48m' #WHITE
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
                dressing = f'{dressing}{text_color.B_DARK}[{text_color.B_HLIGHT}i{text_color.B_DARK}]{text_color.RESET} '
            if kwargs['status'] == 'wait':
                dressing = f'{dressing}{text_color.B_DARK}[{text_color.B_HLIGHT}•{text_color.B_DARK}]{text_color.RESET} '
            elif kwargs['status'] == 'ok':
                dressing = f'{dressing}{text_color.B_DARK}[{text_color.B_OK}✓{text_color.B_DARK}]{text_color.RESET} '
            elif kwargs['status'] == 'warning':
                dressing = f'{dressing}{text_color.B_DARK}[{text_color.B_WARNING}!{text_color.B_DARK}]{text_color.RESET} '
            elif kwargs['status'] == 'fail':
                dressing = f'{dressing}{text_color.B_DARK}[{text_color.B_FAIL}✗{text_color.B_DARK}]{text_color.RESET} '
        else:
            dressing = f'{dressing}{text_color.HLIGHT}'
        print(f'{dressing}{message}{text_color.RESET}')
    stdout.flush()