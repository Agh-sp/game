"""رجیستری موجودیت‌های ادمین — همه جدول‌های بازی با فیلدهای فارسی.

این رجیستری به موتور CRUD عمومی می‌گوید هر جدول چه فیلدهایی دارد،
چه نوعی هستند و چطور نمایش داده شوند — یعنی ادمین می‌تواند
«همه چیز» را بسازد، ویرایش کند و حذف کند.
"""
from dataclasses import dataclass, field as dc_field

from core.images import IMAGE_SECTIONS

IMAGE_SECTIONS_KEYS = list(IMAGE_SECTIONS.keys())


@dataclass
class Field:
    key: str
    label: str
    type: str = "text"          # text|int|float|bool|ref|enum|json
    required: bool = False
    ref_table: str = ""
    ref_title: str = "name"
    options: list = dc_field(default_factory=list)
    min: float | None = None
    max: float | None = None
    help: str = ""
    skip_in_new: bool = False    # در ساخت ردیف جدید پرسیده نشود


@dataclass
class Entity:
    key: str                     # کلید کوتاه برای callback
    table: str
    title: str
    icon: str
    perm: str
    fields: list
    list_title: str = "name"     # عبارت SQL عنوان ردیف
    list_sub: str = ""           # عبارت SQL زیرنویس
    order_by: str = "id DESC"
    search_cols: list = dc_field(default_factory=list)
    can_create: bool = True
    can_delete: bool = True
    note: str = ""
    pk: str = "id"               # کلید اصلی جدول


REGISTRY: list[Entity] = []

E = lambda *a, **k: REGISTRY.append(Entity(*a, **k))

# ─── کاربران ───
E("usr", "users", "کاربران بازی", "👥", "users", [
    Field("id", "آیدی تلگرام", "int"),
    Field("full_name", "نام", "text"),
    Field("username", "یوزرنیم", "text"),
    Field("royal_coins", "سکه شاهی 🪙", "int"),
    Field("money", "پول پایه 💰", "int"),
    Field("country_id", "کشور", "ref", ref_table="countries", ref_title="name"),
    Field("country_taken_at", "زمان گرفتن کشور", "text"),
    Field("banned", "اخراج شده", "bool"),
    Field("joined_at", "تاریخ عضویت", "text", skip_in_new=True),
], list_title="id || ' — ' || COALESCE(full_name,'—')",
   list_sub="COALESCE(username,'')", order_by="id DESC", search_cols=["full_name", "username", "id"],
   can_create=False, note="برای کاربر جدید لازم نیست دستی ردیف بسازید؛ با /start خودکار ساخته می‌شود.")

E("stt", "states", "وضعیت کشورها (رضایت/قطعی/مسدودی)", "📊", "users", [
    Field("user_id", "کاربر", "int"),
    Field("satisfaction", "رضایت مردم", "float", min=0, max=100),
    Field("currency_name", "واحد پولی", "text"),
    Field("religion_id", "دین", "ref", ref_table="religions", ref_title="name"),
    Field("government_id", "حکومت", "ref", ref_table="governments", ref_title="name"),
    Field("chosen_laws", "قوانین انتخابی (JSON)", "json"),
    Field("subsidy_daily", "یارانه روزانه", "int"),
    Field("tax_rate", "نرخ مالیات (۰-۱)", "float", min=0, max=1),
    Field("blackout_power", "قطعی برق (ساعت)", "int", min=0, max=24),
    Field("blackout_water", "قطعی آب (ساعت)", "int", min=0, max=24),
    Field("blackout_gas", "قطعی گاز (ساعت)", "int", min=0, max=24),
    Field("leader_block_until", "مسدودی رهبر تا", "text", help="فرمت: YYYY-MM-DD HH:MM:SS"),
    Field("server_jam_until", "اختلال سرور تا", "text"),
    Field("disarmed_until", "خلع سلاح تا", "text"),
    Field("trade_banned", "تحریم تجاری (JSON)", "json"),
    Field("cyber_power", "قدرت سایبری پایه", "int"),
    Field("last_income", "آخرین درآمد", "text", skip_in_new=True),
], list_title="user_id || ' — رضایت ' || satisfaction", order_by="user_id DESC", pk="user_id")

E("ast", "player_assets", "دارایی بازیکنان (ساختمان/تجهیز/سرباز)", "📦", "users", [
    Field("user_id", "کاربر", "int"),
    Field("item_type", "نوع", "enum", options=["building", "equipment", "soldier", "food", "material"]),
    Field("item_id", "آیدی آیتم", "int"),
    Field("quantity", "تعداد", "int", min=0),
], list_title="user_id || ' → ' || item_type || '#' || item_id || ' ×' || quantity")

