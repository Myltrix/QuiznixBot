import telebot
import random
import json
import sqlite3
import logging
import google.generativeai as genai
from datetime import datetime
import asyncio
import threading
from concurrent.futures import ThreadPoolExecutor

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('ai_bot.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

GEMINI_API_KEY = "YOUR_GEMINI_API_KEY"
bot = telebot.TeleBot('YOUR_TELEGRAM_BOT_TOKEN')

try:
    if GEMINI_API_KEY and GEMINI_API_KEY != "YOUR_GEMINI_API_KEY_HERE":
        genai.configure(api_key=GEMINI_API_KEY)
        model = genai.GenerativeModel("gemini-2.5-flash")
        logger.info("Gemini model successfully initialized")
    else:
        logger.warning("Gemini API key not set or demo key set")
        model = None
except Exception as e:
    logger.error(f"Error initializing Gemini: {e}")
    model = None

def init_db():
    conn = sqlite3.connect('quiz_bot.db', check_same_thread=False)
    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            last_name TEXT,
            private_chat_id INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_profiles (
            user_id INTEGER PRIMARY KEY,
            name TEXT,
            age INTEGER,
            city TEXT,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (user_id)
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_stats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            chat_id INTEGER,
            chat_type TEXT,
            total_points INTEGER DEFAULT 0,
            total_questions INTEGER DEFAULT 0,
            correct_answers INTEGER DEFAULT 0,
            games_played INTEGER DEFAULT 0,
            last_played TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (user_id)
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS questions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            topic TEXT,
            question TEXT,
            options TEXT,
            correct_answer INTEGER,
            points INTEGER,
            difficulty TEXT
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS chat_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            messages TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (user_id)
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS ai_responses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            question TEXT,
            response TEXT,
            liked BOOLEAN DEFAULT 0,
            used_count INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (user_id)
        )
    ''')

    conn.commit()
    return conn

db_connection = init_db()

questions_database = {
    "history": [
        {
            "question": "In which year did World War II begin?",
            "options": ["1939", "1941", "1945", "1914"],
            "correct_answer": 0,
            "points": 5,
            "difficulty": "medium"
        },
        {
            "question": "Who was the first President of the USA?",
            "options": ["Abraham Lincoln", "George Washington", "Thomas Jefferson", "John Adams"],
            "correct_answer": 1,
            "points": 4,
            "difficulty": "easy"
        },
        {
            "question": "In which year did the Soviet Union collapse?",
            "options": ["1989", "1991", "1993", "1985"],
            "correct_answer": 1,
            "points": 5,
            "difficulty": "medium"
        },
        {
            "question": "Who wrote 'War and Peace'?",
            "options": ["Fyodor Dostoevsky", "Leo Tolstoy", "Anton Chekhov", "Ivan Turgenev"],
            "correct_answer": 1,
            "points": 4,
            "difficulty": "easy"
        },
        {
            "question": "Who discovered America?",
            "options": ["Christopher Columbus", "Vasco da Gama", "Ferdinand Magellan", "Amerigo Vespucci"],
            "correct_answer": 0,
            "points": 3,
            "difficulty": "easy"
        },
        {
            "question": "When did the French Revolution occur?",
            "options": ["1776", "1789", "1799", "1812"],
            "correct_answer": 1,
            "points": 6,
            "difficulty": "medium"
        },
        {
            "question": "Who was the first Emperor of Rome?",
            "options": ["Julius Caesar", "Augustus", "Nero", "Constantine"],
            "correct_answer": 1,
            "points": 5,
            "difficulty": "medium"
        },
        {
            "question": "In which year did the Byzantine Empire fall?",
            "options": ["1453", "1492", "1380", "1520"],
            "correct_answer": 0,
            "points": 7,
            "difficulty": "hard"
        },
        {
            "question": "Who built the Taj Mahal?",
            "options": ["Shah Jahan", "Akbar the Great", "Ashoka", "Babur"],
            "correct_answer": 0,
            "points": 6,
            "difficulty": "medium"
        },
        {
            "question": "When did World War I begin?",
            "options": ["1914", "1917", "1939", "1905"],
            "correct_answer": 0,
            "points": 4,
            "difficulty": "easy"
        },
        {
            "question": "Who was the first Russian Tsar?",
            "options": ["Ivan the Terrible", "Peter I", "Ivan III", "Alexey Mikhailovich"],
            "correct_answer": 0,
            "points": 5,
            "difficulty": "medium"
        },
        {
            "question": "In which year did the Battle of Kulikovo take place?",
            "options": ["1380", "1240", "1480", "1547"],
            "correct_answer": 0,
            "points": 6,
            "difficulty": "hard"
        },
        {
            "question": "Who wrote 'Das Kapital'?",
            "options": ["Karl Marx", "Friedrich Engels", "Vladimir Lenin", "Adam Smith"],
            "correct_answer": 0,
            "points": 5,
            "difficulty": "medium"
        },
        {
            "question": "In which year was Kievan Rus' baptized?",
            "options": ["988", "1015", "945", "1054"],
            "correct_answer": 0,
            "points": 6,
            "difficulty": "medium"
        },
        {
            "question": "Who won the Hundred Years' War?",
            "options": ["England", "France", "Spain", "Draw"],
            "correct_answer": 1,
            "points": 7,
            "difficulty": "hard"
        },
        {
            "question": "Who was the first Pope?",
            "options": ["Peter", "Leo I", "Gregory I", "Sylvester I"],
            "correct_answer": 0,
            "points": 7,
            "difficulty": "hard"
        },
        {
            "question": "When was Moscow founded?",
            "options": ["1147", "1240", "1325", "988"],
            "correct_answer": 0,
            "points": 5,
            "difficulty": "medium"
        },
        {
            "question": "Who led the first circumnavigation expedition?",
            "options": ["Ferdinand Magellan", "Christopher Columbus", "Vasco da Gama", "James Cook"],
            "correct_answer": 0,
            "points": 6,
            "difficulty": "medium"
        },
        {
            "question": "When did the Battle of Waterloo take place?",
            "options": ["1815", "1805", "1825", "1830"],
            "correct_answer": 0,
            "points": 6,
            "difficulty": "medium"
        },
        {
            "question": "Who was the last Russian Emperor?",
            "options": ["Nicholas II", "Alexander III", "Peter III", "Paul I"],
            "correct_answer": 0,
            "points": 4,
            "difficulty": "easy"
        },
        {
            "question": "When was the Magna Carta signed?",
            "options": ["1215", "1066", "1415", "1315"],
            "correct_answer": 0,
            "points": 7,
            "difficulty": "hard"
        },
        {
            "question": "Who founded the Romanov dynasty?",
            "options": ["Michael Romanov", "Peter I", "Ivan the Terrible", "Alexey Mikhailovich"],
            "correct_answer": 0,
            "points": 5,
            "difficulty": "medium"
        },
        {
            "question": "When did the October Revolution occur?",
            "options": ["1917", "1905", "1914", "1922"],
            "correct_answer": 0,
            "points": 5,
            "difficulty": "medium"
        },
        {
            "question": "Who was the female pharaoh in Ancient Egypt?",
            "options": ["Hatshepsut", "Nefertiti", "Cleopatra", "Neferusebek"],
            "correct_answer": 0,
            "points": 6,
            "difficulty": "hard"
        },
        {
            "question": "When did the Korean War begin?",
            "options": ["1950", "1945", "1955", "1960"],
            "correct_answer": 0,
            "points": 6,
            "difficulty": "hard"
        },
        {
            "question": "Who wrote 'The Republic'?",
            "options": ["Plato", "Aristotle", "Socrates", "Cicero"],
            "correct_answer": 0,
            "points": 7,
            "difficulty": "hard"
        },
        {
            "question": "When did the Western Roman Empire fall?",
            "options": ["476", "410", "455", "395"],
            "correct_answer": 0,
            "points": 7,
            "difficulty": "hard"
        },
        {
            "question": "Who was the first King of England?",
            "options": ["Alfred the Great", "William the Conqueror", "Athelstan", "Henry I"],
            "correct_answer": 2,
            "points": 8,
            "difficulty": "hard"
        },
        {
            "question": "When did the Battle of Kosovo take place?",
            "options": ["1389", "1242", "1410", "1456"],
            "correct_answer": 0,
            "points": 7,
            "difficulty": "hard"
        },
        {
            "question": "Who discovered penicillin?",
            "options": ["Alexander Fleming", "Louis Pasteur", "Robert Koch", "Ilya Mechnikov"],
            "correct_answer": 0,
            "points": 5,
            "difficulty": "medium"
        },
        {
            "question": "When was the Ottoman Empire founded?",
            "options": ["1299", "1453", "1326", "1402"],
            "correct_answer": 0,
            "points": 7,
            "difficulty": "hard"
        },
        {
            "question": "Who was the first Prime Minister of Great Britain?",
            "options": ["Robert Walpole", "William Pitt", "Charles James Fox", "Henry Pelham"],
            "correct_answer": 0,
            "points": 7,
            "difficulty": "hard"
        },
        {
            "question": "When did the St. Bartholomew's Day massacre occur?",
            "options": ["1572", "1588", "1598", "1618"],
            "correct_answer": 0,
            "points": 7,
            "difficulty": "hard"
        },
        {
            "question": "Who led the Spartacus revolt?",
            "options": ["Spartacus", "Crixus", "Hannibal", "Vercingetorix"],
            "correct_answer": 0,
            "points": 5,
            "difficulty": "medium"
        },
        {
            "question": "When was Alexandria founded?",
            "options": ["331 BC", "300 BC", "350 BC", "280 BC"],
            "correct_answer": 0,
            "points": 7,
            "difficulty": "hard"
        },
        {
            "question": "Who was the first Emperor of China?",
            "options": ["Qin Shi Huang", "Wu Di", "Gao Zu", "Wen Di"],
            "correct_answer": 0,
            "points": 6,
            "difficulty": "medium"
        },
        {
            "question": "When did the Battle of Hastings take place?",
            "options": ["1066", "1016", "1154", "1215"],
            "correct_answer": 0,
            "points": 6,
            "difficulty": "medium"
        },
        {
            "question": "Who wrote the 'Iliad' and 'Odyssey'?",
            "options": ["Homer", "Hesiod", "Virgil", "Sophocles"],
            "correct_answer": 0,
            "points": 4,
            "difficulty": "easy"
        },
        {
            "question": "When did the Hundred Years' War begin?",
            "options": ["1337", "1346", "1356", "1415"],
            "correct_answer": 0,
            "points": 7,
            "difficulty": "hard"
        },
        {
            "question": "Who was the first King of France?",
            "options": ["Clovis I", "Charlemagne", "Philip II", "Louis IX"],
            "correct_answer": 0,
            "points": 7,
            "difficulty": "hard"
        },
        {
            "question": "When did the Battle of Lepanto take place?",
            "options": ["1571", "1588", "1591", "1600"],
            "correct_answer": 0,
            "points": 8,
            "difficulty": "hard"
        },
        {
            "question": "Who founded the city of Rome?",
            "options": ["Romulus", "Numa Pompilius", "Remus", "Tullus Hostilius"],
            "correct_answer": 0,
            "points": 4,
            "difficulty": "easy"
        },
        {
            "question": "When was the US Declaration of Independence signed?",
            "options": ["1776", "1789", "1791", "1801"],
            "correct_answer": 0,
            "points": 5,
            "difficulty": "medium"
        },
        {
            "question": "Who was the first Caliph of Islam?",
            "options": ["Abu Bakr", "Umar", "Uthman", "Ali"],
            "correct_answer": 0,
            "points": 6,
            "difficulty": "medium"
        },
        {
            "question": "When did the Battle of the Kalka River take place?",
            "options": ["1223", "1237", "1240", "1242"],
            "correct_answer": 0,
            "points": 7,
            "difficulty": "hard"
        },
        {
            "question": "Who was the first King of Portugal?",
            "options": ["Afonso I", "Sancho I", "Afonso II", "Peter I"],
            "correct_answer": 0,
            "points": 7,
            "difficulty": "hard"
        },
        {
            "question": "When did the Wars of the Roses begin?",
            "options": ["1455", "1485", "1435", "1460"],
            "correct_answer": 0,
            "points": 7,
            "difficulty": "hard"
        },
        {
            "question": "Who was the first Holy Roman Emperor?",
            "options": ["Otto I", "Charlemagne", "Frederick I", "Henry IV"],
            "correct_answer": 0,
            "points": 7,
            "difficulty": "hard"
        },
        {
            "question": "When did the Battle of Agincourt take place?",
            "options": ["1415", "1429", "1453", "1475"],
            "correct_answer": 0,
            "points": 7,
            "difficulty": "hard"
        },
        {
            "question": "Who was the first woman to win a Nobel Prize?",
            "options": ["Marie Curie", "Rosalind Franklin", "Ada Lovelace", "Jane Goodall"],
            "correct_answer": 0,
            "points": 6,
            "difficulty": "medium"
        }
    ],
    "geography": [
        {
            "question": "What is the longest river in the world?",
            "options": ["Amazon", "Nile", "Yangtze", "Mississippi"],
            "correct_answer": 0,
            "points": 6,
            "difficulty": "medium"
        },
        {
            "question": "Capital of Australia?",
            "options": ["Sydney", "Melbourne", "Canberra", "Perth"],
            "correct_answer": 2,
            "points": 3,
            "difficulty": "easy"
        },
        {
            "question": "Which country is the largest by area?",
            "options": ["Canada", "USA", "Russia", "China"],
            "correct_answer": 2,
            "points": 4,
            "difficulty": "easy"
        },
        {
            "question": "What is the largest desert in the world?",
            "options": ["Sahara", "Gobi", "Arabian", "Antarctic"],
            "correct_answer": 3,
            "points": 7,
            "difficulty": "hard"
        },
        {
            "question": "Capital of Brazil?",
            "options": ["Rio de Janeiro", "São Paulo", "Brasília", "Salvador"],
            "correct_answer": 2,
            "points": 4,
            "difficulty": "medium"
        },
        {
            "question": "What is the highest mountain in the world?",
            "options": ["Kilimanjaro", "Everest", "McKinley", "Aconcagua"],
            "correct_answer": 1,
            "points": 3,
            "difficulty": "easy"
        },
        {
            "question": "What is the deepest lake in the world?",
            "options": ["Baikal", "Tanganyika", "Superior", "Victoria"],
            "correct_answer": 0,
            "points": 5,
            "difficulty": "medium"
        },
        {
            "question": "How many oceans are on Earth?",
            "options": ["4", "5", "6", "7"],
            "correct_answer": 1,
            "points": 3,
            "difficulty": "easy"
        },
        {
            "question": "Which country has the longest coastline?",
            "options": ["Russia", "Canada", "Indonesia", "Philippines"],
            "correct_answer": 1,
            "points": 6,
            "difficulty": "hard"
        },
        {
            "question": "Capital of Iceland?",
            "options": ["Oslo", "Copenhagen", "Reykjavik", "Helsinki"],
            "correct_answer": 2,
            "points": 4,
            "difficulty": "medium"
        },
        {
            "question": "What is the smallest country in the world?",
            "options": ["Monaco", "Vatican City", "San Marino", "Liechtenstein"],
            "correct_answer": 1,
            "points": 5,
            "difficulty": "medium"
        },
        {
            "question": "How many states are in the USA?",
            "options": ["48", "50", "52", "54"],
            "correct_answer": 1,
            "points": 4,
            "difficulty": "easy"
        },
        {
            "question": "Which country is shaped like a boot?",
            "options": ["Italy", "Greece", "Spain", "Portugal"],
            "correct_answer": 0,
            "points": 3,
            "difficulty": "easy"
        },
        {
            "question": "Capital of Canada?",
            "options": ["Toronto", "Vancouver", "Ottawa", "Montreal"],
            "correct_answer": 2,
            "points": 4,
            "difficulty": "medium"
        },
        {
            "question": "Which river flows through Paris?",
            "options": ["Seine", "Thames", "Rhine", "Danube"],
            "correct_answer": 0,
            "points": 4,
            "difficulty": "easy"
        },
        {
            "question": "What is the largest lake in the world?",
            "options": ["Caspian Sea", "Baikal", "Superior", "Victoria"],
            "correct_answer": 0,
            "points": 5,
            "difficulty": "medium"
        },
        {
            "question": "Capital of Egypt?",
            "options": ["Alexandria", "Cairo", "Giza", "Luxor"],
            "correct_answer": 1,
            "points": 3,
            "difficulty": "easy"
        },
        {
            "question": "Which country is located on two continents?",
            "options": ["Turkey", "Egypt", "Russia", "All of the above"],
            "correct_answer": 3,
            "points": 6,
            "difficulty": "medium"
        },
        {
            "question": "What is the highest waterfall in the world?",
            "options": ["Angel Falls", "Niagara", "Victoria", "Iguazu"],
            "correct_answer": 0,
            "points": 5,
            "difficulty": "medium"
        },
        {
            "question": "Capital of Japan?",
            "options": ["Osaka", "Kyoto", "Tokyo", "Yokohama"],
            "correct_answer": 2,
            "points": 3,
            "difficulty": "easy"
        },
        {
            "question": "Which sea is the saltiest?",
            "options": ["Dead Sea", "Red Sea", "Mediterranean Sea", "Black Sea"],
            "correct_answer": 0,
            "points": 5,
            "difficulty": "medium"
        },
        {
            "question": "Capital of Argentina?",
            "options": ["Buenos Aires", "Santiago", "Lima", "Brasilia"],
            "correct_answer": 0,
            "points": 4,
            "difficulty": "medium"
        },
        {
            "question": "Which desert is located in South America?",
            "options": ["Atacama", "Sahara", "Gobi", "Karakum"],
            "correct_answer": 0,
            "points": 5,
            "difficulty": "medium"
        },
        {
            "question": "What is the largest island in the world?",
            "options": ["Greenland", "New Guinea", "Borneo", "Madagascar"],
            "correct_answer": 0,
            "points": 4,
            "difficulty": "easy"
        },
        {
            "question": "Capital of South Korea?",
            "options": ["Busan", "Seoul", "Incheon", "Daegu"],
            "correct_answer": 1,
            "points": 4,
            "difficulty": "easy"
        },
        {
            "question": "Which country has the most islands?",
            "options": ["Sweden", "Indonesia", "Philippines", "Japan"],
            "correct_answer": 0,
            "points": 7,
            "difficulty": "hard"
        },
        {
            "question": "Capital of Norway?",
            "options": ["Oslo", "Stockholm", "Copenhagen", "Helsinki"],
            "correct_answer": 0,
            "points": 4,
            "difficulty": "easy"
        },
        {
            "question": "Which country is landlocked?",
            "options": ["Switzerland", "Austria", "Hungary", "All of the above"],
            "correct_answer": 3,
            "points": 5,
            "difficulty": "medium"
        },
        {
            "question": "What is the largest peninsula in the world?",
            "options": ["Arabian", "Indian", "Scandinavian", "Labrador"],
            "correct_answer": 0,
            "points": 6,
            "difficulty": "hard"
        },
        {
            "question": "Capital of Morocco?",
            "options": ["Casablanca", "Rabat", "Marrakech", "Fez"],
            "correct_answer": 1,
            "points": 5,
            "difficulty": "medium"
        },
        {
            "question": "Which country has the most time zones?",
            "options": ["Russia", "USA", "Canada", "China"],
            "correct_answer": 0,
            "points": 5,
            "difficulty": "medium"
        },
        {
            "question": "Capital of Peru?",
            "options": ["Lima", "Quito", "Bogota", "La Paz"],
            "correct_answer": 0,
            "points": 4,
            "difficulty": "medium"
        },
        {
            "question": "Which lake is between the USA and Canada?",
            "options": ["Superior", "Michigan", "Huron", "All of the above"],
            "correct_answer": 3,
            "points": 6,
            "difficulty": "medium"
        },
        {
            "question": "Capital of Vietnam?",
            "options": ["Hanoi", "Ho Chi Minh City", "Da Nang", "Hue"],
            "correct_answer": 0,
            "points": 4,
            "difficulty": "medium"
        },
        {
            "question": "Which country has the longest land border?",
            "options": ["Russia", "China", "USA", "Canada"],
            "correct_answer": 0,
            "points": 6,
            "difficulty": "hard"
        },
        {
            "question": "Capital of Finland?",
            "options": ["Helsinki", "Stockholm", "Oslo", "Tallinn"],
            "correct_answer": 0,
            "points": 4,
            "difficulty": "easy"
        },
        {
            "question": "Which country is completely surrounded by another country?",
            "options": ["San Marino", "Vatican City", "Lesotho", "All of the above"],
            "correct_answer": 3,
            "points": 7,
            "difficulty": "hard"
        },
        {
            "question": "Capital of Chile?",
            "options": ["Santiago", "Buenos Aires", "Lima", "Bogota"],
            "correct_answer": 0,
            "points": 4,
            "difficulty": "medium"
        },
        {
            "question": "Which country has the most official languages?",
            "options": ["India", "South Africa", "Bolivia", "Switzerland"],
            "correct_answer": 0,
            "points": 6,
            "difficulty": "hard"
        },
        {
            "question": "Capital of Pakistan?",
            "options": ["Islamabad", "Karachi", "Lahore", "Peshawar"],
            "correct_answer": 0,
            "points": 5,
            "difficulty": "medium"
        },
        {
            "question": "Which country has the youngest population?",
            "options": ["Niger", "Uganda", "Mali", "Chad"],
            "correct_answer": 0,
            "points": 7,
            "difficulty": "hard"
        },
        {
            "question": "Capital of Saudi Arabia?",
            "options": ["Riyadh", "Mecca", "Medina", "Jeddah"],
            "correct_answer": 0,
            "points": 5,
            "difficulty": "medium"
        },
        {
            "question": "Which country has the most volcanoes?",
            "options": ["Indonesia", "USA", "Russia", "Japan"],
            "correct_answer": 0,
            "points": 6,
            "difficulty": "hard"
        },
        {
            "question": "Capital of Ukraine?",
            "options": ["Kyiv", "Kharkiv", "Odesa", "Lviv"],
            "correct_answer": 0,
            "points": 3,
            "difficulty": "easy"
        },
        {
            "question": "Which country has the longest subway system?",
            "options": ["China", "USA", "Russia", "South Korea"],
            "correct_answer": 0,
            "points": 6,
            "difficulty": "hard"
        },
        {
            "question": "Capital of Malaysia?",
            "options": ["Kuala Lumpur", "Singapore", "Bangkok", "Jakarta"],
            "correct_answer": 0,
            "points": 4,
            "difficulty": "medium"
        },
        {
            "question": "Which country has the most natural lakes?",
            "options": ["Canada", "Russia", "USA", "Finland"],
            "correct_answer": 0,
            "points": 6,
            "difficulty": "hard"
        },
        {
            "question": "Capital of Algeria?",
            "options": ["Algiers", "Casablanca", "Tunis", "Rabat"],
            "correct_answer": 0,
            "points": 5,
            "difficulty": "medium"
        },
        {
            "question": "Which country has the longest railway network?",
            "options": ["USA", "Russia", "China", "India"],
            "correct_answer": 0,
            "points": 6,
            "difficulty": "hard"
        },
        {
            "question": "What is the largest canyon in the world?",
            "options": ["Grand Canyon", "Colca Canyon", "Fish River Canyon", "Yarlung Tsangpo Grand Canyon"],
            "correct_answer": 3,
            "points": 7,
            "difficulty": "hard"
        },
        {
            "question": "Which country is home to the most UNESCO World Heritage sites?",
            "options": ["Italy", "China", "Germany", "France"],
            "correct_answer": 0,
            "points": 7,
            "difficulty": "hard"
        }
    ],
    "science": [
        {
            "question": "How many elements are in the periodic table?",
            "options": ["118", "92", "150", "206"],
            "correct_answer": 0,
            "points": 7,
            "difficulty": "hard"
        },
        {
            "question": "Which planet is the largest in the solar system?",
            "options": ["Earth", "Saturn", "Jupiter", "Neptune"],
            "correct_answer": 2,
            "points": 3,
            "difficulty": "easy"
        },
        {
            "question": "How many bones are in the adult human body?",
            "options": ["206", "300", "150", "250"],
            "correct_answer": 0,
            "points": 5,
            "difficulty": "medium"
        },
        {
            "question": "Which gas is most abundant in Earth's atmosphere?",
            "options": ["Oxygen", "Nitrogen", "Carbon dioxide", "Argon"],
            "correct_answer": 1,
            "points": 4,
            "difficulty": "easy"
        },
        {
            "question": "How many chromosomes do humans have?",
            "options": ["23", "46", "48", "52"],
            "correct_answer": 1,
            "points": 6,
            "difficulty": "medium"
        },
        {
            "question": "What is the hardest substance in the human body?",
            "options": ["Bone", "Nail", "Tooth enamel", "Hair"],
            "correct_answer": 2,
            "points": 5,
            "difficulty": "medium"
        },
        {
            "question": "How many planets are in the solar system?",
            "options": ["7", "8", "9", "10"],
            "correct_answer": 1,
            "points": 3,
            "difficulty": "easy"
        },
        {
            "question": "Which element has the chemical symbol 'Au'?",
            "options": ["Silver", "Gold", "Aluminum", "Argon"],
            "correct_answer": 1,
            "points": 4,
            "difficulty": "easy"
        },
        {
            "question": "How many moons does Mars have?",
            "options": ["0", "1", "2", "3"],
            "correct_answer": 2,
            "points": 6,
            "difficulty": "hard"
        },
        {
            "question": "What is the speed of light in vacuum?",
            "options": ["300,000 km/s", "150,000 km/s", "500,000 km/s", "1,000,000 km/s"],
            "correct_answer": 0,
            "points": 7,
            "difficulty": "hard"
        },
        {
            "question": "Which is the largest organ in the human body?",
            "options": ["Liver", "Heart", "Skin", "Brain"],
            "correct_answer": 2,
            "points": 5,
            "difficulty": "medium"
        },
        {
            "question": "How many chambers are in the human heart?",
            "options": ["2", "3", "4", "5"],
            "correct_answer": 2,
            "points": 4,
            "difficulty": "medium"
        },
        {
            "question": "Which gas do plants absorb from the atmosphere?",
            "options": ["Oxygen", "Nitrogen", "Carbon dioxide", "Hydrogen"],
            "correct_answer": 2,
            "points": 4,
            "difficulty": "easy"
        },
        {
            "question": "How old is the Earth approximately?",
            "options": ["4.5 billion years", "10 million years", "1 billion years", "100 million years"],
            "correct_answer": 0,
            "points": 6,
            "difficulty": "hard"
        },
        {
            "question": "What is the most abundant element in the universe?",
            "options": ["Hydrogen", "Oxygen", "Carbon", "Nitrogen"],
            "correct_answer": 0,
            "points": 5,
            "difficulty": "medium"
        },
        {
            "question": "How many blood types are in the human ABO system?",
            "options": ["4", "6", "8", "10"],
            "correct_answer": 0,
            "points": 4,
            "difficulty": "easy"
        },
        {
            "question": "Which planet is closest to the Sun?",
            "options": ["Mercury", "Venus", "Earth", "Mars"],
            "correct_answer": 0,
            "points": 3,
            "difficulty": "easy"
        },
        {
            "question": "Which chemical element has the symbol 'O'?",
            "options": ["Gold", "Oxygen", "Osmium", "Tin"],
            "correct_answer": 1,
            "points": 3,
            "difficulty": "easy"
        },
        {
            "question": "How many moons does Jupiter have?",
            "options": ["4", "16", "79", "over 90"],
            "correct_answer": 3,
            "points": 7,
            "difficulty": "hard"
        },
        {
            "question": "What is the smallest bone in the human body?",
            "options": ["Stapes", "Incus", "Malleus", "All of the above"],
            "correct_answer": 0,
            "points": 6,
            "difficulty": "hard"
        },
        {
            "question": "Which gas do plants release during photosynthesis?",
            "options": ["Oxygen", "Carbon dioxide", "Nitrogen", "Hydrogen"],
            "correct_answer": 0,
            "points": 4,
            "difficulty": "easy"
        },
        {
            "question": "How many muscles are in the human body?",
            "options": ["about 600", "about 300", "about 1000", "about 200"],
            "correct_answer": 0,
            "points": 6,
            "difficulty": "hard"
        },
        {
            "question": "Which planet is known for its rings?",
            "options": ["Saturn", "Jupiter", "Uranus", "Neptune"],
            "correct_answer": 0,
            "points": 3,
            "difficulty": "easy"
        },
        {
            "question": "Which element is necessary for chlorophyll formation?",
            "options": ["Magnesium", "Iron", "Calcium", "Potassium"],
            "correct_answer": 0,
            "points": 6,
            "difficulty": "hard"
        },
        {
            "question": "How many chromosomes do chimpanzees have?",
            "options": ["48", "46", "42", "44"],
            "correct_answer": 0,
            "points": 7,
            "difficulty": "hard"
        },
        {
            "question": "Which star is closest to Earth?",
            "options": ["Sun", "Proxima Centauri", "Sirius", "Alpha Centauri"],
            "correct_answer": 0,
            "points": 3,
            "difficulty": "easy"
        },
        {
            "question": "Which gas causes the greenhouse effect?",
            "options": ["Carbon dioxide", "Oxygen", "Nitrogen", "Argon"],
            "correct_answer": 0,
            "points": 4,
            "difficulty": "easy"
        },
        {
            "question": "How many lobes are in the human brain?",
            "options": ["5", "3", "7", "4"],
            "correct_answer": 0,
            "points": 6,
            "difficulty": "hard"
        },
        {
            "question": "Which planet has the largest temperature variation?",
            "options": ["Mercury", "Venus", "Mars", "Earth"],
            "correct_answer": 0,
            "points": 6,
            "difficulty": "hard"
        },
        {
            "question": "Which element makes up about 21% of Earth's atmosphere?",
            "options": ["Oxygen", "Nitrogen", "Carbon dioxide", "Hydrogen"],
            "correct_answer": 0,
            "points": 4,
            "difficulty": "easy"
        },
        {
            "question": "How many bones are in the adult human skull?",
            "options": ["22", "28", "32", "18"],
            "correct_answer": 0,
            "points": 6,
            "difficulty": "hard"
        },
        {
            "question": "Which planet rotates on its side?",
            "options": ["Uranus", "Neptune", "Saturn", "Jupiter"],
            "correct_answer": 0,
            "points": 6,
            "difficulty": "hard"
        },
        {
            "question": "Which vitamin is produced when exposed to sunlight?",
            "options": ["Vitamin D", "Vitamin C", "Vitamin A", "Vitamin B12"],
            "correct_answer": 0,
            "points": 4,
            "difficulty": "easy"
        },
        {
            "question": "How many planets in the solar system have rings?",
            "options": ["4", "2", "3", "5"],
            "correct_answer": 0,
            "points": 7,
            "difficulty": "hard"
        },
        {
            "question": "Which acid is found in the stomach?",
            "options": ["Hydrochloric acid", "Sulfuric acid", "Nitric acid", "Acetic acid"],
            "correct_answer": 0,
            "points": 4,
            "difficulty": "easy"
        },
        {
            "question": "How many moons does Venus have?",
            "options": ["0", "1", "2", "3"],
            "correct_answer": 0,
            "points": 5,
            "difficulty": "medium"
        },
        {
            "question": "Which element has the highest melting point?",
            "options": ["Tungsten", "Iron", "Gold", "Silver"],
            "correct_answer": 0,
            "points": 6,
            "difficulty": "hard"
        },
        {
            "question": "How many sections are in the human spine?",
            "options": ["5", "7", "3", "4"],
            "correct_answer": 0,
            "points": 5,
            "difficulty": "medium"
        },
        {
            "question": "Which planet has the longest day?",
            "options": ["Venus", "Mercury", "Mars", "Jupiter"],
            "correct_answer": 0,
            "points": 6,
            "difficulty": "hard"
        },
        {
            "question": "Which gas is used in balloons?",
            "options": ["Helium", "Hydrogen", "Nitrogen", "Oxygen"],
            "correct_answer": 0,
            "points": 4,
            "difficulty": "easy"
        },
        {
            "question": "How many baby teeth do humans have?",
            "options": ["20", "28", "32", "24"],
            "correct_answer": 0,
            "points": 4,
            "difficulty": "easy"
        },
        {
            "question": "Which planet has the highest density?",
            "options": ["Earth", "Mercury", "Venus", "Mars"],
            "correct_answer": 0,
            "points": 6,
            "difficulty": "hard"
        },
        {
            "question": "Which element is the basis of organic chemistry?",
            "options": ["Carbon", "Oxygen", "Hydrogen", "Nitrogen"],
            "correct_answer": 0,
            "points": 4,
            "difficulty": "easy"
        },
        {
            "question": "How many pairs of ribs do humans have?",
            "options": ["12", "10", "14", "8"],
            "correct_answer": 0,
            "points": 5,
            "difficulty": "medium"
        },
        {
            "question": "What is the brightest star in the night sky?",
            "options": ["Sirius", "Polaris", "Vega", "Arcturus"],
            "correct_answer": 0,
            "points": 5,
            "difficulty": "medium"
        },
        {
            "question": "Which gas makes up 78% of Earth's atmosphere?",
            "options": ["Nitrogen", "Oxygen", "Argon", "Carbon dioxide"],
            "correct_answer": 0,
            "points": 4,
            "difficulty": "easy"
        },
        {
            "question": "How many planets in the solar system are visible to the naked eye?",
            "options": ["5", "3", "6", "4"],
            "correct_answer": 0,
            "points": 6,
            "difficulty": "hard"
        },
        {
            "question": "Which is the largest gland in the human body?",
            "options": ["Liver", "Pancreas", "Thyroid", "Thymus"],
            "correct_answer": 0,
            "points": 4,
            "difficulty": "easy"
        },
        {
            "question": "Which element has atomic number 1?",
            "options": ["Hydrogen", "Helium", "Lithium", "Boron"],
            "correct_answer": 0,
            "points": 3,
            "difficulty": "easy"
        },
        {
            "question": "How many bones are in the human foot?",
            "options": ["26", "28", "24", "22"],
            "correct_answer": 0,
            "points": 6,
            "difficulty": "hard"
        },
        {
            "question": "Which planet has the most moons?",
            "options": ["Saturn", "Jupiter", "Uranus", "Neptune"],
            "correct_answer": 0,
            "points": 6,
            "difficulty": "hard"
        }
    ],
    "programming": [
        {
            "question": "Which programming language is considered the ancestor of many modern languages?",
            "options": ["C", "Python", "Java", "Fortran"],
            "correct_answer": 0,
            "points": 5,
            "difficulty": "medium"
        },
        {
            "question": "What does HTML stand for?",
            "options": ["HyperText Markup Language", "HighTech Modern Language", "HyperTransfer Markup Language", "HighText Machine Language"],
            "correct_answer": 0,
            "points": 3,
            "difficulty": "easy"
        },
        {
            "question": "Which operator is used for equality comparison in Python?",
            "options": ["=", "==", "===", "!="],
            "correct_answer": 1,
            "points": 4,
            "difficulty": "easy"
        },
        {
            "question": "What is OOP?",
            "options": ["Object-Oriented Programming", "Operating Order Processing", "Optimal Object Placement", "Overall Operating Protocol"],
            "correct_answer": 0,
            "points": 4,
            "difficulty": "easy"
        },
        {
            "question": "Which language is used for styling web pages?",
            "options": ["HTML", "JavaScript", "CSS", "PHP"],
            "correct_answer": 2,
            "points": 3,
            "difficulty": "easy"
        },
        {
            "question": "What is Git?",
            "options": ["Programming language", "Version control system", "Text editor", "Operating system"],
            "correct_answer": 1,
            "points": 4,
            "difficulty": "medium"
        },
        {
            "question": "Which data type in Python is mutable?",
            "options": ["int", "str", "tuple", "list"],
            "correct_answer": 3,
            "points": 5,
            "difficulty": "medium"
        },
        {
            "question": "What is API?",
            "options": ["Application Programming Interface", "Advanced Program Integration", "Automated Process Instruction", "Application Process Interface"],
            "correct_answer": 0,
            "points": 5,
            "difficulty": "medium"
        },
        {
            "question": "Which method is used to add an element to a list in Python?",
            "options": ["add()", "append()", "insert()", "push()"],
            "correct_answer": 1,
            "points": 4,
            "difficulty": "easy"
        },
        {
            "question": "What is SQL?",
            "options": ["Simple Query Language", "Structured Query Language", "System Query Logic", "Standard Question Language"],
            "correct_answer": 1,
            "points": 4,
            "difficulty": "medium"
        },
        {
            "question": "Which symbol is used for comments in Python?",
            "options": ["//", "#", "--", "/*"],
            "correct_answer": 1,
            "points": 3,
            "difficulty": "easy"
        },
        {
            "question": "What is recursion?",
            "options": ["Loop execution of code", "Function calling itself", "Fast program execution", "Parallel programming"],
            "correct_answer": 1,
            "points": 6,
            "difficulty": "hard"
        },
        {
            "question": "Which is the most popular Python web framework?",
            "options": ["Flask", "Django", "FastAPI", "Pyramid"],
            "correct_answer": 1,
            "points": 5,
            "difficulty": "medium"
        },
        {
            "question": "What is Big O notation?",
            "options": ["Notation system for large numbers", "Algorithm complexity notation", "Code formatting standard", "Program optimization method"],
            "correct_answer": 1,
            "points": 7,
            "difficulty": "hard"
        },
        {
            "question": "Which operator is used for integer division in Python?",
            "options": ["/", "//", "%", "div"],
            "correct_answer": 1,
            "points": 4,
            "difficulty": "medium"
        },
        {
            "question": "What is Docker?",
            "options": ["Programming language", "Containerization system", "Database", "Testing framework"],
            "correct_answer": 1,
            "points": 6,
            "difficulty": "hard"
        },
        {
            "question": "Which HTTP method is used to retrieve data?",
            "options": ["POST", "GET", "PUT", "DELETE"],
            "correct_answer": 1,
            "points": 4,
            "difficulty": "medium"
        },
        {
            "question": "What is JSON?",
            "options": ["JavaScript Object Notation", "Java Standard Object Network", "JavaScript Online Notation", "Java System Object Notation"],
            "correct_answer": 0,
            "points": 4,
            "difficulty": "easy"
        },
        {
            "question": "Which sorting algorithm is considered fastest on average?",
            "options": ["Bubble sort", "Quick sort", "Selection sort", "Insertion sort"],
            "correct_answer": 1,
            "points": 6,
            "difficulty": "hard"
        },
        {
            "question": "What is MVC?",
            "options": ["Model-View-Controller", "Main-View-Component", "Module-View-Code", "Model-Value-Controller"],
            "correct_answer": 0,
            "points": 5,
            "difficulty": "medium"
        },
        {
            "question": "Which database type uses SQL?",
            "options": ["Relational", "Document", "Key-value", "Graph"],
            "correct_answer": 0,
            "points": 4,
            "difficulty": "medium"
        },
        {
            "question": "What is AJAX?",
            "options": ["Asynchronous JavaScript and XML", "Advanced JavaScript and XML", "Automated JavaScript Application", "Asynchronous Java and XML"],
            "correct_answer": 0,
            "points": 5,
            "difficulty": "medium"
        },
        {
            "question": "Which operator is used for inheritance in Python?",
            "options": ["inherits", "extends", "super", "parentheses in class definition"],
            "correct_answer": 3,
            "points": 6,
            "difficulty": "hard"
        },
        {
            "question": "What is REST API?",
            "options": ["Representational State Transfer", "Remote System Transfer", "Resource State Transfer", "Rapid System Technology"],
            "correct_answer": 0,
            "points": 6,
            "difficulty": "hard"
        },
        {
            "question": "Which method is used to remove an element from a dictionary in Python?",
            "options": ["remove()", "delete()", "pop()", "discard()"],
            "correct_answer": 2,
            "points": 5,
            "difficulty": "medium"
        },
        {
            "question": "What is a variable in programming?",
            "options": ["Constant value", "Named memory location", "Function", "Loop"],
            "correct_answer": 1,
            "points": 3,
            "difficulty": "easy"
        },
        {
            "question": "Which programming language was created by Microsoft?",
            "options": ["Java", "C#", "Python", "Ruby"],
            "correct_answer": 1,
            "points": 4,
            "difficulty": "medium"
        },
        {
            "question": "What is a compiler?",
            "options": ["Text editor", "Program that translates code to machine language", "Database", "Operating system"],
            "correct_answer": 1,
            "points": 5,
            "difficulty": "medium"
        },
        {
            "question": "Which language is used for Android app development?",
            "options": ["Java", "Swift", "C#", "Python"],
            "correct_answer": 0,
            "points": 4,
            "difficulty": "medium"
        },
        {
            "question": "What is an algorithm?",
            "options": ["Sequence of steps to solve a problem", "Programming language", "Database", "Graphical interface"],
            "correct_answer": 0,
            "points": 3,
            "difficulty": "easy"
        },
        {
            "question": "Which programming language is considered most popular for web development?",
            "options": ["JavaScript", "Python", "Java", "C++"],
            "correct_answer": 0,
            "points": 4,
            "difficulty": "easy"
        },
        {
            "question": "What is a bug?",
            "options": ["Error in a program", "Program function", "Data type", "Algorithm"],
            "correct_answer": 0,
            "points": 3,
            "difficulty": "easy"
        },
        {
            "question": "Which language is used for iOS app development?",
            "options": ["Swift", "Java", "Kotlin", "C#"],
            "correct_answer": 0,
            "points": 4,
            "difficulty": "medium"
        },
        {
            "question": "What is a framework?",
            "options": ["Set of tools for development", "Programming language", "Database", "Operating system"],
            "correct_answer": 0,
            "points": 4,
            "difficulty": "medium"
        },
        {
            "question": "Which language has a snake as its mascot?",
            "options": ["Python", "Java", "Ruby", "PHP"],
            "correct_answer": 0,
            "points": 3,
            "difficulty": "easy"
        },
        {
            "question": "What is IDE?",
            "options": ["Integrated Development Environment", "Internet Data Exchange", "Interactive Design Element", "International Development Engine"],
            "correct_answer": 0,
            "points": 4,
            "difficulty": "medium"
        },
        {
            "question": "Which language is considered the language for Data Science?",
            "options": ["Python", "C++", "Java", "Go"],
            "correct_answer": 0,
            "points": 4,
            "difficulty": "medium"
        },
        {
            "question": "What is SQL injection?",
            "options": ["Type of cyber attack", "Query optimization method", "Database type", "Programming language"],
            "correct_answer": 0,
            "points": 6,
            "difficulty": "hard"
        },
        {
            "question": "Which language did Brendan Eich create?",
            "options": ["JavaScript", "Python", "Java", "C++"],
            "correct_answer": 0,
            "points": 5,
            "difficulty": "medium"
        },
        {
            "question": "What is a design pattern?",
            "options": ["Typical solution to common problems", "Programming language", "Database", "Framework"],
            "correct_answer": 0,
            "points": 5,
            "difficulty": "medium"
        },
        {
            "question": "Which language has garbage collection?",
            "options": ["Java", "C", "C++", "Assembly"],
            "correct_answer": 0,
            "points": 5,
            "difficulty": "medium"
        },
        {
            "question": "What are cookies?",
            "options": ["Small data files", "Programming language", "Database", "Algorithm"],
            "correct_answer": 0,
            "points": 4,
            "difficulty": "easy"
        },
        {
            "question": "Which language is considered fastest?",
            "options": ["C++", "Python", "Java", "JavaScript"],
            "correct_answer": 0,
            "points": 5,
            "difficulty": "medium"
        },
        {
            "question": "What is blockchain?",
            "options": ["Distributed database", "Programming language", "Framework", "Sorting algorithm"],
            "correct_answer": 0,
            "points": 6,
            "difficulty": "hard"
        },
        {
            "question": "Which language is used for machine learning?",
            "options": ["Python", "C#", "Java", "Ruby"],
            "correct_answer": 0,
            "points": 4,
            "difficulty": "medium"
        },
        {
            "question": "What are web sockets?",
            "options": ["Protocol for two-way communication", "Programming language", "Database", "Framework"],
            "correct_answer": 0,
            "points": 6,
            "difficulty": "hard"
        },
        {
            "question": "Which language has a coffee cup as its mascot?",
            "options": ["Java", "Python", "JavaScript", "C++"],
            "correct_answer": 0,
            "points": 3,
            "difficulty": "easy"
        },
        {
            "question": "What is ORM?",
            "options": ["Object-Relational Mapping", "Object-Random Memory", "Online Resource Management", "Object-Runtime Module"],
            "correct_answer": 0,
            "points": 6,
            "difficulty": "hard"
        },
        {
            "question": "Which language is considered functional?",
            "options": ["Haskell", "Java", "C++", "Python"],
            "correct_answer": 0,
            "points": 6,
            "difficulty": "hard"
        },
        {
            "question": "What is CI/CD?",
            "options": ["Continuous Integration/Continuous Deployment", "Computer Interface/Computer Design", "Code Integration/Code Development", "Continuous Input/Continuous Data"],
            "correct_answer": 0,
            "points": 6,
            "difficulty": "hard"
        },
        {
            "question": "Who created Python?",
            "options": ["Guido van Rossum", "James Gosling", "Bjarne Stroustrup", "Dennis Ritchie"],
            "correct_answer": 0,
            "points": 4,
            "difficulty": "medium"
        },
        {
            "question": "What is polymorphism in OOP?",
            "options": ["Ability of objects to take different forms", "Class inheritance", "Data encapsulation", "Abstraction"],
            "correct_answer": 0,
            "points": 6,
            "difficulty": "hard"
        }
    ],
    "art": [
        {
            "question": "Who painted 'Black Square'?",
            "options": ["Wassily Kandinsky", "Kazimir Malevich", "Pablo Picasso", "Marc Chagall"],
            "correct_answer": 1,
            "points": 4,
            "difficulty": "easy"
        },
        {
            "question": "Which composer wrote the 'Moonlight Sonata'?",
            "options": ["Wolfgang Amadeus Mozart", "Ludwig van Beethoven", "Johann Sebastian Bach", "Frédéric Chopin"],
            "correct_answer": 1,
            "points": 4,
            "difficulty": "easy"
        },
        {
            "question": "In which century did Leonardo da Vinci live?",
            "options": ["14th century", "15th century", "16th century", "17th century"],
            "correct_answer": 1,
            "points": 5,
            "difficulty": "medium"
        },
        {
            "question": "Who wrote the novel 'War and Peace'?",
            "options": ["Fyodor Dostoevsky", "Leo Tolstoy", "Anton Chekhov", "Ivan Turgenev"],
            "correct_answer": 1,
            "points": 4,
            "difficulty": "easy"
        },
        {
            "question": "Which artistic style is characterized by curved lines and ornamentation?",
            "options": ["Baroque", "Rococo", "Art Nouveau", "Classicism"],
            "correct_answer": 2,
            "points": 6,
            "difficulty": "hard"
        },
        {
            "question": "Who sculpted 'David'?",
            "options": ["Donatello", "Michelangelo", "Bernini", "Rodin"],
            "correct_answer": 1,
            "points": 5,
            "difficulty": "medium"
        },
        {
            "question": "In which country did the Baroque style originate in architecture?",
            "options": ["France", "Italy", "Spain", "Germany"],
            "correct_answer": 1,
            "points": 6,
            "difficulty": "hard"
        },
        {
            "question": "Who wrote the play 'Romeo and Juliet'?",
            "options": ["William Shakespeare", "Arthur Miller", "Bernard Shaw", "Oscar Wilde"],
            "correct_answer": 0,
            "points": 3,
            "difficulty": "easy"
        },
        {
            "question": "Which Russian artist is known for his 'marine' paintings?",
            "options": ["Ivan Aivazovsky", "Ilya Repin", "Vasily Surikov", "Viktor Vasnetsov"],
            "correct_answer": 0,
            "points": 5,
            "difficulty": "medium"
        },
        {
            "question": "Who composed the ballet 'Swan Lake'?",
            "options": ["Pyotr Tchaikovsky", "Igor Stravinsky", "Sergei Prokofiev", "Modest Mussorgsky"],
            "correct_answer": 0,
            "points": 4,
            "difficulty": "easy"
        },
        {
            "question": "Which painting is by Salvador Dalí?",
            "options": ["The Scream", "The Persistence of Memory", "Starry Night", "Girl with a Pearl Earring"],
            "correct_answer": 1,
            "points": 5,
            "difficulty": "medium"
        },
        {
            "question": "Who wrote 'The Hunchback of Notre-Dame'?",
            "options": ["Victor Hugo", "Alexandre Dumas", "Honoré de Balzac", "Gustave Flaubert"],
            "correct_answer": 0,
            "points": 5,
            "difficulty": "medium"
        },
        {
            "question": "Which architect designed St. Peter's Basilica in Rome?",
            "options": ["Donato Bramante", "Michelangelo", "Bernini", "All of the above"],
            "correct_answer": 3,
            "points": 7,
            "difficulty": "hard"
        },
        {
            "question": "Who created the sculpture 'The Thinker'?",
            "options": ["Auguste Rodin", "Michelangelo", "Donatello", "Antonio Canova"],
            "correct_answer": 0,
            "points": 5,
            "difficulty": "medium"
        },
        {
            "question": "In which city is the Prado Museum located?",
            "options": ["Madrid", "Barcelona", "Paris", "Rome"],
            "correct_answer": 0,
            "points": 4,
            "difficulty": "easy"
        },
        {
            "question": "Who wrote the opera 'Carmen'?",
            "options": ["Georges Bizet", "Giuseppe Verdi", "Wolfgang Mozart", "Richard Wagner"],
            "correct_answer": 0,
            "points": 5,
            "difficulty": "medium"
        },
        {
            "question": "Which artist founded the Cubist movement?",
            "options": ["Pablo Picasso", "Henri Matisse", "Wassily Kandinsky", "Salvador Dalí"],
            "correct_answer": 0,
            "points": 6,
            "difficulty": "hard"
        },
        {
            "question": "Who painted the fresco 'The Last Supper'?",
            "options": ["Leonardo da Vinci", "Michelangelo", "Raphael", "Sandro Botticelli"],
            "correct_answer": 0,
            "points": 5,
            "difficulty": "medium"
        },
        {
            "question": "In which style did Vincent van Gogh paint?",
            "options": ["Impressionism", "Post-Impressionism", "Expressionism", "Surrealism"],
            "correct_answer": 1,
            "points": 6,
            "difficulty": "hard"
        },
        {
            "question": "Who wrote 'Anna Karenina'?",
            "options": ["Leo Tolstoy", "Fyodor Dostoevsky", "Anton Chekhov", "Ivan Turgenev"],
            "correct_answer": 0,
            "points": 4,
            "difficulty": "easy"
        },
        {
            "question": "Which composer wrote 'The Four Seasons'?",
            "options": ["Antonio Vivaldi", "Johann Sebastian Bach", "Wolfgang Mozart", "Ludwig van Beethoven"],
            "correct_answer": 0,
            "points": 5,
            "difficulty": "medium"
        },
        {
            "question": "Who directed the film 'The Godfather'?",
            "options": ["Francis Ford Coppola", "Martin Scorsese", "Steven Spielberg", "Alfred Hitchcock"],
            "correct_answer": 0,
            "points": 5,
            "difficulty": "medium"
        },
        {
            "question": "In which genre did Fyodor Dostoevsky write?",
            "options": ["Realism", "Romanticism", "Sentimentalism", "Classicism"],
            "correct_answer": 0,
            "points": 6,
            "difficulty": "hard"
        },
        {
            "question": "Who painted 'Morning in a Pine Forest'?",
            "options": ["Ivan Shishkin", "Ilya Repin", "Vasily Perov", "Viktor Vasnetsov"],
            "correct_answer": 0,
            "points": 5,
            "difficulty": "medium"
        },
        {
            "question": "Which Russian composer wrote 'The Nutcracker'?",
            "options": ["Pyotr Tchaikovsky", "Nikolai Rimsky-Korsakov", "Modest Mussorgsky", "Sergei Prokofiev"],
            "correct_answer": 0,
            "points": 4,
            "difficulty": "easy"
        },
        {
            "question": "Who wrote the novel '1984'?",
            "options": ["George Orwell", "Aldous Huxley", "Ray Bradbury", "Arthur C. Clarke"],
            "correct_answer": 0,
            "points": 5,
            "difficulty": "medium"
        },
        {
            "question": "In which style is the Winter Palace in St. Petersburg built?",
            "options": ["Baroque", "Classicism", "Rococo", "Empire"],
            "correct_answer": 0,
            "points": 6,
            "difficulty": "hard"
        },
        {
            "question": "Who painted 'Guernica'?",
            "options": ["Pablo Picasso", "Salvador Dalí", "Joan Miró", "Frida Kahlo"],
            "correct_answer": 0,
            "points": 5,
            "difficulty": "medium"
        },
        {
            "question": "Which artist is a representative of Pop Art?",
            "options": ["Andy Warhol", "Roy Lichtenstein", "Keith Haring", "All of the above"],
            "correct_answer": 3,
            "points": 6,
            "difficulty": "hard"
        },
        {
            "question": "Who created the sculpture 'Discobolus'?",
            "options": ["Myron", "Polykleitos", "Phidias", "Praxiteles"],
            "correct_answer": 0,
            "points": 7,
            "difficulty": "hard"
        },
        {
            "question": "In which city is the Sistine Chapel located?",
            "options": ["Rome", "Florence", "Venice", "Milan"],
            "correct_answer": 0,
            "points": 5,
            "difficulty": "medium"
        },
        {
            "question": "Who wrote 'The Divine Comedy'?",
            "options": ["Dante Alighieri", "Giovanni Boccaccio", "Francesco Petrarca", "Niccolò Machiavelli"],
            "correct_answer": 0,
            "points": 5,
            "difficulty": "medium"
        },
        {
            "question": "Which Russian artist is known for fairy-tale themed paintings?",
            "options": ["Viktor Vasnetsov", "Mikhail Vrubel", "Ivan Bilibin", "All of the above"],
            "correct_answer": 3,
            "points": 6,
            "difficulty": "hard"
        },
        {
            "question": "Who composed the opera 'Eugene Onegin'?",
            "options": ["Pyotr Tchaikovsky", "Mikhail Glinka", "Nikolai Rimsky-Korsakov", "Modest Mussorgsky"],
            "correct_answer": 0,
            "points": 5,
            "difficulty": "medium"
        },
        {
            "question": "In which style is St. Basil's Cathedral built?",
            "options": ["Tent-style", "Baroque", "Classicism", "Gothic"],
            "correct_answer": 0,
            "points": 6,
            "difficulty": "hard"
        },
        {
            "question": "Who wrote 'The Three Musketeers'?",
            "options": ["Alexandre Dumas", "Victor Hugo", "Honoré de Balzac", "Gustave Flaubert"],
            "correct_answer": 0,
            "points": 4,
            "difficulty": "easy"
        },
        {
            "question": "Which artist is considered the founder of Impressionism?",
            "options": ["Claude Monet", "Édouard Manet", "Pierre-Auguste Renoir", "Edgar Degas"],
            "correct_answer": 0,
            "points": 6,
            "difficulty": "hard"
        },
        {
            "question": "Who wrote the novel 'Crime and Punishment'?",
            "options": ["Fyodor Dostoevsky", "Leo Tolstoy", "Anton Chekhov", "Ivan Turgenev"],
            "correct_answer": 0,
            "points": 5,
            "difficulty": "medium"
        },
        {
            "question": "In which genre did Johann Strauss compose?",
            "options": ["Waltz", "Symphony", "Opera", "Ballet"],
            "correct_answer": 0,
            "points": 5,
            "difficulty": "medium"
        },
        {
            "question": "Who painted 'Girl with Peaches'?",
            "options": ["Valentin Serov", "Ilya Repin", "Vasily Surikov", "Mikhail Vrubel"],
            "correct_answer": 0,
            "points": 5,
            "difficulty": "medium"
        },
        {
            "question": "Which Russian composer wrote 'Polovtsian Dances'?",
            "options": ["Alexander Borodin", "Nikolai Rimsky-Korsakov", "Modest Mussorgsky", "Pyotr Tchaikovsky"],
            "correct_answer": 0,
            "points": 6,
            "difficulty": "hard"
        },
        {
            "question": "Who is the architect of St. Isaac's Cathedral?",
            "options": ["Auguste de Montferrand", "Domenico Trezzini", "Carlo Rossi", "Bartolomeo Rastrelli"],
            "correct_answer": 0,
            "points": 6,
            "difficulty": "hard"
        },
        {
            "question": "In which style is the painting 'The Scream'?",
            "options": ["Expressionism", "Impressionism", "Surrealism", "Cubism"],
            "correct_answer": 0,
            "points": 6,
            "difficulty": "hard"
        },
        {
            "question": "Who wrote the story 'The Overcoat'?",
            "options": ["Nikolai Gogol", "Alexander Pushkin", "Mikhail Lermontov", "Ivan Turgenev"],
            "correct_answer": 0,
            "points": 5,
            "difficulty": "medium"
        },
        {
            "question": "Which artist painted 'The Last Day of Pompeii'?",
            "options": ["Karl Bryullov", "Alexander Ivanov", "Pavel Fedotov", "Orest Kiprensky"],
            "correct_answer": 0,
            "points": 6,
            "difficulty": "hard"
        },
        {
            "question": "Who composed 'The Rite of Spring'?",
            "options": ["Igor Stravinsky", "Sergei Prokofiev", "Dmitri Shostakovich", "Aram Khachaturian"],
            "correct_answer": 0,
            "points": 6,
            "difficulty": "hard"
        },
        {
            "question": "In which city is the Uffizi Gallery located?",
            "options": ["Florence", "Rome", "Venice", "Milan"],
            "correct_answer": 0,
            "points": 5,
            "difficulty": "medium"
        },
        {
            "question": "Who wrote 'Woe from Wit'?",
            "options": ["Alexander Griboyedov", "Alexander Pushkin", "Nikolai Gogol", "Mikhail Lermontov"],
            "correct_answer": 0,
            "points": 5,
            "difficulty": "medium"
        },
        {
            "question": "Which Russian artist is known as the 'master of seascape'?",
            "options": ["Ivan Aivazovsky", "Arkhip Kuindzhi", "Isaac Levitan", "Alexei Savrasov"],
            "correct_answer": 0,
            "points": 4,
            "difficulty": "easy"
        },
        {
            "question": "Who composed the opera 'Prince Igor'?",
            "options": ["Alexander Borodin", "Nikolai Rimsky-Korsakov", "Modest Mussorgsky", "Pyotr Tchaikovsky"],
            "correct_answer": 0,
            "points": 6,
            "difficulty": "hard"
        },
        {
            "question": "In which style is the Cathedral of Christ the Saviour built?",
            "options": ["Russian-Byzantine", "Baroque", "Classicism", "Gothic"],
            "correct_answer": 0,
            "points": 6,
            "difficulty": "hard"
        },
        {
            "question": "Who painted the Mona Lisa?",
            "options": ["Leonardo da Vinci", "Michelangelo", "Raphael", "Titian"],
            "correct_answer": 0,
            "points": 3,
            "difficulty": "easy"
        }
    ],
    "sports": [
        {
            "question": "Which country has won the most gold medals in Summer Olympic history?",
            "options": ["China", "Russia", "USA", "Great Britain"],
            "correct_answer": 2,
            "points": 6,
            "difficulty": "hard"
        },
        {
            "question": "In which sport did Michael Jordan become famous?",
            "options": ["Baseball", "Basketball", "American Football", "Golf"],
            "correct_answer": 1,
            "points": 3,
            "difficulty": "easy"
        },
        {
            "question": "How many players are on a rugby team on the field?",
            "options": ["11", "15", "13", "9"],
            "correct_answer": 1,
            "points": 7,
            "difficulty": "hard"
        },
        {
            "question": "Who holds the record for most goals in football history?",
            "options": ["Pelé", "Cristiano Ronaldo", "Lionel Messi", "Gerd Müller"],
            "correct_answer": 1,
            "points": 5,
            "difficulty": "medium"
        },
        {
            "question": "In which year were the Olympic Games held in Moscow?",
            "options": ["1976", "1980", "1984", "1972"],
            "correct_answer": 1,
            "points": 5,
            "difficulty": "medium"
        },
        {
            "question": "Which tennis player has won the most Grand Slam titles?",
            "options": ["Novak Djokovic", "Rafael Nadal", "Roger Federer", "Pete Sampras"],
            "correct_answer": 0,
            "points": 6,
            "difficulty": "hard"
        },
        {
            "question": "How many periods are in an ice hockey match?",
            "options": ["2", "3", "4", "5"],
            "correct_answer": 1,
            "points": 4,
            "difficulty": "easy"
        },
        {
            "question": "Which country is the birthplace of judo?",
            "options": ["China", "Korea", "Japan", "Vietnam"],
            "correct_answer": 2,
            "points": 5,
            "difficulty": "medium"
        },
        {
            "question": "Who was the youngest Formula 1 champion?",
            "options": ["Lewis Hamilton", "Sebastian Vettel", "Max Verstappen", "Fernando Alonso"],
            "correct_answer": 2,
            "points": 7,
            "difficulty": "hard"
        },
        {
            "question": "In which sport is the Stanley Cup awarded?",
            "options": ["Basketball", "Ice Hockey", "Rugby", "American Football"],
            "correct_answer": 1,
            "points": 4,
            "difficulty": "easy"
        },
        {
            "question": "How many players are on a basketball team on the court?",
            "options": ["5", "6", "7", "8"],
            "correct_answer": 0,
            "points": 3,
            "difficulty": "easy"
        },
        {
            "question": "Which country won the first FIFA World Cup?",
            "options": ["Uruguay", "Brazil", "Argentina", "Italy"],
            "correct_answer": 0,
            "points": 6,
            "difficulty": "hard"
        },
        {
            "question": "In which year were the first modern Olympic Games held?",
            "options": ["1896", "1900", "1888", "1912"],
            "correct_answer": 0,
            "points": 5,
            "difficulty": "medium"
        },
        {
            "question": "Who holds the record for most Wimbledon titles in tennis?",
            "options": ["Roger Federer", "Novak Djokovic", "Pete Sampras", "Rafael Nadal"],
            "correct_answer": 0,
            "points": 6,
            "difficulty": "hard"
        },
        {
            "question": "How many kilometers is a marathon distance?",
            "options": ["42.195 km", "40.2 km", "45 km", "38.5 km"],
            "correct_answer": 0,
            "points": 5,
            "difficulty": "medium"
        },
        {
            "question": "Which country is the birthplace of football (soccer)?",
            "options": ["England", "Brazil", "Italy", "Germany"],
            "correct_answer": 0,
            "points": 4,
            "difficulty": "easy"
        },
        {
            "question": "Who has won the most World Chess Championships?",
            "options": ["Garry Kasparov", "Magnus Carlsen", "Emanuel Lasker", "All of the above"],
            "correct_answer": 0,
            "points": 7,
            "difficulty": "hard"
        },
        {
            "question": "How many points is a three-point shot worth in basketball?",
            "options": ["3", "2", "1", "4"],
            "correct_answer": 0,
            "points": 3,
            "difficulty": "easy"
        },
        {
            "question": "Which country hosted the 2014 Olympic Games?",
            "options": ["Russia", "Brazil", "China", "Great Britain"],
            "correct_answer": 0,
            "points": 4,
            "difficulty": "easy"
        },
        {
            "question": "Who is the most decorated Olympian of all time?",
            "options": ["Michael Phelps", "Larisa Latynina", "Paavo Nurmi", "Mark Spitz"],
            "correct_answer": 0,
            "points": 5,
            "difficulty": "medium"
        },
        {
            "question": "How many players are on a volleyball team on the court?",
            "options": ["6", "5", "7", "8"],
            "correct_answer": 0,
            "points": 4,
            "difficulty": "easy"
        },
        {
            "question": "Which country has won the most FIFA World Cups?",
            "options": ["Brazil", "Germany", "Italy", "Argentina"],
            "correct_answer": 0,
            "points": 5,
            "difficulty": "medium"
        },
        {
            "question": "In which sport is the term 'hat-trick' used?",
            "options": ["Hockey", "Football", "Basketball", "All of the above"],
            "correct_answer": 3,
            "points": 5,
            "difficulty": "medium"
        },
        {
            "question": "Who is the youngest World Cup winner in football?",
            "options": ["Pelé", "Kylian Mbappé", "Diego Maradona", "Zinedine Zidane"],
            "correct_answer": 0,
            "points": 6,
            "difficulty": "hard"
        },
        {
            "question": "How many sets are in a men's Grand Slam tennis match?",
            "options": ["3 or 5", "2 or 3", "only 3", "only 5"],
            "correct_answer": 0,
            "points": 5,
            "difficulty": "medium"
        },
        {
            "question": "Which country is the birthplace of curling?",
            "options": ["Scotland", "Canada", "Sweden", "Norway"],
            "correct_answer": 0,
            "points": 6,
            "difficulty": "hard"
        },
        {
            "question": "Who has won the most UEFA Super Cups?",
            "options": ["Real Madrid", "Barcelona", "AC Milan", "Liverpool"],
            "correct_answer": 0,
            "points": 7,
            "difficulty": "hard"
        },
        {
            "question": "How many laps are in the Monaco Grand Prix?",
            "options": ["78", "70", "65", "80"],
            "correct_answer": 0,
            "points": 7,
            "difficulty": "hard"
        },
        {
            "question": "Which country is the birthplace of badminton?",
            "options": ["England", "India", "China", "Japan"],
            "correct_answer": 0,
            "points": 6,
            "difficulty": "hard"
        },
        {
            "question": "Who holds the record for most goals in a single NHL season?",
            "options": ["Wayne Gretzky", "Alexander Ovechkin", "Mario Lemieux", "Gordie Howe"],
            "correct_answer": 0,
            "points": 7,
            "difficulty": "hard"
        },
        {
            "question": "How many minutes is a half in football?",
            "options": ["45", "40", "50", "35"],
            "correct_answer": 0,
            "points": 3,
            "difficulty": "easy"
        },
        {
            "question": "Which country won the first AFC Asian Cup?",
            "options": ["South Korea", "Japan", "Iran", "Saudi Arabia"],
            "correct_answer": 0,
            "points": 7,
            "difficulty": "hard"
        },
        {
            "question": "Who is the most decorated NBA player?",
            "options": ["Bill Russell", "Michael Jordan", "Kareem Abdul-Jabbar", "LeBron James"],
            "correct_answer": 0,
            "points": 6,
            "difficulty": "hard"
        },
        {
            "question": "How much does a men's shot put weigh?",
            "options": ["7.26 kg", "6 kg", "8 kg", "5 kg"],
            "correct_answer": 0,
            "points": 6,
            "difficulty": "hard"
        },
        {
            "question": "Which country is the birthplace of table tennis?",
            "options": ["England", "China", "Japan", "USA"],
            "correct_answer": 0,
            "points": 6,
            "difficulty": "hard"
        },
        {
            "question": "Who has won the most Ballon d'Or awards?",
            "options": ["Lionel Messi", "Cristiano Ronaldo", "Johan Cruyff", "Michel Platini"],
            "correct_answer": 0,
            "points": 5,
            "difficulty": "medium"
        },
        {
            "question": "How many players are on a baseball team on the field?",
            "options": ["9", "10", "8", "11"],
            "correct_answer": 0,
            "points": 5,
            "difficulty": "medium"
        },
        {
            "question": "Which country is the birthplace of rowing?",
            "options": ["England", "USA", "Germany", "France"],
            "correct_answer": 0,
            "points": 6,
            "difficulty": "hard"
        },
        {
            "question": "Who holds the record for most Tour de France wins?",
            "options": ["Lance Armstrong", "Eddy Merckx", "Miguel Indurain", "Bernard Hinault"],
            "correct_answer": 1,
            "points": 7,
            "difficulty": "hard"
        },
        {
            "question": "How many points is a touchdown worth in American football?",
            "options": ["6", "7", "5", "3"],
            "correct_answer": 0,
            "points": 6,
            "difficulty": "hard"
        },
        {
            "question": "Which country is the birthplace of biathlon?",
            "options": ["Norway", "Sweden", "Finland", "Russia"],
            "correct_answer": 0,
            "points": 6,
            "difficulty": "hard"
        },
        {
            "question": "Who has won the most World Rally Championships?",
            "options": ["Sébastien Loeb", "Mika Häkkinen", "Juha Kankkunen", "Tommi Mäkinen"],
            "correct_answer": 0,
            "points": 7,
            "difficulty": "hard"
        },
        {
            "question": "How many players are on a water polo team?",
            "options": ["7", "6", "8", "5"],
            "correct_answer": 0,
            "points": 5,
            "difficulty": "medium"
        },
        {
            "question": "Which country is the birthplace of synchronized swimming?",
            "options": ["Canada", "USA", "Russia", "Australia"],
            "correct_answer": 0,
            "points": 6,
            "difficulty": "hard"
        },
        {
            "question": "Who holds the record for most Formula 1 Grand Prix wins?",
            "options": ["Lewis Hamilton", "Michael Schumacher", "Sebastian Vettel", "Ayrton Senna"],
            "correct_answer": 0,
            "points": 5,
            "difficulty": "medium"
        },
        {
            "question": "How much does a men's hammer throw weigh?",
            "options": ["7.26 kg", "6 kg", "8 kg", "5 kg"],
            "correct_answer": 0,
            "points": 6,
            "difficulty": "hard"
        },
        {
            "question": "Which country is the birthplace of artistic gymnastics?",
            "options": ["Germany", "France", "Sweden", "Greece"],
            "correct_answer": 0,
            "points": 6,
            "difficulty": "hard"
        },
        {
            "question": "Who has won the most MotoGP World Championships?",
            "options": ["Giacomo Agostini", "Valentino Rossi", "Marc Márquez", "Mick Doohan"],
            "correct_answer": 0,
            "points": 7,
            "difficulty": "hard"
        },
        {
            "question": "How many players are on a rugby sevens team?",
            "options": ["7", "6", "8", "9"],
            "correct_answer": 0,
            "points": 5,
            "difficulty": "medium"
        },
        {
            "question": "Which country is the birthplace of skateboarding?",
            "options": ["USA", "Australia", "Brazil", "Canada"],
            "correct_answer": 0,
            "points": 5,
            "difficulty": "medium"
        },
        {
            "question": "Who holds the record for most Wimbledon titles in women's tennis?",
            "options": ["Martina Navratilova", "Serena Williams", "Steffi Graf", "Margaret Court"],
            "correct_answer": 0,
            "points": 6,
            "difficulty": "hard"
        },
        {
            "question": "Which sport uses the term 'birdie'?",
            "options": ["Golf", "Tennis", "Badminton", "Cricket"],
            "correct_answer": 0,
            "points": 4,
            "difficulty": "easy"
        }
    ]
}

def populate_databases():
    cursor = db_connection.cursor()

    cursor.execute("SELECT COUNT(*) FROM questions")
    if cursor.fetchone()[0] == 0:
        for topic, questions in questions_database.items():
            for q in questions:
                cursor.execute('''
                    INSERT INTO questions (topic, question, options, correct_answer, points, difficulty)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (topic, q['question'], json.dumps(q['options']), q['correct_answer'], q['points'], q['difficulty']))

    db_connection.commit()
    logger.info("Question database populated")

