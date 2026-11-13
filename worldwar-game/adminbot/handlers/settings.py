"""ویرایشگر هدایت‌شده تنظیمات بازی (با توضیح فارسی هر کلید)."""
from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

from adminbot.auth import has
from adminbot.crud import cd, kb
from adminbot.entities import SETTING_LABELS
from adminbot.tools import log_action
from core.db import db, get_setting, set_setting
from core.utils import fmt

router = Router()

ORDER = ["coin_price_toman", "coin_sell_rate", "coins_to_money_rate", "sales_support", "c2c_card", "c2c_holder",
         "join_channels", "announcement_channel", "start_text", "guide_text",
         "income_base", "initial_money", "income_interval_minutes",
         "income_tax_base_m", "income_tax_step_m", "income_oil_unit_m",
         "income_oil_floor_m", "income_resource_m", "income_floor_m",
         "income_strait_m", "income_growth_cap", "oil_rig_bonus_percent",
         "res_price_power", "res_price_water", "res_price_gas", "res_price_food",
         "res_price_oil", "res_price_materials",
         "naval_base_cost", "naval_base_sea_power",
         "capture_province_bonus", "conquest_loot_bonus",
         "nuclear_leak_chance", "nuclear_rebuild_cost", "nuclear_site_hp",
         "nuke_bomb_cost_m", "nuke_bomb_materials", "nuke_bomb_coins", "nuke_bomb_minutes",
         "nuke_bomb_yield_kt", "nuke_bomb_limit", "nuke_strike_cooldown_hours",
         "nuke_blast_provinces", "nuke_blast_max_provinces", "nuke_blast_loot_percent",
         "nuke_blast_wear", "nuke_blast_satisfaction", "nuke_blast_civilian",
         "nuke_fallout_self", "nuke_catastrophe_chance", "battle_reserve_loss_percent",
         "battle_defender_kill_ratio",
         "sabotage_cooldown_minutes", "sabotage_satisfaction_hit", "sabotage_wear_add",
         "internet_max_level", "internet_upgrade_cost", "internet_materials_per_level",
         "internet_growth_bonus", "internet_satisfaction_bonus",
         "attrition_per_strike", "attrition_failed_strike_share", "attrition_max_wear",
         "attrition_decay_per_hour", "attrition_defense_penalty", "attrition_income_penalty",
         "attrition_morale_base", "attrition_morale_per_wear", "attrition_collapse_threshold",
         "enrichment_stage_minutes", "ceasefire_offer_hours", "ceasefire_cooldown_hours",
         "attrition_surrender_threshold", "surrender_provinces",
         "arms_commission_percent", "arms_max_quantity", "arms_listing_hours",
         "attack_cooldown_minutes", "alliance_defense_percent", "alliance_max_members",
         "material_unit_price",
         "food_price_per_ton",
         "trade_tax_percent", "war_vote_minutes",
         "vote_duration_hours", "country_change_hours",
         "cyber_cooldown_hours", "cyber_cooldown_minutes", "bot_off",
         "sec_negotiation", "sec_direct_trade", "sec_rescue_sale", "sec_straits",
         "sec_oil", "sec_rescue_org", "sec_resource_sale",
         "oil_rig_barrels_per_tick", "oil_exploration_cost", "oil_exploration_add",
         "oil_price_per_barrel",
         "rescue_energy_price", "rescue_water_price", "rescue_gas_price", "rescue_oil_price",
         "rescue_vote_hours", "rescue_payout_percent",
         "strait_min_naval", "strait_capture_ratio", "strait_toll_percent",
         "season_vote_hours", "season_required_votes", "daily_report_hour",
         # ═══ 🧨 موتور واقع‌گرایی ═══
         "sec_supply", "supply_ammo_per_tick", "supply_fuel_per_tick",
         "supply_ammo_per_soldier", "supply_fuel_per_soldier", "supply_attack_penalty",
         "supply_penalty_cap", "supply_ration_per_soldier", "supply_unfed_penalty",
         "supply_sabotage_pct", "supply_buy_price", "supply_fuel_price",
         "sec_unrest", "unrest_decay_per_period", "unrest_sat_threshold",
         "unrest_strike_threshold", "unrest_strike_minutes", "unrest_strike_income_penalty",
         "unrest_subsidy_step", "unrest_subsidy_cost_m", "unrest_crackdown_gain",
         "unrest_crackdown_sat", "unrest_crackdown_loss_pct", "unrest_ignore_gain",
         "unrest_ignore_sat", "unrest_rise_per_miss", "unrest_strike_fail_penalty",
         "sec_revolt", "revolt_threshold", "revolt_minutes", "revolt_income_penalty",
         "revolt_negotiate_cost_m", "revolt_negotiate_gain", "revolt_bribe_cost_m",
         "revolt_bribe_chance", "revolt_bribe_gain", "revolt_crush_loss_pct",
         "revolt_rival_share", "revolt_rival_money_pct",
         "sec_elections", "election_interval_hours", "election_campaign_cost_m",
         "election_bonus_step", "election_opposition_threshold",
         "election_party_income_bonus",
         "sec_intel", "intel_cost_m", "intel_radius_base", "intel_radius_step",
         "intel_max_level", "intel_expose_chance", "intel_expire_hours",
         "sec_oil_market", "oil_market_base_usd", "oil_market_shock_war_pct",
         "oil_market_shock_blockade_pct", "oil_market_drift_pct", "oil_market_min_usd",
         "oil_market_max_usd", "oil_market_income_weight",
         "inflation_print_step", "inflation_decay", "inflation_income_weight",
         "inflation_cost_weight", "inflation_cap",
         "loan_rate_percent", "loan_periods", "loan_limit_m", "loan_miss_satisfaction",
         "sec_refugees", "refugee_pct_per_province", "refugee_pct_per_hit",
         "refugee_return_cost_m", "refugee_satisfaction_hit",
         "sec_foreign_base", "fbase_pay_m", "fbase_defense_bonus_pct", "fbase_tech_bonus_pct",
         "fbase_crisis_sat", "fbase_crisis_diplomacy", "fbase_auto_join",
         "sec_grideffect", "grid_hours_per_success", "grid_max_hours",
         "grid_income_penalty_pct", "grid_repair_cost_m_per_hour", "grid_satisfaction_hit",
         "sec_weather", "weather_season_hours", "weather_winter_attack_pct",
         "weather_winter_energy_pct", "weather_summer_water_pct", "weather_drought_chance",
         "weather_storm_chance", "weather_storm_attack_pct", "weather_harvest_bonus_m"]

