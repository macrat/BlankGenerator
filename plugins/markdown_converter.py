import markdown


def init(register):
    md = markdown.Markdown()

    register.converter('.md', (lambda content, context: md.convert(content)))
    register.converter('.markdown',
                       (lambda content, context: md.convert(content)))