# ─── اقتصاد ───
E("pkg", "coin_packages", "پکیج‌های سکه شاهی", "📦", "economy", [
    Field("coins", "تعداد سکه", "int", required=True, min=1),
    Field("price_toman", "قیمت (تومان)", "int", required=True, min=0),
    Field("discount_percent", "تخفیف (٪)", "float", min=0, max=100),
    Field("is_active", "فعال", "bool"),
], list_title="coins || ' سکه — ' || price_toman || ' تومان'")

E("rcp", "receipts", "فیش‌های پرداخت", "🧾", "economy", [
    Field("user_id", "کاربر", "int"),
    Field("kind", "نوع", "enum", options=["country", "coins"]),
    Field("country_id", "کشور (در خرید کشور)", "int"),
    Field("coins", "سکه", "int"),
    Field("toman", "مبلغ تومان", "int"),
    Field("photo_file_id", "فایل عکس", "text"),
    Field("status", "وضعیت", "enum", options=["pending", "approved", "rejected"]),
    Field("note", "یادداشت", "text"),
    Field("reviewed_by", "بررسی‌کننده", "int", skip_in_new=True),
    Field("reviewed_at", "زمان بررسی", "text", skip_in_new=True),
    Field("created_at", "ایجاد", "text", skip_in_new=True),
], list_title="'#' || id || ' — ' || kind || ' — ' || status",
   order_by="status='pending' DESC, id DESC")

E("trd", "trades", "معاملات بازار", "🤝", "economy", [
    Field("seller_id", "فروشنده", "int"),
    Field("amount", "پول پایه", "int"),
    Field("price", "قیمت سکه", "int"),
    Field("status", "وضعیت", "enum", options=["open", "done", "cancelled"]),
    Field("buyer_id", "خریدار", "int"),
], list_title="'#' || id || ' — ' || amount || ' ← ' || price || ' سکه'")

# ─── کشورها ───
E("cnt", "countries", "کشورها", "🏳", "countries", [
    Field("name", "نام", "text", required=True),
    Field("flag", "پرچم (ایموجی)", "text"),
    Field("is_special", "ویژه 👑", "bool"),
    Field("coin_price", "قیمت سکه شاهی 🪙", "int", min=0),
    Field("toman_price", "قیمت پول واقعی 💳", "int", min=0),
    Field("population", "جمعیت", "int", min=0),
    Field("has_sea", "دسترسی به دریا", "bool"),
    Field("region", "منطقه", "enum",
          options=["خاورمیانه", "اروپا", "آسیا", "آفریقا", "آمریکای شمالی", "آمریکای جنوبی", "اقیانوسیه"]),
    Field("is_active", "فعال", "bool"),
    Field("owner_id", "مالک (آیدی کاربر)", "int"),
    Field("flag_url", "عکس پرچم (لینک/شناسه تلگرام)", "text"),
    Field("leader_title", "عنوان رهبر", "text", help="رئیس‌جمهور / نخست‌وزیر / پادشاه / شورا"),
    Field("leader_name", "نام رهبر", "text", help="در صورت ترور، بازی این را خودکار تغییر می‌دهد"),
    Field("leader_since", "رهبر از تاریخ", "text"),
    Field("gdp_factor", "ضریب اقتصاد (درآمد)", "float", min=0),
    Field("oil_income_base", "درآمد نفتی هر ۱۰ دقیقه (میلیون)", "int", min=0, max=100),
], list_title="flag || ' ' || name",
   list_sub="CASE WHEN is_special=1 THEN '👑 ویژه — ' || coin_price || ' سکه' ELSE '🆓 رایگان' END",
   search_cols=["name", "region"])

# ─── نظامی ───
E("eq", "equipment", "تجهیزات نظامی", "🪖", "military", [
    Field("category_id", "دسته", "ref", required=True, ref_table="equipment_categories", ref_title="title"),
    Field("name", "نام", "text", required=True),
    Field("emoji", "ایموجی", "text"),
    Field("attack_power", "قدرت تهاجمی ⚔️", "int", min=0),
    Field("defense_power", "قدرت دفاعی 🛡", "int", min=0),
    Field("cyber_power", "قدرت سایبری 🖥", "int", min=0),
    Field("speed", "سرعت ⚡ (۱-۵)", "int", min=1, max=5,
          help="هرچه بیشتر، زودتر به مقصد نبرد می‌رسد"),
    Field("price_money", "قیمت پول 💰", "int", min=0),
    Field("price_coins", "قیمت سکه 🪙 (۰=فقط پول)", "int", min=0),
    Field("requires_project_id", "پیش‌نیاز پروژه", "ref", ref_table="buildings", ref_title="name"),
    Field("requires_text", "متن پیش‌نیاز", "text"),
    Field("is_active", "فعال", "bool"),
], list_title="emoji || ' ' || name", search_cols=["name"])

