"""
Embedded videos: parse a pasted link into (provider, external_id), confirm the
video exists via the platform's public oEmbed lookup, and build player URLs.
Players are always built from provider + id; oEmbed HTML is never stored or rendered.
"""

import re
from typing import NamedTuple
from urllib.parse import parse_qs, urlparse

import requests
from django.conf import settings


class EmbedError(Exception):
    """A user-facing problem with an embed link."""


class ParsedEmbed(NamedTuple):
    provider: str
    external_id: str
    canonical_url: str


PROVIDER_LABELS = {
    'youtube': 'YouTube',
    'vimeo': 'Vimeo',
    'tiktok': 'TikTok',
    'instagram': 'Instagram',
}

YOUTUBE_ID = r'[A-Za-z0-9_-]{11}'
OEMBED_TIMEOUT_SECONDS = 6


def _normalise_host(hostname):
    host = (hostname or '').lower()
    for prefix in ('www.', 'm.'):
        if host.startswith(prefix):
            host = host[len(prefix):]
    return host


def parse_embed_url(raw_url):
    """Return a ParsedEmbed for a supported link, or raise EmbedError."""
    url = (raw_url or '').strip()
    if not url:
        raise EmbedError('Enter a video link.')

    parsed = urlparse(url if '://' in url else f'https://{url}')
    if parsed.scheme not in ('http', 'https') or not parsed.hostname:
        raise EmbedError('Enter a valid link.')

    host = _normalise_host(parsed.hostname)
    path = parsed.path.rstrip('/')
    query = parse_qs(parsed.query)

    # ── YouTube ──
    if host in ('youtube.com', 'music.youtube.com', 'youtube-nocookie.com'):
        if path == '/watch':
            video_id = query.get('v', [''])[0]
        else:
            match = re.fullmatch(rf'/(?:shorts|embed|live|v)/({YOUTUBE_ID})', path)
            video_id = match.group(1) if match else ''

        if re.fullmatch(YOUTUBE_ID, video_id):
            return ParsedEmbed('youtube', video_id, f'https://www.youtube.com/watch?v={video_id}')
        raise EmbedError("This doesn't look like a YouTube video link.")

    if host == 'youtu.be':
        match = re.fullmatch(rf'/({YOUTUBE_ID})', path)
        if match:
            video_id = match.group(1)
            return ParsedEmbed('youtube', video_id, f'https://www.youtube.com/watch?v={video_id}')
        raise EmbedError("This doesn't look like a YouTube video link.")

    # ── Vimeo (unlisted videos carry a privacy hash) ──
    if host in ('vimeo.com', 'player.vimeo.com'):
        match = re.fullmatch(
            r'(?:/video|/channels/[\w-]+|/groups/[\w-]+/videos)?/(\d+)(?:/([0-9a-f]+))?',
            path,
        )
        if match:
            video_id = match.group(1)
            privacy_hash = match.group(2) or query.get('h', [''])[0]
            if privacy_hash and not re.fullmatch(r'[0-9a-f]+', privacy_hash):
                privacy_hash = ''

            external_id = f'{video_id}:{privacy_hash}' if privacy_hash else video_id
            canonical = f'https://vimeo.com/{video_id}' + (f'/{privacy_hash}' if privacy_hash else '')
            return ParsedEmbed('vimeo', external_id, canonical)
        raise EmbedError("This doesn't look like a Vimeo video link.")

    # ── TikTok (full links only: short links hide the id behind a redirect) ──
    if host in ('vm.tiktok.com', 'vt.tiktok.com'):
        raise EmbedError(
            "Short TikTok links aren't supported. Open the video and copy the full link "
            "(tiktok.com/@name/video/…)."
        )

    if host == 'tiktok.com':
        match = re.fullmatch(r'/@([\w.-]+)/video/(\d+)', path)
        if match:
            username, video_id = match.groups()
            return ParsedEmbed('tiktok', video_id, f'https://www.tiktok.com/@{username}/video/{video_id}')
        raise EmbedError(
            "This doesn't look like a TikTok video link. Use the full link (tiktok.com/@name/video/…)."
        )

    # ── Instagram (posts, reels, IGTV) ──
    if host == 'instagram.com':
        match = re.fullmatch(r'(?:/[\w.]+)?/(?:p|reel|reels|tv)/([A-Za-z0-9_-]+)', path)
        if match:
            code = match.group(1)
            return ParsedEmbed('instagram', code, f'https://www.instagram.com/p/{code}/')
        raise EmbedError("This doesn't look like an Instagram post or reel link.")

    raise EmbedError('Use a link from YouTube, Vimeo, TikTok or Instagram.')


def _oembed_endpoint(provider):
    return {
        'youtube': 'https://www.youtube.com/oembed',
        'vimeo': 'https://vimeo.com/api/oembed.json',
        'tiktok': 'https://www.tiktok.com/oembed',
        'instagram': getattr(
            settings,
            'INSTAGRAM_OEMBED_URL',
            'https://graph.facebook.com/v26.0/instagram_oembed',
        ),
    }[provider]


def verify_embed(parsed):
    """
    Confirm the video exists and can be embedded, via the platform's oEmbed lookup.
    Only ever calls the four fixed platform endpoints (no user-controlled hosts).
    """
    if not getattr(settings, 'VIDEO_EMBED_CHECK', True):
        return

    label = PROVIDER_LABELS[parsed.provider]

    try:
        response = requests.get(
            _oembed_endpoint(parsed.provider),
            params={'url': parsed.canonical_url, 'format': 'json'},
            timeout=OEMBED_TIMEOUT_SECONDS,
        )
    except requests.RequestException:
        raise EmbedError(f"We couldn't reach {label} to check this link. Please try again.")

    if response.status_code == 200:
        return

    if response.status_code in (400, 401, 403, 404):
        raise EmbedError(
            "We couldn't find this video. Check the link, and that the video is public "
            "and allows embedding."
        )

    # 429 (rate limited), 5xx: the platform, not the link
    raise EmbedError(f"{label} couldn't check this link right now. Please try again in a moment.")


def build_player_url(provider, external_id):
    """The iframe URL for an embedded video, built only from provider + id."""
    if not (provider and external_id):
        return ''

    if provider == 'youtube':
        return f'https://www.youtube-nocookie.com/embed/{external_id}'

    if provider == 'vimeo':
        video_id, _, privacy_hash = external_id.partition(':')
        return f'https://player.vimeo.com/video/{video_id}' + (f'?h={privacy_hash}' if privacy_hash else '')

    if provider == 'tiktok':
        return f'https://www.tiktok.com/embed/v2/{external_id}'

    if provider == 'instagram':
        return f'https://www.instagram.com/p/{external_id}/embed'

    return ''