populate_databases()

active_quizzes = {}
user_profiles = {}
user_chat_sessions = {}
pending_ai_responses = {}  

class UserQuiz:
    def __init__(self, user_id, chat_id, chat_type):
        self.user_id = user_id
        self.chat_id = chat_id
        self.chat_type = chat_type
        self.score = 0
        self.current_question = None
        self.questions_answered = 0
        self.correct_answers = 0
        self.quiz_started = False
        self.current_topic = None
        self.waiting_for_topic = False

class UserProfile:
    def __init__(self, user_id):
        self.user_id = user_id
        self.name = None
        self.age = None
        self.city = None
        self.waiting_for = None

def get_user_profile(user_id):
    if user_id not in user_profiles:
        user_profiles[user_id] = UserProfile(user_id)
        load_user_profile_from_db(user_id)
    return user_profiles[user_id]

def save_user_profile_to_db(user_id, user_profile):
    cursor = db_connection.cursor()
    try:
        cursor.execute('''
            INSERT OR REPLACE INTO user_profiles (user_id, name, age, city)
            VALUES (?, ?, ?, ?)
        ''', (user_id, user_profile.name, user_profile.age, user_profile.city))
        db_connection.commit()
        logger.info(f"User profile {user_id} saved")
    except Exception as e:
        logger.error(f"Error saving profile: {e}")

