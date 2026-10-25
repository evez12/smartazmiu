# AzMİU Academic Data (faculties, programs, subjects)

> Source: public pages of the university website (azmiu.edu.az), collected 2026-10-24.
> Purpose: reference data for the SmartAzMİU project (seed data, import templates, UI copy).
> **Status: not verified by the university.** The website itself contains inconsistencies (see §6). Treat this file as a draft and confirm with the dean's offices before using it as production data.

---

## 1. University facts

| Item | Value | Source |
|---|---|---|
| Name (az) | Azərbaycan Memarlıq və İnşaat Universiteti (AzMİU) | azmiu.edu.az |
| Name (en) | Azerbaijan University of Architecture and Construction (AzUAC) | azmiu.edu.az, Wikipedia |
| Origin | Construction faculty since 1920 (Baku Polytechnic Institute); independent institute in the 1930s; university status 1992; renamed by presidential decision on 13 June 2000 | Wikipedia (en) |
| Rector | Prof. Gülçöhrə Məmmədova | edu.gov.az |
| Languages of instruction | Azerbaijani, Russian, English (varies by program) | azmiu.edu.az |
| Grading | 100 points per subject: 50 during the semester (attendance 10, individual work 10, class/seminar/lab work 30) + 50 exam; minimum 17 exam points; absence above 25% of subject hours bars the student from the exam | Faculty pages (Construction, Construction Economics, Mechanics and IT) |
| ECTS scale | F below 51 · E 51–60 · D 61–70 · C 71–80 · B 81–90 · A 91–100 | Faculty of Construction page |
| Course project subjects | Semester score shifts to 20 (seminars/labs) + 10 (project) | Faculty pages |
| Internship | 14 weeks, semester VIII, graded out of 100 by a university commission | Faculty pages |
| Debt clearing | Re-examination on 25% of the course credit, on application to the dean's office | Faculty of Construction page |
| Typical bachelor load | 240 credits, 4 years, 8 semesters (1 credit = 30 hours) | Curriculum PDFs |

**Implication for SmartAzMİU:** the 100-point scale and the "passed" rule (≥ 51) should drive `enrollments.passed`. Grade bands above are useful for the guide `grade_visibility = range` option (the spec uses 51–70 / 71–90 / 91–100).

---

## 2. Faculties and departments (kafedra)

Faculty names follow the website's English pages (azmiu.edu.az/en/pages/...). Azerbaijani names are given where the source used them.

| # | Faculty (en) | Faculty (az) | Departments found on the website |
|---|---|---|---|
| 1 | Faculty of Architecture | Memarlıq fakültəsi | Architectural Design and Urban Planning · Fundamentals of Architecture · Architectural Structures and Restoration of Monuments · Landscape Architecture |
| 2 | Faculty of Construction | İnşaat fakültəsi | Building Constructions · Foundations, Foundations and Underground Structures · Technology, Organization and Management of Construction Production · Social Sciences · Operation and Reconstruction of Buildings and Facilities |
| 3 | Faculty of Water Management and Engineering Communication Systems | Su təsərrüfatı və mühəndis kommunikasiya sistemləri fakültəsi | Melioration and Water Management Construction Engineering · Construction of Engineering Systems and Facilities · Ecology · Higher Mathematics |
| 4 | Faculty of Transport | Nəqliyyat fakültəsi | Transportation and Logistics · Geomatics · Emergency Situations and Life Safety · Physics and Chemistry |
| 5 | Faculty of Design | Dizayn fakültəsi | Graphic and Media Design · Fine Arts · Environmental Design |
| 6 | Faculty of Construction and Economics (also written "Construction Economics") | Tikinti iqtisadiyyatı fakültəsi | Business Economics and Management · Economic Theory and Marketing · Organization and Management of Industry · Foreign Languages |
| 7 | Faculty of Mechanics and Information Technology | Mexanika və informasiya texnologiyaları fakültəsi | Information Technology and Systems · Technological Machines and Equipment · Descriptive Geometry and Engineering Graphics (the source page words it "Inverse Geometry and Engineering Graphics", likely a typo) |

Other structures listed on the site (not faculties with bachelor programs): Dean's Office of Education for Foreign Students · Preparatory Faculty for Foreign Citizens · Faculty of Advanced Training · SABAH Center.

