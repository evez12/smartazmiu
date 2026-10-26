DEFAULT_LANGUAGE = "az"
SUPPORTED_LANGUAGES = ("az", "en")

# User-facing error messages per stable error code. Codes stay in English and never reach the UI text.
ERROR_MESSAGES: dict[str, dict[str, str]] = {
    "auth.unauthenticated": {
        "az": "Sessiyanızın müddəti bitib. Yenidən daxil olun.",
        "en": "Your session has expired. Please sign in again.",
    },
    "auth.forbidden": {
        "az": "Bu əməliyyat üçün icazəniz yoxdur. Lazım olduqda dekanlığa müraciət edin.",
        "en": "You do not have permission for this action. Contact the dean's office if you need it.",
    },
    "auth.account_inactive": {
        "az": "Hesabınız aktiv deyil. Ətraflı məlumat üçün dekanlığa müraciət edin.",
        "en": "Your account is not active. Contact the dean's office for details.",
    },
    "auth.identity_conflict": {
        "az": "Hesabınızın e-poçt ünvanı başqa bir hesabda istifadə olunur. İT xidmətinə müraciət edin.",
        "en": "Your account's e-mail address is used by another account. Contact IT support.",
    },
    "request.validation_failed": {
        "az": "Göndərilən məlumatlarda səhv var. Sahələri yoxlayıb yenidən cəhd edin.",
        "en": "Some of the submitted data is invalid. Check the fields and try again.",
    },
    "request.not_found": {
        "az": "Axtardığınız məlumat tapılmadı.",
        "en": "The requested item was not found.",
    },
    "request.method_not_allowed": {
        "az": "Bu sorğu növü dəstəklənmir.",
        "en": "This request method is not supported.",
    },
    "request.failed": {
        "az": "Sorğunu yerinə yetirmək mümkün olmadı. Yenidən cəhd edin.",
        "en": "The request could not be completed. Please try again.",
    },
    "request.rate_limited": {
        "az": "Çox sayda sorğu göndərdiniz. Bir az gözləyib yenidən cəhd edin.",
        "en": "Too many requests. Wait a little and try again.",
    },
    "schedule.invalid_range": {
        "az": "Tarix aralığı düzgün deyil. Son tarix başlanğıcdan sonra və ən çox 42 gün sonra olmalıdır.",
        "en": "The date range is invalid. The end must follow the start by at most 42 days.",
    },
    "audience.invalid": {
        "az": "Seçilmiş auditoriya tapılmadı. Auditoriyanı yenidən seçin.",
        "en": "The selected audience was not found. Choose the audience again.",
    },
    "announcements.expiry_in_past": {
        "az": "Elanın bitmə vaxtı keçmişdədir. Gələcək bir tarix seçin.",
        "en": "The announcement's end time is in the past. Choose a future date.",
    },
    "announcements.archived": {
        "az": "Bu elan arxivə köçürülüb və dəyişdirilə bilməz.",
        "en": "This announcement has been archived and cannot be changed.",
    },
    "announcements.version_conflict": {
        "az": "Elan bu arada başqa biri tərəfindən dəyişdirilib. Səhifəni yeniləyib yenidən cəhd edin.",
        "en": "Someone else changed the announcement in the meantime. Reload the page and try again.",
    },
    "events.starts_in_past": {
        "az": "Tədbirin başlama vaxtı keçmişdədir. Gələcək bir vaxt seçin.",
        "en": "The event's start time is in the past. Choose a future time.",
    },
    "events.invalid_times": {
        "az": "Bitmə vaxtı başlama vaxtından sonra olmalıdır.",
        "en": "The end time must be after the start time.",
    },
    "events.location_required": {
        "az": "Tədbirin keçiriləcəyi otağı və ya yeri göstərin.",
        "en": "Give the room or the place of the event.",
    },
    "events.room_not_found": {
        "az": "Bu kodla otaq tapılmadı. Kodu kampus xəritəsində yoxlayın.",
        "en": "No room has this code. Check the code on the campus map.",
    },
    "events.capacity_below_registrations": {
        "az": "Yer sayı artıq qeydiyyatdan keçənlərin sayından az ola bilməz.",
        "en": "The capacity cannot be lower than the number of registrations.",
    },
    "events.version_conflict": {
        "az": "Tədbir bu arada başqa biri tərəfindən dəyişdirilib. Səhifəni yeniləyib yenidən cəhd edin.",
        "en": "Someone else changed the event in the meantime. Reload the page and try again.",
    },
    "events.cancelled": {
        "az": "Bu tədbir ləğv edilib.",
        "en": "This event has been cancelled.",
    },
    "events.full": {
        "az": "Bu tədbirdə boş yer qalmayıb.",
        "en": "There are no places left at this event.",
    },
    "events.registration_closed": {
        "az": "Tədbir başlayıb; qeydiyyat artıq dəyişdirilə bilməz.",
        "en": "The event has started; the registration can no longer change.",
    },
    "events.ticket_invalid": {
        "az": "Bilet tanınmadı. Kodu yenidən oxudun və ya iştirakçını siyahıdan tapın.",
        "en": "The ticket was not recognised. Scan it again or find the attendee in the list.",
    },
    "events.ticket_other_event": {
        "az": "Bu bilet başqa tədbirə aiddir.",
        "en": "This ticket is for another event.",
    },
    "events.ticket_cancelled": {
        "az": "Bu biletin qeydiyyatı ləğv edilib.",
        "en": "The registration for this ticket has been cancelled.",
    },
    "events.already_checked_in": {
        "az": "Bu iştirakçı artıq qeydiyyatdan keçib.",
        "en": "This attendee has already checked in.",
    },
    "events.check_in_closed": {
        "az": "Giriş qeydiyyatı tədbirdən 2 saat əvvəl açılır və tədbir bitəndə bağlanır.",
        "en": "Check-in opens 2 hours before the event and closes when it ends.",
    },
    "request.invalid_cursor": {
        "az": "Siyahının növbəti hissəsini yükləmək mümkün olmadı. Səhifəni yeniləyin.",
        "en": "The next part of the list could not be loaded. Reload the page.",
    },
    "notifications.quiet_hours_empty": {
        "az": "Sakit saatların başlanğıcı və sonu eyni ola bilməz. Fərqli vaxt seçin.",
        "en": "Quiet hours cannot start and end at the same time. Choose different times.",
    },
    "notifications.push_endpoint_rejected": {
        "az": "Bu brauzerin bildiriş xidməti dəstəklənmir. Başqa brauzerdən istifadə edin.",
        "en": "This browser's push service is not supported. Use another browser.",
    },
    "notifications.push_unavailable": {
        "az": "Brauzer bildirişləri hazırda istifadəyə verilməyib. Bildirişlər saytda və e-poçtla gəlir.",
        "en": "Browser notifications are not available yet. Notifications arrive in the app and by e-mail.",
    },
    "import.file_too_large": {
        "az": "Fayl çox böyükdür. Ən çox 5 MB və 20 000 sətirlik fayl yükləyin.",
        "en": "The file is too large. Upload at most 5 MB and 20,000 rows.",
    },
    "import.unsupported_format": {
        "az": "Bu fayl növü dəstəklənmir. CSV və ya XLSX faylı yükləyin.",
        "en": "This file type is not supported. Upload a CSV or XLSX file.",
    },
    "import.unreadable": {
        "az": "Faylı oxumaq mümkün olmadı. Faylın zədələnmədiyini yoxlayıb yenidən yükləyin.",
        "en": "The file could not be read. Check that it is not damaged and upload it again.",
    },
    "import.encoding_mismatch": {
        "az": "Fayl seçilmiş kodlaşdırmada oxunmur. Başqa kodlaşdırma seçin və ya faylı UTF-8 kimi saxlayın.",
        "en": "The file cannot be read with the selected encoding. Choose another one or save it as UTF-8.",
    },
    "import.not_applicable": {
        "az": "Bu idxalda xətalar var və tətbiq edilə bilməz. Faylı düzəldib yenidən yükləyin.",
        "en": "This import has errors and cannot be applied. Fix the file and upload it again.",
    },
    "import.expired": {
        "az": "Yoxlamanın müddəti bitib. Faylı yenidən yükləyin.",
        "en": "The preview has expired. Upload the file again.",
    },
    "profile.version_conflict": {
        "az": "Profil başqa pəncərədə dəyişdirilib. Səhifəni yeniləyib dəyişiklikləri yenidən edin.",
        "en": "The profile was changed in another window. Reload the page and make your changes again.",
    },
    "photo.invalid_image": {
        "az": "Şəkil oxunmadı. JPEG, PNG və ya WebP formatında şəkil seçin.",
        "en": "The image could not be read. Choose a JPEG, PNG or WebP image.",
    },
    "photo.too_large": {
        "az": "Şəkil çox böyükdür. Ən çox 5 MB ölçüdə şəkil seçin.",
        "en": "The image is too large. Choose an image of at most 5 MB.",
    },
    "storage.unavailable": {
        "az": "Fayl xidməti müvəqqəti əlçatan deyil. Bir az sonra yenidən cəhd edin.",
        "en": "File storage is temporarily unavailable. Please try again shortly.",
    },
    "admin.user_not_linked": {
        "az": "Bu şəxs hələ sistemə daxil olmayıb. Rolları ilk girişdən sonra təyin etmək olar.",
        "en": "This person has not signed in yet. Roles can be assigned after the first sign-in.",
    },
    "admin.own_admin_role": {
        "az": "Öz administrator rolunuzu silə bilməzsiniz. Bunu başqa administrator etməlidir.",
        "en": "You cannot remove your own administrator role. Another administrator must do it.",
    },
    "identity.unavailable": {
        "az": "Giriş xidməti müvəqqəti əlçatan deyil, rollar dəyişdirilmədi. Bir az sonra yenidən cəhd edin.",
        "en": "The sign-in service is temporarily unavailable; roles were not changed. Try again shortly.",
    },
    "privacy.notice_outdated": {
        "az": "Məxfilik bildirişi yenilənib. Səhifəni yeniləyib yeni mətnlə tanış olun.",
        "en": "The privacy notice has been updated. Reload the page and read the new version.",
    },
    "chat.channel_not_found": {
        "az": "Kanal tapılmadı və ya ona daxil olmaq imkanınız yoxdur.",
        "en": "The channel was not found or you do not have access to it.",
    },
    "chat.account_inactive": {
        "az": "Hesabınız aktiv olmadığı üçün mesaj göndərə bilməzsiniz. Dekanlığa müraciət edin.",
        "en": "Your account is not active, so you cannot send messages. Contact the dean's office.",
    },
    "chat.channel_archived": {
        "az": "Semestr bitib və kanal arxivə köçürülüb. Mesajları oxuya bilərsiniz, yazmaq mümkün deyil.",
        "en": "The semester has ended and the channel is archived. You can read messages but not post.",
    },
    "chat.exam_mode": {
        "az": "İmtahan gedir, kanal müvəqqəti yalnız oxumaq üçündür. İmtahandan sonra yenidən yaza bilərsiniz.",
        "en": "An exam is in progress, so the channel is read-only for now. You can post again after the exam.",
    },
    "chat.channel_readonly": {
        "az": "Bu kanal yalnız oxumaq üçündür.",
        "en": "This channel is read-only.",
    },
    "chat.user_blocked": {
        "az": "Bu istifadəçini bloklamısınız. Mesaj yazmaq üçün əvvəlcə bloku götürün.",
        "en": "You have blocked this person. Unblock them to send a message.",
    },
    "chat.dm_unavailable": {
        "az": "Bu istifadəçiyə hazırda şəxsi mesaj göndərmək mümkün deyil.",
        "en": "You cannot send this person a direct message at the moment.",
    },
    "chat.muted": {
        "az": "Moderator bu kanalda yazmağınızı müvəqqəti məhdudlaşdırıb.",
        "en": "A moderator has temporarily stopped you from posting in this channel.",
    },
    "chat.slow_mode": {
        "az": "Kanalda yavaş rejim aktivdir. Bir az gözləyib yenidən göndərin.",
        "en": "Slow mode is on in this channel. Wait a little and send again.",
    },
    "chat.rate_limited": {
        "az": "Qısa müddətdə çox mesaj göndərdiniz. Bir neçə saniyə gözləyin.",
        "en": "You sent too many messages in a short time. Wait a few seconds.",
    },
    "chat.channel_mention_not_allowed": {
        "az": "Bütün kanalı yalnız müəllimlər və moderatorlar qeyd edə bilər.",
        "en": "Only teachers and moderators can mention the whole channel.",
    },
    "chat.message_empty": {
        "az": "Mesaj boşdur. Mətn yazıb yenidən göndərin.",
        "en": "The message is empty. Write some text and send again.",
    },
    "chat.message_too_long": {
        "az": "Mesaj çox uzundur. Ən çox 4000 simvol yaza bilərsiniz.",
        "en": "The message is too long. You can write at most 4,000 characters.",
    },
    "chat.topic_not_found": {
        "az": "Seçilmiş mövzu bu kanalda yoxdur. Mövzunu yenidən seçin.",
        "en": "The selected topic does not exist in this channel. Choose the topic again.",
    },
    "chat.duplicate_client_id": {
        "az": "Mesaj göndərilmədi. Səhifəni yeniləyib yenidən göndərin.",
        "en": "The message was not sent. Reload the page and send it again.",
    },
    "chat.unavailable": {
        "az": "Mesaj xidməti müvəqqəti əlçatan deyil. Bir az sonra yenidən göndərin.",
        "en": "Messaging is temporarily unavailable. Try sending again shortly.",
    },
    "chat.realtime_unavailable": {
        "az": "Canlı bağlantı müvəqqəti əlçatan deyil. Mesajlar adi yolla göndərilir.",
        "en": "The live connection is temporarily unavailable. Messages are sent the regular way.",
    },
    "chat.dm_self": {
        "az": "Özünüzə şəxsi mesaj yaza bilməzsiniz.",
        "en": "You cannot send a direct message to yourself.",
    },
    "chat.user_not_found": {
        "az": "İstifadəçi tapılmadı.",
        "en": "The person was not found.",
    },
    "chat.block_self": {
        "az": "Özünüzü bloklaya bilməzsiniz.",
        "en": "You cannot block yourself.",
    },
    "server.internal_error": {
        "az": "Gözlənilməz xəta baş verdi. Bir az sonra yenidən cəhd edin.",
        "en": "An unexpected error occurred. Please try again shortly.",
    },
}


def negotiate_language(accept_language: str | None) -> str:
    """Pick the best supported language from an Accept-Language header."""
    if not accept_language:
        return DEFAULT_LANGUAGE
    candidates: list[tuple[float, int, str]] = []
    for position, part in enumerate(accept_language.split(",")):
        tag, _, params = part.strip().partition(";")
        quality = 1.0
        params = params.strip()
        if params.startswith("q="):
            try:
                quality = float(params[2:])
            except ValueError:
                quality = 0.0
        language = tag.strip().lower().split("-")[0]
        if language in SUPPORTED_LANGUAGES and quality > 0:
            candidates.append((-quality, position, language))
    return min(candidates)[2] if candidates else DEFAULT_LANGUAGE


def error_message(code: str, language: str) -> str:
    messages = ERROR_MESSAGES.get(code) or ERROR_MESSAGES["request.failed"]
    return messages.get(language) or messages[DEFAULT_LANGUAGE]