def load_user_profile_from_db(user_id):
    cursor = db_connection.cursor()
    try:
        cursor.execute('''
            SELECT name, age, city FROM user_profiles WHERE user_id = ?
        ''', (user_id,))
        result = cursor.fetchone()
        if result:
            user_profile = get_user_profile(user_id)
            user_profile.name = result[0]
            user_profile.age = result[1]
            user_profile.city = result[2]
            return user_profile
    except Exception as e:
        logger.error(f"Error loading profile: {e}")
    return None

def get_or_create_user(user_id, username, first_name, last_name, private_chat_id=None):
    cursor = db_connection.cursor()
    cursor.execute('''
        INSERT OR REPLACE INTO users (user_id, username, first_name, last_name, private_chat_id)
        VALUES (?, ?, ?, ?, ?)
    ''', (user_id, username, first_name, last_name, private_chat_id))
    db_connection.commit()

def get_user_quiz(user_id, chat_id, chat_type):
    quiz_key = f"{chat_id}_{user_id}"
    if quiz_key not in active_quizzes:
        active_quizzes[quiz_key] = UserQuiz(user_id, chat_id, chat_type)
    return active_quizzes[quiz_key]

def get_chat_session(user_id):
    if user_id not in user_chat_sessions:
        cursor = db_connection.cursor()
        cursor.execute('''
            SELECT messages FROM chat_sessions WHERE user_id = ? ORDER BY updated_at DESC LIMIT 1
        ''', (user_id,))
        result = cursor.fetchone()

        if result:
            messages = json.loads(result[0])
        else:
            messages = []

        user_chat_sessions[user_id] = messages

    return user_chat_sessions[user_id]

