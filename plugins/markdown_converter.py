import markdown


def init(register):
    md = markdown.Markdown()

    register.converter('.md', md.convert)
    register.converter('.markdown', md.convert)
