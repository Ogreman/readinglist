
def init_app(app):
    app.jinja_env.filters['duration'] = do_duration


def do_duration(seconds):
    """Jinja template filter to format seconds to humanized duration.

    3600 becomes "1 hour".
    258732 becomes "2 days, 23 hours, 52 minutes, 12 seconds".
    """
    m, s = divmod(seconds, 60)
    h, m = divmod(m, 60)
    d, h = divmod(h, 24)
    tokens = []
    if d > 1:
        tokens.append('{d} days')
    elif d:
        tokens.append('{d} day')
    if h > 1:
        tokens.append('{h} hours')
    elif h:
        tokens.append('{h} hour')
    if m > 1:
        tokens.append('{m} minutes')
    elif m:
        tokens.append('{m} minute')
    if s > 1:
        tokens.append('{s} seconds')
    elif s:
        tokens.append('{s} second')
    template = ', '.join(tokens)
    return template.format(d=d, h=h, m=m, s=s)
