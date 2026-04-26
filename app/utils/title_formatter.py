# Mirrors calendar-manager-service/internal/ical/formatter.go to keep
# event/subject titles consistent across services


def format_event_title(title: str) -> str:
    if not title:
        return title

    lower = title.lower()
    result = []
    capitalize = True

    for ch in lower:
        if capitalize and ch.isalpha():
            result.append(ch.upper())
            capitalize = False
        else:
            result.append(ch)

        if ch in ('.', '(', '/'):
            capitalize = True

    return ''.join(result)