HELP = {
    "coin_sell_rate": "💰 پول پایه‌ای که بازیکن بابت فروش هر ۱ سکه شاهی می‌گیرد (مثلاً 100000000)",
    "coin_price_toman": "قیمت فروش هر سکه شاهی به تومان (مثلاً 1000 یا 34000000)",
    "coins_to_money_rate": "هر سکه شاهی در تبدیل داخلی چند پول پایه می‌ارزد",
    "sales_support": "آیدی پشتیبانی فروش سکه شاهی — به‌جای کارت به کارت (مثل @MiddleEastDefendSupport)",
    "c2c_card": "شماره کارت برای پرداخت‌های کارت به کارت — خالی بگذارید تا نمایش داده نشود",
    "c2c_holder": "نام صاحب کارت",
    "join_channels": "کانال‌های عضویت اجباری — JSON مثل [\"@channel1\",\"@group2\"] — خالی یعنی بدون عضویت اجباری",
    "announcement_channel": "کانال اعلانات (احداث/جنگ/بیانیه/رای‌گیری) مثل @mychannel — ربات باید ادمین کانال باشد",
    "start_text": "متن خوش‌آمد /start قبل از بررسی عضویت",
    "guide_text": "متن کامل راهنمای بازی که در بخش «راهنمای بازی» نمایش داده می‌شود",
    "income_tax_base_m": "💰 پایهٔ درآمد مالیات هر دوره به میلیون (پیش‌فرض ۱۰)",
    "income_tax_step_m": "💰 به ازای هر واحد ضریب اقتصاد کشور چند میلیون اضافه شود (پیش‌فرض ۸)",
    "income_oil_unit_m": "🛢 ضریب تبدیل پایهٔ نفتی کشور به پول میلیونی (پیش‌فرض ۱)",
    "income_oil_floor_m": "🛢 کف پایهٔ درآمد نفتی هر دوره به میلیون — هیچ کشوری کمتر از این نمی‌گیرد (پیش‌فرض ۱۲)",
    "income_strait_m": "⚓ عوارض هر تنگه برای مالکش به میلیون (پیش‌فرض ۱۴)",
    "income_growth_cap": "📈 سقف ضریب ارتقای درآمد (پیش‌فرض ۵ برابر)",
    "oil_rig_bonus_percent": "🛢 درصد افزایش درآمد نفت به ازای هر دکل نفتی (پیش‌فرض ۸٪)",
    "attack_cooldown_minutes": "⏳ فاصله بین دو حمله نظامی به دقیقه (پیش‌فرض ۳)",
    "alliance_defense_percent": "🤝 درصد توان دفاعی که هر متحد اضافه می‌کند (پیش‌فرض ۳۰)",
    "alliance_max_members": "🤝 حداکثر اعضای هر اتحاد (پیش‌فرض ۸)",
    "material_unit_price": "🧱 قیمت هر واحد مصالح ساختمانی (پیش‌فرض ۲۰۰۰۰)",
    "income_base": "ضریب درآمد روزانه کشورها (پیش‌فرض ۱۰۰) — درآمد = (جمعیت÷۱۰۰۰) × این ضریب × ضریب رضایت × (۱+نرخ مالیات)",
    "initial_money": "بودجه اولیه هر بازیکن تازه‌وارد، به واحد پول پایهٔ بازی — پیش‌فرض ۲۰۰ (با /start اعمال می‌شود و در ریست بازیکنان هم استفاده می‌شود)",
    "war_vote_minutes": "مدت رای‌گیری مجوز جنگ در سازمان ملل (دقیقه — پیش‌فرض ۳۰)",
    "food_price_per_ton": "قیمت خرید هر تن غذا",
    "trade_tax_percent": "مالیات معاملات بازار (درصد)",
    "vote_duration_hours": "مدت رای‌گیری‌های سازمان ملل (ساعت)",
    "country_change_hours": "فاصله مجاز تغییر کشور (ساعت) — طبق قانون بازی ۸",
    "cyber_cooldown_hours": "فاصله بین دو حمله سایبری به یک کشور (ساعت)",
    "cyber_cooldown_minutes": "🕶 فاصله بین دو عملیات سایبری روی یک کشور — دقیقه (پیش‌فرض ۲۰، قبلاً ۶ ساعت بود)",
    "income_resource_m": "♻️ درآمد فروش مازاد هر بخش منابع (برق/آب/گاز/غذا) در هر دوره — میلیون (پیش‌فرض ۱۸)",
    "income_floor_m": "💵 کف تضمینی کل درآمد هر دوره — میلیون. هیچ کشوری کمتر از این نمی‌گیرد (پیش‌فرض ۱۱۰)",
    "income_oil_unit_m": "🛢 ضریب تبدیل oil_income_base کشور به پول میلیونی (پیش‌فرض ۳)",
    "res_price_power": "⚡ پول دریافتی بابت فروش هر واحد برق",
    "res_price_water": "💧 پول هر واحد آب",
    "res_price_gas": "🔥 پول هر واحد گاز",
    "res_price_food": "🍞 پول هر واحد غذا",
    "res_price_oil": "🛢 پول هر بشکه نفت",
    "res_price_materials": "🧱 پول هر واحد مصالح",
    "sec_resource_sale": "♻️ ۱ = بخش «فروش منابع» روشن / ۰ = خاموش",
    "naval_base_cost": "⚓ هزینهٔ ساخت پایگاه دریایی برای کشورهای بدون مرز دریا (پیش‌فرض ۳۰۰ میلیون)",
    "naval_base_sea_power": "⚓ قدرت دریایی که هر پایگاه دریایی به کشور می‌دهد (پیش‌فرض ۱۵۰۰)",
    "capture_province_bonus": "🗺 درصد شانس اضافه برای تصرف استان در «حمله به قصد تسخیر» (پیش‌فرض ۱۵)",
    "conquest_loot_bonus": "💰 درصد غارت بیشتر در حملهٔ تسخیر نسبت به حملهٔ معمولی (پیش‌فرض ۲۰)",
    "nuclear_leak_chance": "☢️ شانس نشت رادیواکتیو هنگام تخریب کامل تأسیسات هسته‌ای (٪ — پیش‌فرض ۳۵)",
    "nuclear_rebuild_cost": "☢️ هزینهٔ پایهٔ بازسازی تأسیسات هسته‌ای (پیش‌فرض ۱۲۰ میلیون)",
    "nuclear_site_hp": "☢️ استحکام پایهٔ تأسیسات هسته‌ای (پیش‌فرض ۱۰۰)",
    "sabotage_cooldown_minutes": "🎯 پس از هر خرابکاری، مهاجم چند دقیقه باید صبر کند (پیش‌فرض ۲۰)",
    "sabotage_satisfaction_hit": "🎯 چند امتیاز از رضایت مردم مدافع در هر خرابکاری موفق کم شود (پیش‌فرض ۳)",
    "sabotage_wear_add": "🎯 چند درصد به فرسایش جنگ کشور مدافع اضافه شود (پیش‌فرض ۸)",
    "internet_max_level": "🌐 حداکثر سطح زیرساخت اینترنت (پیش‌فرض ۵)",
    "internet_upgrade_cost": "🌐 هزینهٔ پایهٔ ارتقای یک سطح اینترنت (پیش‌فرض ۸۰ میلیون)",
    "internet_materials_per_level": "🌐 مصالح لازم پایه برای هر ارتقای اینترنت (پیش‌فرض ۲۵۰)",
    "internet_growth_bonus": "🌐 درصد افزایش ضریب درآمد به ازای هر سطح اینترنت (پیش‌فرض ۵)",
    "internet_satisfaction_bonus": "🌐 امتیاز رضایت مردم به ازای هر سطح اینترنت (پیش‌فرض ۲)",
    "attrition_per_strike": "⛓ هر حملهٔ موفق چند درصد «فرسایش» به کشور مدافع اضافه می‌کند (پیش‌فرض ۱۲). فرسایش توان دفاعی، درآمد و روحیه دشمن را کم می‌کند تا با چند حملهٔ پشت‌سرهم نابود شود.",
    "attrition_failed_strike_share": "⛓ حملهٔ ناموفق چه سهمی از فرسایش را اعمال کند (۰.۳۵ = ۳۵٪)",
    "attrition_max_wear": "⛓ سقف فرسایش یک کشور (٪ — پیش‌فرض ۹۰)",
    "attrition_decay_per_hour": "⛓ هر ساعت چند درصد از فرسایش خودبه‌خود کم شود (پیش‌فرض ۶ — یعنی حدود ۱۵ ساعت برای بازیابی کامل)",
    "attrition_defense_penalty": "⛓ با فرسایش ۱۰۰٪ چه کسری از توان دفاعی از بین برود (۰.۶ = ۶۰٪)",
    "attrition_income_penalty": "⛓ با فرسایش ۱۰۰٪ چه کسری از درآمد از بین برود (۱.۰ = ۱۰۰٪، ولی کف تضمینی درآمد حفظ می‌شود)",
    "attrition_morale_base": "⛓ ریزش پایهٔ رضایت مردم در هر حملهٔ موفق (پیش‌فرض ۳)",
    "attrition_morale_per_wear": "⛓ ریزش اضافهٔ رضایت به ازای هر درصد فرسایش (پیش‌فرض ۰.۱۲)",
    "attrition_collapse_threshold": "⛓ اگر فرسایش کشور به این درصد برسد، در آستانهٔ سقوط است (پیش‌فرض ۸۵)",
    "enrichment_stage_minutes": "☢️ مدت هر مرحلهٔ غنی‌سازی اورانیوم به دقیقه (پیش‌فرض ۵)",
    # ── ☢️ سلاح هسته‌ای (بمب اتم) ──
    "nuke_bomb_cost_m": "☢️ هزینهٔ ساخت هر کلاهک هسته‌ای به میلیون (پیش‌فرض ۱۸۰۰ = ۱٫۸ میلیارد)",
    "nuke_bomb_materials": "☢️ مصالح لازم برای هر کلاهک (پیش‌فرض ۴۰٬۰۰۰ واحد)",
    "nuke_bomb_coins": "☢️ سکه شاهی لازم برای هر کلاهک (۰ = بدون سکه)",
    "nuke_bomb_minutes": "⏱ مدت ساخت هر کلاهک به دقیقه (پیش‌فرض ۳۰ — ۰ = فوری)",
    "nuke_bomb_yield_kt": "💣 قدرت هر کلاهک به کیلوتن (پیش‌فرض ۱۵۰)",
    "nuke_bomb_limit": "📦 حداکثر کلاهک در زرادخانهٔ هر کشور (۰ = بی‌سقف)",
    "nuke_strike_cooldown_hours": "⏱ فاصلهٔ لازم بین دو ضربهٔ هسته‌ای به ساعت (۰ = بدون کول‌داون)",
    "nuke_blast_provinces": "🗺 درصد احتمال جدا شدن هر استان از کشور هدف در ضربهٔ هسته‌ای",
    "nuke_blast_max_provinces": "🗺 حداکثر استان‌هایی که در یک ضربه جدا می‌شوند",
    "nuke_blast_loot_percent": "💰 درصد غارت خزانهٔ کشور هدف در ضربهٔ هسته‌ای",
    "nuke_blast_wear": "⛓ فرسایش اضافه‌شده به کشور هدف در ضربهٔ هسته‌ای (٪)",
    "nuke_blast_satisfaction": "😞 افت رضایت مردم کشور هدف در ضربهٔ هسته‌ای (٪)",
    "nuke_blast_civilian": "💀 تلفات غیرنظامی تخمینی هر ضربهٔ هسته‌ای (نفر — فقط نمایشی)",
    "nuke_fallout_self": "🌍 افت رضایت خود مهاجم به‌خاطر محکومیت جهانی (٪)",
    "nuke_catastrophe_chance": "🔥 درصد احتمال فاجعهٔ انسانی/نشت در ضربهٔ هسته‌ای",
    "battle_reserve_loss_percent": "🎯 درصد فرسایش ذخیرهگاه (یگان‌هایی که در نبرد شرکت نکردند) — پیش‌فرض ۲",
    "battle_defender_kill_ratio": "🎯 سقف یگان‌های مدافع که به ازای هر یگان مهاجم می‌تواند از بین برود (پیش‌فرض ۱٫۵)",
    "ceasefire_offer_hours": "🕊 طرف مقابل چند ساعت فرصت دارد به پیشنهاد آتش‌بس پاسخ دهد (پیش‌فرض ۲۴)",
    "ceasefire_cooldown_hours": "🕊 فاصلهٔ مجاز بین دو پیشنهاد آتش‌بس از یک کشور (ساعت)",
    "attrition_surrender_threshold": "🏳 کشوری که فرسایشش از این درصد بگذرد می‌تواند تسلیم شود (پیش‌فرض ۶۰)",
    "surrender_provinces": "🏳 در تسلیم، چند استان به مهاجم واگذار می‌شود (پیش‌فرض ۲)",
    "arms_commission_percent": "🛒 درصد کارمزدی که بازار از فروش تسلیحات می‌گیرد (پیش‌فرض ۵)",
    "arms_max_quantity": "🛒 حداکثر تعداد تجهیزات در یک آگهی بازار تسلیحات (پیش‌فرض ۵۰۰۰)",
    "arms_listing_hours": "🛒 مدت اعتبار آگهی بازار تسلیحات (ساعت)",
    "bot_off": "۱ = بازی خاموش / ۰ = روشن",
    "income_interval_minutes": "فاصله پرداخت خودکار درآمد/مالیات/یارانه (دقیقه — پیش‌فرض ۳۰)",
    "sec_negotiation": "۱ = بخش مذاکره روشن / ۰ = خاموش",
    "sec_direct_trade": "۱ = تجارت مستقیم روشن / ۰ = خاموش",
    "sec_rescue_sale": "۱ = فروش انرژی به سازمان نجات روشن / ۰ = خاموش",
    "sec_straits": "۱ = کل بخش تنگه‌ها روشن / ۰ = خاموش",
    "sec_oil": "۱ = بخش نفت روشن / ۰ = خاموش",
    "sec_rescue_org": "۱ = سازمان نجات روشن / ۰ = خاموش",
    "oil_rig_barrels_per_tick": "هر دکل نفتی در هر تیک چند بشکه استخراج می‌کند (پیش‌فرض ۵۰۰)",
    "oil_exploration_cost": "هزینه اکتشاف نفتی (پول)",
    "oil_exploration_add": "در اکتشاف موفق چند بشکه به مخزن اضافه می‌شود",
    "oil_price_per_barrel": "ارزش پولی هر بشکه نفت در آمار تجارت",
    "rescue_energy_price": "قیمت خرید هر kWh برق توسط سازمان نجات",
    "rescue_water_price": "قیمت خرید هر واحد آب توسط سازمان نجات",
    "rescue_gas_price": "قیمت خرید هر واحد گاز توسط سازمان نجات",
    "rescue_oil_price": "قیمت خرید هر بشکه نفت توسط سازمان نجات",
    "rescue_vote_hours": "مدت رای‌گیری هر کمپین سازمان نجات (ساعت)",
    "rescue_payout_percent": "درصد پرداخت ذخیره سازمان به کشور برنده (پیش‌فرض ۱۰)",
    "strait_min_naval": "حداقل قدرت دریایی برای تصاحب تنگه بدون مالک (پیش‌فرض ۵۰۰)",
    "strait_capture_ratio": "برای گرفتن تنگه در یک حمله چند برابر قدرت دریایی مالک لازم است (پیش‌فرض ۱.۳)",
    "strait_attrition_percent": "درصد فرسایش ناوگان مدافع در هر حملهٔ دریایی — حتی حملهٔ ناموفق (پیش‌فرض ۱۸)",
    "strait_attrition_min_attacker": "حداقل درصد تلفات ناوگان مهاجم در هر حمله (پیش‌فرض ۵)",
    "strait_toll_percent": "عوارض تنگه از درآمد غیرمالیاتی کشورها (٪ — پیش‌فرض ۱.۵)",
    "season_vote_hours": "مدت رای‌گیری سیزن در کانال (ساعت)",
    "season_required_votes": "حداقل رأی برای انتخاب سیزن جدید (پیش‌فرض ۱۰)",
    "daily_report_hour": "ساعت ارسال گزارش روزانه به ادمین‌ها (به وقت تهران)",
    # ═══ 🧨 موتور واقع‌گرایی ═══
    "sec_supply": "🚚 ۱ = بخش تأمین روشن / ۰ = خاموش. با خاموش‌بودن هیچ حمله‌ای تدارکات مصرف نمی‌کند.",
    "supply_ammo_per_tick": "📦 مهمات تولیدشده برای هر کشور در هر دورهٔ درآمد (پایه؛ هر پالایشگاه +۲۵٪ و هر شرکت +۸٪).",
    "supply_fuel_per_tick": "⛽ سوخت تولیدشده در هر دوره (پایه). سوخت و مهمات با هم مصرف می‌شوند.",
    "supply_ammo_per_soldier": "📦 مهمات مصرفی به ازای هر یگان اعزامی (تجهیز + سرباز) در هر حمله.",
    "supply_fuel_per_soldier": "⛽ سوخت مصرفی به ازای هر یگان اعزامی در هر حمله.",
    "supply_attack_penalty": "📉 ۰.۵۵ = با انبار خالی، قدرت حمله تا ۵۵٪ کم می‌شود (هرچه بیشتر، سخت‌تر).",
    "supply_penalty_cap": "📉 حداکثر درصد افت قدرت حمله به‌خاطر کمبود تدارکات (پیش‌فرض ۴۵).",
    "supply_ration_per_soldier": "🍞 هر سرباز در هر دوره چند واحد مهمات به‌عنوان تدارکات مصرف می‌کند؛ اگر نرسد سرباز فرار می‌کند.",
    "supply_unfed_penalty": "🍞 ۰.۳۵ = ارتش گرسنه، پدافند را ضعیف‌تر می‌کند.",
    "supply_sabotage_pct": "🔥 هر خرابکاری موفق در پالایشگاه/دکل، این سهم از انبار مهمات و سوخت دشمن را می‌سوزاند (۰.۰۸ = ۸٪).",
    "supply_buy_price": "🛒 قیمت هر واحد مهمات در بازار داخلی (پول).",
    "supply_fuel_price": "🛒 قیمت هر واحد سوخت در بازار داخلی (پول).",
    "sec_unrest": "✊ ۱ = سیستم ناآرامی/اعتصاب روشن / ۰ = خاموش.",
    "unrest_decay_per_period": "✊ در هر دوره که فشار جدیدی نباشد، این مقدار از ناآرامی کم می‌شود (پیش‌فرض ۴)، مشابه نارضایتی اجتماعی که فروکش می‌کند.",
    "unrest_sat_threshold": "✊ اگر رضایت مردم از این عدد کمتر باشد، ناآرامی بالا می‌رود (پیش‌فرض ۵۰).",
    "unrest_strike_threshold": "✊ عبور ناآرامی از این درصد = اعتصاب سراسری (درآمد نصف، شرکت‌ها تعطیل).",
    "unrest_strike_minutes": "✊ مدت اعتصاب سراسری به دقیقه (پیش‌فرض ۱۲۰).",
    "unrest_strike_income_penalty": "✊ ۰.۵ = در اعتصاب فقط نصف درآمد وصول می‌شود.",
    "unrest_subsidy_step": "🎁 هر بستهٔ یارانه چند امتیاز از ناآرامی کم می‌کند.",
    "unrest_subsidy_cost_m": "🎁 هزینهٔ هر بستهٔ یارانه به میلیون.",
    "unrest_crackdown_gain": "🪖 هر سرکوب نظامی چند امتیاز ناآرامی را پایین می‌آورد.",
    "unrest_crackdown_sat": "🪖 سرکوب نظامی چند امتیاز از رضایت مردم کم می‌کند.",
    "unrest_crackdown_loss_pct": "🪖 ۰.۰۶ = ۶٪ از سربازان در سرکوب از دست می‌روند.",
    "unrest_ignore_gain": "⏳ نادیده‌گرفتن اعتراض‌ها چند امتیاز ناآرامی را کم می‌کند (ارزان ولی خطرناک).",
    "unrest_ignore_sat": "⏳ نادیده‌گرفتن چند امتیاز رضایت را می‌خورد.",
    "unrest_rise_per_miss": "✊ اگر بازیکن کاری نکند، ناآرامی هر دوره این مقدار بالا می‌رود.",
    "unrest_strike_fail_penalty": "✊ شکستن اعتصاب با نیروی امنیتی چند امتیاز رضایت را کم می‌کند.",
    "sec_revolt": "🔥 ۱ = جنگ داخلی روشن / ۰ = خاموش (ناآرامی هرگز به شورش نمی‌رسد).",
    "revolt_threshold": "🔥 اگر ناآرامی از این درصد بگذرد، جنگ داخلی آغاز می‌شود.",
    "revolt_minutes": "🔥 مهلت مهار جنگ داخلی به دقیقه؛ اگر تمام شود شورشی‌ها کشور را می‌گیرند.",
    "revolt_income_penalty": "🔥 ۰.۳۵ = در جنگ داخلی فقط یک‌سوم درآمد وصول می‌شود.",
    "revolt_negotiate_cost_m": "🤝 هزینهٔ امتیازدهی به شورشی‌ها (میلیون).",
    "revolt_negotiate_gain": "🤝 امتیازدهی چند امتیاز از شدت شورش کم می‌کند.",
    "revolt_bribe_cost_m": "💼 هزینهٔ خریدن فرماندهان شورشی (میلیون).",
    "revolt_bribe_chance": "💼 شانس موفقیت رشوه به فرماندهان شورشی (٪).",
    "revolt_bribe_gain": "💼 رشوهٔ موفق چند امتیاز از شدت شورش کم می‌کند.",
    "revolt_crush_loss_pct": "🪖 ۰.۱۸ = ۱۸٪ سربازان در سرکوب شورش از دست می‌روند.",
    "revolt_rival_share": "🔥 اگر شورشی‌ها پیروز شوند، این سهم از تجهیزات/سرباز بازیکن از بین می‌رود (۰.۱ = ۱۰٪).",
    "revolt_rival_money_pct": "🔥 سهم خزانه‌ای که شورشی‌ها غارت می‌کنند (۰.۲۵ = ۲۵٪).",
    "sec_elections": "🗳 ۱ = انتخابات دوره‌ای روشن / ۰ = خاموش.",
    "election_interval_hours": "🗳 هر چند ساعت یک‌بار انتخابات برگزار می‌شود.",
    "election_campaign_cost_m": "📣 هزینهٔ هر رأی تبلیغاتی (میلیون).",
    "election_bonus_step": "📣 هر رأی تبلیغاتی چند درصد شانس ماندن حزب را بالا می‌برد.",
    "election_opposition_threshold": "🗳 آستانهٔ پایهٔ پیروزی اپوزیسیون (٪)؛ رضایت پایین و ناآرامی آن را بالا می‌برند.",
    "election_party_income_bonus": "🏛 پاداش درآمدی ثابت برای هر حزب حاکم (۰.۰۵ = ۵٪).",
    "sec_intel": "🕵 ۱ = جاسوسی و مه اطلاعات روشن / ۰ = خاموش (پیش‌بینی جنگ عدد قطعی می‌شود).",
    "intel_cost_m": "🕵 هزینهٔ هر عملیات جاسوسی (میلیون).",
    "intel_radius_base": "🕵 پهنای پایهٔ بازهٔ برآورد توان دشمن (۰.۳۵ = ±۳۵٪).",
    "intel_radius_step": "🕵 هر سطح شبکهٔ اطلاعات چند از پهنای بازه کم می‌کند.",
    "intel_max_level": "🕵 حداکثر سطح شبکهٔ اطلاعات هر بازیکن.",
    "intel_expose_chance": "🚨 شانس لو رفتن جاسوس (٪)؛ لو رفتن = رسوایی دیپلماتیک و بهانهٔ جنگ برای طرف مقابل.",
    "intel_expire_hours": "🕵 گزارش جاسوسی چند ساعت معتبر است.",
    "sec_oil_market": "🛢 ۱ = بازار جهانی نفت روشن / ۰ = خاموش.",
    "oil_market_base_usd": "🛢 قیمت پایهٔ هر بشکه نفت (دلار)؛ مبنای ضریب درآمد نفتی همهٔ کشورها.",
    "oil_market_shock_war_pct": "🛢 با هر جنگ فعال، قیمت این درصد بالا می‌رود (واقعیت: جنگ قیمت نفت را می‌پراند بالا).",
    "oil_market_shock_blockade_pct": "🛢 با بسته‌شدن هر تنگه، قیمت این درصد بالا می‌رود.",
    "oil_market_drift_pct": "🛢 نوسان تصادفی قیمت در هر تیک (٪).",
    "oil_market_min_usd": "🛢 کف مطلق قیمت نفت.",
    "oil_market_max_usd": "🛢 سقف مطلق قیمت نفت.",
    "oil_market_income_weight": "🛢 ۰.۷۵ = قیمت بازار با این وزن روی درآمد نفتی اثر می‌گذارد (۱ = اثر کامل).",
    "inflation_print_step": "💸 هر بار چاپ پول چند درصد تورم می‌آورد.",
    "inflation_decay": "💸 هر دوره چند درصد از تورم فروکش می‌کند.",
    "inflation_income_weight": "💸 اثر تورم بر قدرت خرید درآمد (۰.۵ = با تورم ۱۰۰٪ نیمی از درآمد می‌سوزد).",
    "inflation_cost_weight": "💸 اثر تورم بر گرانی خریدهای بازیکن.",
    "inflation_cap": "💸 حداکثر تورم قابل ثبت (٪).",
    "loan_rate_percent": "🏦 بهرهٔ هر دورهٔ وام (٪).",
    "loan_periods": "🏦 تعداد اقساط هر وام؛ هر دوره یک قسط از خزانه کسر می‌شود.",
    "loan_limit_m": "🏦 سقف پایهٔ وام (میلیون)؛ سقف واقعی بر اساس درآمد کشور هم محاسبه می‌شود.",
    "loan_miss_satisfaction": "🏦 اگر قسط پرداخت نشود، چند امتیاز رضایت کم می‌شود (همراه با جریمهٔ تأخیر).",
    "sec_refugees": "🏃 ۱ = پناهندگان روشن / ۰ = خاموش.",
    "refugee_pct_per_province": "🏃 هر استان اشغال‌شده چه سهمی از جمعیت را فراری می‌دهد (۰.۰۵ = ۵٪).",
    "refugee_pct_per_hit": "🏃 هر قطعی برق/آب/گاز/خاموشی چه سهمی از جمعیت را فراری می‌دهد.",
    "refugee_return_cost_m": "🏠 هزینهٔ اسکان هر ۱۰۰۰ پناهنده (میلیون).",
    "refugee_satisfaction_hit": "🏃 کشور میزبان با پذیرش پناهندگان چند امتیاز رضایت از دست می‌دهد.",
    "sec_foreign_base": "📡 ۱ = بخش پایگاه خارجی روشن / ۰ = خاموش.",
    "fbase_pay_m": "📡 میزبان از هر پایگاه خارجی در هر دوره چند میلیون می‌گیرد.",
    "fbase_defense_bonus_pct": "📡 میزبان به‌خاطر حضور نیروی خارجی چند درصد بونوس دفاعی می‌گیرد.",
    "fbase_tech_bonus_pct": "📡 مهمان به‌خاطر پایگاه خارجی چند درصد بونوس حمله می‌گیرد.",
    "fbase_crisis_sat": "📡 اگر میزبان قرارداد را یک‌طرفه لغو کند، چند امتیاز رضایت کم می‌شود.",
    "fbase_crisis_diplomacy": "📡 افت روابط بین‌المللی میزبان پس از لغو یک‌طرفهٔ قرارداد.",
    "fbase_auto_join": "📡 ۱ = اگر به میزبان حمله شود، مهمان خودکار وارد جنگ می‌شود / ۰ = خاموش.",
    "sec_grideffect": "⚡ ۱ = اثر آبشاری خاموشی روشن / ۰ = خاموش.",
    "grid_hours_per_success": "⚡ هر خرابکاری موفق در نیروگاه/اینترنت چند ساعت خاموشی می‌سازد.",
    "grid_max_hours": "⚡ حداکثر ساعت خاموشی انبار (سقف).",
    "grid_income_penalty_pct": "⚡ هر ساعت خاموشی چند درصد درآمد کشور را کم می‌کند.",
    "grid_repair_cost_m_per_hour": "🔧 هزینهٔ ترمیم اضطراری هر ساعت خاموشی (میلیون).",
    "grid_satisfaction_hit": "⚡ افت رضایت مردم به ازای هر ساعت خاموشی.",
    "sec_weather": "🍁 ۱ = فصل‌ها و آب‌وهوا روشن / ۰ = خاموش.",
    "weather_season_hours": "🍁 هر فصل چند ساعت طول می‌کشد (بهار → تابستان → پاییز → زمستان).",
    "weather_winter_attack_pct": "❄️ در زمستان قدرت حمله چند درصد کم می‌شود (ژنرال زمستان).",
    "weather_winter_energy_pct": "❄️ مصرف اضافهٔ انرژی در زمستان (٪).",
    "weather_summer_water_pct": "☀️ افت آب تولیدی در تابستان (٪).",
    "weather_drought_chance": "☀️ شانس خشکسالی در هر تابستان (٪).",
    "weather_storm_chance": "🌪 شانس طوفان در پاییز (٪).",
    "weather_storm_attack_pct": "🌪 کندی حمله در طوفان (٪).",
    "weather_harvest_bonus_m": "🌾 بونوس برداشت پاییز به میلیون (کشورهایی که مزرعه دارند).",
}


