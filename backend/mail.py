from __future__ import annotations

import logging

import httpx

from .settings import (
    APP_URL,
    MAIL_FROM,
    RESEND_API_KEY,
    SMTP_HOST,
    SMTP_PASS,
    SMTP_PORT,
    SMTP_USER,
)

log = logging.getLogger(__name__)


def _wrap(inner: str, preheader: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="uk"><body style="margin:0;padding:0;background:#EEF1FA;">
<div style="display:none;max-height:0;overflow:hidden;opacity:0;">{preheader}</div>
<table role="presentation" width="100%" style="background:#EEF1FA;"><tr><td align="center" style="padding:28px 14px 60px;">
<table role="presentation" width="100%" style="max-width:540px;">
<tr><td style="padding:0 6px 18px;font-family:Arial,sans-serif;font-size:20px;font-weight:bold;color:#0A0B0E;">flix<span style="color:#2B5CF6;">маркет</span></td></tr>
<tr><td style="background:#FFFFFF;border-radius:24px;padding:34px 30px;font-family:Arial,sans-serif;color:#232838;">{inner}</td></tr>
</table></td></tr></table></body></html>"""


def _btn(url: str, label: str) -> str:
    return (
        f'<p><a href="{url}" style="display:inline-block;padding:15px 30px;background:#2B5CF6;'
        f'border-radius:999px;color:#fff;text-decoration:none;font-weight:bold;">{label}</a></p>'
    )


async def send(to: str, subject: str, html: str):
    if RESEND_API_KEY:
        async with httpx.AsyncClient(timeout=20) as client:
            res = await client.post(
                "https://api.resend.com/emails",
                headers={"Authorization": f"Bearer {RESEND_API_KEY}", "Content-Type": "application/json"},
                json={"from": MAIL_FROM, "to": [to], "subject": subject, "html": html},
            )
        if res.status_code >= 400:
            raise RuntimeError(f"Resend {res.status_code}: {res.text}")
        return
    if SMTP_HOST:
        import smtplib
        from email.mime.multipart import MIMEMultipart
        from email.mime.text import MIMEText

        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = MAIL_FROM
        msg["To"] = to
        msg.attach(MIMEText(html, "html", "utf-8"))
        with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT) as smtp:
            smtp.login(SMTP_USER, SMTP_PASS)
            smtp.sendmail(SMTP_USER, [to], msg.as_string())
        return
    log.info("[mail:dev] → %s · %s", to, subject)


async def send_verify(to: str, token: str):
    url = f"{APP_URL}/api/auth/verify?token={token}"
    html = _wrap(f"<h1>Підтверди пошту</h1><p>Один клік — і акаунт активний.</p>{_btn(url, 'Підтвердити пошту')}", "Підтверди пошту")
    await send(to, "Підтверди пошту", html)


async def send_welcome(to: str):
    html = _wrap(f"<h1>Привіт, ти з нами</h1><p>Акаунт створено. У кабінеті видно всі підписки.</p>{_btn(f'{APP_URL}/cabinet', 'Відкрити кабінет')}", "Ласкаво просимо")
    await send(to, "Привіт, ти з нами", html)


async def send_reset(to: str, token: str):
    url = f"{APP_URL}/reset?token={token}"
    html = _wrap(f"<h1>Новий пароль</h1><p>Якщо це ти — тисни кнопку.</p>{_btn(url, 'Задати новий пароль')}", "Скидання пароля")
    await send(to, "Скидання пароля", html)


async def send_login(to: str, when: str, ip: str):
    html = _wrap(f"<h1>Новий вхід</h1><p>{when}<br>IP: {ip}</p>{_btn(f'{APP_URL}/login', 'Відкрити вхід')}", "Новий вхід у акаунт")
    await send(to, "Новий вхід у твій акаунт", html)