E("cat", "equipment_categories", "دسته‌های تجهیزات", "🗂", "military", [
    Field("key", "کلید لاتین", "text", required=True, help="مثلاً air / land / sea / cyber / space"),
    Field("title", "عنوان فارسی", "text", required=True),
    Field("emoji", "ایموجی", "text"),
    Field("is_active", "فعال", "bool"),
], list_title="emoji || ' ' || title")

E("sld", "soldier_types", "انواع سرباز", "🎖", "military", [
    Field("name", "نام", "text", required=True),
    Field("emoji", "ایموجی", "text"),
    Field("power", "قدرت هر نفر", "int", min=0),
    Field("cyber_power", "قدرت سایبری هر نفر", "int", min=0),
    Field("cost_per_unit", "هزینه آموزش هر نفر", "int", min=0),
    Field("train_hours", "مدت آموزش (ساعت)", "int", min=1),
    Field("is_active", "فعال", "bool"),
], list_title="emoji || ' ' || name")

E("trn", "soldier_trainings", "آموزش‌های در جریان", "🎓", "military", [
    Field("user_id", "کاربر", "int"),
    Field("type_id", "نوع سرباز", "ref", ref_table="soldier_types", ref_title="name"),
    Field("count", "تعداد", "int", min=1),
    Field("completes_at", "پایان آموزش", "text"),
], list_title="user_id || ' — ' || count || ' نفر'", can_create=False)

E("bas", "bases", "پایگاه‌های نظامی", "🚚", "military", [
    Field("host_id", "کشور میزبان", "int"),
    Field("guest_id", "مستقرکننده", "int"),
    Field("status", "وضعیت", "enum", options=["pending", "active"]),
    Field("created_at", "ایجاد", "text", skip_in_new=True),
], list_title="'#' || id || ' — ' || status")

# ─── دنیا و قوانین ───
E("bld", "buildings", "ساختمان‌ها و پروژه‌ها", "🏗", "world", [
    Field("sector", "بخش", "enum", required=True,
          options=["power", "water", "gas", "food", "health", "housing", "fun", "science"]),
    Field("name", "نام", "text", required=True),
    Field("emoji", "ایموجی", "text"),
    Field("description", "توضیح", "text"),
    Field("cost_money", "هزینه پول 💰", "int", min=0),
    Field("cost_coins", "هزینه سکه 🪙", "int", min=0),
    Field("satisfaction", "اثر رضایت 😊", "float"),
    Field("capacity", "ظرفیت تولید", "int", min=0),
    Field("duration_hours", "مدت ساخت (ساعت)", "float", min=0),
    Field("requires_building_id", "پیش‌نیاز ساختمان", "ref", ref_table="buildings", ref_title="name"),
    Field("requires_ratio", "نسبت پیش‌نیاز", "int", min=0, help="مثلاً ۵ یعنی هر واحد به ۵ عدد پیش‌نیاز نیاز دارد"),
    Field("requires_project_id", "پیش‌نیاز پروژه", "ref", ref_table="buildings", ref_title="name"),
    Field("requires_text", "متن پیش‌نیاز", "text"),
    Field("is_active", "فعال", "bool"),
], list_title="emoji || ' ' || name || ' (' || sector || ')'", search_cols=["name", "sector"])

E("law", "laws", "قوانین کشور", "⚖️", "world", [
    Field("title", "عنوان", "text", required=True),
    Field("options", "گزینه‌ها (JSON)", "json", required=True,
          help='[{"label":"آزاد","satisfaction":3},...]'),
    Field("religion_effects", "اثر ادیان (JSON)", "json"),
    Field("government_effects", "اثر حکومت‌ها (JSON)", "json"),
    Field("is_active", "فعال", "bool"),
], list_title="title")

E("rel", "religions", "ادیان", "⛪", "world", [
    Field("name", "نام", "text", required=True),
    Field("emoji", "ایموجی", "text"),
    Field("description", "توضیح", "text"),
    Field("effects", "اثرها (JSON)", "json", help='مثل {"satisfaction":3,"science":5}'),
    Field("is_active", "فعال", "bool"),
], list_title="emoji || ' ' || name")

E("gov", "governments", "حکومت‌ها", "🏛", "world", [
    Field("name", "نام", "text", required=True),
    Field("emoji", "ایموجی", "text"),
    Field("flag", "پرچم حکومتی", "text"),
    Field("description", "توضیح", "text"),
    Field("effects", "اثرها (JSON)", "json",
          help='مثل {"attack":20,"satisfaction":-10}'),
    Field("is_active", "فعال", "bool"),
], list_title="emoji || ' ' || name")