Notes:
- The Azerbaijani faculty names in the table are translations of the English page titles, except where the sources used Azerbaijani. Confirm the official Azerbaijani names.
- The Faculty of Design was separated from the Faculty of Architecture (Design was previously a specialization there). Faculty of Water Management and Engineering Communication Systems was established 20.09.2001 (merger of two earlier faculties).

---

## 3. Bachelor programs (2025–2026 admission list)

Columns: program name (az) · state code from the site · languages (Az/En/Ru) · study form (FT = full-time/əyani, PT = part-time/qiyabi).
Source: azmiu.edu.az/en/pages/96 and /132. Codes: the site shows the newer 6-digit codes (e.g. 6006031) in the program list, while curriculum PDFs and some faculty pages still use the older 6-digit codes (e.g. 050626). Both are shown where known.

### Faculty of Architecture
| Program | Code (new) | Old code | Languages | Form |
|---|---|---|---|---|
| Memarlıq (Architecture) | 6006031 | 050626 | Az, En, Ru | FT |
| Şəhərsalma (Urban Planning) | 6006042 | 050637 | Az, Ru | FT |

### Faculty of Construction
| Program | Code | Old code | Languages | Form |
|---|---|---|---|---|
| İnşaat mühəndisliyi (Civil Engineering) | 6006018 | 050617 | Az, En, Ru | FT |
| Materiallar mühəndisliyi (Materials Engineering) | 6006027 | – | Az | FT |
| Sənaye mühəndisliyi (Industrial Engineering) | 6006041 | – | Az | FT |

The faculty page also lists Metrology, Standardization and Certification Engineering (050647) as a bachelor/master program; it does not appear in the 2025–2026 admission list.

### Faculty of Water Management and Engineering Communication Systems
| Program | Code | Languages | Form |
|---|---|---|---|
| Kommunikasiya sistemləri mühəndisliyi (Communication Systems Engineering) | 6006021 | Az, En | FT |
| Meliorasiya mühəndisliyi (Melioration / Land Reclamation Engineering) | 6006030 | Az, Ru | FT |
| Ekologiya mühəndisliyi (Ecology Engineering) | 6006007 | Az, En, Ru | FT |
| Neft-qaz mühəndisliyi (Oil and Gas Engineering) | 6006035 | Az | FT |
| Elektrik və elektronika mühəndisliyi (Electrical and Electronics Engineering; dual degree with Ankara University) | 6006008 | Az, En | FT |

### Faculty of Transport
| Program | Code | Languages | Form |
|---|---|---|---|
| Yerquruluşu və daşınmaz əmlakın kadastrı (Land Management and Real Estate Cadastre) | 6007009 | Az | FT, PT |
| Geomatika və geodeziya mühəndisliyi (Geomatics and Geodesy Engineering) | 6006011 | Az | FT |
| Logistika və nəqliyyat texnologiyaları mühəndisliyi (Logistics and Transport Technologies Engineering) | 6006025 | Az | FT |
| Nəqliyyat mühəndisliyi (Transport Engineering) | 6006036 | Az | FT |
| Nəqliyyat tikintisi mühəndisliyi (Transport Construction Engineering) | 6006037 | Az | FT |
| Həyat fəaliyyətinin təhlükəsizliyi mühəndisliyi (Life Safety Engineering) | 6006015 | Az | FT |

### Faculty of Design
| Program | Code | Old code | Languages | Form |
|---|---|---|---|---|
| Dizayn (Design) | 050306 (as listed) | – | Az, En, Ru | FT |

### Faculty of Construction and Economics
| Program | Code | Old code | Languages | Form |
|---|---|---|---|---|
| İqtisadiyyat (Economics) | 6004004 | 050405 | Az | FT, PT |
| Menecment (Management) | 6004007 (see note) | 050407/050408 | Az | FT, PT |
| Marketinq (Marketing) | 6004007 (see note) | 050407/050408 | Az, En | FT, PT |
| Biznesin idarə edilməsi (Business Administration) | 6004002 | 050402/050409 | Az | FT, PT |
| Davamlı inkişaf (Sustainable Development / Sustainability Management) | 6002002 | 050403 | Az | FT |