def save_chat_session(user_id, messages):
    cursor = db_connection.cursor()
    try:
        cursor.execute('''
            INSERT OR REPLACE INTO chat_sessions (user_id, messages, updated_at)
            VALUES (?, ?, CURRENT_TIMESTAMP)
        ''', (user_id, json.dumps(messages)))
        db_connection.commit()
        user_chat_sessions[user_id] = messages
    except Exception as e:
        logger.error(f"Error saving chat session: {e}")

def clear_chat_session(user_id):
    cursor = db_connection.cursor()
    try:
        cursor.execute('DELETE FROM chat_sessions WHERE user_id = ?', (user_id,))
        db_connection.commit()
        if user_id in user_chat_sessions:
            del user_chat_sessions[user_id]
    except Exception as e:
        logger.error(f"Error clearing chat session: {e}")

def get_saved_ai_response(user_id, question):
    cursor = db_connection.cursor()
    cursor.execute('''
        SELECT response FROM ai_responses 
        WHERE user_id = ? AND question = ? AND liked = 1
        ORDER BY used_count DESC, created_at DESC
        LIMIT 1
    ''', (user_id, question))
    result = cursor.fetchone()
    return result[0] if result else None

def save_ai_response(user_id, question, response, liked=True):
    cursor = db_connection.cursor()
    try:
        cursor.execute('''
            INSERT INTO ai_responses (user_id, question, response, liked, used_count)
            VALUES (?, ?, ?, ?, ?)
        ''', (user_id, question, response, liked, 1 if liked else 0))
        db_connection.commit()
        logger.info(f"AI response saved for user {user_id}")
    except Exception as e:
        logger.error(f"Error saving AI response: {e}")