# ─── شرکت‌ها و پروژه‌ها ───
E("ctp", "company_types", "انواع شرکت", "🏢", "projects", [
    Field("key", "کلید لاتین", "text", required=True),
    Field("title", "عنوان فارسی", "text", required=True),
    Field("emoji", "ایموجی", "text"),
    Field("base_income", "درآمد روزانه پایه", "int", min=0),
    Field("satisfaction", "اثر رضایت", "float"),
    Field("is_active", "فعال", "bool"),
], list_title="emoji || ' ' || title")

E("cmp", "companies", "شرکت‌های بازیکنان", "🏭", "projects", [
    Field("owner_id", "مالک", "int"),
    Field("type_id", "نوع", "ref", ref_table="company_types", ref_title="title"),
    Field("name", "نام شرکت", "text", required=True),
    Field("income_daily", "درآمد روزانه", "int", min=0),
    Field("announced", "اعلام شده", "bool"),
    Field("last_withdraw", "آخرین برداشت", "text"),
], list_title="name")

E("prj", "player_projects", "پروژه‌ها و پژوهش‌های بازیکنان", "🔬", "projects", [
    Field("user_id", "کاربر", "int"),
    Field("building_id", "پروژه", "ref", ref_table="buildings", ref_title="name"),
    Field("name", "نام دلخواه", "text"),
    Field("status", "وضعیت", "enum", options=["in_progress", "done"]),
    Field("completes_at", "اتمام", "text"),
    Field("cost_money", "هزینه پول", "int"),
    Field("cost_coins", "هزینه سکه", "int"),
], list_title="COALESCE(name,'—') || ' (' || status || ')'",
   note="برای حذف پژوهش/پروژه یک کشور، ردیفش را از اینجا حذف کنید.")

# ─── سازمان ملل و جنگ ───
E("vot", "un_votes", "رای‌گیری‌ها", "🗳", "un", [
    Field("title", "عنوان", "text", required=True),
    Field("kind", "نوع", "enum", options=["war", "crime", "sanction"]),
    Field("subject_id", "موضوع (آیدی)", "int"),
    Field("options", "گزینه‌ها (JSON)", "json"),
    Field("status", "وضعیت", "enum", options=["open", "closed"]),
    Field("ends_at", "پایان", "text"),
    Field("created_by", "ایجادکننده", "int"),
], list_title="title")

E("bal", "un_ballots", "آرای سازمان ملل", "✋", "un", [
    Field("vote_id", "رای‌گیری", "int"),
    Field("user_id", "کاربر", "int"),
    Field("choice", "گزینه (شماره)", "int"),
    Field("weight", "وزن رأی", "int"),
], list_title="'رأی ' || user_id || ' در ' || vote_id", can_create=False, pk="rowid",
   order_by="rowid DESC")

E("war", "wars", "جنگ‌ها", "⚔️", "un", [
    Field("attacker_id", "مهاجم", "int"),
    Field("defender_id", "مدافع", "int"),
    Field("reason", "دلیل", "text"),
    Field("permission", "با مجوز", "bool"),
    Field("status", "وضعیت", "enum", options=["voting", "active", "rejected", "ended"]),
    Field("war_crime", "جنایت جنگی", "bool"),
    Field("ended_at", "پایان", "text"),
], list_title="'جنگ #' || id || ' — ' || status")

E("bat", "battles", "نبردها", "💥", "un", [
    Field("war_id", "جنگ", "int"),
    Field("attacker_id", "مهاجم", "int"),
    Field("defender_id", "مدافع", "int"),
    Field("atk_type", "نوع حمله", "enum", options=["sea", "air", "land", "space", "mixed"]),
    Field("atk_power", "قدرت حمله", "int"),
    Field("def_power", "قدرت دفاع", "int"),
    Field("result", "نتیجه", "enum", options=["win", "lose"]),
    Field("loot", "غارت", "int"),
], list_title="'نبرد #' || id", can_create=False)

E("cyb", "cyber_ops", "عملیات سایبری", "🕶", "un", [
    Field("attacker_id", "مهاجم", "int"),
    Field("defender_id", "هدف", "int"),
    Field("kind", "نوع", "enum", options=["assass", "steal", "jam"]),
    Field("success", "موفق", "bool"),
    Field("amount", "مبلغ دزدی", "int"),
], list_title="kind || ' — ' || CASE WHEN success=1 THEN 'موفق' ELSE 'ناموفق' END", can_create=False)

E("stm", "statements", "بیانیه‌ها", "📢", "un", [
    Field("user_id", "کاربر", "int"),
    Field("text", "متن بیانیه", "text", required=True),
], list_title="'بیانیه #' || id")