class SetFSM(StatesGroup):
    value = State()


@router.message(Command("settings"))
async def cmd_settings(message: Message, perms: set):
    if not has(perms, "settings"):
        return await message.answer("⛔️ دسترسی ندارید")
    await message.answer(**await settings_menu_payload())


async def settings_menu_payload() -> dict:
    lines = ["⚙️ <b>تنظیمات بازی</b>\n"]
    buttons = []
    # هر کلید تازه‌ای که در دیتابیس باشد ولی در ORDER نباشد هم نمایش داده می‌شود
    db_keys = [r["key"] for r in await db.fetchall("SELECT key FROM settings ORDER BY key")]
    keys = list(dict.fromkeys(list(ORDER) + db_keys))
    for key in keys:
        value = await get_setting(key, "")
        shown = value if len(value) < 40 else value[:37] + "…"
        lines.append(f"▪️ {SETTING_LABELS.get(key, key)}: <code>{shown or '—'}</code>")
        buttons.append([(SETTING_LABELS.get(key, key)[:45], f"a|sete|{key}")])
    buttons.append([("✏️ ویرایش خام جدول تنظیمات", cd("set", "p", 0))])
    buttons.append([("◀️ بازگشت", "a|root")])
    return {"text": "\n".join(lines), "reply_markup": kb(buttons)}