def increment_ai_response_usage(response_id):
    cursor = db_connection.cursor()
    try:
        cursor.execute('''
            UPDATE ai_responses SET used_count = used_count + 1 WHERE id = ?
        ''', (response_id,))
        db_connection.commit()
    except Exception as e:
        logger.error(f"Error updating usage counter: {e}")

def query_gemini(user_id, question):
    try:
        saved_response = get_saved_ai_response(user_id, question)
        if saved_response:
            logger.info(f"Used saved response for user {user_id}")
            return f"💾 *Response from saved:*\n\n{saved_response}"

        if model is None:
            return "❌ AI service temporarily unavailable.\n\nPlease check your Gemini API key settings."

        messages = get_chat_session(user_id)

        chat_history = []
        for msg in messages[-10:]:
            if msg['role'] == 'user':
                chat_history.append({"role": "user", "parts": [msg['content']]})
            else:
                chat_history.append({"role": "model", "parts": [msg['content']]})

        chat_history.append({"role": "user", "parts": [question]})

        def generate_response():
            response = model.generate_content(chat_history)
            return response.text.strip()

        with ThreadPoolExecutor() as executor:
            future = executor.submit(generate_response)
            reply = future.result(timeout=30)  # 30 second timeout

        if reply:
            messages.append({"role": "user", "content": question})
            messages.append({"role": "assistant", "content": reply})

            if len(messages) > 20:
                messages = messages[-20:]

            save_chat_session(user_id, messages)
            return reply
        else:
            return "❌ Could not get a response from AI. Response was empty or invalid."

    except Exception as e:
        logger.error(f"Gemini API error: {str(e)}")

        error_msg = str(e).lower()

        if "quota" in error_msg or "billing" in error_msg:
            return "❌ API quota exceeded or billing issue. Check your Google AI Studio settings."
        elif "safety" in error_msg or "blocked" in error_msg:
            return "❌ Request was blocked by safety systems. Try rephrasing your question."
        elif "api key" in error_msg:
            return "❌ Problem with API key. Check your Gemini key."
        elif "network" in error_msg or "connection" in error_msg:
            return "❌ Network issue. Check your internet connection."
        elif "timeout" in error_msg:
            return "❌ Response timeout. Please try again."
        else:
            return f"❌ Error contacting AI: {str(e)}\n\nTry rephrasing your question or try again later."