# ─── ماموریت‌ها ───
E("msn", "missions", "ماموریت‌های روزانه", "🎯", "missions", [
    Field("title", "عنوان", "text", required=True),
    Field("description", "توضیح", "text"),
    Field("target_type", "نوع هدف", "enum", required=True,
          options=["login", "built", "trained", "bought", "statements", "voted", "war"],
          help="login=ورود روزانه، built=ساخت، trained=آموزش سرباز، bought=خرید تجهیز، "
               "statements=بیانیه، voted=رأی سازمان ملل، war=نبرد"),
    Field("target_value", "مقدار هدف", "int", min=1),
    Field("reward_money", "پاداش پول 💰", "int", min=0),
    Field("reward_coins", "پاداش سکه 🪙", "int", min=0),
    Field("is_active", "فعال", "bool"),
], list_title="title")

# ─── تیکت‌ها ───
E("tik", "tickets", "تیکت‌های پشتیبانی", "🎫", "tickets", [
    Field("user_id", "کاربر", "int"),
    Field("kind", "نوع", "enum", options=["complaint", "idea", "bug"]),
    Field("text", "متن", "text"),
    Field("photo_file_id", "عکس", "text"),
    Field("status", "وضعیت", "enum", options=["open", "answered", "closed"]),
    Field("reply", "پاسخ", "text"),
    Field("replied_by", "پاسخ‌دهنده", "int"),
], list_title="'#' || id || ' — ' || kind || ' — ' || status")

# ─── تجارت، پیمان‌ها و بخش‌های جدید ───
E("neg", "negotiations", "مذاکره‌ها", "🕊", "trade", [
    Field("initiator_id", "آغازگر", "int"),
    Field("status", "وضعیت", "enum", options=["pending", "open", "ended", "failed", "rejected"]),
    Field("ended_at", "پایان", "text"),
], list_title="'#' || id || ' — ' || status", can_create=False)

E("trt", "treaties", "پیمان‌ها", "📜", "trade", [
    Field("kind", "نوع", "enum", options=["military", "trade", "peace", "trust", "brothers"]),
    Field("party_a", "طرف الف", "int"),
    Field("party_b", "طرف ب", "int"),
    Field("witness_id", "شاهد", "int"),
    Field("neg_id", "مذاکره", "int"),
    Field("status", "وضعیت", "enum", options=["pending", "active", "broken", "rejected", "ended"]),
    Field("trade_percent", "درصد تجاری", "float", min=0, max=100),
], list_title="'#' || id || ' — ' || kind || ' — ' || status", can_create=False)

E("dtr", "direct_trades", "تجارت‌های مستقیم", "🔁", "trade", [
    Field("from_id", "پیشنهاددهنده", "int"),
    Field("to_id", "طرف مقابل", "int"),
    Field("give_type", "می‌دهد (نوع)", "enum", options=["money", "coins", "energy", "water", "gas", "oil", "equip", "soldier"]),
    Field("give_id", "آیدی آیتم", "int"),
    Field("give_qty", "مقدار", "int"),
    Field("want_type", "می‌خواهد (نوع)", "enum", options=["money", "coins", "energy", "water", "gas", "oil", "equip", "soldier"]),
    Field("want_id", "آیدی آیتم", "int"),
    Field("want_qty", "مقدار", "int"),
    Field("value_estimate", "ارزش تقریبی", "int"),
    Field("status", "وضعیت", "enum", options=["pending", "accepted", "declined", "cancelled", "failed"]),
], list_title="'#' || id || ' — ' || status", can_create=False)

E("ofo", "oil_offers", "عرضه‌های نفت", "🛢", "trade", [
    Field("seller_id", "فروشنده", "int"),
    Field("barrels", "بشکه", "int", min=0),
    Field("price_money", "قیمت پول", "int", min=0),
    Field("price_coins", "قیمت سکه", "int", min=0),
    Field("status", "وضعیت", "enum", options=["open", "done", "cancelled"]),
    Field("buyer_id", "خریدار", "int"),
], list_title="'#' || id || ' — ' || barrels || ' بشکه'")

E("rev", "revolutions", "انقلاب‌ها", "🔥", "un", [
    Field("user_id", "کاربر", "int"),
    Field("country_id", "کشور", "ref", ref_table="countries", ref_title="name"),
    Field("severity", "شدت انقلاب", "int", min=0, max=100),
    Field("status", "وضعیت", "enum", options=["active", "resolved", "suppressed", "succeeded", "cancelled", "paused"]),
    Field("trigger", "علت", "text"),
    Field("ends_at", "مهلت", "text", help="YYYY-MM-DD HH:MM:SS"),
    Field("outcome", "نتیجه", "text"),
    Field("money_spent", "پول‌پاشی", "int"),
    Field("troops_lost", "تلفات سرباز", "int"),
], list_title="'🔥 #' || id || ' — ' || COALESCE(status,'')", can_create=False)

