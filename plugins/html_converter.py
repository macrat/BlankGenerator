import jinja2


def converter(content, context):
    return jinja2.Template(content).render(context)


def init(register):
    register.converter('.html', converter)
