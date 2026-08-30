"""Mail reply routing policy: single source for the operator reply address.

OPERATOR_EMAIL is the owner-approved public operator address (already
published in docs/legal.html and SECURITY.md). Transactional and campaign
mails route Reply-To here so replies reach the operator instead of
noreply@ekklesia.gr.
"""

OPERATOR_EMAIL: str = "kaspartisan@proton.me"


def operator_reply_to() -> dict[str, str]:
    """Brevo transactional (smtp/email) replyTo object."""
    return {"email": OPERATOR_EMAIL}
