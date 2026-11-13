import nh3

RICH_TEXT_TAGS = {
    'p',
    'br',
    'h2',
    'h3',
    'strong',
    'em',
    'ul',
    'ol',
    'li',
    'blockquote',
    'a',
}

RICH_TEXT_ATTRIBUTES = {
    'a': {'href', 'title', 'target'},
}

RICH_TEXT_URL_SCHEMES = {'http', 'https', 'mailto'}

def sanitize_rich_text(html:str) -> str:
    if not html:
        return ''

    return nh3.clean(
        html,
        tags=RICH_TEXT_TAGS,
        attributes=RICH_TEXT_ATTRIBUTES,
        url_schemes=RICH_TEXT_URL_SCHEMES,
        link_rel='noopener noreferrer'
    ).strip()


def rich_text_is_empty(html:str) -> bool:
    text_only = nh3.clean(html or '',tags=set())
    return not text_only.replace('&nbsp;','').strip()