def get_user_stats(user_id, chat_id, chat_type):
    cursor = db_connection.cursor()
    cursor.execute('''
        SELECT total_points, total_questions, correct_answers, games_played, last_played
        FROM user_stats
        WHERE user_id = ? AND chat_id = ? AND chat_type = ?
    ''', (user_id, chat_id, chat_type))
    result = cursor.fetchone()

    if result:
        return {
            'total_points': result[0],
            'total_questions': result[1],
            'correct_answers': result[2],
            'games_played': result[3],
            'last_played': result[4]
        }
    else:
        cursor.execute('''
            INSERT INTO user_stats (user_id, chat_id, chat_type)
            VALUES (?, ?, ?)
        ''', (user_id, chat_id, chat_type))
        db_connection.commit()
        return {
            'total_points': 0,
            'total_questions': 0,
            'correct_answers': 0,
            'games_played': 0,
            'last_played': None
        }

def update_user_stats(user_id, chat_id, chat_type, points=0, questions=0, correct=0, game_played=False):
    cursor = db_connection.cursor()
    stats = get_user_stats(user_id, chat_id, chat_type)

    new_points = stats['total_points'] + points
    new_questions = stats['total_questions'] + questions
    new_correct = stats['correct_answers'] + correct
    new_games = stats['games_played'] + (1 if game_played else 0)

    cursor.execute('''
        UPDATE user_stats
        SET total_points = ?, total_questions = ?, correct_answers = ?, games_played = ?, last_played = CURRENT_TIMESTAMP
        WHERE user_id = ? AND chat_id = ? AND chat_type = ?
    ''', (new_points, new_questions, new_correct, new_games, user_id, chat_id, chat_type))
    db_connection.commit()

def get_random_question(topic=None):
    cursor = db_connection.cursor()

    if topic:
        cursor.execute('''
            SELECT id, topic, question, options, correct_answer, points
            FROM questions
            WHERE topic = ?
            ORDER BY RANDOM()
            LIMIT 1
        ''', (topic,))
    else:
        cursor.execute('''
            SELECT id, topic, question, options, correct_answer, points
            FROM questions
            ORDER BY RANDOM()
            LIMIT 1
        ''')

    result = cursor.fetchone()
    if result:
        return {
            'id': result[0],
            'topic': result[1],
            'question': result[2],
            'options': json.loads(result[3]),
            'correct_answer': result[4],
            'points': result[5]
        }
    return None

