import markdown

import register


register.mimetype('text/markdown', '.md')
register.mimetype('text/markdown', '.markdown')


md = markdown.Markdown()


@register.converter('text/markdown')
def convert(content: str) -> str:
    return md.convert(content)
