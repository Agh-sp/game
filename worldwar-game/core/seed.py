"""داده‌های اولیه بازی — فقط در صورت خالی بودن جدول‌ها درج می‌شود."""
from core.utils import jdumps

# (name, flag, iso_code, is_special, coin_price, population, has_sea, region, currency, oil_reserve, oil_richness)
COUNTRIES = [
    ("ایران", "🇮🇷", "ir", 0, 0, 86_000_000, 1, "خاورمیانه", "ریال", 208_000_000_000, 65),
    ("عراق", "🇮🇶", "iq", 0, 0, 44_000_000, 1, "خاورمیانه", "دینار عراق", 145_000_000_000, 55),
    ("سوریه", "🇸🇾", "sy", 0, 0, 23_000_000, 1, "خاورمیانه", "لیره سوریه", 2_500_000_000, 25),
    ("افغانستان", "🇦🇫", "af", 0, 0, 40_000_000, 0, "آسیا", "افغانی", 1_800_000_000, 15),
    ("پاکستان", "🇵🇰", "pk", 0, 0, 240_000_000, 1, "آسیا", "روپیه پاکستان", 1_200_000_000, 20),
    ("مصر", "🇪🇬", "eg", 0, 0, 105_000_000, 1, "آفریقا", "پوند مصر", 3_600_000_000, 30),
    ("قزاقستان", "🇰🇿", "kz", 0, 0, 19_000_000, 0, "آسیا", "تنگه", 30_000_000_000, 50),
    ("ازبکستان", "🇺🇿", "uz", 0, 0, 35_000_000, 0, "آسیا", "سوم", 600_000_000, 10),
    ("ویتنام", "🇻🇳", "vn", 0, 0, 98_000_000, 1, "آسیا", "دونگ", 4_400_000_000, 30),
    ("تایلند", "🇹🇭", "th", 0, 0, 71_000_000, 1, "آسیا", "بات", 500_000_000, 15),
    ("نیجریه", "🇳🇬", "ng", 0, 0, 223_000_000, 1, "آفریقا", "نایرا", 37_000_000_000, 55),
    ("آفریقای جنوبی", "🇿🇦", "za", 0, 0, 60_000_000, 1, "آفریقا", "راند", 15_000_000_000, 35),
    ("آرژانتین", "🇦🇷", "ar", 0, 0, 46_000_000, 1, "آمریکای جنوبی", "پزو آرژانتین", 2_400_000_000, 25),
    ("ونزوئلا", "🇻🇪", "ve", 0, 0, 28_000_000, 1, "آمریکای جنوبی", "بولیوار", 303_000_000_000, 70),
    ("مراکش", "🇲🇦", "ma", 0, 0, 37_000_000, 1, "آفریقا", "درهم مراکش", 700_000_000, 15),
    ("آمریکا", "🇺🇸", "us", 1, 2000, 335_000_000, 1, "آمریکای شمالی", "دلار", 68_000_000_000, 60),
    ("روسیه", "🇷🇺", "ru", 1, 1800, 144_000_000, 1, "آسیا", "روبل", 108_000_000_000, 65),
    ("چین", "🇨🇳", "cn", 1, 1800, 1_412_000_000, 1, "آسیا", "یوان", 26_000_000_000, 45),
    ("هند", "🇮🇳", "in", 1, 900, 1_430_000_000, 1, "آسیا", "روپیه هند", 4_600_000_000, 30),
    ("انگلیس", "🇬🇧", "gb", 1, 900, 67_000_000, 1, "اروپا", "پوند", 2_600_000_000, 30),
    ("ژاپن", "🇯🇵", "jp", 1, 850, 124_000_000, 1, "آسیا", "ین", 400_000_000, 10),
    ("آلمان", "🇩🇪", "de", 1, 800, 84_000_000, 1, "اروپا", "یورو", 130_000_000, 8),
    ("فرانسه", "🇫🇷", "fr", 1, 800, 65_000_000, 1, "اروپا", "یورو", 120_000_000, 8),
    ("اسرائیل", "🇮🇱", "il", 1, 700, 9_500_000, 1, "خاورمیانه", "شکل", 15_000_000, 5),
    ("ترکیه", "🇹🇷", "tr", 1, 600, 85_000_000, 1, "خاورمیانه", "لیر ترکیه", 5_200_000_000, 25),
    ("عربستان", "🇸🇦", "sa", 1, 600, 36_000_000, 1, "خاورمیانه", "ریال سعودی", 267_000_000_000, 75),
    ("کره شمالی", "🇰🇵", "kp", 1, 550, 26_000_000, 1, "آسیا", "وون کره شمالی", 500_000_000, 15),
    ("برزیل", "🇧🇷", "br", 1, 550, 216_000_000, 1, "آمریکای جنوبی", "رئال", 12_900_000_000, 40),
    ("کره جنوبی", "🇰🇷", "kr", 1, 500, 52_000_000, 1, "آسیا", "وون کره جنوبی", 200_000_000, 8),
    ("امارات", "🇦🇪", "ae", 1, 500, 9_500_000, 1, "خاورمیانه", "درهم امارات", 97_800_000_000, 65),
    ("کانادا", "🇨🇦", "ca", 1, 500, 39_000_000, 1, "آمریکای شمالی", "دلار کانادا", 163_000_000_000, 60),
    ("استرالیا", "🇦🇺", "au", 1, 450, 26_000_000, 1, "اقیانوسیه", "دلار استرالیا", 1_900_000_000, 18),
    ("اندونزی", "🇮🇩", "id", 1, 400, 275_000_000, 1, "آسیا", "روپیه اندونزی", 3_700_000_000, 28),
    ("اسپانیا", "🇪🇸", "es", 1, 400, 48_000_000, 1, "اروپا", "یورو", 200_000_000, 8),
    ("قطر", "🇶🇦", "qa", 1, 350, 3_000_000, 1, "خاورمیانه", "ریال قطر", 25_000_000_000, 60),
    ("سوییس", "🇨🇭", "ch", 1, 350, 9_000_000, 0, "اروپا", "فرانک سوییس", 0, 0),
    ("اوکراین", "🇺🇦", "ua", 1, 300, 38_000_000, 1, "اروپا", "هریونیا", 400_000_000, 12),
    ("هلند", "🇳🇱", "nl", 1, 300, 17_000_000, 1, "اروپا", "یورو", 300_000_000, 8),
    ("سنگاپور", "🇸🇬", "sg", 1, 300, 5_900_000, 1, "آسیا", "دلار سنگاپور", 90_000_000, 5),
    ("ایتالیا", "🇮🇹", "it", 1, 500, 59_000_000, 1, "اروپا", "یورو", 600_000_000, 10),
    ("مکزیک", "🇲🇽", "mx", 1, 300, 128_000_000, 1, "آمریکای شمالی", "پزو مکزیک", 9_800_000_000, 35),
    ("لهستان", "🇵🇱", "pl", 1, 250, 38_000_000, 1, "اروپا", "زلوتی", 100_000_000, 6),
    ("سوئد", "🇸🇪", "se", 1, 250, 10_500_000, 1, "اروپا", "کرون سوئد", 0, 0),
    ("مالزی", "🇲🇾", "my", 1, 200, 34_000_000, 1, "آسیا", "رینگیت", 3_000_000_000, 25),
    ("یونان", "🇬🇷", "gr", 1, 150, 10_000_000, 1, "اروپا", "یورو", 10_000_000, 2),
]

