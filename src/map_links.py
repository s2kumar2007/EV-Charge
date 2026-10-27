"""Open existing source coordinates in Google Maps without a paid API."""
import html
import math
from urllib.parse import urlencode
import config


def google_links(latitude,longitude):
    if not config.GOOGLE_MAPS_LINKS_ENABLED:
        return ''
    if not math.isfinite(float(latitude)) or not math.isfinite(float(longitude)):
        raise ValueError('Google Maps links need finite coordinates')
    position=f'{latitude},{longitude}'
    search=config.GOOGLE_MAPS_SEARCH_URL+'?'+urlencode({'api':config.GOOGLE_MAPS_URL_VERSION,'query':position})
    directions=config.GOOGLE_MAPS_DIRECTIONS_URL+'?'+urlencode({'api':config.GOOGLE_MAPS_URL_VERSION,'destination':position,'travelmode':config.GOOGLE_MAPS_TRAVEL_MODE})
    # These links transfer coordinates only after the user chooses to open them.
    return '<br>'+ ' | '.join(f'<a href="{html.escape(url,quote=True)}" target="_blank" rel="noopener noreferrer">{label}</a>' for url,label in [(search,'Open in Google Maps'),(directions,'Directions')])