E("obs", "oil_business", "کسب‌وکار نفت (ارتقا و فروش خودکار)", "🛢", "trade", [
    Field("user_id", "کاربر", "int"),
    Field("level", "سطح تجهیزات", "int", min=1, max=12),
    Field("auto_sell", "فروش خودکار", "bool"),
    Field("last_sale_at", "آخرین فروش", "text"),
    Field("last_income", "درآمد آخر", "int"),
    Field("total_income", "مجموع درآمد", "int"),
    Field("sales", "تعداد فروش", "int"),
    Field("barrels_sold", "بشکه فروخته‌شده", "int"),
], list_title="'🛢 ' || user_id || ' — سطح ' || level")

E("cur", "currency_requests", "درخواست‌های ارز", "💵", "economy", [
    Field("user_id", "کاربر", "int"),
    Field("req_type", "نوع", "enum", options=["adopt", "create"]),
    Field("value", "ارز", "text"),
    Field("status", "وضعیت", "enum", options=["pending", "approved", "rejected"]),
    Field("reviewed_by", "بررسی‌کننده", "int", skip_in_new=True),
], list_title="'#' || id || ' — ' || req_type || ' — ' || value",
   order_by="status='pending' DESC, id DESC", can_create=False)

E("rsc", "rescue_campaigns", "کمپین‌های سازمان نجات", "🛟", "un", [
    Field("war_id", "جنگ", "int"),
    Field("status", "وضعیت", "enum", options=["open", "closed"]),
    Field("winner_id", "برنده", "int"),
    Field("distributed", "پرداخت‌شده", "int"),
], list_title="'#' || id || ' — ' || status", can_create=False)

E("str", "straits", "تنگه‌ها", "⚓", "world", [
    Field("key", "کلید", "text", required=True),
    Field("name", "نام", "text", required=True),
    Field("emoji", "ایموجی", "text"),
    Field("is_active", "فعال", "bool"),
    Field("owner_id", "مالک (آیدی کاربر)", "int"),
], list_title="emoji || ' ' || name",
   list_sub="CASE WHEN owner_id IS NULL THEN '🆓 بدون مالک' ELSE '👑 ' || owner_id END")

E("sea", "seasons", "سیزن‌ها", "🎬", "seasons", [
    Field("name", "نام سیزن", "text", required=True),
    Field("mode", "مود", "enum", options=["worldwar", "crusades", "ancient"]),
    Field("is_active", "فعال", "bool"),
], list_title="name",
   list_sub="CASE WHEN is_active=1 THEN '🟢 فعال' ELSE '⚪ غیرفعال' END")

E("svt", "season_votes", "رای‌گیری‌های سیزن", "🗳", "seasons", [
    Field("options", "گزینه‌ها (JSON)", "json"),
    Field("required_votes", "حداقل رأی", "int", min=1),
    Field("status", "وضعیت", "enum", options=["open", "closed", "cancelled"]),
    Field("ends_at", "پایان", "text"),
    Field("winner", "برنده", "text"),
], list_title="'#' || id || ' — ' || status", can_create=False)

E("img", "images", "کتابخانه تصاویر", "🖼", "media", [
    Field("name", "اسم تصویر", "text", required=True,
          help="با همین اسم در بخش‌های مختلف استفاده می‌شود"),
    Field("section", "بخش", "enum", options=list(IMAGE_SECTIONS_KEYS)),
    Field("file_id", "فایل تلگرام", "text", skip_in_new=True),
    Field("uploaded_by", "بارگذار", "int", skip_in_new=True),
], list_title="name", search_cols=["name", "section"], can_create=False,
   note="تصاویر را از منوی 🖼 کتابخانه تصاویر (ارسال عکس) اضافه کنید.")

E("gev", "game_events", "رویدادهای بازی", "📋", "logs", [
    Field("kind", "نوع", "text"),
    Field("text", "متن", "text"),
], list_title="'#' || id || ' — ' || kind", can_create=False)