@router.callback_query(F.data == "a|set")
async def settings_menu(call: CallbackQuery, perms: set):
    if not has(perms, "settings"):
        return await call.answer("⛔️ دسترسی ندارید", show_alert=True)
    payload = await settings_menu_payload()
    await call.answer()
    await call.message.edit_text(payload["text"], reply_markup=payload["reply_markup"])


@router.callback_query(F.data.startswith("a|sete|"))
async def setting_edit(call: CallbackQuery, state: FSMContext, perms: set):
    if not has(perms, "settings"):
        return await call.answer("⛔️ دسترسی ندارید", show_alert=True)
    key = call.data.split("|")[2]
    value = await get_setting(key, "")
    await state.set_state(SetFSM.value)
    await state.update_data(set_key=key)
    await call.answer()
    shown = value if len(value) < 600 else value[:600] + "…"
    await call.message.edit_text(
        f"⚙️ <b>{SETTING_LABELS.get(key, key)}</b>\n\n"
        f"مقدار فعلی:\n<code>{shown or '—'}</code>\n\n"
        f"💡 {HELP.get(key, '')}\n\n"
        "مقدار جدید را بفرستید:\n برای انصراف /cancel",
        reply_markup=kb([
            [("♻️ بازنشانی راهنما (فقط guide_text)", "a|setrst")] if key == "guide_text" else
            [("◀️ بازگشت", "a|set")],
        ]))


