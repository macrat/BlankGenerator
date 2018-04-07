import jinja2


def converter(content, context):
    """
    >>> converter('hello {{ name }}!', {'name': 'world'})
    'hello world!'
    """

    return jinja2.Template(content).render(context)


def init(register):
    register.converter('.html', converter)
