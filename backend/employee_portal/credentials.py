"""Login details for joiners and buddies: their candidate or employee id is the username, and a
password made once for them is the password. COMPASS emails both when the Program admin adds them,
and sends the same ones again when asked."""
import logging

from notifications import emails

logger = logging.getLogger(__name__)


def issue_login(person, kind: str) -> bool:
    """Email the person their username and their one password (made now if they have none yet).
    Returns True if sent. The person is already saved, so an email problem is logged instead of
    undoing anything."""
    password = person.fixed_password()
    try:
        return emails.send_login_details(person, kind, password, emails.stamp())
    except Exception:
        logger.exception("Could not email login details to %s %s", kind, person.pk)
        return False