# تنگه‌های راهبردی دنیا
STRAITS = [
    ("hormuz", "تنگه هرمز", "⚓"),
    ("bab_el_mandeb", "تنگه باب‌المندب", "🌊"),
    ("suez", "کانال سوئز", "🚢"),
    ("malacca", "تنگه مالاکا", "🌊"),
    ("gibraltar", "تنگه جبل‌الطارق", "⚓"),
    ("bosporus", "تنگه بسفر و داردانل", "⚓"),
    ("panama", "کانال پاناما", "🚢"),
    ("bering", "تنگه برینگ", "❄️"),
]

# مودهای سیزن
SEASON_MODES = {
    "worldwar": "🌍 جنگ جهانی",
    "crusades": "✝️ جنگ‌های صلیبی",
    "ancient": "🏛 جنگ‌های باستان",
}

EQUIPMENT_CATEGORIES = [
    ("air", "هوایی", "✈️"),
    ("land", "زمینی", "🪖"),
    ("sea", "دریایی", "⚓"),
    ("cyber", "سایبری", "💻"),
    ("space", "فضایی", "🛰️"),
    ("missile", "موشکی", "🚀"),
]

# (category_key, subcategory, name, emoji, atk, def, cyber, speed, price_money, price_coins, requires_text)
EQUIPMENT = [
    # ── هوایی ──
    ("air", "drone", "پهپاد شناسایی ابابیل (پایه)", "🛸", 150, 80, 0, 4, 3_000_000, 0, ""),
    ("air", "drone", "پهپاد انتحاری شاهد ۱۳۶", "🎯", 450, 120, 0, 5, 8_000_000, 0, ""),
    ("air", "drone", "پهپاد تهاجمی MQ-9", "🛩️", 750, 300, 0, 4, 18_000_000, 0, ""),
    ("air", "fighter", "جنگنده رهگیر F-5 (پایه)", "✈️", 500, 400, 0, 3, 15_000_000, 0, ""),
    ("air", "fighter", "جنگنده چندمنظوره سوخو ۳۵", "🛩️", 1200, 800, 0, 4, 55_000_000, 0, ""),
    ("air", "fighter", "جنگنده نسل ۵ اف ۳۵ لایتنینگ", "⚡", 2200, 1400, 0, 5, 120_000_000, 0, ""),
    ("air", "bomber", "بمب‌افکن تاکتیکی سوخو ۲۴ (پایه)", "🛫", 900, 300, 0, 3, 35_000_000, 0, ""),
    ("air", "bomber", "بمب‌افکن استراتژیک B-2 اسپیریت", "🦇", 2500, 600, 0, 4, 160_000_000, 0, ""),
    ("air", "air_defense", "سامانه پدافند کوتاه برد تور ام۱ (پایه)", "🛡️", 100, 700, 0, 2, 20_000_000, 0, ""),
    ("air", "air_defense", "سامانه موشکی پاتریوت", "🚀", 200, 1500, 0, 2, 60_000_000, 0, ""),
    ("air", "air_defense", "سامانه برد بلند اس ۴۰۰ پیروزی", "🏰", 300, 2600, 0, 2, 110_000_000, 0, ""),
    ("air", "transport", "هواپیمای ترابری C-130 (پایه)", "🛬", 50, 250, 0, 3, 10_000_000, 0, ""),
    # ── زمینی ──
    ("land", "tank", "تانک ذوالفقار ۳ (پایه)", "💥", 400, 450, 0, 2, 12_000_000, 0, ""),
    ("land", "tank", "تانک تی ۹۰ ام روسی", "🛡️", 900, 850, 0, 2, 45_000_000, 0, ""),
    ("land", "tank", "تانک آبرامز M1A2", "🚜", 1400, 1300, 0, 2, 80_000_000, 0, ""),
    ("land", "apc", "نفربر خشایار (پایه)", "🚐", 80, 200, 0, 3, 5_000_000, 0, ""),
    ("land", "apc", "نفربر زرهی BTR-82A", "🚛", 220, 500, 0, 3, 18_000_000, 0, ""),
    ("land", "apc", "زره‌پوش رزمی بردلی M2", "🛡️", 450, 800, 0, 3, 35_000_000, 0, ""),
    ("land", "artillery", "توپخانه خودکششی رعد ۲ (پایه)", "💥", 350, 150, 0, 2, 9_000_000, 0, ""),
    ("land", "artillery", "راکت‌انداز چندگانه گراد BM-21", "🚀", 700, 200, 0, 2, 25_000_000, 0, ""),
    ("land", "artillery", "سامانه موشکی هایمارس M142", "🎯", 1500, 400, 0, 3, 75_000_000, 0, ""),
    # ── دریایی ──
    ("sea", "speedboat", "قایق تندرو موشک‌انداز ذوالفقار (پایه)", "🚤", 250, 180, 0, 5, 8_000_000, 0, ""),
    ("sea", "speedboat", "قایق تندر کاتاماران شهید سلیمانی", "⚡", 600, 400, 0, 5, 22_000_000, 0, ""),
    ("sea", "frigate", "ناوچه جماران (پایه)", "🚢", 800, 700, 0, 3, 40_000_000, 0, ""),
    ("sea", "frigate", "ناوشکن سنگین دنا", "🛳️", 1600, 1300, 0, 2, 110_000_000, 0, ""),
    ("sea", "submarine", "زیردریایی سبک کلاس غدیر (پایه)", "🦈", 500, 300, 0, 3, 25_000_000, 0, ""),
    ("sea", "submarine", "زیردریایی کلاس فاتح", "🐋", 1200, 800, 0, 3, 70_000_000, 0, ""),
    ("sea", "submarine", "زیردریایی هسته‌ای تهاجمی تایفون", "☢️", 2200, 1100, 0, 3, 220_000_000, 0, "نیازمند پروژه غنی‌سازی اورانیوم ۲۰٪"),
    ("sea", "carrier", "ناو هواپیمابر کلاس نیمیتز", "⛴️", 3000, 2200, 0, 1, 350_000_000, 0, ""),
    # ── سایبری ──
    ("cyber", "malware", "کرم نفوذگر دیداس (پایه)", "👾", 0, 0, 25_000, 0, 10_000_000, 0, ""),
    ("cyber", "malware", "بدافزار تخریب صنعتی استاکس‌نت", "💻", 0, 0, 70_000, 0, 35_000_000, 0, ""),
    ("cyber", "firewall", "سپر فایروال سایبری ملی (پایه)", "🛡️", 0, 0, 30_000, 0, 12_000_000, 0, ""),
    ("cyber", "firewall", "مرکز امنیت ابری و داده‌های ملی", "🗄️", 0, 0, 85_000, 0, 48_000_000, 0, ""),
    ("cyber", "ew", "سامانه اخلال راداری و ارتباطی (پایه)", "📡", 0, 0, 40_000, 0, 18_000_000, 0, ""),
    ("cyber", "ew", "واحد جنگ الکترونیک پیشرفته کراسوخا", "⚡", 0, 0, 130_000, 0, 85_000_000, 0, ""),
    # ── فضایی ──
    ("space", "space_weapon", "ماهواره شناسایی و هدایت نور", "🛰️", 2500, 0, 20_000, 5, 0, 150, ""),
    ("space", "space_weapon", "سلاح لیزر فضایی مداری", "🔆", 5000, 0, 0, 5, 0, 300, ""),
    ("space", "space_weapon", "موشک بالستیک مداری از ماه", "🌙", 8500, 0, 0, 5, 0, 500, "نیازمند شهر فضایی"),
    ("space", "space_weapon", "سامانه شهاب‌سنگ هدایت‌شده", "☄️", 7000, 0, 0, 4, 0, 450, ""),
    # ── موشکی (زمین‌به‌زمین / ضدکشتی / پدافند موشکی) ──
    ("missile", "cruise", "موشک کروز سومار", "🚀", 1200, 80, 0, 4, 30_000_000, 0, ""),
    ("missile", "cruise", "موشک کروز دریایی قدیر", "🛫", 1900, 120, 0, 5, 65_000_000, 0, ""),
    ("missile", "ballistic", "موشک بالستیک فاتح ۱۱۰", "🎯", 2400, 100, 0, 4, 55_000_000, 0, ""),
    ("missile", "ballistic", "موشک بالستیک خرمشهر", "☄️", 3600, 150, 0, 3, 110_000_000, 0, ""),
    ("missile", "antiship", "موشک ضدکشتی نور", "🌊", 1500, 120, 0, 5, 35_000_000, 0, ""),
    ("missile", "antiship", "موشک ضدکشتی خلیج فارس", "⚓", 2600, 180, 0, 5, 85_000_000, 0, ""),
    ("missile", "sam", "سامانه پدافند موشکی باور ۳۷۳", "🛡️", 250, 2100, 0, 3, 90_000_000, 0, ""),
]

