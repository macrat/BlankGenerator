import typing

import docutils.core
import docutils.parsers.rst
import docutils.nodes
import jmespath


def convert(content: str, context: typing.Mapping[str, typing.Any]) -> str:
    """
    >>> convert('hello :var:`name`!', {'name': 'world'})
    '<div class="document">\\n<p>hello <span>world</span>!</p>\\n</div>\\n'
    """

    def var_role(name: str,
                 rawtext: str,
                 text: str,
                 lineno: int,
                 inliner: docutils.parsers.rst.states.Inliner,
                 options: typing.Mapping[str, typing.Any] = {},
                 content: typing.List[str] = []) -> typing.Tuple:

        try:
            value = jmespath.search(text, context)
        except:
            msg = inliner.reporter.error(
                'invalid query: {}'.format(repr(text)),
                line=lineno,
            )
            prb = inliner.problematic(rawtext, rawtext, msg)
            return [prb], [msg]

        if value is None:
            return [], []
        else:
            return [docutils.nodes.inline(rawtext, str(value))], []

    docutils.parsers.rst.roles.register_local_role('var', var_role)

    return docutils.core.publish_parts(content,
                                       writer_name='html')['html_body']


def init(register):
    register.converter('.rst', convert)
