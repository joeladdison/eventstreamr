from duration import str2delta


def prompt(string, default=None):
    """ Return user input, or default value if they just press enter """
    if default is not None:
        return raw_input("{0} [{1}]: ".format(string, default)) or str(default)
    else:
        return raw_input("{0}: ".format(string))


def prompt_for_number(string, default=None):
    """ Return user input as an int if possible, else None """
    response = prompt(string, default)
    try:
        return int(response)
    except ValueError:
        return None


def prompt_for_time(string, default=None):
    """ Return user imput as a datetime if possible, else None"""
    response = prompt(string, default)
    try:
        return str2delta(response)
    except ValueError:
        return None