SOLDIER_TYPES = [
    ("سرباز عادی", "🪖", 10, 0, 50_000, 0.15),
    ("تکاور", "🥷", 40, 0, 200_000, 0.3),
    ("نیروی ویژه", "🎯", 80, 0, 500_000, 0.5),
    ("خلبان جنگی", "🕹️", 120, 0, 1_000_000, 0.75),
    ("تکاور دریایی", "🤿", 60, 0, 400_000, 0.4),
    ("هکر نظامی", "👨‍💻", 5, 5_000, 800_000, 0.5),
]

# (sector, name, emoji, description, cost_money, cost_coins, satisfaction, capacity, duration_hours, requires_text)
BUILDINGS = [
    # ── برق ──
    ("power", "نیروگاه بادی", "🌬", "تولید برق از انرژی باد", 8_000_000, 0, 1, 500, 0, ""),
    ("power", "سد برق‌آبی", "🏞", "تولید برق از نیروی آب", 20_000_000, 0, 2, 1_500, 0, ""),
    ("power", "نیروگاه هسته‌ای", "☢️", "تولید انبوه برق — نیازمند پروژه غنی‌سازی اورانیوم ۲۰٪", 120_000_000, 0, 3, 4_000, 0, "پروژه غنی‌سازی اورانیوم ۲۰٪"),
    ("power", "نیروگاه کوانتومی", "⚛️", "مدرن‌ترین نیروگاه — فقط با سکه شاهی", 0, 250, 5, 10_000, 0, ""),
    # ── آب ──
    ("water", "تصفیه‌خانه فاضلاب", "♻️", "بازچرخانی و تصفیه آب", 10_000_000, 0, 1, 800, 0, ""),
    ("water", "استخراج آب زیرزمینی", "🕳", "حفاری چاه‌های عمیق", 15_000_000, 0, 0, 1_500, 0, ""),
    ("water", "برداشت یخچال‌ها", "🧊", "ذوب یخچال‌های طبیعی", 25_000_000, 0, 0, 3_500, 0, ""),
    ("water", "ساخت محلول آب", "💠", "تولید آب مصنوعی — فقط با سکه شاهی", 0, 120, 2, 10_000, 0, ""),
    # ── گاز شهری ──
    ("gas", "شبکه گاز شهری", "🔥", "توزیع گاز شهری در منازل و صنایع", 12_000_000, 0, 1, 600, 0, ""),
    ("gas", "ایستگاه تقویت فشار گاز", "🏭", "تقویت و پالایش خطوط انتقال گاز", 25_000_000, 0, 2, 1_800, 0, ""),
    ("gas", "مخازن ذخیره‌سازی گاز مایع", "🏔", "ذخایر استراتژیک گاز کشوری", 45_000_000, 0, 2, 4_000, 0, ""),
    ("gas", "ساخت محلول گاز", "🌀", "تولید گاز مصنوعی — فقط با سکه شاهی", 0, 100, 3, 10_000, 0, ""),
    # ── غذا ──
    ("food", "مزرعه میوه", "🍎", "تولید میوه و مرکبات", 8_000_000, 0, 1, 600, 0, ""),
    ("food", "مزرعه گندم", "🌾", "تولید غلات و نان", 10_000_000, 0, 1, 1_600, 0, ""),
    ("food", "مجتمع گلخانه‌ای مدرن", "🥗", "تولید محصولات مکانیزه کشاورزی", 22_000_000, 0, 2, 3_500, 0, ""),
    ("food", "غذای کپسولی", "💊", "غذای فشرده — فقط با سکه شاهی", 0, 80, 2, 10_000, 0, ""),
    # ── بهداشت ──
    ("health", "درمانگاه", "🏥", "خدمات درمان پایه", 12_000_000, 0, 2, 800, 0, ""),
    ("health", "بیمارستان", "🏬", "خدمات درمان پیشرفته", 40_000_000, 0, 4, 2_500, 0, ""),
    ("health", "واردات دارو", "💉", "تأمین دارو از خارج", 5_000_000, 0, 1, 500, 0, ""),
    ("health", "انتی‌بیوتیک همه‌کاره", "🧬", "داروی معجزه‌گر — فقط با سکه شاهی", 0, 60, 6, 8_000, 0, ""),
    # ── مسکن ──
    ("housing", "روستا", "🏚", "مسکن روستایی", 5_000_000, 0, 2, 500, 0, ""),
    ("housing", "شهرستان", "🏘", "ساخت شهرستان جدید", 18_000_000, 0, 3, 2_000, 0, ""),
    ("housing", "شهر بزرگ", "🌆", "کلان‌شهر مدرن", 60_000_000, 0, 5, 8_000, 0, ""),
    ("housing", "پایتخت جدید", "🏛", "جابه‌جایی پایتخت — فقط با سکه شاهی", 0, 200, 10, 20_000, 0, ""),
    # ── تفریحی (پروژه ملی - زمان کوتاه و مصالح مورد نیاز) ──
    ("fun", "موزه ملی", "🏛", "مرکز فرهنگی و تاریخی کشور", 25_000_000, 0, 3, 0, 0.15, ""),
    ("fun", "برج ملی", "🗼", "نماد اقتدار و معماری کشور", 80_000_000, 0, 5, 0, 0.3, "هزینه بر اساس ارتفاع محاسبه می‌شود"),
    ("fun", "ورزشگاه کوچک", "⚽", "ورزشگاه محلی با ظرفیت ۲۰ هزار نفر", 20_000_000, 0, 2, 0, 0.15, ""),
    ("fun", "ورزشگاه متوسط", "🏟", "ورزشگاه ملی با ظرفیت ۵۰ هزار نفر", 50_000_000, 0, 3, 0, 0.25, ""),
    ("fun", "ورزشگاه بزرگ", "🏟", "ورزشگاه المپیک با ظرفیت ۸۰ هزار نفر", 120_000_000, 0, 4, 0, 0.4, ""),
    ("fun", "ورزشگاه ابربزرگ", "🏟", "ورزشگاه بین‌المللی — فقط با سکه شاهی", 0, 150, 6, 0, 0.6, ""),
    ("fun", "جزیره مصنوعی", "🏝", "جزیره تفریحی لوکس", 200_000_000, 0, 7, 0, 0.8, ""),
    ("fun", "شهربازی فضایی", "🚀", "فقط با سکه شاهی", 0, 300, 9, 0, 1.0, ""),
    # ── علمی (پروژه ملی - زمان کوتاه و مصالح مورد نیاز) ──
    ("science", "پروژه ویروس", "🦠", "سلاح زیستی — قابل استفاده در اتاق جنگ", 60_000_000, 0, 0, 0, 0.25, ""),
    ("science", "پروژه واکسن", "💉", "پادزهر ویروس — دفاع در برابر سلاح زیستی", 40_000_000, 0, 1, 0, 0.2, ""),
    ("science", "غنی‌سازی اورانیوم ۲۰٪", "☢️", "پیش‌نیاز نیروگاه هسته‌ای و زیردریایی هسته‌ای", 90_000_000, 0, 1, 0, 0.5, ""),
    ("science", "پروژه رفتن به ماه", "🌕", "نخستین فرود روی ماه", 300_000_000, 0, 4, 0, 0.8, ""),
    ("science", "هوش مصنوعی", "🤖", "تحلیل‌گر نظامی — ۱۰٪ قدرت حمله بیشتر", 250_000_000, 0, 3, 0, 0.6, ""),
    ("science", "شهر فضایی", "🛸", "پیش‌نیاز موشک از ماه — فقط با سکه شاهی", 0, 400, 5, 0, 1.2, ""),
    ("science", "ایجاد موجود", "🧬", "آفرینش موجود زیستی با نام دلخواه — فقط با سکه شاهی", 0, 250, 5, 0, 0.5, ""),
]

