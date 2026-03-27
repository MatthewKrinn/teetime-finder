from tee_time_finder.providers.html_regex import HtmlRegexProvider
from tee_time_finder.providers.json_api import JsonApiProvider
from tee_time_finder.providers.site_family import SiteFamilyProvider
from tee_time_finder.providers.tenfore import TenForeProvider
from tee_time_finder.providers.teeitup import TeeItUpProvider

provider_registry = {
    "json_api": JsonApiProvider(),
    "html_regex": HtmlRegexProvider(),
    "tenfore": TenForeProvider(),
    "teeitup": TeeItUpProvider(),
    "golfnow": SiteFamilyProvider(),
}