Note: the admission list shows the same code 6004007 for Management and Marketing, which is probably a typo on the site.

### Faculty of Mechanics and Information Technology
Old codes below come from the faculty page, which lists them next to program names in a garbled layout. The match for the two mechanics programs (050622 vs 050628) is a best guess.

| Program | Code | Old code | Languages | Form |
|---|---|---|---|---|
| İnformasiya texnologiyaları (Information Technology) | 6006016 | 050616 | Az, En, Ru | FT |
| İnformasiya təhlükəsizliyi (Information Security) | 6006017 | 050615 | Az, En | FT |
| Maşın mühəndisliyi (Machine Engineering) | 6006026 | 050622 | Az | FT |
| Mexanika mühəndisliyi (Mechanics Engineering) | 6006028 | 050628 | Az | FT |
| Proseslərin avtomatlaşdırılması mühəndisliyi (Process Automation Engineering) | 6006039 | 050634 | Az | FT |

### SABAH groups (separate admission lines)
Memarlıq (050626) and İnşaat mühəndisliyi (050617), Az, full-time.

---

## 4. Master's programs (curricula listed on the site)

The site does not state the faculty for each master's program. Names as listed (azmiu.edu.az/en/pages/132, English translation):

Urban Planning · Architecture · Design (specializations: Architectural Environment Design; Design and Technical Aesthetics; Visual Design and Media) · Civil Engineering · Metrology, Standardization and Certification Engineering · Land Reclamation and Water Management Construction Engineering · Engineering Systems and Facilities Construction Engineering · Ecological Engineering · Oil and Gas Facilities Engineering · Electrical Engineering · Process Automation Engineering · Transport Construction Engineering · Ground Transport Vehicles Engineering · Geodesy and Cartography Engineering · Land Structure, Soil and Urban Cadastre · Construction Materials and Products Technology Engineering · Materials Science Engineering · Emergency and Life Safety Engineering · Business Administration · Management · Industrial Organization and Management · Marketing · Information Technology and Systems Engineering · Technological Machinery and Equipment Engineering · Mechanics Engineering.

Doctoral programs exist (not listed on the pages fetched).

---

## 5. Subjects (fənlər) by program

Only the Economics plan could be read cleanly. The other PDFs were garbled when extracted; see the links in §7 for the originals. Credits and hours are as shown in the plan (1 credit = 30 hours).

### 5.1 İqtisadiyyat (Economics, 050405) — Faculty of Construction and Economics
This is the program that contains **Mikroiqtisadiyyat** (semester 3).

**Semester 1**
| Fənn | Credits | Hours |
|---|---|---|
| Azərbaycan tarixi | 5 | 150 |
| Xarici dildə işgüzar və akademik kommunikasiya-1 | 4 | 120 |
| Xətti cəbr və riyazi analiz | 8 | 240 |
| İKT-baza kompyuter bilikləri | 8 | 240 |
| Karyera planlaşması-1 | 5 | 150 |

**Semester 2**
| Fənn | Credits | Hours |
|---|---|---|
| Azərbaycan dilində işgüzar və akademik kommunikasiya | 4 | 120 |
| Xarici dildə işgüzar və akademik kommunikasiya-2 | 3 | 90 |
| İqtisadiyyata giriş | 6 | 180 |
| Ehtimal nəzəriyyəsi və riyazi statistika | 8 | 240 |
| Karyera planlaşması-2 | 9 | 270 |

**Semester 3**
| Fənn | Credits | Hours |
|---|---|---|
| Xarici dildə işgüzar və akademik kommunikasiya-3 | 4 | 120 |
| **Mikroiqtisadiyyat** | 10 | 300 |
| Statistika | 10 | 300 |
| Mülki müdafiə | 3 | 90 |
| Seçmə (I Blok, choose one): Fəlsəfə · Sosiologiya · Hüququn əsasları · Məntiq · Etika və estetika · Multikulturalizmə giriş | 3 | 90 |