COMPANY_TYPES = [
    ("game", "بازی‌سازی", "🎮", 3_000_000, 1),
    ("food", "غذایی", "🍔", 2_500_000, 1),
    ("film", "فیلم‌سازی", "🎬", 3_500_000, 2),
    ("auto", "خودروسازی", "🚗", 5_000_000, 2),
    ("pharma", "داروسازی", "💊", 6_000_000, 3),
    ("materials", "مصالح‌سازی", "🏗", 8_000_000, 4),
]

# (title, options [{label, satisfaction}], religion_effects, government_effects)
LAWS = [
    ("حجاب",
     [("آزاد", 3), ("اختیاری", 1), ("اجباری", -2)],
     {"اسلام": {"اجباری": 4, "آزاد": -3, "اختیاری": 2}, "بی‌دین": {"اجباری": -6}, "مسیحیت": {"اختیاری": 2}, "زرتشت": {"اختیاری": 2}},
     {"تئوکراسی": {"اجباری": 5, "آزاد": -4}, "جمهوری": {"اختیاری": 2}}),
    ("انتقاد از کشور",
     [("آزاد", 4), ("جریمه", -1), ("اعدام", -6)],
     {},
     {"دیکتاتوری": {"اعدام": 2, "آزاد": -4}, "فاشیسم": {"جریمه": 2, "آزاد": -3}, "جمهوری": {"آزاد": 3}}),
    ("دست‌فروشی",
     [("آزاد", 2), ("جریمه", -1), ("اعدام", -5)],
     {},
     {"دیکتاتوری": {"جریمه": 1}, "کمونیسم": {"جریمه": 2, "آزاد": -2}}),
    ("مشروبات الکلی",
     [("ممنوع", 0), ("مجاز از ۱۸ سال", 2), ("آزاد", 3)],
     {"اسلام": {"ممنوع": 3, "آزاد": -4}, "مسیحیت": {"مجاز از ۱۸ سال": 1}, "یهودی": {"مجاز از ۱۸ سال": 1}},
     {}),
    ("آزادی مطبوعات",
     [("آزاد", 5), ("سانسور", -2), ("دولتی", -1)],
     {},
     {"جمهوری": {"آزاد": 3}, "دیکتاتوری": {"سانسور": 2, "آزاد": -3}, "فاشیسم": {"دولتی": 2}}),
    ("حق سلاح",
     [("ممنوع", 1), ("با مجوز", 0), ("آزاد", -2)],
     {},
     {}),
    ("مجازات اعدام",
     [("لغو", 2), ("موارد خاص", 0), ("گسترده", -5)],
     {"بودایی": {"لغو": 3, "گسترده": -3}},
     {"تئوکراسی": {"گسترده": 2}, "جمهوری": {"موارد خاص": 1}}),
    ("ازدواج هم‌جنس",
     [("ممنوع", -1), ("مدنی", 3), ("مذهبی", 0)],
     {"اسلام": {"ممنوع": 2, "مدنی": -3}, "مسیحیت": {"ممنوع": 1}, "یهودی": {"ممنوع": 1}, "بی‌دین": {"مدنی": 2}},
     {}),
    ("آموزش",
     [("رایگان", 4), ("شهریه‌ای", -3)],
     {},
     {"کمونیسم": {"رایگان": 3}, "جمهوری": {"رایگان": 2}}),
    ("کار کودکان",
     [("ممنوع", 3), ("مجاز", -4)],
     {},
     {"کمونیسم": {"ممنوع": 2}, "فاشیسم": {"مجاز": 1}}),
]