@router.message(SetFSM.value)
async def setting_input(message: Message, state: FSMContext):
    data = await state.get_data()
    key = data.get("set_key")
    await state.clear()
    value = (message.text or "").strip()
    if not value:
        return await message.answer("❌ مقدار خالی است.")
    if key == "join_channels":
        import json
        try:
            json.loads(value)
        except ValueError:
            return await message.answer('❌ باید JSON معتبر باشد مثل ["@channel1"]')
    if key == "bot_off" and value not in ("0", "1"):
        return await message.answer("❌ فقط 0 یا 1")
    await set_setting(key, value)
    await log_action(message.from_user.id, "تنظیمات", f"{key} = {value[:100]}")
    await message.answer(f"✅ «{SETTING_LABELS.get(key, key)}» آپدیت شد:\n<code>{value[:200]}</code>")
    payload = await settings_menu_payload()
    await message.answer(payload["text"], reply_markup=payload["reply_markup"])


@router.callback_query(F.data == "a|setrst")
async def guide_reset(call: CallbackQuery, perms: set):
    if not has(perms, "settings"):
        return await call.answer("⛔️ دسترسی ندارید", show_alert=True)
    from core import texts
    await set_setting("guide_text", texts.GUIDE)
    await log_action(call.from_user.id, "تنظیمات", "بازنشانی متن راهنما")
    await call.answer("♻️ راهنما به متن پیش‌فرض برگشت")
    payload = await settings_menu_payload()
    await call.message.edit_text(payload["text"], reply_markup=payload["reply_markup"])