**Semester 4**
| Fənn | Credits | Hours |
|---|---|---|
| Xarici dildə işgüzar və akademik kommunikasiya-4 | 4 | 120 |
| Makroiqtisadiyyat | 10 | 300 |
| Menecment | 7 | 210 |
| Seçmə (II Blok, choose one): İnformasiyanın idarə edilməsi · İnformasiya texnologiyaları (ixtisas üzrə) · Sahibkarlığın əsasları və biznesə giriş · Politologiya | 3 | 90 |
| Seçmə (VI Blok, choose one): Keyfiyyətə nəzarət · İqtisadi diplomatiya · İqtisadi dinamikanın inkişafı | 6 | 180 |

**Semester 5**
| Fənn | Credits | Hours |
|---|---|---|
| Ekonometrika | 10 | 300 |
| Azərbaycan iqtisadiyyatı | 6 | 180 |
| İqtisadi fikir tarixi | 4 | 120 |
| İnkişaf iqtisadiyyatı | 4 | 120 |
| Seçmə (IV Blok, choose one): Müəssisənin (firmanın) iqtisadiyyatı · İqtisadi tənzimləmə · Müəssisənin planlaşdırılması | 6 | 180 |

**Semester 6**
| Fənn | Credits | Hours |
|---|---|---|
| Sosial sahələrin iqtisadiyyatı | 6 | 180 |
| Beynəlxalq iqtisadiyyat | 4 | 120 |
| Ətraf mühitin iqtisadiyyatı | 6 | 180 |
| Seçmə (I Blok, choose one): Sənaye iqtisadiyyatı · Reqional iqtisadiyyat · Aqrar iqtisadiyyat | 6 | 180 |
| Seçmə (XIII Blok, choose one): İstehsalın təşkili · Sənayedə innovasiyanın idarə edilməsi · Antiböhranlı idarə etmə | 4 | 120 |

**Semester 7**
| Fənn | Credits | Hours |
|---|---|---|
| Rəqəmsal iqtisadiyyat (sahə iqtisadiyyatı) | 6 | 180 |
| Əməyin iqtisadiyyatı | 4 | 120 |
| Seçmə (VIII Blok, choose one): Tikintinin iqtisadiyyatı · İnvestisiyanın qiymətləndirilməsi · Tikinti müəssisəsinin (firmanın) xarici iqtisadi fəaliyyəti | 8 | 240 |
| Seçmə (IX Blok, choose one): Tikintidə smeta işi · İqtisadiyyatın tənzimlənməsi · İqtisadi təhlükəsizlik | 8 | 240 |
| Seçmə (XII Blok, choose one): Tikinti müəssisələrinin təsərrüfat fəaliyyətinin təhlili · Strateji planlaşdırma · Layihələrin idarə edilməsi | 6 | 180 |
| Seçmə (XIV Blok, choose one): Daşınmaz əmlakın iqtisadiyyatı · Mühəndis sistemlərinin iqtisadiyyatı · İnvestisiya layihələrinin idarə edilməsi | 6 | 180 |

**Semester 8**
| Fənn | Credits | Hours |
|---|---|---|
| Karyera planlaşması-3 | 10 | 300 |
| İstehsalat təcrübəsi (internship) | 6 | 180 |
| Seçmə (VIII Blok, choose one): Müəssisənin (firmanın) inkişaf strategiyası · Vergilər və vergitutma · İnsan resurslarının idarə edilməsi | 6 | 180 |
| Seçmə (X Blok, choose one): Mühasibat uçotu və audit · Maliyyə · Marketinq | 4 | 120 |

### 5.2 Menecment (Management) and Biznesin idarə edilməsi (Business Administration)
The curriculum PDFs published for both programs list **the same subjects as the Economics plan above** (same semester structure, same elective blocks). This is probably a copy-paste on the website, so the real plans may differ. Confirm with the faculty.

### 5.3 Marketinq (Marketing, 050407)
Shares semesters 1–4 mostly with Economics, but **Mikroiqtisadiyyat is in semester 2** and Makroiqtisadiyyat in semester 3 (the plan also repeats Makroiqtisadiyyat in semester 4, likely a mistake). Program-specific subjects (as extracted):

