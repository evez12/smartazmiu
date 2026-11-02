DEFAULT_LANGUAGE = "az"
SUPPORTED_LANGUAGES = ("az", "en", "ru")

# User-facing error messages per stable error code. Codes stay in English and never reach the UI text.
ERROR_MESSAGES: dict[str, dict[str, str]] = {
    "auth.unauthenticated": {
        "az": "Sessiyanızın müddəti bitib. Yenidən daxil olun.",
        "en": "Your session has expired. Please sign in again.",
        "ru": "Срок действия сессии истёк. Войдите снова.",
    },
    "auth.forbidden": {
        "az": "Bu əməliyyat üçün icazəniz yoxdur. Lazım olduqda dekanlığa müraciət edin.",
        "en": "You do not have permission for this action. Contact the dean's office if you need it.",
        "ru": "У вас нет прав для этого действия. При необходимости обратитесь в деканат.",
    },
    "auth.account_inactive": {
        "az": "Hesabınız aktiv deyil. Ətraflı məlumat üçün dekanlığa müraciət edin.",
        "en": "Your account is not active. Contact the dean's office for details.",
        "ru": "Ваша учётная запись неактивна. Подробности можно узнать в деканате.",
    },
    "auth.identity_conflict": {
        "az": "Hesabınızın e-poçt ünvanı başqa bir hesabda istifadə olunur. İT xidmətinə müraciət edin.",
        "en": "Your account's e-mail address is used by another account. Contact IT support.",
        "ru": "Адрес электронной почты вашей учётной записи используется другой учётной записью. Обратитесь в ИТ-службу.",
    },
    "request.validation_failed": {
        "az": "Göndərilən məlumatlarda səhv var. Sahələri yoxlayıb yenidən cəhd edin.",
        "en": "Some of the submitted data is invalid. Check the fields and try again.",
        "ru": "В отправленных данных есть ошибки. Проверьте поля и повторите попытку.",
    },
    "request.not_found": {
        "az": "Axtardığınız məlumat tapılmadı.",
        "en": "The requested item was not found.",
        "ru": "Запрошенные данные не найдены.",
    },
    "request.method_not_allowed": {
        "az": "Bu sorğu növü dəstəklənmir.",
        "en": "This request method is not supported.",
        "ru": "Этот тип запроса не поддерживается.",
    },
    "request.failed": {
        "az": "Sorğunu yerinə yetirmək mümkün olmadı. Yenidən cəhd edin.",
        "en": "The request could not be completed. Please try again.",
        "ru": "Не удалось выполнить запрос. Повторите попытку.",
    },
    "request.rate_limited": {
        "az": "Çox sayda sorğu göndərdiniz. Bir az gözləyib yenidən cəhd edin.",
        "en": "Too many requests. Wait a little and try again.",
        "ru": "Слишком много запросов. Немного подождите и повторите попытку.",
    },
    "schedule.invalid_range": {
        "az": "Tarix aralığı düzgün deyil. Son tarix başlanğıcdan sonra və ən çox 42 gün sonra olmalıdır.",
        "en": "The date range is invalid. The end must follow the start by at most 42 days.",
        "ru": "Период указан неверно. Конец периода должен быть позже начала не более чем на 42 дня.",
    },
    "audience.invalid": {
        "az": "Seçilmiş auditoriya tapılmadı. Auditoriyanı yenidən seçin.",
        "en": "The selected audience was not found. Choose the audience again.",
        "ru": "Выбранная аудитория не найдена. Выберите аудиторию заново.",
    },
    "announcements.expiry_in_past": {
        "az": "Elanın bitmə vaxtı keçmişdədir. Gələcək bir tarix seçin.",
        "en": "The announcement's end time is in the past. Choose a future date.",
        "ru": "Время окончания объявления уже прошло. Выберите дату в будущем.",
    },
    "announcements.archived": {
        "az": "Bu elan arxivə köçürülüb və dəyişdirilə bilməz.",
        "en": "This announcement has been archived and cannot be changed.",
        "ru": "Объявление перенесено в архив, изменить его нельзя.",
    },
    "announcements.version_conflict": {
        "az": "Elan bu arada başqa biri tərəfindən dəyişdirilib. Səhifəni yeniləyib yenidən cəhd edin.",
        "en": "Someone else changed the announcement in the meantime. Reload the page and try again.",
        "ru": "Объявление уже изменил кто-то другой. Обновите страницу и повторите попытку.",
    },
    "events.starts_in_past": {
        "az": "Tədbirin başlama vaxtı keçmişdədir. Gələcək bir vaxt seçin.",
        "en": "The event's start time is in the past. Choose a future time.",
        "ru": "Время начала мероприятия уже прошло. Выберите время в будущем.",
    },
    "events.invalid_times": {
        "az": "Bitmə vaxtı başlama vaxtından sonra olmalıdır.",
        "en": "The end time must be after the start time.",
        "ru": "Время окончания должно быть позже времени начала.",
    },
    "events.location_required": {
        "az": "Tədbirin keçiriləcəyi otağı və ya yeri göstərin.",
        "en": "Give the room or the place of the event.",
        "ru": "Укажите аудиторию или место проведения мероприятия.",
    },
    "events.room_not_found": {
        "az": "Bu kodla otaq tapılmadı. Kodu kampus xəritəsində yoxlayın.",
        "en": "No room has this code. Check the code on the campus map.",
        "ru": "Аудитории с таким кодом нет. Проверьте код на карте кампуса.",
    },
    "events.capacity_below_registrations": {
        "az": "Yer sayı artıq qeydiyyatdan keçənlərin sayından az ola bilməz.",
        "en": "The capacity cannot be lower than the number of registrations.",
        "ru": "Число мест не может быть меньше числа регистраций.",
    },
    "events.version_conflict": {
        "az": "Tədbir bu arada başqa biri tərəfindən dəyişdirilib. Səhifəni yeniləyib yenidən cəhd edin.",
        "en": "Someone else changed the event in the meantime. Reload the page and try again.",
        "ru": "Мероприятие уже изменил кто-то другой. Обновите страницу и повторите попытку.",
    },
    "events.cancelled": {
        "az": "Bu tədbir ləğv edilib.",
        "en": "This event has been cancelled.",
        "ru": "Это мероприятие отменено.",
    },
    "events.full": {
        "az": "Bu tədbirdə boş yer qalmayıb.",
        "en": "There are no places left at this event.",
        "ru": "На это мероприятие не осталось мест.",
    },
    "events.registration_closed": {
        "az": "Tədbir başlayıb; qeydiyyat artıq dəyişdirilə bilməz.",
        "en": "The event has started; the registration can no longer change.",
        "ru": "Мероприятие уже началось, регистрацию изменить нельзя.",
    },
    "events.ticket_invalid": {
        "az": "Bilet tanınmadı. Kodu yenidən oxudun və ya iştirakçını siyahıdan tapın.",
        "en": "The ticket was not recognised. Scan it again or find the attendee in the list.",
        "ru": "Билет не распознан. Отсканируйте его снова или найдите участника в списке.",
    },
    "events.ticket_other_event": {
        "az": "Bu bilet başqa tədbirə aiddir.",
        "en": "This ticket is for another event.",
        "ru": "Этот билет относится к другому мероприятию.",
    },
    "events.ticket_cancelled": {
        "az": "Bu biletin qeydiyyatı ləğv edilib.",
        "en": "The registration for this ticket has been cancelled.",
        "ru": "Регистрация по этому билету отменена.",
    },
    "events.already_checked_in": {
        "az": "Bu iştirakçı artıq qeydiyyatdan keçib.",
        "en": "This attendee has already checked in.",
        "ru": "Этот участник уже отмечен.",
    },
    "events.check_in_closed": {
        "az": "Giriş qeydiyyatı tədbirdən 2 saat əvvəl açılır və tədbir bitəndə bağlanır.",
        "en": "Check-in opens 2 hours before the event and closes when it ends.",
        "ru": "Отметка открывается за 2 часа до начала мероприятия и закрывается после его окончания.",
    },
    "request.invalid_cursor": {
        "az": "Siyahının növbəti hissəsini yükləmək mümkün olmadı. Səhifəni yeniləyin.",
        "en": "The next part of the list could not be loaded. Reload the page.",
        "ru": "Не удалось загрузить следующую часть списка. Обновите страницу.",
    },
    "notifications.quiet_hours_empty": {
        "az": "Sakit saatların başlanğıcı və sonu eyni ola bilməz. Fərqli vaxt seçin.",
        "en": "Quiet hours cannot start and end at the same time. Choose different times.",
        "ru": "Тихие часы не могут начинаться и заканчиваться в одно время. Выберите другое время.",
    },
    "notifications.push_endpoint_rejected": {
        "az": "Bu brauzerin bildiriş xidməti dəstəklənmir. Başqa brauzerdən istifadə edin.",
        "en": "This browser's push service is not supported. Use another browser.",
        "ru": "Служба push-уведомлений этого браузера не поддерживается. Используйте другой браузер.",
    },
    "notifications.push_unavailable": {
        "az": "Brauzer bildirişləri hazırda istifadəyə verilməyib. Bildirişlər saytda və e-poçtla gəlir.",
        "en": "Browser notifications are not available yet. Notifications arrive in the app and by e-mail.",
        "ru": "Уведомления в браузере пока недоступны. Уведомления приходят в приложение и на электронную почту.",
    },
    "import.file_too_large": {
        "az": "Fayl çox böyükdür. Ən çox 5 MB və 20 000 sətirlik fayl yükləyin.",
        "en": "The file is too large. Upload at most 5 MB and 20,000 rows.",
        "ru": "Файл слишком большой. Загрузите файл размером не более 5 МБ и не более 20 000 строк.",
    },
    "import.unsupported_format": {
        "az": "Bu fayl növü dəstəklənmir. CSV və ya XLSX faylı yükləyin.",
        "en": "This file type is not supported. Upload a CSV or XLSX file.",
        "ru": "Этот тип файла не поддерживается. Загрузите файл CSV или XLSX.",
    },
    "import.unreadable": {
        "az": "Faylı oxumaq mümkün olmadı. Faylın zədələnmədiyini yoxlayıb yenidən yükləyin.",
        "en": "The file could not be read. Check that it is not damaged and upload it again.",
        "ru": "Не удалось прочитать файл. Убедитесь, что он не повреждён, и загрузите его снова.",
    },
    "import.encoding_mismatch": {
        "az": "Fayl seçilmiş kodlaşdırmada oxunmur. Başqa kodlaşdırma seçin və ya faylı UTF-8 kimi saxlayın.",
        "en": "The file cannot be read with the selected encoding. Choose another one or save it as UTF-8.",
        "ru": "Файл не читается в выбранной кодировке. Выберите другую или сохраните файл в UTF-8.",
    },
    "import.not_applicable": {
        "az": "Bu idxalda xətalar var və tətbiq edilə bilməz. Faylı düzəldib yenidən yükləyin.",
        "en": "This import has errors and cannot be applied. Fix the file and upload it again.",
        "ru": "В этом импорте есть ошибки, применить его нельзя. Исправьте файл и загрузите его снова.",
    },
    "import.expired": {
        "az": "Yoxlamanın müddəti bitib. Faylı yenidən yükləyin.",
        "en": "The preview has expired. Upload the file again.",
        "ru": "Срок действия предварительного просмотра истёк. Загрузите файл снова.",
    },
    "profile.version_conflict": {
        "az": "Profil başqa pəncərədə dəyişdirilib. Səhifəni yeniləyib dəyişiklikləri yenidən edin.",
        "en": "The profile was changed in another window. Reload the page and make your changes again.",
        "ru": "Профиль был изменён в другом окне. Обновите страницу и внесите изменения заново.",
    },
    "photo.invalid_image": {
        "az": "Şəkil oxunmadı. JPEG, PNG və ya WebP formatında şəkil seçin.",
        "en": "The image could not be read. Choose a JPEG, PNG or WebP image.",
        "ru": "Не удалось прочитать изображение. Выберите изображение JPEG, PNG или WebP.",
    },
    "photo.too_large": {
        "az": "Şəkil çox böyükdür. Ən çox 5 MB ölçüdə şəkil seçin.",
        "en": "The image is too large. Choose an image of at most 5 MB.",
        "ru": "Изображение слишком большое. Выберите изображение размером не более 5 МБ.",
    },
    "storage.unavailable": {
        "az": "Fayl xidməti müvəqqəti əlçatan deyil. Bir az sonra yenidən cəhd edin.",
        "en": "File storage is temporarily unavailable. Please try again shortly.",
        "ru": "Хранилище файлов временно недоступно. Повторите попытку чуть позже.",
    },
    "admin.user_not_linked": {
        "az": "Bu şəxs hələ sistemə daxil olmayıb. Rolları ilk girişdən sonra təyin etmək olar.",
        "en": "This person has not signed in yet. Roles can be assigned after the first sign-in.",
        "ru": "Этот человек ещё не входил в систему. Роли можно назначить после первого входа.",
    },
    "admin.own_admin_role": {
        "az": "Öz administrator rolunuzu silə bilməzsiniz. Bunu başqa administrator etməlidir.",
        "en": "You cannot remove your own administrator role. Another administrator must do it.",
        "ru": "Нельзя снять с себя роль администратора. Это должен сделать другой администратор.",
    },
    "identity.unavailable": {
        "az": "Giriş xidməti müvəqqəti əlçatan deyil, rollar dəyişdirilmədi. Bir az sonra yenidən cəhd edin.",
        "en": "The sign-in service is temporarily unavailable; roles were not changed. Try again shortly.",
        "ru": "Служба входа временно недоступна, роли не изменены. Повторите попытку чуть позже.",
    },
    "privacy.notice_outdated": {
        "az": "Məxfilik bildirişi yenilənib. Səhifəni yeniləyib yeni mətnlə tanış olun.",
        "en": "The privacy notice has been updated. Reload the page and read the new version.",
        "ru": "Уведомление о конфиденциальности обновлено. Обновите страницу и ознакомьтесь с новой версией.",
    },
    "chat.channel_not_found": {
        "az": "Kanal tapılmadı və ya ona daxil olmaq imkanınız yoxdur.",
        "en": "The channel was not found or you do not have access to it.",
        "ru": "Канал не найден или у вас нет к нему доступа.",
    },
    "chat.account_inactive": {
        "az": "Hesabınız aktiv olmadığı üçün mesaj göndərə bilməzsiniz. Dekanlığa müraciət edin.",
        "en": "Your account is not active, so you cannot send messages. Contact the dean's office.",
        "ru": "Ваша учётная запись неактивна, поэтому отправлять сообщения нельзя. Обратитесь в деканат.",
    },
    "chat.channel_archived": {
        "az": "Semestr bitib və kanal arxivə köçürülüb. Mesajları oxuya bilərsiniz, yazmaq mümkün deyil.",
        "en": "The semester has ended and the channel is archived. You can read messages but not post.",
        "ru": "Семестр завершён, канал перенесён в архив. Сообщения можно читать, но писать нельзя.",
    },
    "chat.exam_mode": {
        "az": "İmtahan gedir, kanal müvəqqəti yalnız oxumaq üçündür. İmtahandan sonra yenidən yaza bilərsiniz.",
        "en": "An exam is in progress, so the channel is read-only for now. You can post again after the exam.",
        "ru": "Идёт экзамен, поэтому канал пока доступен только для чтения. После экзамена писать снова можно будет.",
    },
    "chat.channel_readonly": {
        "az": "Bu kanal yalnız oxumaq üçündür.",
        "en": "This channel is read-only.",
        "ru": "Этот канал доступен только для чтения.",
    },
    "chat.user_blocked": {
        "az": "Bu istifadəçini bloklamısınız. Mesaj yazmaq üçün əvvəlcə bloku götürün.",
        "en": "You have blocked this person. Unblock them to send a message.",
        "ru": "Вы заблокировали этого пользователя. Разблокируйте его, чтобы отправить сообщение.",
    },
    "chat.dm_unavailable": {
        "az": "Bu istifadəçiyə hazırda şəxsi mesaj göndərmək mümkün deyil.",
        "en": "You cannot send this person a direct message at the moment.",
        "ru": "Сейчас вы не можете отправить этому пользователю личное сообщение.",
    },
    "chat.muted": {
        "az": "Moderator bu kanalda yazmağınızı müvəqqəti məhdudlaşdırıb.",
        "en": "A moderator has temporarily stopped you from posting in this channel.",
        "ru": "Модератор временно ограничил вам отправку сообщений в этом канале.",
    },
    "chat.slow_mode": {
        "az": "Kanalda yavaş rejim aktivdir. Bir az gözləyib yenidən göndərin.",
        "en": "Slow mode is on in this channel. Wait a little and send again.",
        "ru": "В этом канале включён медленный режим. Немного подождите и отправьте сообщение снова.",
    },
    "chat.rate_limited": {
        "az": "Qısa müddətdə çox mesaj göndərdiniz. Bir neçə saniyə gözləyin.",
        "en": "You sent too many messages in a short time. Wait a few seconds.",
        "ru": "Вы отправили слишком много сообщений за короткое время. Подождите несколько секунд.",
    },
    "chat.channel_mention_not_allowed": {
        "az": "Bütün kanalı yalnız müəllimlər və moderatorlar qeyd edə bilər.",
        "en": "Only teachers and moderators can mention the whole channel.",
        "ru": "Упоминать весь канал могут только преподаватели и модераторы.",
    },
    "chat.message_empty": {
        "az": "Mesaj boşdur. Mətn yazıb yenidən göndərin.",
        "en": "The message is empty. Write some text and send again.",
        "ru": "Сообщение пустое. Напишите текст и отправьте снова.",
    },
    "chat.message_blocked": {
        "az": "Mesaj qaydalara uyğun deyil. Mətni dəyişib yenidən göndərin.",
        "en": "The message does not meet the rules. Edit it and try again.",
        "ru": "Сообщение не соответствует правилам. Измените его и повторите попытку.",
    },
    "chat.blocked_term_invalid": {
        "az": "Bloklama qaydası düzgün deyil. İfadəni yoxlayın.",
        "en": "The blocked-term rule is invalid. Check the pattern.",
        "ru": "Правило запрещённых слов задано неверно. Проверьте шаблон.",
    },
    "chat.blocked_term_not_found": {
        "az": "Bloklama qaydası tapılmadı. Siyahını yeniləyin.",
        "en": "The blocked-term rule was not found. Refresh the list.",
        "ru": "Правило запрещённых слов не найдено. Обновите список.",
    },
    "chat.thread_locked": {
        "az": "Bu mövzu kilidlənib. Yeni cavab yazmaq mümkün deyil.",
        "en": "This thread is locked. New replies are not allowed.",
        "ru": "Это обсуждение закрыто. Новые ответы недоступны.",
    },
    "moderation.forbidden": {
        "az": "Bu moderator əməliyyatı üçün icazəniz yoxdur.",
        "en": "You do not have permission for this moderation action.",
        "ru": "У вас нет прав для этого действия модерации.",
    },
    "moderation.channel_not_found": {
        "az": "Kanal tapılmadı və ya bu kanalı idarə etmək icazəniz yoxdur.",
        "en": "The channel was not found or you cannot moderate it.",
        "ru": "Канал не найден или вы не можете им модерировать.",
    },
    "moderation.message_not_found": {
        "az": "Mesaj tapılmadı. Siyahını yeniləyin.",
        "en": "The message was not found. Refresh the list.",
        "ru": "Сообщение не найдено. Обновите список.",
    },
    "moderation.protected_target": {
        "az": "Bu istifadəçi barədə həmin əməliyyatı tətbiq etmək olmaz.",
        "en": "That action cannot be applied to this user.",
        "ru": "Это действие нельзя применить к данному пользователю.",
    },
    "moderation.reason_required": {
        "az": "Qərarın səbəbini yazın.",
        "en": "Give a reason for the decision.",
        "ru": "Укажите причину решения.",
    },
    "moderation.invalid_duration": {
        "az": "Seçilmiş müddət qəbul edilmir.",
        "en": "The selected duration is not allowed.",
        "ru": "Выбранная длительность недопустима.",
    },
    "moderation.target_required": {
        "az": "Əməliyyat üçün istifadəçi seçilməyib.",
        "en": "No user was selected for the action.",
        "ru": "Для действия не выбран пользователь.",
    },
    "moderation.thread_not_found": {
        "az": "Yalnız əsas mesajın mövzusunu kilidləmək olar.",
        "en": "Only a root message thread can be locked.",
        "ru": "Закрыть можно только обсуждение, начатое корневым сообщением.",
    },
    "chat.message_too_long": {
        "az": "Mesaj çox uzundur. Ən çox 4000 simvol yaza bilərsiniz.",
        "en": "The message is too long. You can write at most 4,000 characters.",
        "ru": "Сообщение слишком длинное. Максимальная длина — 4 000 символов.",
    },
    "chat.topic_not_found": {
        "az": "Seçilmiş mövzu bu kanalda yoxdur. Mövzunu yenidən seçin.",
        "en": "The selected topic does not exist in this channel. Choose the topic again.",
        "ru": "Выбранной темы нет в этом канале. Выберите тему заново.",
    },
    "chat.duplicate_client_id": {
        "az": "Mesaj göndərilmədi. Səhifəni yeniləyib yenidən göndərin.",
        "en": "The message was not sent. Reload the page and send it again.",
        "ru": "Сообщение не отправлено. Обновите страницу и отправьте его снова.",
    },
    "chat.unavailable": {
        "az": "Mesaj xidməti müvəqqəti əlçatan deyil. Bir az sonra yenidən göndərin.",
        "en": "Messaging is temporarily unavailable. Try sending again shortly.",
        "ru": "Отправка сообщений временно недоступна. Повторите попытку чуть позже.",
    },
    "chat.realtime_unavailable": {
        "az": "Canlı bağlantı müvəqqəti əlçatan deyil. Mesajlar adi yolla göndərilir.",
        "en": "The live connection is temporarily unavailable. Messages are sent the regular way.",
        "ru": "Соединение в реальном времени временно недоступно. Сообщения отправляются обычным способом.",
    },
    "chat.dm_self": {
        "az": "Özünüzə şəxsi mesaj yaza bilməzsiniz.",
        "en": "You cannot send a direct message to yourself.",
        "ru": "Нельзя отправить личное сообщение самому себе.",
    },
    "chat.user_not_found": {
        "az": "İstifadəçi tapılmadı.",
        "en": "The person was not found.",
        "ru": "Пользователь не найден.",
    },
    "chat.block_self": {
        "az": "Özünüzü bloklaya bilməzsiniz.",
        "en": "You cannot block yourself.",
        "ru": "Нельзя заблокировать самого себя.",
    },
    "chat.message_not_found": {
        "az": "Mesaj tapılmadı. Ola bilsin ki, silinib.",
        "en": "The message was not found. It may have been deleted.",
        "ru": "Сообщение не найдено. Возможно, оно удалено.",
    },
    "chat.not_author": {
        "az": "Yalnız öz mesajınızı dəyişə və ya silə bilərsiniz.",
        "en": "You can only change or delete your own messages.",
        "ru": "Изменять и удалять можно только свои сообщения.",
    },
    "chat.change_window_expired": {
        "az": "Mesajı yalnız göndərildikdən sonra 15 dəqiqə ərzində dəyişmək və ya silmək olar.",
        "en": "A message can only be changed or deleted within 15 minutes of sending it.",
        "ru": "Сообщение можно изменить или удалить только в течение 15 минут после отправки.",
    },
    "chat.parent_not_found": {
        "az": "Cavab yazdığınız mesaj tapılmadı. Ola bilsin ki, silinib.",
        "en": "The message you are replying to was not found. It may have been deleted.",
        "ru": "Сообщение, на которое вы отвечаете, не найдено. Возможно, оно удалено.",
    },
    "chat.reaction_not_allowed": {
        "az": "Bu reaksiya mövcud deyil. Siyahıdakı reaksiyalardan birini seçin.",
        "en": "This reaction is not available. Choose one from the list.",
        "ru": "Эта реакция недоступна. Выберите реакцию из списка.",
    },
    "chat.attachments_not_allowed": {
        "az": "Yeni hesablar ilk 24 saat ərzində fənn icmalarına fayl əlavə edə bilməz.",
        "en": "New accounts cannot attach files in subject communities during their first 24 hours.",
        "ru": "Новые учётные записи не могут прикреплять файлы в сообществах по дисциплинам в первые 24 часа.",
    },
    "chat.attachment_type_not_allowed": {
        "az": "Bu fayl növü qəbul olunmur. Şəkil, PDF, DOCX, PPTX və ya ZIP faylı əlavə edin.",
        "en": "This file type is not accepted. Attach an image, PDF, DOCX, PPTX or ZIP file.",
        "ru": "Этот тип файла не принимается. Прикрепите изображение либо файл PDF, DOCX, PPTX или ZIP.",
    },
    "chat.attachment_too_large": {
        "az": "Fayl ən çox 25 MB ola bilər. Daha kiçik fayl seçin.",
        "en": "Files can be at most 25 MB.",
        "ru": "Размер файла не должен превышать 25 МБ.",
    },
    "chat.too_many_attachments": {
        "az": "Bir mesaja ən çox 10 fayl əlavə etmək olar.",
        "en": "A message can have at most 10 attachments.",
        "ru": "К сообщению можно прикрепить не более 10 файлов.",
    },
    "chat.attachment_not_found": {
        "az": "Fayl tapılmadı. Yenidən əlavə edin.",
        "en": "The file was not found. Attach it again.",
        "ru": "Файл не найден. Прикрепите его снова.",
    },
    "chat.attachment_not_uploaded": {
        "az": "Fayl hələ yüklənməyib. Yükləmə bitənə qədər gözləyin və ya faylı yenidən əlavə edin.",
        "en": "The file has not been uploaded yet. Wait for the upload to finish or attach it again.",
        "ru": "Файл ещё не загружен. Дождитесь окончания загрузки или прикрепите файл снова.",
    },
    "chat.attachment_size_mismatch": {
        "az": "Yüklənən fayl gözlənilən ölçüdə deyil. Faylı yenidən əlavə edin.",
        "en": "The uploaded file does not have the expected size. Attach it again.",
        "ru": "Размер загруженного файла отличается от ожидаемого. Прикрепите файл снова.",
    },
    "chat.attachment_not_available": {
        "az": "Fayl hələ yoxlanılır və ya yoxlamadan keçməyib. Bir neçə dəqiqədən sonra səhifəni yeniləyin.",
        "en": "The file is still being checked or did not pass the check.",
        "ru": "Файл ещё проверяется или не прошёл проверку.",
    },
    "chat.attachments_unavailable": {
        "az": "Fayl yükləmə xidməti müvəqqəti işləmir. Mətn mesajları göndərmək olar; faylı bir az sonra əlavə edin.",
        "en": "File uploads are temporarily unavailable. Text messages still work; attach the file later.",
        "ru": "Загрузка файлов временно недоступна. Текстовые сообщения работают, прикрепите файл позже.",
    },
    "reports.target_not_found": {
        "az": "Şikayət etdiyiniz mesaj və ya istifadəçi tapılmadı.",
        "en": "The message or person you are reporting was not found.",
        "ru": "Сообщение или пользователь, на которых вы жалуетесь, не найдены.",
    },
    "reports.own_content": {
        "az": "Öz mesajınızdan və ya özünüzdən şikayət edə bilməzsiniz.",
        "en": "You cannot report your own message or yourself.",
        "ru": "Нельзя пожаловаться на собственное сообщение или на самого себя.",
    },
    "reports.not_found": {
        "az": "Şikayət tapılmadı.",
        "en": "The report was not found.",
        "ru": "Жалоба не найдена.",
    },
    "mentorship.subject_not_found": {
        "az": "Fənn tapılmadı və ya onun bələdçilərinə baxmaq imkanınız yoxdur.",
        "en": "The subject was not found or you cannot see its guides.",
        "ru": "Дисциплина не найдена, или вы не можете видеть её наставников.",
    },
    "mentorship.consent_required": {
        "az": "Bələdçi olmaq üçün razılığınızı təsdiq edin.",
        "en": "Confirm your consent to become a guide.",
        "ru": "Подтвердите согласие, чтобы стать наставником.",
    },
    "mentorship.not_eligible": {
        "az": "Bu fənn üzrə bələdçi ola bilməzsiniz: fənni keçmiş semestrdə uğurla bitirmiş olmalısınız.",
        "en": "You cannot guide this subject: you must have passed it in a past semester.",
        "ru": "Вы не можете быть наставником по этой дисциплине: её нужно сдать в одном из прошлых семестров.",
    },
    "mentorship.profile_not_found": {
        "az": "Bu fənn üzrə bələdçi profiliniz yoxdur. Əvvəlcə bələdçi olmağa razılıq verin.",
        "en": "You have no guide profile for this subject. Opt in first.",
        "ru": "У вас нет профиля наставника по этой дисциплине. Сначала подключитесь.",
    },
    "mentorship.body_required": {
        "az": "Sorğunun mətnini yazın.",
        "en": "Write the text of the request.",
        "ru": "Напишите текст запроса.",
    },
    "mentorship.self_request": {
        "az": "Özünüzə sorğu göndərə bilməzsiniz.",
        "en": "You cannot send a request to yourself.",
        "ru": "Нельзя отправить запрос самому себе.",
    },
    "mentorship.guide_unavailable": {
        "az": "Bu bələdçi hazırda yeni sorğu qəbul etmir. Başqa bələdçi seçin və ya sorğunu bütün bələdçilərə göndərin.",
        "en": "This guide is not taking new requests. Choose another guide or ask any guide.",
        "ru": "Этот наставник сейчас не принимает новые запросы. Выберите другого наставника или обратитесь к любому.",
    },
    "mentorship.request_exists": {
        "az": "Bu bələdçiyə bu fənn üzrə açıq sorğunuz artıq var. Cavabını gözləyin.",
        "en": "You already have an open request to this guide for this subject.",
        "ru": "У вас уже есть открытый запрос к этому наставнику по этой дисциплине.",
    },
    "mentorship.request_not_found": {
        "az": "Sorğu tapılmadı.",
        "en": "The request was not found.",
        "ru": "Запрос не найден.",
    },
    "mentorship.request_closed": {
        "az": "Bu sorğu artıq bağlanıb və ya başqa vəziyyətdədir. Səhifəni yeniləyin.",
        "en": "The request is no longer in a state that allows this. Reload the page.",
        "ru": "Запрос уже находится в состоянии, которое не допускает это действие. Обновите страницу.",
    },
    "mentorship.not_available": {
        "az": "Sorğu qəbul etmək üçün vəziyyətinizi «Əlçatan» edin.",
        "en": "Set your availability to available to accept requests.",
        "ru": "Чтобы принимать запросы, установите статус «доступен».",
    },
    "mentorship.capacity_reached": {
        "az": "Açıq sorğularınızın sayı limitə çatıb. Birini həll edin və ya limiti artırın.",
        "en": "You reached your limit of open requests. Resolve one or raise the limit.",
        "ru": "Вы достигли лимита открытых запросов. Закройте один из них или увеличьте лимит.",
    },
    "mentorship.request_not_resolved": {
        "az": "Rəy yalnız həll edilmiş sorğuya verilə bilər.",
        "en": "Feedback can be given only to a resolved request.",
        "ru": "Отзыв можно оставить только по завершённому запросу.",
    },
    "mentorship.feedback_exists": {
        "az": "Bu sorğuya artıq rəy vermisiniz.",
        "en": "You already gave feedback on this request.",
        "ru": "Вы уже оставили отзыв по этому запросу.",
    },
    "chat.anonymous_not_allowed": {
        "az": "Anonim sual yalnız fənn və icma kanallarının #suallar bölməsində yeni mesaj kimi yazıla bilər.",
        "en": "Anonymous questions are allowed only as new posts in #suallar of course and community channels.",
        "ru": "Анонимные вопросы разрешены только как новые сообщения в #suallar каналов дисциплин и сообществ.",
    },
    "chat.pin_not_allowed": {
        "az": "Bu kanalda mesajları yalnız moderatorlar və müəllimlər sancaqlaya bilər.",
        "en": "Only moderators and teachers can pin messages in this channel.",
        "ru": "Закреплять сообщения в этом канале могут только модераторы и преподаватели.",
    },
    "chat.pin_limit": {
        "az": "Kanalda ən çox 50 sancaqlanmış mesaj ola bilər. Əvvəlcə birini çıxarın.",
        "en": "A channel can have at most 50 pinned messages. Unpin one first.",
        "ru": "В канале можно закрепить не более 50 сообщений. Сначала открепите одно из них.",
    },
    "chat.poll_invalid_options": {
        "az": "Sorğuda 2-dən 10-a qədər fərqli, boş olmayan variant olmalıdır.",
        "en": "A poll needs 2 to 10 distinct, non-empty options.",
        "ru": "В опросе должно быть от 2 до 10 различных непустых вариантов.",
    },
    "chat.poll_invalid_deadline": {
        "az": "Bitmə vaxtı gələcəkdə olmalıdır.",
        "en": "The deadline must be in the future.",
        "ru": "Срок должен быть в будущем.",
    },
    "chat.poll_not_found": {
        "az": "Sorğu tapılmadı.",
        "en": "The poll was not found.",
        "ru": "Опрос не найден.",
    },
    "chat.poll_closed": {
        "az": "Sorğu bağlanıb, səs vermək mümkün deyil.",
        "en": "The poll is closed.",
        "ru": "Опрос закрыт.",
    },
    "chat.poll_invalid_vote": {
        "az": "Variant seçin. Tək seçimli sorğuda yalnız bir variant seçilə bilər.",
        "en": "Choose an option. Single-choice polls take exactly one.",
        "ru": "Выберите вариант. В опросе с одним ответом нужно выбрать ровно один.",
    },
    "chat.verify_not_allowed": {
        "az": "Cavabı yalnız fənnin müəllimi (fənn kanalında) və ya bələdçi (fənn icmasında) təsdiqləyə bilər.",
        "en": "Only the course teacher or a guide of the subject can verify answers here.",
        "ru": "Подтверждать ответы здесь могут только преподаватель дисциплины или её наставник.",
    },
    "chat.verify_needs_reply": {
        "az": "Yalnız sual mövzusundakı cavabı təsdiqləmək olar.",
        "en": "Only a reply in a question's thread can be verified.",
        "ru": "Подтвердить можно только ответ в обсуждении вопроса.",
    },
    "chat.anonymous_author_hidden": {
        "az": "Anonim sualın müəllifini yalnız moderatorlar görə bilər.",
        "en": "Only moderators can see who asked an anonymous question.",
        "ru": "Автора анонимного вопроса могут видеть только модераторы.",
    },
    "tips.subject_not_found": {
        "az": "Fənn tapılmadı və ya onun kartlarına baxmaq imkanınız yoxdur.",
        "en": "The subject was not found or you cannot see its cards.",
        "ru": "Дисциплина не найдена, или вы не можете видеть её карточки.",
    },
    "tips.not_eligible": {
        "az": "Kartı yalnız bu fənni həmin semestrdə uğurla bitirmiş tələbə yaza bilər.",
        "en": "Only students who passed the subject in that semester can write a card.",
        "ru": "Написать карточку могут только студенты, сдавшие дисциплину в этом семестре.",
    },
    "tips.invalid_link": {
        "az": "Keçid http:// və ya https:// ilə başlamalıdır.",
        "en": "Links must start with http:// or https://.",
        "ru": "Ссылки должны начинаться с http:// или https://.",
    },
    "tips.invalid_material": {
        "az": "Seçilmiş material bu fənnə aid deyil və ya əlçatan deyil.",
        "en": "The chosen material does not belong to this subject or is not available.",
        "ru": "Выбранный материал не относится к этой дисциплине или недоступен.",
    },
    "tips.not_found": {
        "az": "Kart tapılmadı.",
        "en": "The card was not found.",
        "ru": "Карточка не найдена.",
    },
    "tips.own_tip": {
        "az": "Öz kartınıza səs verə bilməzsiniz.",
        "en": "You cannot upvote your own card.",
        "ru": "Нельзя голосовать за собственную карточку.",
    },
    "tips.invalid_status": {
        "az": "Bu vəziyyəti seçmək olmaz.",
        "en": "This status cannot be chosen.",
        "ru": "Этот статус выбрать нельзя.",
    },
    "materials.subject_not_found": {
        "az": "Fənn tapılmadı və ya onun materiallarına baxmaq icazəniz yoxdur.",
        "en": "The subject was not found or you cannot view its materials.",
        "ru": "Дисциплина не найдена, или вы не можете просматривать её материалы.",
    },
    "materials.upload_not_allowed": {
        "az": "Bu fənn və semestr üçün material yükləmək icazəniz yoxdur.",
        "en": "You cannot upload materials for this subject and semester.",
        "ru": "Вы не можете загружать материалы по этой дисциплине и семестру.",
    },
    "materials.type_not_allowed": {
        "az": "Bu fayl növü qəbul olunmur: PDF, DOCX, PPTX, ZIP və ya şəkil yükləyin.",
        "en": "This file type is not accepted. Upload a PDF, DOCX, PPTX, ZIP or image.",
        "ru": "Этот тип файла не принимается. Загрузите файл PDF, DOCX, PPTX, ZIP или изображение.",
    },
    "materials.too_large": {
        "az": "Fayl ən çox 50 MB ola bilər. Daha kiçik fayl seçin.",
        "en": "Files can be at most 50 MB.",
        "ru": "Размер файла не должен превышать 50 МБ.",
    },
    "materials.storage_unavailable": {
        "az": "Fayl xidməti müvəqqəti işləmir. Bir az sonra yenidən cəhd edin.",
        "en": "File storage is temporarily unavailable. Try again shortly.",
        "ru": "Хранилище файлов временно недоступно. Повторите попытку чуть позже.",
    },
    "materials.upload_not_found": {
        "az": "Yüklənən fayl tapılmadı. Faylı yenidən seçin.",
        "en": "The uploaded file was not found. Choose the file again.",
        "ru": "Загруженный файл не найден. Выберите файл снова.",
    },
    "materials.upload_missing": {
        "az": "Fayl hələ yüklənməyib. Yükləmə bitənə qədər gözləyin və ya faylı yenidən seçin.",
        "en": "The file has not been uploaded yet. Wait for the upload to finish or choose the file again.",
        "ru": "Файл ещё не загружен. Дождитесь окончания загрузки или выберите файл снова.",
    },
    "materials.upload_size_mismatch": {
        "az": "Yüklənən fayl gözlənilən ölçüdə deyil. Faylı yenidən seçin.",
        "en": "The uploaded file does not have the expected size. Choose the file again.",
        "ru": "Размер загруженного файла отличается от ожидаемого. Выберите файл снова.",
    },
    "materials.copyright_required": {
        "az": "Faylı paylaşmaq hüququnuzu təsdiq edin.",
        "en": "Confirm that you have the right to share the file.",
        "ru": "Подтвердите, что вы вправе делиться этим файлом.",
    },
    "materials.title_required": {
        "az": "Materialın adını yazın.",
        "en": "Enter a title for the material.",
        "ru": "Укажите название материала.",
    },
    "materials.not_found": {
        "az": "Material tapılmadı.",
        "en": "The material was not found.",
        "ru": "Материал не найден.",
    },
    "materials.not_available": {
        "az": "Fayl hələ yoxlanılır və ya yoxlamadan keçməyib. Bir neçə dəqiqədən sonra səhifəni yeniləyin.",
        "en": "The file is still being checked or did not pass the check.",
        "ru": "Файл ещё проверяется или не прошёл проверку.",
    },
    "materials.report_not_found": {
        "az": "Şikayət tapılmadı.",
        "en": "The report was not found.",
        "ru": "Жалоба не найдена.",
    },
    "feedback.message_required": {
        "az": "Rəyinizi yazın.",
        "en": "Write your feedback.",
        "ru": "Напишите свой отзыв.",
    },
    "feedback.not_found": {
        "az": "Rəy tapılmadı.",
        "en": "The feedback was not found.",
        "ru": "Отзыв не найден.",
    },
    "assignments.not_found": {
        "az": "Tapşırıq tapılmadı.",
        "en": "The assignment was not found.",
        "ru": "Задание не найдено.",
    },
    "assignments.offering_not_found": {
        "az": "Bu fənn üzrə tapşırıq yaratmaq mümkün deyil.",
        "en": "You cannot add assignments to this course.",
        "ru": "Вы не можете добавлять задания в эту дисциплину.",
    },
    "assignments.submission_not_found": {
        "az": "Təqdim olunan iş tapılmadı.",
        "en": "The submission was not found.",
        "ru": "Работа не найдена.",
    },
    "assignments.not_student": {
        "az": "Yalnız bu fənnin tələbələri iş təqdim edə bilər.",
        "en": "Only students of this course can submit work.",
        "ru": "Сдавать работы могут только студенты этой дисциплины.",
    },
    "assignments.not_a_student": {
        "az": "Yalnız bu fənnin tələbələri iş təqdim edə bilər.",
        "en": "Only students of this course can submit work.",
        "ru": "Сдавать работы могут только студенты этой дисциплины.",
    },
    "assignments.not_available": {
        "az": "Tapşırıq hələ açılmayıb.",
        "en": "The assignment is not open yet.",
        "ru": "Задание ещё не открыто.",
    },
    "assignments.closed": {
        "az": "Təqdimetmə müddəti bitib. Müəllimlə əlaqə saxlayın.",
        "en": "The deadline has passed. Contact your teacher.",
        "ru": "Срок сдачи истёк. Обратитесь к преподавателю.",
    },
    "assignments.graded": {
        "az": "İş artıq qiymətləndirilib, onu dəyişmək olmaz.",
        "en": "The work is already graded and cannot be changed.",
        "ru": "Работа уже оценена, изменить её нельзя.",
    },
    "assignments.grade_exceeds_maximum": {
        "az": "Bal tapşırığın maksimum balından çox ola bilməz.",
        "en": "The points cannot exceed the maximum of the assignment.",
        "ru": "Баллов не может быть больше максимума за задание.",
    },
    "assignments.upload_not_found": {
        "az": "Yüklənmiş fayl tapılmadı. Faylı yenidən seçin.",
        "en": "The uploaded file was not found. Choose the file again.",
        "ru": "Загруженный файл не найден. Выберите файл снова.",
    },
    "assignments.upload_missing": {
        "az": "Fayl hələ yüklənməyib. Yükləmənin bitməsini gözləyin.",
        "en": "The file has not finished uploading. Wait for the upload to end.",
        "ru": "Файл ещё не загружен полностью. Дождитесь окончания загрузки.",
    },
    "assignments.upload_size_mismatch": {
        "az": "Yüklənən faylın ölçüsü uyğun gəlmir. Faylı yenidən yükləyin.",
        "en": "The uploaded file size does not match. Upload the file again.",
        "ru": "Размер загруженного файла не совпадает. Загрузите файл снова.",
    },
    "assignments.type_not_allowed": {
        "az": "Bu fayl növü qəbul olunmur. İcazə verilən növlərdən birini seçin.",
        "en": "This file type is not accepted. Choose one of the allowed types.",
        "ru": "Этот тип файла не принимается. Выберите один из допустимых типов.",
    },
    "assignments.too_large": {
        "az": "Fayl çox böyükdür.",
        "en": "The file is too large.",
        "ru": "Файл слишком большой.",
    },
    "assignments.file_not_available": {
        "az": "Fayl hələ yoxlanılır və ya yoxlamadan keçməyib.",
        "en": "The file is still being checked or did not pass the check.",
        "ru": "Файл ещё проверяется или не прошёл проверку.",
    },
    "assignments.storage_unavailable": {
        "az": "Fayl saxlama xidməti müvəqqəti əlçatan deyil. Bir az sonra cəhd edin.",
        "en": "File storage is temporarily unavailable. Try again shortly.",
        "ru": "Хранилище файлов временно недоступно. Повторите попытку чуть позже.",
    },
    "quizzes.not_found": {
        "az": "Test tapılmadı.",
        "en": "The quiz was not found.",
        "ru": "Квиз не найден.",
    },
    "quizzes.offering_not_found": {
        "az": "Bu fənn üzrə test yaratmaq mümkün deyil.",
        "en": "You cannot add quizzes to this course.",
        "ru": "Вы не можете добавлять квизы в эту дисциплину.",
    },
    "quizzes.question_not_found": {
        "az": "Sual tapılmadı.",
        "en": "The question was not found.",
        "ru": "Вопрос не найден.",
    },
    "quizzes.attempt_not_found": {
        "az": "Cəhd tapılmadı.",
        "en": "The attempt was not found.",
        "ru": "Попытка не найдена.",
    },
    "quizzes.already_published": {
        "az": "Test dərc olunub, onu dəyişmək olmaz.",
        "en": "The quiz is published and cannot be changed.",
        "ru": "Квиз опубликован, изменить его нельзя.",
    },
    "quizzes.no_questions": {
        "az": "Dərc etməzdən əvvəl ən azı bir sual əlavə edin.",
        "en": "Add at least one question before publishing.",
        "ru": "Перед публикацией добавьте хотя бы один вопрос.",
    },
    "quizzes.too_many_questions": {
        "az": "Testdə sualların sayı həddi aşıb.",
        "en": "The quiz has too many questions.",
        "ru": "В квизе слишком много вопросов.",
    },
    "quizzes.invalid_answers": {
        "az": "Cavablar düzgün formatda deyil.",
        "en": "The answers are not in the expected format.",
        "ru": "Ответы имеют неожиданный формат.",
    },
    "quizzes.points_out_of_range": {
        "az": "Bal sualın maksimum balı daxilində olmalıdır.",
        "en": "The points must be within the maximum of the question.",
        "ru": "Баллов должно быть не больше максимума за вопрос.",
    },
    "quizzes.not_a_student": {
        "az": "Yalnız bu fənnin tələbələri testi həll edə bilər.",
        "en": "Only students of this course can take the quiz.",
        "ru": "Проходить квиз могут только студенты этой дисциплины.",
    },
    "quizzes.not_available": {
        "az": "Test hazırda əlçatan deyil.",
        "en": "The quiz is not available right now.",
        "ru": "Квиз сейчас недоступен.",
    },
    "quizzes.attempt_limit_reached": {
        "az": "Cəhd sayı bitib.",
        "en": "You have used all attempts.",
        "ru": "Вы использовали все попытки.",
    },
    "quizzes.attempt_closed": {
        "az": "Bu cəhd artıq bitib.",
        "en": "This attempt is already finished.",
        "ru": "Эта попытка уже завершена.",
    },
    "quizzes.attempt_not_finished": {
        "az": "Cəhd hələ bitməyib.",
        "en": "The attempt is not finished yet.",
        "ru": "Попытка ещё не завершена.",
    },
    "quizzes.expired": {
        "az": "Testin vaxtı bitib.",
        "en": "The quiz time has run out.",
        "ru": "Время на квиз вышло.",
    },
    "quizzes.time_is_up": {
        "az": "Vaxt bitdi, cavablarınız təqdim olundu.",
        "en": "Time is up and your answers were submitted.",
        "ru": "Время вышло, ваши ответы отправлены.",
    },
    "quizzes.not_an_open_question": {
        "az": "Bu sual əl ilə qiymətləndirilmir.",
        "en": "This question is not graded by hand.",
        "ru": "Этот вопрос не оценивается вручную.",
    },
    "community.not_found": {
        "az": "Məzmun tapılmadı.",
        "en": "The content was not found.",
        "ru": "Материал не найден.",
    },
    "community.post_not_found": {
        "az": "Yazı tapılmadı.",
        "en": "The post was not found.",
        "ru": "Публикация не найдена.",
    },
    "community.question_not_found": {
        "az": "Sual tapılmadı.",
        "en": "The question was not found.",
        "ru": "Вопрос не найден.",
    },
    "community.answer_not_found": {
        "az": "Cavab tapılmadı.",
        "en": "The answer was not found.",
        "ru": "Ответ не найден.",
    },
    "community.thread_not_found": {
        "az": "Mesaj tapılmadı.",
        "en": "The message was not found.",
        "ru": "Сообщение не найдено.",
    },
    "community.tag_not_found": {
        "az": "Etiket tapılmadı.",
        "en": "The tag was not found.",
        "ru": "Тег не найден.",
    },
    "community.invalid_cursor": {
        "az": "Səhifə göstəricisi etibarsızdır. Siyahını yeniləyin.",
        "en": "The page marker is invalid. Refresh the list.",
        "ru": "Маркер страницы недействителен. Обновите список.",
    },
    "community.content_rejected": {
        "az": "Mətn qaydalara uyğun gəlmir. Onu dəyişib yenidən göndərin.",
        "en": "The text breaks the rules. Edit it and send again.",
        "ru": "Текст нарушает правила. Измените его и отправьте снова.",
    },
    "community.own_content": {
        "az": "Öz məzmununuza səs vermək və ya şikayət etmək olmaz.",
        "en": "You cannot vote for or report your own content.",
        "ru": "Нельзя голосовать за собственный материал или жаловаться на него.",
    },
    "community.not_question_author": {
        "az": "Cavabı yalnız sualın müəllifi qəbul edə bilər.",
        "en": "Only the author of the question can accept an answer.",
        "ru": "Принять ответ может только автор вопроса.",
    },
    "community.not_verifier": {
        "az": "Cavabı yalnız müəllim təsdiq edə bilər.",
        "en": "Only a teacher can verify an answer.",
        "ru": "Подтвердить ответ может только преподаватель.",
    },
    "community.promotion_not_allowed": {
        "az": "Bu mesajı foruma çıxarmaq mümkün deyil.",
        "en": "This message cannot be promoted to the forum.",
        "ru": "Это сообщение нельзя перенести на форум.",
    },
    "attendance.not_found": {
        "az": "Dərs tapılmadı.",
        "en": "The class meeting was not found.",
        "ru": "Занятие не найдено.",
    },
    "attendance.offering_not_found": {
        "az": "Bu fənn üzrə davamiyyət aça bilməzsiniz.",
        "en": "You cannot run attendance for this course.",
        "ru": "Вы не можете вести посещаемость по этой дисциплине.",
    },
    "attendance.student_not_found": {
        "az": "Bu tələbə fənnin siyahısında yoxdur.",
        "en": "This student is not in the course list.",
        "ru": "Этого студента нет в списке дисциплины.",
    },
    "attendance.session_open": {
        "az": "Bu fənn üçün açıq dərs artıq var. Əvvəlcə onu bağlayın.",
        "en": "A meeting is already open for this course. Close it first.",
        "ru": "По этой дисциплине уже открыто занятие. Сначала закройте его.",
    },
    "attendance.session_closed": {
        "az": "Bu dərsin iştirak qeydi bağlanıb.",
        "en": "Check-in for this meeting is closed.",
        "ru": "Отметка на этом занятии закрыта.",
    },
    "attendance.code_invalid": {
        "az": "Kod düzgün deyil. Müəllimin ekranındakı koda baxıb yenidən cəhd edin.",
        "en": "The code is not valid. Check the code on the teacher screen and try again.",
        "ru": "Код недействителен. Проверьте код на экране преподавателя и повторите попытку.",
    },
    "attendance.code_expired": {
        "az": "Kodun vaxtı bitib. Ekrandakı yeni kodu skan edin.",
        "en": "The code has expired. Scan the new code on the screen.",
        "ru": "Срок действия кода истёк. Отсканируйте новый код на экране.",
    },
    "attendance.not_enrolled": {
        "az": "Siz bu fənnə yazılmamısınız.",
        "en": "You are not enrolled in this course.",
        "ru": "Вы не записаны на эту дисциплину.",
    },
    "exams.not_found": {
        "az": "İmtahan tapılmadı.",
        "en": "The exam was not found.",
        "ru": "Экзамен не найден.",
    },
    "exams.offering_not_found": {
        "az": "Bu fənn təyinatı tapılmadı.",
        "en": "This course offering was not found.",
        "ru": "Занятия по этой дисциплине не найдены.",
    },
    "exams.unknown_room": {
        "az": "Belə otaq kampus xəritəsində yoxdur. Otaq kodunu yoxlayın.",
        "en": "This room is not on the campus map. Check the room code.",
        "ru": "Этой аудитории нет на карте кампуса. Проверьте код аудитории.",
    },
    "exams.window_too_long": {
        "az": "İmtahan 12 saatdan uzun ola bilməz.",
        "en": "An exam cannot be longer than 12 hours.",
        "ru": "Экзамен не может длиться более 12 часов.",
    },
    "exams.duplicate": {
        "az": "Bu fənn üçün həmin başlama vaxtında imtahan artıq var.",
        "en": "This course already has an exam starting at that time.",
        "ru": "У этой дисциплины уже есть экзамен с таким временем начала.",
    },
    "exams.subject_not_found": {
        "az": "Fənn tapılmadı.",
        "en": "The subject was not found.",
        "ru": "Дисциплина не найдена.",
    },
    "exams.type_not_allowed": {
        "az": "Bu fayl növü qəbul olunmur. İcazə verilən növlərdən birini seçin.",
        "en": "This file type is not accepted. Choose one of the allowed types.",
        "ru": "Этот тип файла не принимается. Выберите один из допустимых типов.",
    },
    "exams.too_large": {
        "az": "Fayl çox böyükdür.",
        "en": "The file is too large.",
        "ru": "Файл слишком большой.",
    },
    "exams.storage_unavailable": {
        "az": "Fayl saxlama xidməti müvəqqəti əlçatan deyil. Bir az sonra cəhd edin.",
        "en": "File storage is temporarily unavailable. Try again shortly.",
        "ru": "Хранилище файлов временно недоступно. Повторите попытку чуть позже.",
    },
    "exams.upload_not_found": {
        "az": "Yüklənmiş fayl tapılmadı. Faylı yenidən seçin.",
        "en": "The uploaded file was not found. Choose the file again.",
        "ru": "Загруженный файл не найден. Выберите файл снова.",
    },
    "exams.upload_missing": {
        "az": "Fayl hələ yüklənməyib. Yükləmənin bitməsini gözləyin.",
        "en": "The file has not finished uploading. Wait for the upload to end.",
        "ru": "Файл ещё не загружен полностью. Дождитесь окончания загрузки.",
    },
    "exams.upload_size_mismatch": {
        "az": "Yüklənən faylın ölçüsü uyğun gəlmir. Faylı yenidən yükləyin.",
        "en": "The uploaded file size does not match. Upload the file again.",
        "ru": "Размер загруженного файла не совпадает. Загрузите файл снова.",
    },
    "exams.consent_required": {
        "az": "Kağızı paylaşmaq üçün təsdiq qutusunu işarələyin.",
        "en": "Tick the confirmation box to share the paper.",
        "ru": "Отметьте подтверждение, чтобы поделиться работой.",
    },
    "exams.semester_not_finished": {
        "az": "Yalnız bitmiş semestrlərin imtahan kağızları paylaşıla bilər.",
        "en": "Only papers of semesters that have ended can be shared.",
        "ru": "Делиться можно только работами завершённых семестров.",
    },
    "exams.paper_not_found": {
        "az": "İmtahan kağızı tapılmadı.",
        "en": "The paper was not found.",
        "ru": "Работа не найдена.",
    },
    "exams.paper_not_scanned": {
        "az": "Fayl hələ yoxlanılır və ya yoxlamadan keçməyib. Təsdiq etmək mümkün deyil.",
        "en": "The file is still being checked or did not pass the check. It cannot be approved.",
        "ru": "Файл ещё проверяется или не прошёл проверку. Одобрить его нельзя.",
    },
    "exams.paper_not_available": {
        "az": "Fayl hələ yoxlanılır və ya yoxlamadan keçməyib.",
        "en": "The file is still being checked or did not pass the check.",
        "ru": "Файл ещё проверяется или не прошёл проверку.",
    },
    "server.internal_error": {
        "az": "Gözlənilməz xəta baş verdi. Bir az sonra yenidən cəhd edin.",
        "en": "An unexpected error occurred. Please try again shortly.",
        "ru": "Произошла непредвиденная ошибка. Повторите попытку чуть позже.",
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