RELIGIONS = [
    ("زرتشت", "🔥", "دین کهن ایران — احترام به طبیعت", {"satisfaction": 2, "science": 5}),
    ("اسلام", "☪️", "قوانین دینی اثر بیشتری روی رضایت دارند", {"satisfaction": 3, "laws": 2}),
    ("مسیحیت", "✝️", "پایداری اجتماعی و رفاه", {"welfare": 5, "satisfaction": 1}),
    ("یهودی", "✡️", "استعداد تجاری — ۱۰٪ مالیات تجارت کمتر", {"trade": 10}),
    ("بودایی", "☸️", "صلح‌طلب — رضایت پایه بیشتر", {"satisfaction": 5, "attack": -5}),
    ("بی‌دین", "⚛️", "علم‌گرایی — ۱۰٪ هزینه پروژه‌های علمی کمتر", {"science": 10, "satisfaction": -2}),
]

GOVERNMENTS = [
    ("فاشیسم", "🦅", "🦅", "قدرت تهاجمی بالا، رضایت پایین", {"attack": 20, "satisfaction": -10}),
    ("دیکتاتوری", "🗿", "🗿", "نظامی‌گری و مالیات بیشتر", {"attack": 10, "satisfaction": -15, "tax": 5}),
    ("کمونیسم", "🚩", "🚩", "دفاع قوی، تجارت ضعیف", {"defense": 15, "satisfaction": -5, "trade": -10}),
    ("جمهوری", "🗳", "🗳", "رضایت و تجارت بالا", {"satisfaction": 15, "trade": 10}),
    ("پادشاهی", "👑", "👑", "ثبات و رضایت متوسط", {"satisfaction": 8}),
    ("تئوکراسی", "📜", "📜", "قوانین دینی قوی، علم ضعیف", {"religion": 20, "science": -20, "satisfaction": 5}),
]