- Semester 4: Marketinq (6 credits)
- Semester 5: Pərakəndə ticarət marketinqi · Marketinq tədqiqatları · elective blocks (Marketinqdə qiymət siyasəti; İstehlak mallarının əmtəəşünaslığı və ekspertizası; Marketinq kommunikasiya sistemi; İstehsalın texnologiyası və təşkili; Dünya iqtisadiyyatı; Birja ticarətinin təşkili)
- Semester 6: İstehlakçı davranışı · Rəqəmsal marketinq · elective blocks (Azərbaycan iqtisadiyyatı; Xərclərin idarə edilməsi; Maliyyə uçotu; İctimaiyyətlə əlaqə; Brend marketinq; Logistika; Bazar infrastrukturu; Ehtiyatların idarə edilməsi; Elektron ticarət)
- Semester 7: Strateji marketinq · Satışın idarə edilməsi · elective blocks (İnnovasiya iqtisadiyyatı; Beynəlxalq marketinq; Sosial media marketinqi; Marketinqin idarə edilməsi; Marketinqin informasiya sistemi; Kommersiya fəaliyyəti)
- Semester 8: Karyera planlaşması-3 · İstehsalat təcrübəsi · Reklam işi · elective blocks (İqtisadiyyatın tənzimlənməsi; İnsan resurslarının idarə edilməsi; Bank marketinqi; İnşaatda marketinq; Aqromarketinq; Tərəfdaş münasibətləri marketinqi; Sahibkarlığın nəzəri və praktiki fəaliyyəti; İstehsal sahələri marketinqi; Xidmət sahələrinin marketinqi)

Credit/hour columns in this plan are partly inconsistent in the source.

### 5.4 İnformasiya texnologiyaları (Information Technology, 050616)
Subject list is reliable, **semester assignment is not** (the table was garbled). Total shown: 212 credits.

- **Humanitarian:** Azərbaycan tarixi · Azərbaycan dili və nitq mədəniyyəti · Xarici dildə işgüzar və akademik kommunikasiya 1, 2 (ingilis dili)
- **Elective humanitarian blocks:** Fəlsəfə / Sosiologiya / Məntiq / Etika və estetika / Multikulturalizmə giriş; Sahibkarlığın əsasları və biznesə giriş / İnformasiya axtarış üsulları / E-kommersiya
- **Core:** Xətti cəbr və analitik həndəsə · Riyazi analiz · Diskret riyaziyyat · Ehtimal nəzəriyyəsi və riyazi statistika · Fizika · İnformasiya texnologiyalarının əsasları · Kompüterlərin arxitekturası · Proqramlaşdırmanın əsasları · Diferensial tənliklər · Əməliyyat sistemləri · Verilənlərin strukturu və alqoritmlər · Verilənlər bazası sistemləri · Multimediya texnologiyaları · İnformasiya təhlükəsizliyi · İnsan-kompüter interfeysləri · Kompüter şəbəkələri · Web sistemləri və texnologiyaları · Süni intellekt · İT layihələrin idarə edilməsi · Mülki müdafiə · Müasir proqramlaşdırma dili
- **Elective specialty blocks (examples):** Obyekt-yönümlü proqramlaşdırma · Sistem mühəndisliyi · Database proqramlaşdırma · Sənaye interneti · Simsiz rabitə sistemləri · İnformasiya sistemləri · Sistemli analiz və modelləşdirmə · İnformasiya nəzəriyyəsi · Siqnalların analizi texnologiyaları

Note: the curriculum includes a subject named "Süni intellekt" (Artificial Intelligence). This is only an existing course name; it does not conflict with the SmartAzMİU out-of-scope rule on AI features.

### 5.5 İnşaat mühəndisliyi (Civil Engineering, 050617)
Subject list below is **approximate** (the semester split is unclear in the source, 240 credits total). Core and compulsory subjects mentioned: Azərbaycan tarixi · Azərbaycan dilində işgüzar və akademik kommunikasiya · Xarici dildə işgüzar və akademik kommunikasiya-1, 2 · Fizika-1, Fizika-2 (Elektrik) · Kimya · Tərsimi həndəsə və kompyuter qrafikası · İnformatika · Statika · Dinamika · Mülki müdafiə · Hidrologiya · Xətti cəbr və analitik həndəsə · Riyazi analiz · Mühəndis riyaziyyatı · Materiallar müqaviməti-1, 2 · İnşaat mexanikası-1, 2 · Dəmirbeton konstruksiyaları-1, 2 · Metal konstruksiyaları · Mühəndis geodeziyası · İnşaat materialları · Mühəndis geologiyası və qrunt mexanikası · İnşaat mühəndisliyində layihələndirmə. Elective blocks include: Memarlıq konstruksiyaları-1, 2 · Tikintidə smeta işi · Əsaslar və özüllər · Binaların zəlzələyə davamlılığı · Tikinti istehsalatının təşkili · Tikinti istehsalının texnologiyası · İnşaat konstruksiyalarının kompüter modelləşdirilməsi.

