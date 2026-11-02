# SmartAzMİU terminology glossary (az → en → ru)

> **Status: approved by the product owner on 2026-11-02** (British English, "Quiz", "Room" / «Аудитория» for both
> `Auditoriya` and `Otaq`; the other open choices of section 9 as proposed). The app's English and Russian texts
> follow it (D-113, D-114). No official EN/RU terminology list from the university exists; the English column follows
> the university's own English pages (`docs/AZMIU_ACADEMIC_DATA.md`) where they exist, the Russian column common usage
> in Azerbaijani Russian-language higher education. The texts have not been reviewed by a native speaker (D-114).

## 1. Rules for every string

| Rule | az | en | ru |
|---|---|---|---|
| Register | formal-friendly "siz" | plain, polite, second person ("you") | formal "вы" (lowercase mid-sentence, never "Вы" except in a letter's greeting) |
| Imperatives | verb + "-in" form: "Yadda saxlayın" | bare verb: "Save" | infinitive for buttons ("Сохранить"), polite imperative in sentences ("Проверьте поля") |
| Headings, buttons, labels | sentence case | sentence case ("Add a subject", not "Add A Subject") | sentence case |
| Exclamation marks | none | none | none |
| Emoji, slang, superlatives | none | none | none |
| One term per concept | glossary below | glossary below | glossary below |
| Placeholders | `{name}`, `{count}` identical in every locale | identical | identical |
| Plurals | ICU `plural` | `one` / `other` | `one` / `few` / `many` / `other` |
| Proper names | "SmartAzMİU", "AzMİU", group codes (`765a2`), room codes, "ÜOMG" stay as written | same | same, never transliterated |
| Numbers | decimal comma, thin grouping as today | locale default of next-intl (`24.5`), points in grades follow the locale | `24,5` with the comma |
| Dates and times | Asia/Baku, 24-hour, Monday first, `24 Oktyabr 2026` | `24 October 2026` (day first, month name from the locale) | `24 октября 2026 г.` |

Dates stay day-first in English as well (the university and its users are in Baku); this is deliberate and differs
from the US default.

## 2. Institution and people

| az | en | ru | Note |
|---|---|---|---|
| SmartAzMİU | SmartAzMİU | SmartAzMİU | wordmark, never translated |
| AzMİU | AzUAC (full name: Azerbaijan University of Architecture and Construction) | AzMİU (полное название: Азербайджанский университет архитектуры и строительства) | the university writes "AzUAC" in English; the app uses the full name once on public pages, "the university" elsewhere |
| Universitet | University | Университет | |
| Fakültə | Faculty | Факультет | |
| Kafedra | Department | Кафедра | the academic chair, not an administrative department |
| İxtisas | Specialty | Специальность | |
| Qrup | Group | Группа | e.g. `765a2` |
| Kurs (təhsil ili) | Year of study | Курс | "Kurs" as a year is the Russian sense; never used for a subject |
| Dekanlıq | Dean's office | Деканат | |
| Dekanlıq əməkdaşı | Dean's office staff | Сотрудник деканата | role `staff` |
| Tələbə | Student | Студент | |
| Müəllim | Teacher | Преподаватель | role `teacher`; never "Professor" |
| Kurator | Curator | Куратор | the group curator, role relation to a group; not "tutor" |
| Moderator | Moderator | Модератор | |
| Sistem administratoru | System administrator | Системный администратор | role `admin` |
| Qonaq | Guest | Гость | |
| Bələdçi | Guide | Наставник | a student who passed a subject and helps others; see section 9 (open choice 1) |
| Məsləhət | Advice | Совет | the guide's answer; "Məsləhət sorğusu" = advice request / запрос совета |
| İstifadəçi | User | Пользователь | |
| Hesab | Account | Учётная запись | "аккаунт" is not used |
| Profil | Profile | Профиль | |
| Rol | Role | Роль | |

## 3. Academic calendar and structure

| az | en | ru | Note |
|---|---|---|---|
| Fənn | Subject | Дисциплина | the discipline taught; the university's English pages say "subject" |
| Fənn icması | Subject community | Сообщество по дисциплине | persistent, across cohorts |
| Fənn təyinatı | Course offering | Занятия по дисциплине | a subject taught in one semester to given groups; see section 9 (open choice 2) |
| Fənn kartı | Subject card | Карточка дисциплины | guide's tips for a subject |
| Semestr | Semester | Семестр | |
| Payız semestri | Fall semester | Осенний семестр | |
| Yaz semestri | Spring semester | Весенний семестр | |
| Yay semestri | Summer semester | Летний семестр | |
| Tədris ili | Academic year | Учебный год | `2026–2027` |
| Həftə | Week | Неделя | |
| Üst həftə / Alt həftə | Upper week / Lower week | Верхняя неделя / Нижняя неделя | alternating schedule parity |
| Dərs cədvəli | Class schedule | Расписание занятий | nav label "Cədvəl" → "Schedule" / «Расписание» |
| Mühazirə | Lecture | Лекция | |
| Seminar | Seminar | Семинар | |
| Laboratoriya | Laboratory class | Лабораторное занятие | |
| Məşğələ | Practical class | Практическое занятие | |
| Auditoriya | Room | Аудитория | a classroom; "Otaq" is also "Room"; the app uses "Room" for both |
| Korpus | Building | Корпус | |
| Kredit | Credit | Кредит | ECTS credits: "ECTS credits" / «кредиты ECTS» |
| Qiymət | Grade | Оценка | the result of an assessment |
| Bal | Points | Балл (балла, баллов) | the 100-point scale |
| ÜOMG | GPA (ÜOMG) | Средний балл (ÜOMG) | Ümumi Orta Müvəffəqiyyət Göstəricisi; on a 100-point scale, not 4.0. The abbreviation stays next to the translation on first use per screen |
| Davamiyyət | Attendance | Посещаемость | |
| İmtahan | Exam | Экзамен | |
| İmtahan mərkəzi | Exam center | Экзаменационный центр | spelling: see section 9 (open choice 4) |
| İmtahan rejimi | Exam mode | Режим экзамена | the read-only chat mode during exams |
| Keçmiş imtahan kağızı | Past exam paper | Экзаменационные работы прошлых лет | |
| Sessiya | Exam session | Экзаменационная сессия | |
| Tapşırıq | Assignment | Задание | |
| Test | Quiz | Тест | the in-course test; "quiz" in English |
| Müddət | Deadline | Срок сдачи | for assignments; the generic "duration" is "Продолжительность" / "Duration" |
| Təqdim etmək | Submit | Отправить | for assignment work |
| Geridə qalan / gecikmiş | Late | С опозданием | |
| Şəxsi kabinet | Personal cabinet | Личный кабинет | the university system (Group C) |
| Transkript | Transcript | Академическая справка | see section 9 (open choice 3) |

## 4. App features

| az | en | ru | Note |
|---|---|---|---|
| Ana səhifə | Home | Главная | |
| Elan | Announcement | Объявление | |
| Tədbir | Event | Мероприятие | |
| Bildiriş | Notification | Уведомление | |
| Lent | Feed | Лента | |
| Sual-cavab | Q&A | Вопросы и ответы | the forum |
| Çat | Chat | Чат | |
| Kanal | Channel | Канал | |
| Mesaj | Message | Сообщение | |
| Şəxsi mesaj | Direct message | Личное сообщение | |
| Mövzu (söhbət) | Thread | Обсуждение | a reply thread in chat |
| Qeyd etmək | Mention | Упомянуть | |
| Reaksiya | Reaction | Реакция | |
| Material | Material | Материал | |
| Şikayət | Report | Жалоба | a user's report about content; as a verb "report" = «пожаловаться» |
| Moderasiya | Moderation | Модерация | |
| Rəy | Feedback | Отзыв | |
| Kampus xəritəsi | Campus map | Карта кампуса | |
| Məlumat idxalı | Data import | Импорт данных | |
| Audit jurnalı | Audit log | Журнал аудита | |
| Məxfilik | Privacy | Конфиденциальность | |
| Dəstək | Support | Поддержка | |
| Tanışlıq (onboarding) | Getting started | Знакомство с системой | |
| Əlçatanlıq | Accessibility | Доступность | |
| Tətbiq | App | Приложение | the PWA; "installed app" = «установленное приложение» |
| Tarixçə | History | История | |

## 5. Generic interface words

| az | en | ru |
|---|---|---|
| Yadda saxlayın | Save | Сохранить |
| Ləğv edin | Cancel | Отмена |
| Silin | Delete | Удалить |
| Redaktə edin | Edit | Изменить |
| Əlavə edin | Add | Добавить |
| Yaradın | Create | Создать |
| Göndərin | Send | Отправить |
| Yükləyin | Upload | Загрузить |
| Endirin | Download | Скачать |
| Axtarın | Search | Найти |
| Filtr | Filter | Фильтр |
| Yenidən cəhd edin | Try again | Повторить |
| Bağlayın | Close | Закрыть |
| Geri | Back | Назад |
| Növbəti / Əvvəlki | Next / Previous | Далее / Назад |
| Təsdiq edin | Confirm | Подтвердить |
| Rədd edin | Reject | Отклонить |
| Qəbul edin | Accept | Принять |
| Çıxış edin | Sign out | Выйти |
| Daxil olun | Sign in | Войти |
| Yüklənir | Loading | Загрузка |
| Heç nə tapılmadı | Nothing found | Ничего не найдено |
| İcazəniz yoxdur | You do not have permission | Нет доступа |
| Yeni | New | Новое |
| Hamısı | All | Все |
| Arxiv | Archive | Архив |
| Qaralama | Draft | Черновик |
| Dərc olunub | Published | Опубликовано |
| Gözləyir | Pending | Ожидает |
| Təsdiqlənib | Approved | Одобрено |
| Rədd edilib | Rejected | Отклонено |
| Aktiv / Deaktiv | Active / Inactive | Активна / Неактивна (по роду существительного) |
| Silinmiş istifadəçi | Deleted user | Удалённый пользователь |

## 6. Status and message conventions

| Case | az | en | ru |
|---|---|---|---|
| Error: what happened + what to do | "Faylı yükləmək mümkün olmadı. Yenidən cəhd edin." | "The file could not be uploaded. Try again." | «Не удалось загрузить файл. Повторите попытку.» |
| Validation, inline | plain sentence, no codes | plain sentence, no codes | plain sentence, no codes |
| Success toast (≤ 4 s) | "Yadda saxlanıldı." | "Saved." | «Сохранено.» |
| Empty state | one sentence + next action | one sentence + next action | one sentence + next action |
| Counts | `{count, plural, ...}` | `one` / `other` | `one` / `few` / `many` / `other` |
| Relative times | "5 dəqiqə əvvəl" | "5 minutes ago" | «5 минут назад» (through `Intl.RelativeTimeFormat`, not hand-made) |

## 7. E-mail and push wording

Notification kinds (`messages.py`) use the same terms. Greeting: "Hörmətli {name}," / "Dear {name}," /
«Здравствуйте, {name}!» is **not** used because Russian greetings take an exclamation mark; the proposed form is
«Здравствуйте, {name}.» (full stop, a conscious exception to the Russian convention to keep one rule: no exclamation
marks anywhere). Subjects keep the label and title: `{label}: {title}`.

## 8. Not translated

User-generated content (chat messages, posts, answers, assignment text), subject and group names, room codes, person
names, seeded academic data, file names, the "SmartAzMİU" wordmark, and the Keycloak login theme (stays Azerbaijani,
Sprint 15 answer 3).

## 9. Choices made at review

1. **Bələdçi.** EN "Guide" is direct and matches the roadmap. RU "Наставник" (mentor) reads better than "Гид"
   (tour guide) or "Проводник"; "Куратор" is taken by the group curator. Proposed: **Guide / Наставник**.
2. **Fənn təyinatı** (the subject taught to a group in one semester). EN "Course offering" mirrors the data model;
   RU has no short natural term. Proposed: **Course offering / Занятия по дисциплине**, with the shorter
   «Дисциплина» wherever the semester context is already on the screen.
3. **Transkript.** Proposed: **Transcript / Академическая справка** (the document students know). Alternative RU:
   «Транскрипт». Affects Group C only; can be decided later.
4. **Spelling.** British or American English? The university's English pages mix both. Proposed: **British**
   ("centre", "programme", "organisation") except for the product term "Exam center" which is kept short;
   if you prefer one rule, say "American" and every string follows it.
5. **Quiz vs Test.** Proposed EN **Quiz**, RU **Тест**. Say if EN should be "Test".
6. **Auditoriya vs Otaq.** Both become "Room" / «Аудитория» everywhere (decided at review). The classroom *type* on the
   map reads "Classroom" / «Учебная аудитория»; the audience of an announcement (also `Auditoriya`) is
   "Audience" / «Адресаты».
7. **Dates in English.** Day-first (`24 October 2026`), as in section 1 (accepted).
8. **Russian greeting without "!"** in e-mail (section 7) (accepted).