# ─── تنظیمات ───
SETTING_LABELS = {
    "coin_price_toman": "💵 قیمت هر سکه شاهی (تومان)",
    "coins_to_money_rate": "🔄 نرخ تبدیل سکه به پول پایه",
    "sales_support": "🛒 آیدی پشتیبانی فروش",
    "coin_sell_rate": "💰 نرخ فروش هر سکه به بازیکن",
    "oil_rig_bonus_percent": "🛢 پاداش هر دکل نفتی (٪)",
    "c2c_card": "💳 شماره کارت به کارت (اختیاری)",
    "c2c_holder": "👤 نام صاحب کارت",
    "join_channels": "📢 کانال‌های عضویت اجباری (JSON)",
    "announcement_channel": "📣 کانال اعلانات",
    "start_text": "👋 متن استارت",
    "bot_off": "🔴 خاموشی ربات (۰/۱)",
    "trade_tax_percent": "💼 مالیات تجارت (٪)",
    "income_base": "💰 ضریب درآمد روزانه",
    "initial_money": "💵 بودجه اولیه بازیکن جدید",
    "war_vote_minutes": "🗳 مدت رای‌گیری مجوز جنگ (دقیقه)",
    "vote_duration_hours": "⏳ مدت رای‌گیری (ساعت)",
    "country_change_hours": "⏰ فاصله تغییر کشور (ساعت)",
    "cyber_cooldown_hours": "🕶 فاصله حمله سایبری (ساعت)",
    "food_price_per_ton": "🍞 قیمت هر تن غذا",
    "guide_text": "📖 متن راهنمای بازی",
    "income_interval_minutes": "⏱ فاصله درآمد خودکار (دقیقه)",
    "sec_negotiation": "🕊 بخش مذاکره (۰/۱)",
    "sec_direct_trade": "🔁 بخش تجارت مستقیم (۰/۱)",
    "sec_rescue_sale": "🏥 بخش فروش انرژی به سازمان نجات (۰/۱)",
    "sec_straits": "⚓ بخش تنگه‌ها (۰/۱)",
    "sec_oil": "🛢 بخش نفت (۰/۱)",
    "sec_rescue_org": "🛟 بخش سازمان نجات (۰/۱)",
    "oil_rig_barrels_per_tick": "🛢 بشکه هر دکل در هر تیک",
    "oil_exploration_cost": "⛏ هزینه اکتشاف نفتی",
    "oil_exploration_add": "🛢 بشکه اکتشاف موفق",
    "oil_price_per_barrel": "🛢 ارزش هر بشکه نفت",
    "rescue_energy_price": "⚡️ قیمت برق سازمان نجات/واحد",
    "rescue_water_price": "💧 قیمت آب سازمان نجات/واحد",
    "rescue_gas_price": "🔥 قیمت گاز سازمان نجات/واحد",
    "rescue_oil_price": "🛢 قیمت نفت سازمان نجات/بشکه",
    "rescue_vote_hours": "🛟 مدت رای‌گیری نجات (ساعت)",
    "rescue_payout_percent": "🛟 درصد پرداخت ذخیره (٪)",
    "strait_min_naval": "⚓ حداقل قدرت دریایی تنگه آزاد",
    "strait_capture_ratio": "⚓ ضریب تصاحب تنگه دارای مالک",
    "strait_toll_percent": "⚓ عوارض تنگه (٪)",
    "season_name": "🎬 نام سیزن فعلی",
    "season_mode": "🎬 مود سیزن فعلی",
    "season_vote_hours": "🗳 مدت رای‌گیری سیزن (ساعت)",
    "season_required_votes": "🗳 حداقل رأی سیزن",
    "daily_report_hour": "📋 ساعت گزارش روزانه (تهران)",
    "main_currency": "💵 ارز اصلی فعلی",
    # ── موتور درآمد میلیونی (core/income.py) ──
    "income_tax_base_m": "💰 پایهٔ مالیات هر دوره (میلیون)",
    "income_tax_step_m": "💰 پلهٔ ضریب اقتصاد (میلیون)",
    "income_oil_unit_m": "🛢 ضریب تبدیل پایهٔ نفتی",
    "income_oil_floor_m": "🛢 کف درآمد نفتی (میلیون)",
    "income_strait_m": "⚓ درآمد هر تنگه (میلیون)",
    "income_resource_m": "♻️ درآمد فروش هر بخش منابع (میلیون)",
    "income_floor_m": "💵 کف تضمینی کل درآمد (میلیون)",
    "income_growth_cap": "📈 سقف ضریب ارتقای درآمد",
    "oil_level_income_bonus": "🛠 پاداش هر سطح تجهیزات استخراج",
    # ── ♻️ فروش منابع ──
    "res_price_power": "⚡ قیمت فروش برق",
    "res_price_water": "💧 قیمت فروش آب",
    "res_price_gas": "🔥 قیمت فروش گاز",
    "res_price_food": "🍞 قیمت فروش غذا",
    "res_price_oil": "🛢 قیمت فروش نفت (بشکه)",
    "res_price_materials": "🧱 قیمت فروش مصالح",
    "sec_resource_sale": "♻️ بخش فروش منابع (۰/۱)",
    # ── ⚔️ نبرد / استان / پایگاه دریایی ──
    "attack_cooldown_minutes": "⏳ فاصله حمله (دقیقه)",
    "cyber_cooldown_minutes": "🕶 فاصله عملیات سایبری (دقیقه)",
    "naval_base_cost": "⚓ هزینهٔ پایگاه دریایی",
    "naval_base_sea_power": "⚓ قدرت دریایی هر پایگاه",
    "capture_province_bonus": "🗺 شانس تصرف استان (٪)",
    "conquest_loot_bonus": "💰 پاداش غارت تسخیر (٪)",
    "province_defense_min_chance": "🗺 حداقل شانس دفاع استان (٪)",
    "province_defense_max_chance": "🗺 حداکثر شانس دفاع استان (٪)",
    # ── ☢️ تأسیسات هسته‌ای ──
    "nuclear_leak_chance": "☢️ شانس نشت رادیواکتیو (٪)",
    "nuclear_rebuild_cost": "☢️ هزینهٔ بازسازی تأسیسات",
    "nuclear_site_hp": "☢️ استحکام تأسیسات",
    # ── 🕊 آتش‌بس / 🛒 بازار تسلیحات / ☢️ غنی‌سازی ──
    "enrichment_stage_minutes": "☢️ مدت هر مرحلهٔ غنی‌سازی (دقیقه)",
    "ceasefire_offer_hours": "🕊 مهلت پاسخ آتش‌بس (ساعت)",
    "ceasefire_cooldown_hours": "🕊 فاصلهٔ پیشنهاد آتش‌بس (ساعت)",
    "attrition_surrender_threshold": "🏳 حداقل فرسایش برای تسلیم (٪)",
    "surrender_provinces": "🏳 استان‌های واگذارشده در تسلیم",
    "arms_commission_percent": "🛒 کمیسیون بازار تسلیحات (٪)",
    "arms_max_quantity": "🛒 حداکثر تعداد هر معامله",
    "arms_listing_hours": "🛒 اعتبار آگهی تسلیحات (ساعت)",
    # ── ⛓ جنگ فرسایشی ──
    "attrition_per_strike": "⛓ فرسایش هر حملهٔ موفق (٪)",
    "attrition_failed_strike_share": "⛓ سهم فرسایش حملهٔ ناموفق",
    "attrition_max_wear": "⛓ سقف فرسایش (٪)",
    "attrition_decay_per_hour": "⛓ بازیابی فرسایش در ساعت (٪)",
    "attrition_defense_penalty": "⛓ ضریب افت توان دفاعی",
    "attrition_income_penalty": "⛓ ضریب افت درآمد",
    "attrition_morale_base": "⛓ ریزش پایهٔ رضایت",
    "attrition_morale_per_wear": "⛓ ریزش رضایت هر درصد فرسایش",
    "attrition_collapse_threshold": "⛓ آستانهٔ سقوط (٪)",
    # ── 🌐 رفاه اینترنت ──
    "internet_max_level": "🌐 حداکثر سطح اینترنت",
    "internet_upgrade_cost": "🌐 هزینهٔ پایهٔ ارتقای اینترنت",
    "internet_materials_per_level": "🌐 مصالح لازم هر ارتقا",
    "internet_growth_bonus": "🌐 سهم درآمد هر سطح (٪)",
    "internet_satisfaction_bonus": "🌐 رضایت هر سطح",
}