### 5.6 Mechanics and IT faculty — subjects mentioned on the faculty page
Systems Engineering · Information Security · Computer Networks · Operations Research and Optimization Methods · Theory of Machines and Mechanisms · Fundamentals of Machine Parts and Design · Technology of Construction Materials · Geometry and Engineering Graphics · Machines for Earthworks · Construction Machines and Equipment.

### 5.7 Other programs
Subject lists were not extracted. Open the curriculum PDFs from §7 (Architecture, Urban Planning, Design, Transport, Water Management programs, Mechanics programs).

---

## 6. Gaps and inconsistencies found

1. Program codes on the site mix two numbering systems (old 05xxxx and new 6xxxxxx). A Management/Marketing code conflict (050407 vs 050408; 6004007 for both) appears in the source.
2. Management and Business Administration curricula appear to be copies of the Economics plan.
3. Several curriculum PDFs have garbled tables; semester assignments for IT and Civil Engineering are unreliable.
4. Wikipedia's English article is outdated (it lists faculties and 30 specialties from an older structure). The official site pages were used instead.
5. Not found: dean names for most faculties, academic group naming rules (for example what `765a2` encodes), schedule/room/building data, and the official Azerbaijani faculty names.
6. The 2025–2026 admission list reflects the current structure; the structure may change for 2026–2027.

---

## 7. Sources

- AzMİU, English site: [Faculty of Water Management and Engineering Communication Systems](https://azmiu.edu.az/en/pages/74)
- AzMİU: [Bachelor's program page](https://azmiu.edu.az/en/pages/96) (2025–2026 program list, codes, languages)
- AzMİU: [Academic programs](https://azmiu.edu.az/en/pages/132) (curricula and program PDFs, master's list)
- AzMİU faculty pages: [Architecture](https://azmiu.edu.az/en/pages/72), [Construction](https://azmiu.edu.az/en/pages/73), [Transport](https://azmiu.edu.az/en/pages/75), [Construction and Economics](https://azmiu.edu.az/en/pages/80), [Mechanics and IT](https://azmiu.edu.az/en/pages/81), [Design](https://azmiu.edu.az/en/pages/650)
- Curriculum PDFs: [Economics](http://azmiu.edu.az/upload/ckeditor/1174880398.pdf), [Management](http://azmiu.edu.az/upload/ckeditor/2062174772.pdf), [Marketing](http://azmiu.edu.az/upload/ckeditor/1298255450.pdf), [Business Administration](http://azmiu.edu.az/upload/ckeditor/1440310812.pdf), [Information Technology](http://azmiu.edu.az/upload/ckeditor/772359597.pdf), [Civil Engineering](http://azmiu.edu.az/upload/ckeditor/2103664538.pdf). Other curriculum PDFs are linked from the Academic programs page.
- [Wikipedia: Azerbaijan University of Architecture and Construction](https://en.wikipedia.org/wiki/Azerbaijan_University_of_Architecture_and_Construction) (history and dates only)
- [edu.gov.az: design program article](https://edu.gov.az/az/printpage/20616) (Design faculty background, rector)

---

## 8. How this file should be used in SmartAzMİU

- Use §2–§3 to seed `faculties` and `specialties`, and §5.1 as realistic seed data for `subjects` and `course_offerings` (Mikroiqtisadiyyat, Makroiqtisadiyyat, Statistika, Ekonometrika, etc.).
- Do not treat this as authoritative: the real import (Sprint 2) must come from the university's own roster/curriculum export.
- Group codes such as `765a2` are known only from the product owner's context; their structure is not documented in these sources.