def create_keyboard(options=None, main_menu=False):
    markup = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)

    if main_menu:
        buttons = ["🎯 Start Quiz", "🤖 Ask AI", "📊 My Stats",
                  "🏆 Leaderboard", "👤 My Profile", "📈 Compare", "🧹 Clear History", "❓ Help"]
        markup.add(*buttons)
    elif options:
        buttons = [f"{chr(65+i)}) {option}" for i, option in enumerate(options)]
        for i in range(0, len(buttons), 2):
            if i + 1 < len(buttons):
                markup.add(buttons[i], buttons[i + 1])
            else:
                markup.add(buttons[i])
        markup.add("⏹️ Stop")

    return markup

def create_topic_keyboard():
    cursor = db_connection.cursor()
    cursor.execute("SELECT DISTINCT topic FROM questions")
    topics = [row[0] for row in cursor.fetchall()]

    markup = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(*topics)
    markup.add("🎲 Random Topic", "🔙 Back")
    return markup

def format_question(question_data, question_number):
    question = f"❓ Question {question_number}:\n{question_data['question']}\n\n"
    options = question_data['options']
    for i, option in enumerate(options):
        question += f"{chr(65+i)}) {option}\n"
    question += f"\n🏅 Points for correct answer: {question_data['points']}"
    return question

def create_feedback_keyboard():
    markup = telebot.types.InlineKeyboardMarkup()
    markup.row(
        telebot.types.InlineKeyboardButton("👍 Liked", callback_data="feedback_like"),
        telebot.types.InlineKeyboardButton("👎 Disliked", callback_data="feedback_dislike")
    )
    return markup

def create_compare_keyboard():
    markup = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    buttons = ["📊 Compare with top players", "👥 Compare with average", "📈 Compare by accuracy", "🔙 Back"]
    markup.add(*buttons)
    return markup

def compare_stats_command(message, chat_type):
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    user_stats = get_user_stats(user_id, chat_id, chat_type)
    
    cursor = db_connection.cursor()
    
    if chat_type == 'private':
        cursor.execute('''
            SELECT 
                COUNT(*) as total_players,
                AVG(total_points) as avg_points,
                AVG(total_questions) as avg_questions,
                AVG(correct_answers) as avg_correct,
                AVG(CASE WHEN total_questions > 0 THEN correct_answers * 100.0 / total_questions ELSE 0 END) as avg_accuracy,
                MAX(total_points) as max_points,
                MAX(CASE WHEN total_questions > 0 THEN correct_answers * 100.0 / total_questions ELSE 0 END) as max_accuracy
            FROM user_stats 
            WHERE chat_type = 'private' AND total_questions > 0
        ''')
    else:
        cursor.execute('''
            SELECT 
                COUNT(*) as total_players,
                AVG(total_points) as avg_points,
                AVG(total_questions) as avg_questions,
                AVG(correct_answers) as avg_correct,
                AVG(CASE WHEN total_questions > 0 THEN correct_answers * 100.0 / total_questions ELSE 0 END) as avg_accuracy,
                MAX(total_points) as max_points,
                MAX(CASE WHEN total_questions > 0 THEN correct_answers * 100.0 / total_questions ELSE 0 END) as max_accuracy
            FROM user_stats 
            WHERE chat_id = ? AND chat_type = 'group' AND total_questions > 0
        ''', (chat_id,))
    
    stats_result = cursor.fetchone()
    
    if not stats_result or stats_result[0] == 0:
        bot.send_message(message.chat.id, "📊 Not enough data for comparison yet. Play a few quizzes!")
        return
    
    total_players, avg_points, avg_questions, avg_correct, avg_accuracy, max_points, max_accuracy = stats_result
    
    user_accuracy = (user_stats['correct_answers'] / user_stats['total_questions'] * 100) if user_stats['total_questions'] > 0 else 0
    
    if chat_type == 'private':
        cursor.execute('''
            SELECT u.first_name, u.username, us.total_points, 
                   CASE WHEN us.total_questions > 0 THEN us.correct_answers * 100.0 / us.total_questions ELSE 0 END as accuracy
            FROM user_stats us
            JOIN users u ON us.user_id = u.user_id
            WHERE us.chat_type = 'private' AND us.total_questions > 0
            ORDER BY us.total_points DESC
            LIMIT 3
        ''')
    else:
        cursor.execute('''
            SELECT u.first_name, u.username, us.total_points, 
                   CASE WHEN us.total_questions > 0 THEN us.correct_answers * 100.0 / us.total_questions ELSE 0 END as accuracy
            FROM user_stats us
            JOIN users u ON us.user_id = u.user_id
            WHERE us.chat_id = ? AND us.chat_type = 'group' AND us.total_questions > 0
            ORDER BY us.total_points DESC
            LIMIT 3
        ''', (chat_id,))
    
    top_players = cursor.fetchall()
    
    compare_text = f"📊 *Statistics Comparison*\n"
    compare_text += f"👤 *Your Statistics:*\n"
    compare_text += f"🏅 Points: {user_stats['total_points']}\n"
    compare_text += f"✅ Correct Answers: {user_stats['correct_answers']}/{user_stats['total_questions']}\n"
    compare_text += f"🎯 Accuracy: {user_accuracy:.1f}%\n"
    compare_text += f"🎮 Games Played: {user_stats['games_played']}\n\n"
    
    compare_text += f"📈 *Overall Statistics {'in this group' if chat_type == 'group' else 'global'}:*\n"
    compare_text += f"👥 Total Players: {total_players}\n"
    compare_text += f"📊 Average Points: {avg_points:.0f}\n"
    compare_text += f"🎯 Average Accuracy: {avg_accuracy:.1f}%\n"
    compare_text += f"⭐ Maximum Points: {max_points}\n"
    compare_text += f"💎 Maximum Accuracy: {max_accuracy:.1f}%\n\n"

    points_diff = user_stats['total_points'] - avg_points
    accuracy_diff = user_accuracy - avg_accuracy
    
    compare_text += f"🆚 *Comparison with Average:*\n"
    if points_diff > 0:
        compare_text += f"🏅 You are {points_diff:.0f} points above average! 🎉\n"
    elif points_diff < 0:
        compare_text += f"🏅 You are {abs(points_diff):.0f} points below average 💪\n"
    else:
        compare_text += f"🏅 You are at average points level\n"
    
    if accuracy_diff > 0:
        compare_text += f"🎯 Accuracy is {accuracy_diff:.1f}% above average! 🎉\n"
    elif accuracy_diff < 0:
        compare_text += f"🎯 Accuracy is {abs(accuracy_diff):.1f}% below average 💪\n"
    else:
        compare_text += f"🎯 Accuracy is at average level\n"
    
    if top_players:
        compare_text += f"\n🏆 *Top 3 Players:*\n"
        for i, (first_name, username, points, accuracy) in enumerate(top_players, 1):
            name = f"@{username}" if username else first_name
            medal = ["🥇", "🥈", "🥉"][i-1]
            
            if user_stats['total_points'] == points:
                compare_text += f"{medal} {name} - {points} points ({accuracy:.1f}%) ← THAT'S YOU! 🎉\n"
            else:
                compare_text += f"{medal} {name} - {points} points ({accuracy:.1f}%)\n"
            
            if i == 1 and user_stats['total_points'] < points:
                diff = points - user_stats['total_points']
                compare_text += f"   📍 Distance to leader: {diff} points\n"
    
    if user_stats['total_questions'] == 0:
        compare_text += f"\n💡 *Tip:* Play your first quiz with /quiz command!"
    elif user_stats['total_points'] < avg_points:
        compare_text += f"\n💪 *Motivation:* Keep playing! You can beat the average!"
    else:
        compare_text += f"\n🎉 *Excellent!* You're ahead of most players! Keep it up!"
    
    bot.send_message(message.chat.id, compare_text, parse_mode='Markdown')

@bot.message_handler(commands=['start'])
def handle_start(message):
    chat_type = 'private' if message.chat.type == 'private' else 'group'
    user_id = message.from_user.id

    get_or_create_user(
        user_id=user_id,
        username=message.from_user.username,
        first_name=message.from_user.first_name,
        last_name=message.from_user.last_name,
        private_chat_id=message.chat.id if chat_type == 'private' else None
    )

    user_profile = get_user_profile(user_id)
    if user_profile.name and user_profile.age and user_profile.city:
        welcome_text = (
            f"Welcome back, {user_profile.name}! 👋\n\n"
            f"I remember about you:\n"
            f"👤 Name: {user_profile.name}\n"
            f"🎂 Age: {user_profile.age}\n"
            f"🏙 City: {user_profile.city}\n\n"
            "Now I can answer ANY of your questions! 🤖\n"
            "Just type something, and I'll try to help!\n\n"
            "Choose a mode from the menu below:"
        )
        bot.send_message(message.chat.id, welcome_text, reply_markup=create_keyboard(main_menu=True), parse_mode='Markdown')
    else:
        user_profile.waiting_for = 'name'
        bot.send_message(
            message.chat.id,
            f"Hello! 👋 Let's get acquainted!\n\n"
            f"What's your name?",
            reply_markup=telebot.types.ReplyKeyboardRemove()
        )

@bot.message_handler(commands=['help', 'quiz', 'stats', 'top', 'ai', 'profile', 'clear', 'compare'])
def handle_other_commands(message):
    chat_type = 'private' if message.chat.type == 'private' else 'group'
    user_id = message.from_user.id

    get_or_create_user(
        user_id=user_id,
        username=message.from_user.username,
        first_name=message.from_user.first_name,
        last_name=message.from_user.last_name,
        private_chat_id=message.chat.id if chat_type == 'private' else None
    )

    if message.text.startswith('/help'):
        help_command(message)
    elif message.text.startswith('/quiz'):
        start_quiz_command(message, chat_type)
    elif message.text.startswith('/stats'):
        stats_command(message, chat_type)
    elif message.text.startswith('/top'):
        top_command(message, chat_type)
    elif message.text.startswith('/ai'):
        ai_command(message)
    elif message.text.startswith('/profile'):
        profile_command(message)
    elif message.text.startswith('/clear'):
        clear_history_command(message)
    elif message.text.startswith('/compare'):
        compare_stats_command(message, chat_type)

def help_command(message):
    help_text = (
        "📖 *Help and Bot Commands*\n\n"
        
        "🎯 *Quiz*:\n"
        "• /quiz or '🎯 Start Quiz' button - start a quiz\n"
        "• Choose topic: history, geography, science, programming, art, sports\n"
        "• Answer questions and earn points\n"
        "• Press '⏹️ Stop' to end the quiz\n\n"
        
        "🤖 *AI Assistant*:\n"
        "• /ai or '🤖 Ask AI' button - ask any question\n"
        "• Just type any question in the chat\n"
        "• Uses Google Gemini AI\n"
        "• Bot remembers conversation context\n"
        "• 👍/👎 - rate AI responses for improvement\n\n"
        
        "📊 *Statistics and Rankings*:\n"
        "• /stats or '📊 My Stats' button - your statistics\n"
        "• /top or '🏆 Leaderboard' button - leaderboard\n"
        "• /compare or '📈 Compare' button - compare with other players\n\n"
        
        "👤 *Profile*:\n"
        "• /profile or '👤 My Profile' button - view profile\n"
        "• /start - fill/edit profile\n\n"
        
        "⚙️ *Other Commands*:\n"
        "• /clear or '🧹 Clear History' button - clear chat history\n"
        "• /help or '❓ Help' button - this message\n"
        "• /start - restart the bot\n\n"
        
        "🎮 *How to Play*:\n"
        "1. Press '🎯 Start Quiz'\n"
        "2. Choose a topic or '🎲 Random Topic'\n"
        "3. Answer questions by choosing A, B, C, or D\n"
        "4. Earn points and improve your statistics!\n\n"
        
        "💡 *Tip*: Just type any question in the chat - I'll answer it! 🤖\n\n"
        
        "*Good luck with the quiz!* 🚀"
    )
    bot.send_message(message.chat.id, help_text, parse_mode='Markdown')

def start_quiz_command(message, chat_type):
    user_id = message.from_user.id
    chat_id = message.chat.id

    user_quiz = get_user_quiz(user_id, chat_id, chat_type)
    user_quiz.waiting_for_topic = True

    bot.send_message(
        message.chat.id,
        f"🎯 {message.from_user.first_name}, choose a topic for the quiz:",
        reply_markup=create_topic_keyboard()
    )

def stats_command(message, chat_type):
    user_id = message.from_user.id
    chat_id = message.chat.id
    stats = get_user_stats(user_id, chat_id, chat_type)

    accuracy = (stats['correct_answers'] / stats['total_questions'] * 100) if stats['total_questions'] > 0 else 0

    stats_text = (
        f"📊 Statistics for {message.from_user.first_name}:\n\n"
        f"🏅 Total Points: {stats['total_points']}\n"
        f"✅ Correct Answers: {stats['correct_answers']}\n"
        f"📝 Total Questions: {stats['total_questions']}\n"
        f"🎯 Accuracy: {accuracy:.1f}%\n"
        f"🎮 Games Played: {stats['games_played']}\n"
        f"⏰ Last Played: {stats['last_played'] or 'Never'}"
    )

    bot.send_message(message.chat.id, stats_text)

