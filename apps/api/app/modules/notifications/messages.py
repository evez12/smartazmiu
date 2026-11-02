"""Push and e-mail wording per notification kind and recipient locale (the in-app text lives in the web app)."""

from dataclasses import dataclass

from app.core.i18n import DEFAULT_LANGUAGE
from app.modules.notifications.models import Notification, NotificationKind

KIND_LABELS: dict[NotificationKind, dict[str, str]] = {
    NotificationKind.ANNOUNCEMENT_PUBLISHED: {
        "az": "Yeni elan",
        "en": "New announcement",
        "ru": "Новое объявление",
    },
    NotificationKind.EVENT_PUBLISHED: {
        "az": "Yeni tədbir",
        "en": "New event",
        "ru": "Новое мероприятие",
    },
    NotificationKind.EVENT_CHANGED: {
        "az": "Tədbirdə dəyişiklik",
        "en": "Event changed",
        "ru": "Изменение в мероприятии",
    },
    NotificationKind.EVENT_CANCELLED: {
        "az": "Tədbir ləğv edildi",
        "en": "Event cancelled",
        "ru": "Мероприятие отменено",
    },
    NotificationKind.SCHEDULE_CHANGED: {
        "az": "Dərs cədvəlində dəyişiklik",
        "en": "Class schedule changed",
        "ru": "Изменение в расписании занятий",
    },
    NotificationKind.CHAT_MENTION: {
        "az": "Sizi çatda qeyd etdilər",
        "en": "You were mentioned in a chat",
        "ru": "Вас упомянули в чате",
    },
    NotificationKind.CHAT_REPLY: {
        "az": "Mesajınıza cavab yazdılar",
        "en": "Someone replied to your message",
        "ru": "На ваше сообщение ответили",
    },
    NotificationKind.CHAT_ATTACHMENT_REJECTED: {
        "az": "Fayl göstərilmir",
        "en": "A file is not shown",
        "ru": "Файл не отображается",
    },
    NotificationKind.MATERIAL_VERSION_REJECTED: {
        "az": "Material versiyası qəbul olunmadı",
        "en": "Material version not accepted",
        "ru": "Версия материала не принята",
    },
    NotificationKind.MENTORSHIP_INVITATION: {
        "az": "Bələdçi olmağa dəvət",
        "en": "Invitation to become a guide",
        "ru": "Приглашение стать наставником",
    },
    NotificationKind.MENTORSHIP_REQUEST_RECEIVED: {
        "az": "Yeni məsləhət sorğusu",
        "en": "New advice request",
        "ru": "Новый запрос совета",
    },
    NotificationKind.MENTORSHIP_REQUEST_ACCEPTED: {
        "az": "Məsləhət sorğunuz qəbul edildi",
        "en": "Your advice request was accepted",
        "ru": "Ваш запрос совета принят",
    },
    NotificationKind.MENTORSHIP_REQUEST_DECLINED: {
        "az": "Məsləhət sorğunuz qəbul edilmədi",
        "en": "Your advice request was declined",
        "ru": "Ваш запрос совета отклонён",
    },
    NotificationKind.MENTORSHIP_REQUEST_EXPIRED: {
        "az": "Məsləhət sorğunuzun vaxtı bitdi",
        "en": "Your advice request expired",
        "ru": "Срок вашего запроса совета истёк",
    },
    NotificationKind.MENTORSHIP_ADVICE_POST: {
        "az": "#məsləhət bölməsində yeni sual",
        "en": "New question in #məsləhət",
        "ru": "Новый вопрос в #məsləhət",
    },
    NotificationKind.MENTORSHIP_TIP_PROMPT: {
        "az": "Fənn kartını doldurun",
        "en": "Fill in the subject card",
        "ru": "Заполните карточку дисциплины",
    },
    NotificationKind.CHAT_ANSWER_VERIFIED: {
        "az": "Sualınıza təsdiqlənmiş cavab verildi",
        "en": "Your question has a verified answer",
        "ru": "На ваш вопрос дан подтверждённый ответ",
    },
    NotificationKind.EXAM_SCHEDULED: {
        "az": "Yeni imtahan vaxtı",
        "en": "New exam time",
        "ru": "Новое время экзамена",
    },
    NotificationKind.EXAM_MOVED: {
        "az": "İmtahan vaxtı dəyişdi",
        "en": "Exam time changed",
        "ru": "Время экзамена изменено",
    },
    NotificationKind.PAST_PAPER_APPROVED: {
        "az": "İmtahan kağızınız təsdiqləndi",
        "en": "Your past exam paper was approved",
        "ru": "Ваша работа прошлых лет одобрена",
    },
    NotificationKind.PAST_PAPER_REJECTED: {
        "az": "İmtahan kağızınız qəbul olunmadı",
        "en": "Your past exam paper was not accepted",
        "ru": "Ваша работа прошлых лет не принята",
    },
}

# {label}, {name}, {url} and {settings_url} are filled in; every locale keeps the same four facts.
EMAIL_BODY: dict[str, str] = {
    "az": (
        "Hörmətli {name},\n\n"
        "{label}: {title}\n\n"
        "Ətraflı məlumat: {url}\n\n"
        "Bu məktub SmartAzMİU tərəfindən avtomatik göndərilib; cavab yazmağa ehtiyac yoxdur.\n"
        "Bildiriş ayarlarınızı dəyişmək üçün: {settings_url}\n"
    ),
    "en": (
        "Dear {name},\n\n"
        "{label}: {title}\n\n"
        "Details: {url}\n\n"
        "SmartAzMİU sent this message automatically; there is no need to reply.\n"
        "To change your notification settings: {settings_url}\n"
    ),
    "ru": (
        "Здравствуйте, {name}.\n\n"
        "{label}: {title}\n\n"
        "Подробности: {url}\n\n"
        "Это письмо отправлено системой SmartAzMİU автоматически, отвечать на него не нужно.\n"
        "Изменить настройки уведомлений можно здесь: {settings_url}\n"
    ),
}


@dataclass(frozen=True, slots=True)
class Email:
    subject: str
    text: str


def _language(locale: str | None) -> str:
    return locale if locale in EMAIL_BODY else DEFAULT_LANGUAGE


def kind_label(kind: NotificationKind, locale: str | None) -> str:
    return KIND_LABELS[kind][_language(locale)]


def push_payload(notification: Notification, url: str, locale: str | None) -> dict[str, str]:
    # Lock screens show this text, so it carries no more than the in-app row does.
    return {
        "title": kind_label(notification.kind, locale),
        "body": notification.title,
        "url": url,
        "tag": str(notification.id),
    }


def email(
    notification: Notification,
    recipient_name: str,
    url: str,
    settings_url: str,
    locale: str | None,
) -> Email:
    label = kind_label(notification.kind, locale)
    return Email(
        subject=f"{label}: {notification.title}",
        text=EMAIL_BODY[_language(locale)].format(
            name=recipient_name,
            label=label,
            title=notification.title,
            url=url,
            settings_url=settings_url,
        ),
    )
