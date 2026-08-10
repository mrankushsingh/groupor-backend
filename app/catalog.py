CATEGORIES = [
    {"slug": "adult", "name": "Adult/18+/Hot"},
    {"slug": "art-design-photography", "name": "Art/Design/Photography"},
    {"slug": "auto-vehicle", "name": "Auto/Vehicle"},
    {"slug": "business-advertising-marketing", "name": "Business/Advertising/Marketing"},
    {"slug": "comedy-funny", "name": "Comedy/Funny"},
    {"slug": "dating-flirting-chatting", "name": "Dating/Flirting/Chatting"},
    {"slug": "education-school", "name": "Education/School"},
    {"slug": "entertainment-masti", "name": "Entertainment/Masti"},
    {"slug": "family-relationships", "name": "Family/Relationships"},
    {"slug": "fan-club-celebrities", "name": "Fan Club/Celebrities"},
    {"slug": "fashion-style-clothing", "name": "Fashion/Style/Clothing"},
    {"slug": "film-animation", "name": "Film/Animation"},
    {"slug": "food-drinks", "name": "Food/Drinks"},
    {"slug": "gaming-apps", "name": "Gaming/Apps"},
    {"slug": "health-beauty-fitness", "name": "Health/Beauty/Fitness"},
    {"slug": "jobs-career", "name": "Jobs/Career"},
    {"slug": "money-earning", "name": "Money/Earning"},
    {"slug": "music-audio-songs", "name": "Music/Audio/Songs"},
    {"slug": "news-magazines-politics", "name": "News/Magazines/Politics"},
    {"slug": "pets-animals-nature", "name": "Pets/Animals/Nature"},
    {"slug": "roleplay-comics", "name": "Roleplay/Comics"},
    {"slug": "science-technology", "name": "Science/Technology"},
    {"slug": "shopping-buy-sell", "name": "Shopping/Buy/Sell"},
    {"slug": "social-friendship-community", "name": "Social/Friendship/Community"},
    {"slug": "spiritual-devotional", "name": "Spiritual/Devotional"},
    {"slug": "sports-games", "name": "Sports/Games"},
    {"slug": "thoughts-quotes-jokes", "name": "Thoughts/Quotes/Jokes"},
    {"slug": "travel-local-place", "name": "Travel/Local/Place"},
]

COUNTRIES = [
    "Algeria", "Argentina", "Australia", "Austria", "Azerbaijan", "Bahrain", "Bangladesh",
    "Belarus", "Belgium", "Bolivia", "Bosnia and Herzegovina", "Brazil", "Bulgaria", "Canada",
    "Chile", "China", "Colombia", "Croatia", "Czechia", "Denmark", "Egypt", "Estonia",
    "Ethiopia", "Finland", "France", "Georgia", "Germany", "Ghana", "Greece", "Hong Kong",
    "Hungary", "Iceland", "India", "Indonesia", "Iraq", "Ireland", "Israel", "Italy",
    "Jamaica", "Japan", "Jordan", "Kazakhstan", "Kenya", "Kuwait", "Latvia", "Lebanon",
    "Libya", "Lithuania", "Luxembourg", "Macedonia", "Malawi", "Malaysia", "Mexico",
    "Montenegro", "Morocco", "Mozambique", "Nepal", "Netherlands", "New Zealand", "Nigeria",
    "Norway", "Oman", "Pakistan", "Panama", "Peru", "Philippines", "Poland", "Portugal",
    "Puerto Rico", "Qatar", "Romania", "Russia", "Saudi Arabia", "Senegal", "Serbia",
    "Singapore", "Slovakia", "Slovenia", "South Africa", "South Korea", "Spain", "Sri Lanka",
    "Sweden", "Switzerland", "Taiwan", "Tanzania", "Thailand", "Togo", "Tunisia", "Turkey",
    "Uganda", "Ukraine", "United Arab Emirates", "United Kingdom", "United States",
    "Venezuela", "Vietnam", "Yemen", "Zimbabwe",
]

LANGUAGES = [
    "Afrikaans", "Albanian", "Amharic", "Arabic", "Armenian", "Azerbaijani", "Bangla",
    "Basque", "Belarusian", "Bosnian", "Bulgarian", "Catalan", "Chinese", "Croatian",
    "Czech", "Danish", "Dutch", "English", "Estonian", "Filipino", "Finnish", "French",
    "Galician", "Georgian", "German", "Greek", "Gujarati", "Hebrew", "Hindi", "Hungarian",
    "Icelandic", "Indonesian", "Italian", "Japanese", "Kannada", "Kazakh", "Khmer",
    "Korean", "Kyrgyz", "Lao", "Latvian", "Lithuanian", "Macedonian", "Malay", "Malayalam",
    "Marathi", "Mongolian", "Myanmar", "Nepali", "Norwegian", "Persian", "Polish",
    "Portuguese", "Punjabi", "Romanian", "Russian", "Serbian", "Sinhala", "Slovak",
    "Slovenian", "Spanish", "Swahili", "Swedish", "Tamil", "Telugu", "Thai", "Turkish",
    "Ukrainian", "Urdu", "Uzbek", "Vietnamese", "Zulu",
]


def category_name(slug: str) -> str:
    for item in CATEGORIES:
        if item["slug"] == slug:
            return item["name"]
    return slug or "Community"
