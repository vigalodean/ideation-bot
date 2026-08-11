import time
import re
import random
import logging
from datetime import datetime
import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}

# Theme keys mapped directly to Straits Times Singapore sub-category URLs
THEME_MAP = {
    "environment": {
        "name": "🌿 Environment & Sustainability",
        "path": "environment",
        "description": "Green Plan 2030, recycling, climate adaptation, and conservation news."
    },
    "health": {
        "name": "🧠 Health & Wellness",
        "path": "health",
        "description": "Healthcare, mental well-being, hospitals, and medical research news."
    },
    "education": {
        "name": "📚 Parenting & Education",
        "path": "parenting-education",
        "description": "Schools, youth, parenting, and education policy news."
    },
    "community": {
        "name": "🎨 Community, Arts & Heritage",
        "path": "community",
        "description": "Arts, local culture, heritage trails, and estate community news."
    },
    "transport": {
        "name": "🚌 Urban Mobility & Transport",
        "path": "transport",
        "description": "Public transport, cycling paths, EV infrastructure, and traffic news."
    },
    "housing": {
        "name": "🏠 Housing & Estate Living",
        "path": "housing",
        "description": "HDB estates, town council initiatives, and urban living news."
    },
    "jobs": {
        "name": "💼 Jobs & Economy",
        "path": "jobs",
        "description": "Employment, workforce reskilling, gig economy, and workplace news."
    },
    "crime": {
        "name": "🛡️ Scam & Safety Prevention",
        "path": "courts-crime",
        "description": "Anti-scam initiatives, public safety, and law enforcement news."
    }
}

# Cache of candidate (headline, url) pairs per theme, to avoid re-fetching the
# section page on every request. The final set of articles shown is randomly
# sampled from these candidates on each call, so repeat requests for the same
# theme surface different headlines instead of always the same top few.
_SECTION_CACHE = {}
CACHE_TTL_SECONDS = 3600


def parse_st_date(text: str):
    """Extracts date from Straits Times text and checks if within last year."""
    match = re.search(r'Published\s*([A-Za-z]+\s+\d{1,2},\s+\d{4})', text) or re.search(r'([A-Z][a-z]{2}\s+\d{1,2},\s+\d{4})', text)
    if match:
        date_str = match.group(1)
        try:
            dt = datetime.strptime(date_str, "%b %d, %Y")
            return dt, date_str
        except Exception:
            pass
    return None, "Recent ST News"


def get_live_articles_for_theme(theme_key: str, max_articles: int = 5):
    """
    Scrapes live Straits Times news articles for a given theme category under /singapore/.
    Only returns articles published within the last 1 year (365 days).
    """
    theme_info = THEME_MAP.get(theme_key)
    if not theme_info:
        logger.error(f"Unknown theme_key: {theme_key}")
        return []

    # Check cache for the candidate headline/url pool (not the final articles,
    # so the sample shown to the user still varies between requests)
    now_ts = time.time()
    if theme_key in _SECTION_CACHE and now_ts - _SECTION_CACHE[theme_key]["timestamp"] < CACHE_TTL_SECONDS:
        candidates = _SECTION_CACHE[theme_key]["candidates"]
        logger.info(f"Using cached ST candidate pool for theme '{theme_key}' ({len(candidates)} candidates)")
    else:
        subcat = theme_info["path"]
        section_url = f"https://www.straitstimes.com/singapore/{subcat}"
        logger.info(f"Fetching Straits Times section page: {section_url}")

        try:
            resp = requests.get(section_url, headers=HEADERS, timeout=10)
            resp.raise_for_status()
        except Exception as e:
            logger.error(f"Failed to fetch {section_url}: {e}")
            return []

        soup = BeautifulSoup(resp.text, "html.parser")
        candidates = []
        seen_urls = set()

        for a in soup.find_all("a", href=True):
            href = a["href"]
            text = a.get_text(strip=True)
            if "/singapore/" in href and text and len(text) > 15:
                full_url = href if href.startswith("http") else f"https://www.straitstimes.com{href}"
                # Ensure it's an article page (contains subcat path or article slug)
                if full_url not in seen_urls and len(full_url.split("/")) > 4:
                    seen_urls.add(full_url)
                    candidates.append((text, full_url))

        _SECTION_CACHE[theme_key] = {"timestamp": now_ts, "candidates": candidates}

    # Randomize order so repeat requests don't always surface the same top
    # headlines, then walk the shuffled pool until we have enough articles
    # (skipping any that fail to fetch or fall outside the 1-year window).
    shuffled_candidates = candidates.copy()
    random.shuffle(shuffled_candidates)

    articles = []
    now_dt = datetime.now()

    for headline, link in shuffled_candidates:
        if len(articles) >= max_articles:
            break
        try:
            art_resp = requests.get(link, headers=HEADERS, timeout=5)
            if art_resp.status_code != 200:
                continue

            art_soup = BeautifulSoup(art_resp.text, "html.parser")
            h1 = art_soup.find("h1")
            clean_headline = h1.get_text(strip=True) if h1 else headline

            # Parse published date
            page_text = art_soup.get_text()
            dt, date_formatted = parse_st_date(page_text)

            # Strict 1-year date filter
            if dt:
                days_old = (now_dt - dt).days
                if days_old > 365:
                    logger.info(f"Skipping article '{clean_headline}' - {days_old} days old (>1 year)")
                    continue

            # Extract lead paragraphs as article summary context
            paras = [
                p.get_text(strip=True)
                for p in art_soup.find_all("p")
                if len(p.get_text(strip=True)) > 40
            ]
            summary = " ".join(paras[:2]) if paras else clean_headline

            articles.append({
                "headline": clean_headline,
                "url": link,
                "date": date_formatted,
                "summary": summary,
                "theme_key": theme_key,
                "theme_name": theme_info["name"]
            })
        except Exception as e:
            logger.warning(f"Error scraping article {link}: {e}")
            continue

    return articles