E("set", "settings", "تنظیمات بازی", "⚙️", "settings", [
    Field("key", "کلید", "text", required=True),
    Field("value", "مقدار", "text", required=True),
], list_title="key", search_cols=["key", "value"], pk="key", order_by="key",
   note="مقدار join_channels باید JSON باشد مثل [\"@channel1\",\"@channel2\"]")

# ─── ادمین‌ها و لاگ ───
E("adm", "admins", "ادمین‌ها", "🛡", "admins", [
    Field("id", "آیدی تلگرام", "int"),
    Field("name", "نام", "text"),
    Field("is_super", "سوپرادمین", "bool"),
    Field("perms", "دسترسی‌ها (JSON)", "json",
          help='مثل ["users","economy"] — سوپرادمین به همه چیز دسترسی دارد'),
    Field("added_by", "افزوده توسط", "int"),
], list_title="'🛡 ' || id || ' — ' || COALESCE(name,'')")

E("log", "admin_logs", "لاگ عملیات ادمین‌ها", "📜", "logs", [
    Field("admin_id", "ادمین", "int"),
    Field("action", "عملیات", "text"),
    Field("detail", "جزئیات", "text"),
], list_title="'#' || id || ' — ' || action", can_create=False, can_delete=True)


def by_key(key: str) -> Entity | None:
    for e in REGISTRY:
        if e.key == key:
            return e
    return None


def for_perm(perm: str) -> list[Entity]:
    return [e for e in REGISTRY if e.perm == perm]
