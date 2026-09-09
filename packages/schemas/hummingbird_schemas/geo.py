"""Nigeria state approximate centroids (WGS84) for geocoding fallbacks."""

STATE_CENTROIDS: dict[str, tuple[float, float]] = {
    "Abia": (5.4527, 7.5248),
    "Adamawa": (9.3265, 12.3984),
    "Akwa Ibom": (5.0077, 7.8530),
    "Anambra": (6.2209, 6.9370),
    "Bauchi": (10.3158, 9.8442),
    "Bayelsa": (4.7719, 6.0699),
    "Benue": (7.3369, 8.7404),
    "Borno": (11.8846, 13.1519),
    "Cross River": (5.8702, 8.5988),
    "Delta": (5.7040, 5.9339),
    "Ebonyi": (6.2649, 8.0137),
    "Edo": (6.5244, 5.8987),
    "Ekiti": (7.6656, 5.3103),
    "Enugu": (6.5364, 7.4356),
    "FCT": (9.0765, 7.3986),
    "Federal Capital Territory": (9.0765, 7.3986),
    "Gombe": (10.2791, 11.1731),
    "Imo": (5.5720, 7.0588),
    "Jigawa": (12.2280, 9.5616),
    "Kaduna": (10.5105, 7.4165),
    "Kano": (11.7471, 8.5247),
    "Katsina": (12.9908, 7.6006),
    "Kebbi": (11.4942, 4.2333),
    "Kogi": (7.7960, 6.7340),
    "Kwara": (8.9669, 4.3874),
    "Lagos": (6.5244, 3.3792),
    "Nasarawa": (8.4991, 8.5150),
    "Niger": (9.9309, 5.5983),
    "Ogun": (6.9098, 3.2584),
    "Ondo": (7.1000, 5.0500),
    "Osun": (7.5629, 4.5200),
    "Oyo": (8.1574, 3.6147),
    "Plateau": (9.2182, 9.5179),
    "Rivers": (4.8156, 6.9990),
    "Sokoto": (13.0533, 5.3223),
    "Taraba": (8.0000, 10.7000),
    "Yobe": (12.0000, 11.5000),
    "Zamfara": (12.1222, 6.2236),
    # National aggregates (no specific state) — country centroid, not an LGA pin
    "Nigeria": (9.0820, 8.6753),
}


def normalize_state(name: str) -> str:
    key = name.strip()
    for s in STATE_CENTROIDS:
        if s.lower() == key.lower():
            return "FCT" if s == "Federal Capital Territory" else s
    return key.title()


def centroid_for_state(state: str) -> tuple[float, float] | None:
    normalized = normalize_state(state)
    return STATE_CENTROIDS.get(normalized) or STATE_CENTROIDS.get(state)