# (title, description, target_type, target_value, reward_money, reward_coins)
MISSIONS = [
    ("ورود روزانه", "هر روز وارد بازی شوید", "login", 1, 2_000_000, 1),
    ("معمار کشور", "یک ساختمان یا نیروگاه بسازید", "built", 1, 3_000_000, 1),
    ("فرمانده آموزش‌دیده", "۱۰۰ سرباز آموزش دهید", "trained", 100, 2_000_000, 0),
    ("خرید نظامی", "یک تجهیز نظامی بخرید", "bought", 1, 0, 2),
    ("صدای ملت", "یک بیانیه رسمی منتشر کنید", "statements", 1, 1_500_000, 0),
    ("دیپلمات فعال", "در یک رای‌گیری سازمان ملل شرکت کنید", "voted", 1, 0, 1),
    ("مرد جنگ", "در یک نبرد شرکت کنید", "war", 1, 0, 3),
]

COIN_PACKAGES = [
    (10, 10_000, 0),
    (50, 47_500, 5),
    (100, 90_000, 10),
    (500, 425_000, 15),
]


async def run(db) -> None:
    """درج داده‌های اولیه در صورت خالی بودن جدول‌ها."""
    if await _count(db, "countries") == 0:
        for name, flag, iso, special, coins, pop, sea, region, cur, oil, rich in COUNTRIES:
            toman = coins * 100_000
            flag_url = f"https://flagcdn.com/w640/{iso}.png"
            await db.execute(
                "INSERT INTO countries(name, flag, iso_code, flag_url, is_special, coin_price, toman_price, population, has_sea, region, "
                "currency, oil_reserve, oil_richness) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (name, flag, iso, flag_url, special, coins, toman, pop, sea, region, cur, oil, rich),
            )
    else:
        # به‌روزرسانی پرچم‌های واقعی (FlagCDN)، کد ISO و مقادیر نفت/ارز
        await db.execute(
            "UPDATE countries SET currency=name WHERE currency IS NULL OR currency=''")
        for name, flag, iso, special, coins, pop, sea, region, cur, oil, rich in COUNTRIES:
            flag_url = f"https://flagcdn.com/w640/{iso}.png"
            # ⚠️ پرچم انتخاب‌شده توسط بازیکن/ادمین (flag_url غیرخالی) هرگز بازنویسی نمی‌شود
            await db.execute(
                "UPDATE countries SET iso_code=?, flag=?, "
                "flag_url=CASE WHEN flag_url IS NULL OR flag_url='' THEN ? ELSE flag_url END "
                "WHERE name=?",
                (iso, flag, flag_url, name))
            await db.execute(
                "UPDATE countries SET currency=?, oil_reserve=?, oil_richness=? "
                "WHERE name=? AND ((currency IS NULL OR currency='') OR (oil_reserve IS NULL OR oil_reserve=0))",
                (cur, oil, rich, name))

    if await _count(db, "straits") == 0:
        for key, name, emoji in STRAITS:
            await db.execute(
                "INSERT INTO straits(key, name, emoji, is_active) VALUES(?,?,?,1)",
                (key, name, emoji))

    if await _count(db, "seasons") == 0:
        await db.execute(
            "INSERT INTO seasons(name, mode, is_active) VALUES(?,?,1)",
            ("سیزن ۱ — جنگ جهانی", "worldwar"))
        await db.execute(
            "INSERT OR IGNORE INTO settings(key, value) VALUES('season_name','سیزن ۱ — جنگ جهانی')")
        await db.execute(
            "INSERT OR IGNORE INTO settings(key, value) VALUES('season_mode','worldwar')")

    # دسته‌بندی‌ها: هر دسته جدید (مثل موشکی) حتی در دیتابیس‌های قبلی اضافه می‌شود
    for key, title, emoji in EQUIPMENT_CATEGORIES:
        await db.execute(
            "INSERT OR IGNORE INTO equipment_categories(key, title, emoji) VALUES(?,?,?)",
            (key, title, emoji),
        )

    # تجهیزات نظامی با زیردسته‌ها و مقادیر پایه — غیرمخرب و بدون تغییر ID
    cats = {r["key"]: r["id"] for r in await db.fetchall("SELECT id, key FROM equipment_categories")}
    for cat, subcat, name, emoji, atk, dfn, cyb, spd, money, coins, req in EQUIPMENT:
        if cat in cats:
            exists = await db.fetchone("SELECT id FROM equipment WHERE name=?", (name,))
            if exists:
                await db.execute(
                    "UPDATE equipment SET category_id=?, subcategory=?, emoji=?, attack_power=?, defense_power=?, "
                    "cyber_power=?, speed=?, price_money=?, price_coins=?, requires_text=? WHERE id=?",
                    (cats[cat], subcat, emoji, atk, dfn, cyb, spd, money, coins, req, exists["id"]),
                )
            else:
                await db.execute(
                    "INSERT INTO equipment(category_id, subcategory, name, emoji, attack_power, defense_power, cyber_power, "
                    "speed, price_money, price_coins, requires_text) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                    (cats[cat], subcat, name, emoji, atk, dfn, cyb, spd, money, coins, req),
                )
    # پیش‌نیازهای پروژه‌ای تجهیزات
    await _link_equipment_requirement(db, "زیردریایی هسته‌ای تهاجمی تایفون", "غنی‌سازی اورانیوم ۲۰٪")
    await _link_equipment_requirement(db, "موشک بالستیک مداری از ماه", "شهر فضایی")

    # به‌روزرسانی زمان تعلیم سربازان
    for name, emoji, power, cyb, cost, hours in SOLDIER_TYPES:
        exists = await db.fetchone("SELECT id FROM soldier_types WHERE name=?", (name,))
        if exists:
            await db.execute("UPDATE soldier_types SET train_hours=?, cost_per_unit=?, power=?, cyber_power=? WHERE id=?",
                             (hours, cost, power, cyb, exists["id"]))
        else:
            await db.execute(
                "INSERT INTO soldier_types(name, emoji, power, cyber_power, cost_per_unit, train_hours) VALUES(?,?,?,?,?,?)",
                (name, emoji, power, cyb, cost, hours),
            )

    # به‌روزرسانی زمان و ظرفیت پروژه‌ها و ساختمان‌ها
    for sector, name, emoji, desc, money, coins, sat, cap, dur, req_text in BUILDINGS:
        exists = await db.fetchone("SELECT id FROM buildings WHERE name=?", (name,))
        if exists:
            await db.execute("UPDATE buildings SET sector=?, emoji=?, description=?, cost_money=?, cost_coins=?, satisfaction=?, capacity=?, duration_hours=?, requires_text=? WHERE id=?",
                             (sector, emoji, desc, money, coins, sat, cap, dur, req_text, exists["id"]))
        else:
            await db.execute(
                "INSERT INTO buildings(sector, name, emoji, description, cost_money, cost_coins, satisfaction, "
                "capacity, duration_hours, requires_text) VALUES(?,?,?,?,?,?,?,?,?,?)",
                (sector, name, emoji, desc, money, coins, sat, cap, dur, req_text),
            )
    await _link_building_requirement(db, "نیروگاه هسته‌ای", "غنی‌سازی اورانیوم ۲۰٪")
    await _link_building_ratio(db, "ایستگاه تقویت فشار گاز", "شبکه گاز شهری", 3)

    if await _count(db, "company_types") == 0:
        for key, title, emoji, income, sat in COMPANY_TYPES:
            await db.execute(
                "INSERT INTO company_types(key, title, emoji, base_income, satisfaction) VALUES(?,?,?,?,?)",
                (key, title, emoji, income, sat),
            )

    if await _count(db, "laws") == 0:
        for title, options, rel_eff, gov_eff in LAWS:
            await db.execute(
                "INSERT INTO laws(title, options, religion_effects, government_effects) VALUES(?,?,?,?)",
                (title, jdumps([{"label": l, "satisfaction": s} for l, s in options]),
                 jdumps(rel_eff), jdumps(gov_eff)),
            )

    if await _count(db, "religions") == 0:
        for name, emoji, desc, effects in RELIGIONS:
            await db.execute(
                "INSERT INTO religions(name, emoji, description, effects) VALUES(?,?,?,?)",
                (name, emoji, desc, jdumps(effects)),
            )

    if await _count(db, "governments") == 0:
        for name, emoji, flag, desc, effects in GOVERNMENTS:
            await db.execute(
                "INSERT INTO governments(name, emoji, flag, description, effects) VALUES(?,?,?,?,?)",
                (name, emoji, flag, desc, jdumps(effects)),
            )

    if await _count(db, "missions") == 0:
        for title, desc, ttype, tval, money, coins in MISSIONS:
            await db.execute(
                "INSERT INTO missions(title, description, target_type, target_value, reward_money, reward_coins) "
                "VALUES(?,?,?,?,?,?)",
                (title, desc, ttype, tval, money, coins),
            )

    if await _count(db, "coin_packages") == 0:
        for coins, toman, discount in COIN_PACKAGES:
            await db.execute(
                "INSERT INTO coin_packages(coins, price_toman, discount_percent) VALUES(?,?,?)",
                (coins, toman, discount),
            )


