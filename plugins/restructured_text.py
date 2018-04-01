import docutils.core


def convert(content: str) -> str:
    return docutils.core.publish_parts(content,
                                       writer_name='html')['html_body']


def init(register):
    register.converter('.rst', convert)
