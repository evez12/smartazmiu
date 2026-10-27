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
    "chat.message_not_found": {
        "az": "Mesaj tapılmadı. Ola bilsin ki, silinib.",
        "en": "The message was not found. It may have been deleted.",
    },
    "chat.not_author": {
        "az": "Yalnız öz mesajınızı dəyişə və ya silə bilərsiniz.",
        "en": "You can only change or delete your own messages.",
    },
    "chat.change_window_expired": {
        "az": "Mesajı yalnız göndərildikdən sonra 15 dəqiqə ərzində dəyişmək və ya silmək olar.",
        "en": "A message can only be changed or deleted within 15 minutes of sending it.",
    },
    "chat.parent_not_found": {
        "az": "Cavab yazdığınız mesaj tapılmadı. Ola bilsin ki, silinib.",
        "en": "The message you are replying to was not found. It may have been deleted.",
    },
    "chat.reaction_not_allowed": {
        "az": "Bu reaksiya mövcud deyil. Siyahıdakı reaksiyalardan birini seçin.",
        "en": "This reaction is not available. Choose one from the list.",
    },
    "chat.attachments_not_allowed": {
        "az": "Yeni hesablar ilk 24 saat ərzində fənn icmalarına fayl əlavə edə bilməz.",
        "en": "New accounts cannot attach files in subject communities during their first 24 hours.",
    },
    "chat.attachment_type_not_allowed": {
        "az": "Bu fayl növü qəbul olunmur. Şəkil, PDF, DOCX, PPTX və ya ZIP faylı əlavə edin.",
        "en": "This file type is not accepted. Attach an image, PDF, DOCX, PPTX or ZIP file.",
    },
    "chat.attachment_too_large": {
        "az": "Fayl ən çox 25 MB ola bilər. Daha kiçik fayl seçin.",
        "en": "Files can be at most 25 MB.",
    },
    "chat.too_many_attachments": {
        "az": "Bir mesaja ən çox 10 fayl əlavə etmək olar.",
        "en": "A message can have at most 10 attachments.",
    },
    "chat.attachment_not_found": {
        "az": "Fayl tapılmadı. Yenidən əlavə edin.",
        "en": "The file was not found. Attach it again.",
    },
    "chat.attachment_not_uploaded": {
        "az": "Fayl hələ yüklənməyib. Yükləmə bitənə qədər gözləyin və ya faylı yenidən əlavə edin.",
        "en": "The file has not been uploaded yet. Wait for the upload to finish or attach it again.",
    },
    "chat.attachment_size_mismatch": {
        "az": "Yüklənən fayl gözlənilən ölçüdə deyil. Faylı yenidən əlavə edin.",
        "en": "The uploaded file does not have the expected size. Attach it again.",
    },
    "chat.attachment_not_available": {
        "az": "Fayl hələ yoxlanılır və ya yoxlamadan keçməyib. Bir neçə dəqiqədən sonra səhifəni yeniləyin.",
        "en": "The file is still being checked or did not pass the check.",
    },
    "chat.attachments_unavailable": {
        "az": "Fayl yükləmə xidməti müvəqqəti işləmir. Mətn mesajları göndərmək olar; faylı bir az sonra əlavə edin.",
        "en": "File uploads are temporarily unavailable. Text messages still work; attach the file later.",
    },
    "reports.target_not_found": {
        "az": "Şikayət etdiyiniz mesaj və ya istifadəçi tapılmadı.",
        "en": "The message or person you are reporting was not found.",
    },
    "reports.own_content": {
        "az": "Öz mesajınızdan və ya özünüzdən şikayət edə bilməzsiniz.",
        "en": "You cannot report your own message or yourself.",
    },
    "reports.not_found": {
        "az": "Şikayət tapılmadı.",
        "en": "The report was not found.",
    },
    "mentorship.subject_not_found": {
        "az": "Fənn tapılmadı və ya onun bələdçilərinə baxmaq imkanınız yoxdur.",
        "en": "The subject was not found or you cannot see its guides.",
    },
    "mentorship.consent_required": {
        "az": "Bələdçi olmaq üçün razılığınızı təsdiq edin.",
        "en": "Confirm your consent to become a guide.",
    },
    "mentorship.not_eligible": {
        "az": "Bu fənn üzrə bələdçi ola bilməzsiniz: fənni keçmiş semestrdə uğurla bitirmiş olmalısınız.",
        "en": "You cannot guide this subject: you must have passed it in a past semester.",
    },
    "mentorship.profile_not_found": {
        "az": "Bu fənn üzrə bələdçi profiliniz yoxdur. Əvvəlcə bələdçi olmağa razılıq verin.",
        "en": "You have no guide profile for this subject. Opt in first.",
    },
    "mentorship.body_required": {
        "az": "Sorğunun mətnini yazın.",
        "en": "Write the text of the request.",
    },
    "mentorship.self_request": {
        "az": "Özünüzə sorğu göndərə bilməzsiniz.",
        "en": "You cannot send a request to yourself.",
    },
    "mentorship.guide_unavailable": {
        "az": "Bu bələdçi hazırda yeni sorğu qəbul etmir. Başqa bələdçi seçin və ya sorğunu bütün bələdçilərə göndərin.",
        "en": "This guide is not taking new requests. Choose another guide or ask any guide.",
    },
    "mentorship.request_exists": {
        "az": "Bu bələdçiyə bu fənn üzrə açıq sorğunuz artıq var. Cavabını gözləyin.",
        "en": "You already have an open request to this guide for this subject.",
    },
    "mentorship.request_not_found": {
        "az": "Sorğu tapılmadı.",
        "en": "The request was not found.",
    },
    "mentorship.request_closed": {
        "az": "Bu sorğu artıq bağlanıb və ya başqa vəziyyətdədir. Səhifəni yeniləyin.",
        "en": "The request is no longer in a state that allows this. Reload the page.",
    },
    "mentorship.not_available": {
        "az": "Sorğu qəbul etmək üçün vəziyyətinizi «Əlçatan» edin.",
        "en": "Set your availability to available to accept requests.",
    },
    "mentorship.capacity_reached": {
        "az": "Açıq sorğularınızın sayı limitə çatıb. Birini həll edin və ya limiti artırın.",
        "en": "You reached your limit of open requests. Resolve one or raise the limit.",
    },
    "mentorship.request_not_resolved": {
        "az": "Rəy yalnız həll edilmiş sorğuya verilə bilər.",
        "en": "Feedback can be given only to a resolved request.",
    },
    "mentorship.feedback_exists": {
        "az": "Bu sorğuya artıq rəy vermisiniz.",
        "en": "You already gave feedback on this request.",
    },
    "chat.anonymous_not_allowed": {
        "az": "Anonim sual yalnız fənn və icma kanallarının #suallar bölməsində yeni mesaj kimi yazıla bilər.",
        "en": "Anonymous questions are allowed only as new posts in #suallar of course and community channels.",
    },
    "chat.pin_not_allowed": {
        "az": "Bu kanalda mesajları yalnız moderatorlar və müəllimlər sancaqlaya bilər.",
        "en": "Only moderators and teachers can pin messages in this channel.",
    },
    "chat.pin_limit": {
        "az": "Kanalda ən çox 50 sancaqlanmış mesaj ola bilər. Əvvəlcə birini çıxarın.",
        "en": "A channel can have at most 50 pinned messages. Unpin one first.",
    },
    "chat.poll_invalid_options": {
        "az": "Sorğuda 2-dən 10-a qədər fərqli, boş olmayan variant olmalıdır.",
        "en": "A poll needs 2 to 10 distinct, non-empty options.",
    },
    "chat.poll_invalid_deadline": {
        "az": "Bitmə vaxtı gələcəkdə olmalıdır.",
        "en": "The deadline must be in the future.",
    },
    "chat.poll_not_found": {
        "az": "Sorğu tapılmadı.",
        "en": "The poll was not found.",
    },
    "chat.poll_closed": {
        "az": "Sorğu bağlanıb, səs vermək mümkün deyil.",
        "en": "The poll is closed.",
    },
    "chat.poll_invalid_vote": {
        "az": "Variant seçin. Tək seçimli sorğuda yalnız bir variant seçilə bilər.",
        "en": "Choose an option. Single-choice polls take exactly one.",
    },
    "chat.verify_not_allowed": {
        "az": "Cavabı yalnız fənnin müəllimi (fənn kanalında) və ya bələdçi (fənn icmasında) təsdiqləyə bilər.",
        "en": "Only the course teacher or a guide of the subject can verify answers here.",
    },
    "chat.verify_needs_reply": {
        "az": "Yalnız sual mövzusundakı cavabı təsdiqləmək olar.",
        "en": "Only a reply in a question's thread can be verified.",
    },
    "chat.anonymous_author_hidden": {
        "az": "Anonim sualın müəllifini yalnız moderatorlar görə bilər.",
        "en": "Only moderators can see who asked an anonymous question.",
    },
    "tips.subject_not_found": {
        "az": "Fənn tapılmadı və ya onun kartlarına baxmaq imkanınız yoxdur.",
        "en": "The subject was not found or you cannot see its cards.",
    },
    "tips.not_eligible": {
        "az": "Kartı yalnız bu fənni həmin semestrdə uğurla bitirmiş tələbə yaza bilər.",
        "en": "Only students who passed the subject in that semester can write a card.",
    },
    "tips.invalid_link": {
        "az": "Keçid http:// və ya https:// ilə başlamalıdır.",
        "en": "Links must start with http:// or https://.",
    },
    "tips.invalid_material": {
        "az": "Seçilmiş material bu fənnə aid deyil və ya əlçatan deyil.",
        "en": "The chosen material does not belong to this subject or is not available.",
    },
    "tips.not_found": {
        "az": "Kart tapılmadı.",
        "en": "The card was not found.",
    },
    "tips.own_tip": {
        "az": "Öz kartınıza səs verə bilməzsiniz.",
        "en": "You cannot upvote your own card.",
    },
    "tips.invalid_status": {
        "az": "Bu vəziyyəti seçmək olmaz.",
        "en": "This status cannot be chosen.",
    },
    "materials.subject_not_found": {
        "az": "Fənn tapılmadı və ya onun materiallarına baxmaq icazəniz yoxdur.",
        "en": "The subject was not found or you cannot view its materials.",
    },
    "materials.upload_not_allowed": {
        "az": "Bu fənn və semestr üçün material yükləmək icazəniz yoxdur.",
        "en": "You cannot upload materials for this subject and semester.",
    },
    "materials.type_not_allowed": {
        "az": "Bu fayl növü qəbul olunmur: PDF, DOCX, PPTX, ZIP və ya şəkil yükləyin.",
        "en": "This file type is not accepted. Upload a PDF, DOCX, PPTX, ZIP or image.",
    },
    "materials.too_large": {
        "az": "Fayl ən çox 50 MB ola bilər. Daha kiçik fayl seçin.",
        "en": "Files can be at most 50 MB.",
    },
    "materials.storage_unavailable": {
        "az": "Fayl xidməti müvəqqəti işləmir. Bir az sonra yenidən cəhd edin.",
        "en": "File storage is temporarily unavailable. Try again shortly.",
    },
    "materials.upload_not_found": {
        "az": "Yüklənən fayl tapılmadı. Faylı yenidən seçin.",
        "en": "The uploaded file was not found. Choose the file again.",
    },
    "materials.upload_missing": {
        "az": "Fayl hələ yüklənməyib. Yükləmə bitənə qədər gözləyin və ya faylı yenidən seçin.",
        "en": "The file has not been uploaded yet. Wait for the upload to finish or choose the file again.",
    },
    "materials.upload_size_mismatch": {
        "az": "Yüklənən fayl gözlənilən ölçüdə deyil. Faylı yenidən seçin.",
        "en": "The uploaded file does not have the expected size. Choose the file again.",
    },
    "materials.copyright_required": {
        "az": "Faylı paylaşmaq hüququnuzu təsdiq edin.",
        "en": "Confirm that you have the right to share the file.",
    },
    "materials.title_required": {
        "az": "Materialın adını yazın.",
        "en": "Enter a title for the material.",
    },
    "materials.not_found": {
        "az": "Material tapılmadı.",
        "en": "The material was not found.",
    },
    "materials.not_available": {
        "az": "Fayl hələ yoxlanılır və ya yoxlamadan keçməyib. Bir neçə dəqiqədən sonra səhifəni yeniləyin.",
        "en": "The file is still being checked or did not pass the check.",
    },
    "materials.report_not_found": {
        "az": "Şikayət tapılmadı.",
        "en": "The report was not found.",
    },
    "feedback.message_required": {
        "az": "Rəyinizi yazın.",
        "en": "Write your feedback.",
    },
    "feedback.not_found": {
        "az": "Rəy tapılmadı.",
        "en": "The feedback was not found.",
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