def top_command(message, chat_type):
    chat_id = message.chat.id
    cursor = db_connection.cursor()

    if chat_type == 'private':
        cursor.execute('''
            SELECT u.first_name, u.username, us.total_points, us.correct_answers, us.total_questions
            FROM user_stats us
            JOIN users u ON us.user_id = u.user_id
            WHERE us.chat_type = 'private'
            ORDER BY us.total_points DESC
            LIMIT 10
        ''')
    else:
        cursor.execute('''
            SELECT u.first_name, u.username, us.total_points, us.correct_answers, us.total_questions
            FROM user_stats us
            JOIN users u ON us.user_id = u.user_id
            WHERE us.chat_id = ? AND us.chat_type = 'group'
            ORDER BY us.total_points DESC
            LIMIT 10
        ''', (chat_id,))

    leaderboard = cursor.fetchall()

    if not leaderboard:
        bot.send_message(message.chat.id, "🏆 No players in the leaderboard yet! Be the first! 🎯")
        return

    top_text = f"🏆 {'Global' if chat_type == 'private' else 'Group'} Leaderboard:\n\n"

    for i, (first_name, username, points, correct, total) in enumerate(leaderboard, 1):
        accuracy = (correct / total * 100) if total > 0 else 0
        name = f"@{username}" if username else first_name
        medal = ["🥇", "🥈", "🥉"][i-1] if i <= 3 else f"{i}."

        top_text += f"{medal} {name} - {points} points ({accuracy:.1f}%)\n"

    bot.send_message(message.chat.id, top_text)

def ai_command(message):
    bot.send_message(
        message.chat.id,
        "🤖 *AI Assistant Mode*\n\n"
        "Ask ANY question, and I'll try to answer! 🚀\n"
        "I remember the context of our conversation.\n\n"
        "Example questions:\n"
        "• Explain quantum physics in simple terms\n"
        "• Tell me about the history of Ancient Rome\n"
        "Waiting for your question...",
        parse_mode='Markdown'
    )

def profile_command(message):
    user_id = message.from_user.id
    user_profile = get_user_profile(user_id)

    if user_profile.name and user_profile.age and user_profile.city:
        profile_text = (
            f"👤 Your Profile:\n\n"
            f"Name: {user_profile.name}\n"
            f"Age: {user_profile.age}\n"
            f"City: {user_profile.city}\n\n"
            f"Want to change information? Type /start again!"
        )
    else:
        profile_text = (
            "❌ Your profile information is not filled.\n\n"
            "Type /start to introduce yourself!"
        )

    bot.send_message(message.chat.id, profile_text)

def clear_history_command(message):
    user_id = message.from_user.id
    clear_chat_session(user_id)
    bot.send_message(
        message.chat.id,
        "🧹 Chat history cleared! Starting a new dialogue!",
        reply_markup=create_keyboard(main_menu=True)
    )

@bot.message_handler(func=lambda message: message.text in [
    "🎯 Start Quiz", "🤖 Ask AI", "📊 My Stats",
    "🏆 Leaderboard", "👤 My Profile", "📈 Compare", "🧹 Clear History", "❓ Help"
])
def handle_menu_buttons(message):
    chat_type = 'private' if message.chat.type == 'private' else 'group'
    user_id = message.from_user.id

    get_or_create_user(
        user_id=user_id,
        username=message.from_user.username,
        first_name=message.from_user.first_name,
        last_name=message.from_user.last_name,
        private_chat_id=message.chat.id if chat_type == 'private' else None
    )

    if message.text == "🎯 Start Quiz":
        start_quiz_command(message, chat_type)
    elif message.text == "🤖 Ask AI":
        ai_command(message)
    elif message.text == "📊 My Stats":
        stats_command(message, chat_type)
    elif message.text == "🏆 Leaderboard":
        top_command(message, chat_type)
    elif message.text == "👤 My Profile":
        profile_command(message)
    elif message.text == "📈 Compare":
        compare_stats_command(message, chat_type)
    elif message.text == "🧹 Clear History":
        clear_history_command(message)
    elif message.text == "❓ Help":
        help_command(message)

@bot.message_handler(func=lambda message: get_user_profile(message.from_user.id).waiting_for is not None)
def handle_profile_info(message):
    user_id = message.from_user.id
    user_profile = get_user_profile(user_id)

    if user_profile.waiting_for == 'name':
        user_profile.name = message.text
        user_profile.waiting_for = 'age'
        bot.send_message(message.chat.id, f"Nice to meet you, {user_profile.name}! 🎉\n\nHow old are you?")

    elif user_profile.waiting_for == 'age':
        try:
            age = int(message.text)
            if age < 1 or age > 120:
                bot.send_message(message.chat.id, "Please enter a real age (1-120 years):")
                return
            user_profile.age = age
            user_profile.waiting_for = 'city'
            bot.send_message(message.chat.id, f"Great! Which city are you from?")
        except ValueError:
            bot.send_message(message.chat.id, "Please enter age in numbers:")

    elif user_profile.waiting_for == 'city':
        user_profile.city = message.text
        user_profile.waiting_for = None

        save_user_profile_to_db(user_id, user_profile)

        welcome_text = (
            f"Super! 🎉 Here's what I know about you:\n\n"
            f"👤 Name: {user_profile.name}\n"
            f"🎂 Age: {user_profile.age}\n"
            f"🏙 City: {user_profile.city}\n\n"
            f"Now I can answer ANY of your questions! 🤖\n"
            f"Just type something, and I'll try to help!\n\n"
            f"Choose a mode from the menu below:"
        )
        bot.send_message(message.chat.id, welcome_text, reply_markup=create_keyboard(main_menu=True))

@bot.callback_query_handler(func=lambda call: call.data.startswith('feedback_'))
def handle_feedback(call):
    user_id = call.from_user.id
    message_id = call.message.message_id
    
    if call.data == 'feedback_like':
        if user_id in pending_ai_responses and message_id in pending_ai_responses[user_id]:
            question, response = pending_ai_responses[user_id][message_id]
            save_ai_response(user_id, question, response, liked=True)
            
            del pending_ai_responses[user_id][message_id]
            
            bot.answer_callback_query(call.id, "✅ Response saved! Will use it in the future.")
            bot.edit_message_text(
                f"🤖 *AI Response:*\n\n{response}\n\n✅ *Response saved to database*",
                call.message.chat.id,
                call.message.message_id,
                parse_mode='Markdown'
            )
        else:
            bot.answer_callback_query(call.id, "⚠️ Response information not found")
    
    elif call.data == 'feedback_dislike':
        if user_id in pending_ai_responses and message_id in pending_ai_responses[user_id]:
            question, old_response = pending_ai_responses[user_id][message_id]
            
            del pending_ai_responses[user_id][message_id]
            
            bot.answer_callback_query(call.id, "🔄 Generating new response...")
            
            new_response = query_gemini(user_id, question)
            
            sent_message = bot.send_message(
                call.message.chat.id,
                f"🤖 *AI Response (updated):*\n\n{new_response}",
                parse_mode='Markdown',
                reply_markup=create_feedback_keyboard()
            )
            
            if user_id not in pending_ai_responses:
                pending_ai_responses[user_id] = {}
            pending_ai_responses[user_id][sent_message.message_id] = (question, new_response)
            
            try:
                bot.delete_message(call.message.chat.id, call.message.message_id)
            except:
                pass

@bot.message_handler(func=lambda message: True)
def handle_all_messages(message):
    if message.text and message.text.startswith('/'):
        return

    chat_type = 'private' if message.chat.type == 'private' else 'group'
    user_id = message.from_user.id
    chat_id = message.chat.id

    user_quiz = get_user_quiz(user_id, chat_id, chat_type)

    cursor = db_connection.cursor()
    cursor.execute("SELECT DISTINCT topic FROM questions")
    all_topics = [row[0] for row in cursor.fetchall()]

    if message.text == "⏹️ Stop":
        if user_quiz.quiz_started:
            end_quiz(message, user_quiz)
        else:
            bot.send_message(message.chat.id, "❌ Quiz not active.",
                           reply_markup=create_keyboard(main_menu=True))
        return

    if message.text == "🔙 Back":
        user_quiz.waiting_for_topic = False
        user_quiz.quiz_started = False
        bot.send_message(message.chat.id, "Returning to main menu:",
                        reply_markup=create_keyboard(main_menu=True))
        return

    if user_quiz.waiting_for_topic and (message.text in all_topics or message.text in ["🎲 Random Topic", "🔙 Back"]):
        handle_topic_selection(message, user_quiz, chat_type)
        return

    if user_quiz.quiz_started and user_quiz.current_question:
        user_answer = message.text.strip()
        if user_answer and len(user_answer) > 0 and user_answer[0].upper() in ['A', 'B', 'C', 'D']:
            handle_quiz_answer(message, user_quiz)
            return
        else:
            bot.send_message(message.chat.id, "Please choose answer option A, B, C, or D.")
            return

    user_profile = get_user_profile(user_id)
    if user_profile.waiting_for is None:
        bot.send_chat_action(chat_id, 'typing')
        ai_response = query_gemini(user_id, message.text)
        
        sent_message = bot.send_message(
            chat_id, 
            f"🤖 *AI Response:*\n\n{ai_response}", 
            parse_mode='Markdown',
            reply_markup=create_feedback_keyboard()
        )
        
        if user_id not in pending_ai_responses:
            pending_ai_responses[user_id] = {}
        pending_ai_responses[user_id][sent_message.message_id] = (message.text, ai_response)

def handle_topic_selection(message, user_quiz, chat_type):
    if message.text == "🔙 Back":
        user_quiz.waiting_for_topic = False
        bot.send_message(message.chat.id, "Returning to main menu:",
                        reply_markup=create_keyboard(main_menu=True))
        return

    if message.text == "🎲 Random Topic":
        user_quiz.current_topic = None
        topic_name = "random questions"
    else:
        user_quiz.current_topic = message.text
        topic_name = message.text

    user_quiz.quiz_started = True
    user_quiz.waiting_for_topic = False
    user_quiz.score = 0
    user_quiz.questions_answered = 0
    user_quiz.correct_answers = 0

    bot.send_message(
        message.chat.id,
        f"🎯 {message.from_user.first_name}, topic: {topic_name.capitalize()}\n\n"
        "Quiz is starting! Answer questions and earn points! 💫\n"
        "To stop the quiz, press '⏹️ Stop'",
        reply_markup=telebot.types.ReplyKeyboardRemove()
    )

    ask_question(message.chat.id, user_quiz)

def handle_quiz_answer(message, user_quiz):
    user_answer = message.text[0].upper() if message.text else ''
    correct_index = user_quiz.current_question['correct_answer']
    correct_letter = chr(65 + correct_index)

    if user_answer == correct_letter:
        points = user_quiz.current_question['points']
        user_quiz.score += points
        user_quiz.correct_answers += 1

        response_text = (
            f"✅ Correct! 🎉\n\n"
            f"You get {points} points!\n"
            f"Current score: {user_quiz.score} points"
        )

        update_user_stats(
            user_id=user_quiz.user_id,
            chat_id=user_quiz.chat_id,
            chat_type=user_quiz.chat_type,
            points=points,
            questions=1,
            correct=1
        )
    else:
        correct_answer = user_quiz.current_question['options'][correct_index]
        response_text = (
            f"❌ Incorrect 😔\n\n"
            f"Correct answer: {correct_letter}) {correct_answer}\n"
            f"Your score: {user_quiz.score} points"
        )

        update_user_stats(
            user_id=user_quiz.user_id,
            chat_id=user_quiz.chat_id,
            chat_type=user_quiz.chat_type,
            questions=1
        )

    bot.send_message(user_quiz.chat_id, response_text)
    user_quiz.questions_answered += 1
    ask_question(user_quiz.chat_id, user_quiz)

def ask_question(chat_id, user_quiz):
    question_data = get_random_question(user_quiz.current_topic)
    if question_data:
        user_quiz.current_question = question_data
        question_text = format_question(question_data, user_quiz.questions_answered + 1)
        bot.send_message(chat_id, question_text, reply_markup=create_keyboard(question_data['options']))
    else:
        bot.send_message(chat_id, "❌ No more questions!", reply_markup=create_keyboard(main_menu=True))
        user_quiz.quiz_started = False

def end_quiz(message, user_quiz):
    if user_quiz.questions_answered > 0:
        accuracy = (user_quiz.correct_answers / user_quiz.questions_answered * 100) if user_quiz.questions_answered > 0 else 0

        final_text = (
            f"🏁 Quiz finished, {message.from_user.first_name}!\n\n"
            f"📊 Results:\n"
            f"✅ Correct answers: {user_quiz.correct_answers}/{user_quiz.questions_answered}\n"
            f"🎯 Accuracy: {accuracy:.1f}%\n"
            f"🏅 Points earned: {user_quiz.score}\n\n"
            f"Play again? 🎯"
        )

        update_user_stats(
            user_id=user_quiz.user_id,
            chat_id=user_quiz.chat_id,
            chat_type=user_quiz.chat_type,
            game_played=True
        )
    else:
        final_text = "❌ Quiz stopped."

    user_quiz.quiz_started = False
    user_quiz.waiting_for_topic = False
    bot.send_message(message.chat.id, final_text, reply_markup=create_keyboard(main_menu=True))

def check_gemini_availability():
    try:
        if model:
            response = model.generate_content("Hello! Reply 'OK' if you're working.")
            return response.text is not None
        return False
    except:
        return False

if __name__ == "__main__":
    print("=" * 50)
    print("🤖 Bot is starting...")

    gemini_available = check_gemini_availability()

    if gemini_available:
        print("✅ Gemini AI is active and ready to work!")
    else:
        print("❌ Gemini AI is unavailable. Check API key and settings.")

    print("🎯 Bot is ready! Use /start")
    print("=" * 50)

    try:
        bot.polling(none_stop=True, interval=0, timeout=60)
    except Exception as e:
        logger.error(f"Error starting bot: {e}")
        print(f"❌ An error occurred: {e}")
