"""Shared HTML metadata and safe JSON-LD serialization for generated pages."""
import json


TEXT_TEMPLATE_KEYS = {
    'TITLE', 'DESCRIPTION', 'CANONICAL', 'H1', 'SUBTITLE', 'BACK_LINK', 'BACK_LABEL',
    'BODY_CLASS', 'SOCIAL_IMAGE', 'SOCIAL_IMAGE_ALT', 'ICS_DOWNLOAD',
    'ICS_SUBSCRIPTION_WEBCAL', 'ICS_SUBSCRIPTION_GOOGLE',
}


def script_json(value) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2).replace('<', '\\u003c')


def jsonld_script(value) -> str:
    return '<script type="application/ld+json">\n' + script_json(value) + '\n</script>'


def breadcrumbs_jsonld(items) -> str:
    return jsonld_script({
        '@context': 'https://schema.org',
        '@type': 'BreadcrumbList',
        'itemListElement': [
            {'@type': 'ListItem', 'position': position, 'name': name, 'item': url}
            for position, (name, url) in enumerate(items, start=1)
        ],
    })


def page_jsonld(meta, base_url: str) -> str:
    home = base_url.rstrip('/') + '/'
    canonical = meta['CANONICAL']
    organization = 'https://litovle.cz/#organization'
    website = home + '#website'
    return jsonld_script({
        '@context': 'https://schema.org',
        '@graph': [
            {
                '@type': 'Organization', '@id': organization, 'name': 'Litovle.cz',
                'url': 'https://litovle.cz/',
                'description': 'Nezávislá občanská iniciativa.',
            },
            {
                '@type': 'WebSite', '@id': website, 'name': 'Svoz odpadu Litovel',
                'url': home, 'inLanguage': 'cs', 'publisher': {'@id': organization},
            },
            {
                '@type': 'CollectionPage' if canonical in {home, home + 'bio/'} else 'WebPage',
                '@id': canonical + '#webpage', 'url': canonical,
                'name': meta.get('H1') or meta['TITLE'], 'description': meta['DESCRIPTION'],
                'inLanguage': 'cs', 'isPartOf': {'@id': website},
                'publisher': {'@id': organization},
            },
        ],
    })
