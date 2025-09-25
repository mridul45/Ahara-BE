from enum import Enum


class GenderEnum(Enum):
    MALE = "Male"
    FEMALE = "Female"
    OTHER = "Other"
    PREFER_NOT_TO_SAY = "Prefer not to say"


class StateEnum(Enum):
    ANDHRA_PRADESH = "Andhra Pradesh"
    ARUNACHAL_PRADESH = "Arunachal Pradesh"
    ASSAM = "Assam"
    BIHAR = "Bihar"
    CHHATTISGARH = "Chhattisgarh"
    GOA = "Goa"
    GUJARAT = "Gujarat"
    HARYANA = "Haryana"
    HIMACHAL_PRADESH = "Himachal Pradesh"
    JHARKHAND = "Jharkhand"
    KARNATAKA = "Karnataka"
    KERALA = "Kerala"
    MADHYA_PRADESH = "Madhya Pradesh"
    MAHARASHTRA = "Maharashtra"
    MANIPUR = "Manipur"
    MEGHALAYA = "Meghalaya"
    MIZORAM = "Mizoram"
    NAGALAND = "Nagaland"
    ODISHA = "Odisha"
    PUNJAB = "Punjab"
    RAJASTHAN = "Rajasthan"
    SIKKIM = "Sikkim"
    TAMIL_NADU = "Tamil Nadu"
    TELANGANA = "Telangana"
    TRIPURA = "Tripura"
    UTTAR_PRADESH = "Uttar Pradesh"
    UTTARAKHAND = "Uttarakhand"
    WEST_BENGAL = "West Bengal"
    ANDAMAN_AND_NICOBAR_ISLANDS = "Andaman and Nicobar Islands"
    CHANDIGARH = "Chandigarh"
    DADRA_AND_NAGAR_HAVELI_AND_DAMAN_AND_DIU = (
        "Dadra and Nagar Haveli and Daman and Diu"
    )
    DELHI = "Delhi"
    JAMMU_AND_KASHMIR = "Jammu and Kashmir"
    LADAKH = "Ladakh"
    LAKSHADWEEP = "Lakshadweep"
    PUDUCHERRY = "Puducherry"



class ContentGenreEnum(Enum):
    """Categories of playlists in Ahara app."""

    # Core Practices
    MEDITATION_SERIES = "Meditation Series"
    BREATHWORK_SERIES = "Breathwork Series"
    MINDFULNESS = "Mindfulness Practices"
    ZEN_MODE = "Zen Mode Exclusives"

    # Wellness & Lifestyle
    SLEEP_WELLNESS = "Sleep & Relaxation"
    STRESS_RELIEF = "Stress Relief"
    WEIGHT_MANAGEMENT = "Weight Management"
    FLEXIBILITY = "Flexibility & Mobility"
    STRENGTH = "Strength Building"
    ENERGY_BOOST = "Energy Boost"
    FOCUS_CONCENTRATION = "Focus & Concentration"
    ANXIETY_RELIEF = "Anxiety Relief"
    EMOTIONAL_BALANCE = "Emotional Balance"
    DETOX_CLEANSE = "Detox & Cleanse"
    IMMUNITY_SUPPORT = "Immunity Support"

    # Time-based programs
    DAILY_CHALLENGE = "Daily Challenge"
    WEEKLY_PROGRAM = "Weekly Program"
    MONTHLY_JOURNEY = "Monthly Journey"
    QUICK_SESSIONS = "Quick 5–10 min Sessions"
    LONG_FORM_RETREAT = "Long-form Retreat"

    # Special Interest
    PRENATAL = "Prenatal Yoga"
    POSTNATAL = "Postnatal Yoga"
    KIDS = "Kids Yoga & Mindfulness"
    SENIORS = "Senior Wellness"
    OFFICE_BREAK = "Office/Workplace Break"
    TRAVEL_FRIENDLY = "Travel-Friendly Routines"

    # Cultural/Spiritual
    TRADITIONAL_HATHA = "Traditional Hatha Yoga"
    VINYASA_FLOW = "Vinyasa Flow"
    ASHTANGA = "Ashtanga Series"
    BHAKTI_DEVOTIONAL = "Bhakti/Devotional"
    SUTRAS_MANTRAS = "Sutras & Mantras"


class LanguageEnum(Enum):
    """Supported languages for Ahara content (major world languages)."""

    # Global / International
    ENGLISH = "English"
    SPANISH = "Spanish"
    FRENCH = "French"
    GERMAN = "German"
    ITALIAN = "Italian"
    PORTUGUESE = "Portuguese"
    RUSSIAN = "Russian"
    CHINESE_SIMPLIFIED = "Chinese (Simplified)"
    CHINESE_TRADITIONAL = "Chinese (Traditional)"
    JAPANESE = "Japanese"
    KOREAN = "Korean"
    ARABIC = "Arabic"
    TURKISH = "Turkish"
    DUTCH = "Dutch"
    SWEDISH = "Swedish"
    NORWEGIAN = "Norwegian"
    DANISH = "Danish"
    GREEK = "Greek"
    HEBREW = "Hebrew"
    POLISH = "Polish"
    UKRAINIAN = "Ukrainian"
    THAI = "Thai"
    VIETNAMESE = "Vietnamese"
    INDONESIAN = "Indonesian"
    MALAY = "Malay"
    FILIPINO = "Filipino"

    # Indian Subcontinent (important for Ahara’s core market)
    HINDI = "Hindi"
    BENGALI = "Bengali"
    PUNJABI = "Punjabi"
    MARATHI = "Marathi"
    GUJARATI = "Gujarati"
    TAMIL = "Tamil"
    TELUGU = "Telugu"
    KANNADA = "Kannada"
    MALAYALAM = "Malayalam"
    ODIA = "Odia"
    ASSAMESE = "Assamese"
    URDU = "Urdu"
    SANSKRIT = "Sanskrit"


class CTypeEnum(Enum):
    """Different types of content supported in Ahara."""

    EBOOK = "E-Book"
    ARTICLE = "Article"
    BLOG = "Blog"
    VIDEO = "Video"
    AUDIO = "Audio"
    PODCAST = "Podcast"
    GUIDE = "Guide / Handbook"
    RESEARCH_PAPER = "Research Paper"


class DifficultyLevelEnum(Enum):
    BEGINNER = "Beginner"
    INTERMEDIATE = "Intermediate"
    ADVANCED = "Advanced"
    ALL_LEVELS = "All Levels"