async def _count(db, table: str) -> int:
    row = await db.fetchone(f"SELECT COUNT(*) AS c FROM {table}")
    return row["c"] if row else 0


async def _link_equipment_requirement(db, eq_name: str, project_name: str) -> None:
    eq = await db.fetchone("SELECT id FROM equipment WHERE name=?", (eq_name,))
    prj = await db.fetchone("SELECT id FROM buildings WHERE name=?", (project_name,))
    if eq and prj:
        await db.execute("UPDATE equipment SET requires_project_id=? WHERE id=?", (prj["id"], eq["id"]))


async def _link_building_requirement(db, b_name: str, project_name: str) -> None:
    b = await db.fetchone("SELECT id FROM buildings WHERE name=?", (b_name,))
    prj = await db.fetchone("SELECT id FROM buildings WHERE name=?", (project_name,))
    if b and prj:
        await db.execute("UPDATE buildings SET requires_project_id=? WHERE id=?", (prj["id"], b["id"]))


async def _link_building_ratio(db, b_name: str, req_name: str, ratio: int) -> None:
    b = await db.fetchone("SELECT id FROM buildings WHERE name=?", (b_name,))
    req = await db.fetchone("SELECT id FROM buildings WHERE name=?", (req_name,))
    if b and req:
        await db.execute(
            "UPDATE buildings SET requires_building_id=?, requires_ratio=? WHERE id=?",
            (req["id"], ratio, b["id"]),
        )
