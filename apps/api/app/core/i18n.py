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
