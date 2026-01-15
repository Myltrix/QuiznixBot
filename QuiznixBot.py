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

GEMINI_API_KEY = "AIzaSyA8u0FUt-XafGpW2zEzerBSIbx3olm0RuQ"
bot = telebot.TeleBot('8208989400:AAFhtAdu3XWZSo8U5nSd4vED8OV_99OK4bc')

try:
    if GEMINI_API_KEY and GEMINI_API_KEY != "YOUR_GEMINI_API_KEY_HERE":
        genai.configure(api_key=GEMINI_API_KEY)
        model = genai.GenerativeModel("gemini-2.5-flash")
        logger.info("Gemini модель успешно инициализирована")
    else:
        logger.warning("Gemini API ключ не установлен или установлен демо-ключ")
        model = None
except Exception as e:
    logger.error(f"Ошибка инициализации Gemini: {e}")
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
    "история": [
        {
            "question": "В каком году началась Вторая мировая война?",
            "options": ["1939", "1941", "1945", "1914"],
            "correct_answer": 0,
            "points": 5,
            "difficulty": "medium"
        },
        {
            "question": "Кто был первым президентом США?",
            "options": ["Авраам Линкольн", "Джордж Вашингтон", "Томас Джефферсон", "Джон Адамс"],
            "correct_answer": 1,
            "points": 4,
            "difficulty": "easy"
        },
        {
            "question": "В каком году распался Советский Союз?",
            "options": ["1989", "1991", "1993", "1985"],
            "correct_answer": 1,
            "points": 5,
            "difficulty": "medium"
        },
        {
            "question": "Кто написал 'Войну и мир'?",
            "options": ["Федор Достоевский", "Лев Толстой", "Антон Чехов", "Иван Тургенев"],
            "correct_answer": 1,
            "points": 4,
            "difficulty": "easy"
        },
        {
            "question": "Кто открыл Америку?",
            "options": ["Христофор Колумб", "Васко да Гама", "Фернан Магеллан", "Америго Веспуччи"],
            "correct_answer": 0,
            "points": 3,
            "difficulty": "easy"
        },
        {
            "question": "Когда произошла Великая французская революция?",
            "options": ["1776", "1789", "1799", "1812"],
            "correct_answer": 1,
            "points": 6,
            "difficulty": "medium"
        },
        {
            "question": "Кто был первым императором Рима?",
            "options": ["Юлий Цезарь", "Октавиан Август", "Нерон", "Константин"],
            "correct_answer": 1,
            "points": 5,
            "difficulty": "medium"
        },
        {
            "question": "В каком году пала Византийская империя?",
            "options": ["1453", "1492", "1380", "1520"],
            "correct_answer": 0,
            "points": 7,
            "difficulty": "hard"
        },
        {
            "question": "Кто построил Тадж-Махал?",
            "options": ["Шах-Джахан", "Акбар Великий", "Ашока", "Бабур"],
            "correct_answer": 0,
            "points": 6,
            "difficulty": "medium"
        },
        {
            "question": "Когда началась Первая мировая война?",
            "options": ["1914", "1917", "1939", "1905"],
            "correct_answer": 0,
            "points": 4,
            "difficulty": "easy"
        },
        {
            "question": "Кто был первым русским царем?",
            "options": ["Иван Грозный", "Петр I", "Иван III", "Алексей Михайлович"],
            "correct_answer": 0,
            "points": 5,
            "difficulty": "medium"
        },
        {
            "question": "В каком году произошла Куликовская битва?",
            "options": ["1380", "1240", "1480", "1547"],
            "correct_answer": 0,
            "points": 6,
            "difficulty": "hard"
        },
        {
            "question": "Кто написал 'Капитал'?",
            "options": ["Карл Маркс", "Фридрих Энгельс", "Владимир Ленин", "Адам Смит"],
            "correct_answer": 0,
            "points": 5,
            "difficulty": "medium"
        },
        {
            "question": "В каком году крестили Русь?",
            "options": ["988", "1015", "945", "1054"],
            "correct_answer": 0,
            "points": 6,
            "difficulty": "medium"
        },
        {
            "question": "Кто победил в Столетней войне?",
            "options": ["Англия", "Франция", "Испания", "Ничья"],
            "correct_answer": 1,
            "points": 7,
            "difficulty": "hard"
        },
        {
            "question": "Кто был первым римским папой?",
            "options": ["Петр", "Лев I", "Григорий I", "Сильвестр I"],
            "correct_answer": 0,
            "points": 7,
            "difficulty": "hard"
        },
        {
            "question": "Когда была основана Москва?",
            "options": ["1147", "1240", "1325", "988"],
            "correct_answer": 0,
            "points": 5,
            "difficulty": "medium"
        },
        {
            "question": "Кто возглавил первую кругосветную экспедицию?",
            "options": ["Фернан Магеллан", "Христофор Колумб", "Васко да Гама", "Джеймс Кук"],
            "correct_answer": 0,
            "points": 6,
            "difficulty": "medium"
        },
        {
            "question": "Когда произошла битва при Ватерлоо?",
            "options": ["1815", "1805", "1825", "1830"],
            "correct_answer": 0,
            "points": 6,
            "difficulty": "medium"
        },
        {
            "question": "Кто был последним российским императором?",
            "options": ["Николай II", "Александр III", "Петр III", "Павел I"],
            "correct_answer": 0,
            "points": 4,
            "difficulty": "easy"
        },
        {
            "question": "Когда была подписана Magna Carta?",
            "options": ["1215", "1066", "1415", "1315"],
            "correct_answer": 0,
            "points": 7,
            "difficulty": "hard"
        },
        {
            "question": "Кто основал династию Романовых?",
            "options": ["Михаил Романов", "Петр I", "Иван Грозный", "Алексей Михайлович"],
            "correct_answer": 0,
            "points": 5,
            "difficulty": "medium"
        },
        {
            "question": "Когда произошла Великая октябрьская революция?",
            "options": ["1917", "1905", "1914", "1922"],
            "correct_answer": 0,
            "points": 5,
            "difficulty": "medium"
        },
        {
            "question": "Кто был фараоном-женщиной в Древнем Египте?",
            "options": ["Хатшепсут", "Нефертити", "Клеопатра", "Нефрусебек"],
            "correct_answer": 0,
            "points": 6,
            "difficulty": "hard"
        },
        {
            "question": "Когда началась Корейская война?",
            "options": ["1950", "1945", "1955", "1960"],
            "correct_answer": 0,
            "points": 6,
            "difficulty": "hard"
        },
        {
            "question": "Кто написал 'Государство'?",
            "options": ["Платон", "Аристотель", "Сократ", "Цицерон"],
            "correct_answer": 0,
            "points": 7,
            "difficulty": "hard"
        },
        {
            "question": "Когда пала Западная Римская империя?",
            "options": ["476", "410", "455", "395"],
            "correct_answer": 0,
            "points": 7,
            "difficulty": "hard"
        },
        {
            "question": "Кто был первым королем Англии?",
            "options": ["Альфред Великий", "Вильгельм Завоеватель", "Этельстан", "Генрих I"],
            "correct_answer": 2,
            "points": 8,
            "difficulty": "hard"
        },
        {
            "question": "Когда произошла битва на Косовом поле?",
            "options": ["1389", "1242", "1410", "1456"],
            "correct_answer": 0,
            "points": 7,
            "difficulty": "hard"
        },
        {
            "question": "Кто открыл пенициллин?",
            "options": ["Александр Флеминг", "Луи Пастер", "Роберт Кох", "Илья Мечников"],
            "correct_answer": 0,
            "points": 5,
            "difficulty": "medium"
        },
        {
            "question": "Когда была основана Османская империя?",
            "options": ["1299", "1453", "1326", "1402"],
            "correct_answer": 0,
            "points": 7,
            "difficulty": "hard"
        },
        {
            "question": "Кто был первым премьер-министром Великобритании?",
            "options": ["Роберт Уолпол", "Уильям Питт", "Чарльз Джеймス Фокс", "Генри Пелэм"],
            "correct_answer": 0,
            "points": 7,
            "difficulty": "hard"
        },
        {
            "question": "Когда произошла Варфоломеевская ночь?",
            "options": ["1572", "1588", "1598", "1618"],
            "correct_answer": 0,
            "points": 7,
            "difficulty": "hard"
        },
        {
            "question": "Кто возглавил восстание Спартака?",
            "options": ["Спартак", "Крикс", "Ганнибал", "Верцингеториг"],
            "correct_answer": 0,
            "points": 5,
            "difficulty": "medium"
        },
        {
            "question": "Когда была основана Александрия?",
            "options": ["331 до н.э.", "300 до н.э.", "350 до н.э.", "280 до н.э."],
            "correct_answer": 0,
            "points": 7,
            "difficulty": "hard"
        },
        {
            "question": "Кто был первым императором Китая?",
            "options": ["Цинь Шихуанди", "У-ди", "Гао-цзу", "Вэнь-ди"],
            "correct_answer": 0,
            "points": 6,
            "difficulty": "medium"
        },
        {
            "question": "Когда произошла битва при Гастингсе?",
            "options": ["1066", "1016", "1154", "1215"],
            "correct_answer": 0,
            "points": 6,
            "difficulty": "medium"
        },
        {
            "question": "Кто написал 'Илиаду' и 'Одиссею'?",
            "options": ["Гомер", "Гесиод", "Вергилий", "Софокл"],
            "correct_answer": 0,
            "points": 4,
            "difficulty": "easy"
        },
        {
            "question": "Когда началась Столетняя война?",
            "options": ["1337", "1346", "1356", "1415"],
            "correct_answer": 0,
            "points": 7,
            "difficulty": "hard"
        },
        {
            "question": "Кто был первым королем Франции?",
            "options": ["Хлодвиг I", "Карл Великий", "Филипп II", "Людовик IX"],
            "correct_answer": 0,
            "points": 7,
            "difficulty": "hard"
        },
        {
            "question": "Когда произошла битва при Лепанто?",
            "options": ["1571", "1588", "1591", "1600"],
            "correct_answer": 0,
            "points": 8,
            "difficulty": "hard"
        },
        {
            "question": "Кто основал город Рим?",
            "options": ["Ромул", "Нума Помпилий", "Рем", "Тулл Гостилий"],
            "correct_answer": 0,
            "points": 4,
            "difficulty": "easy"
        },
        {
            "question": "Когда была подписана Декларация независимости США?",
            "options": ["1776", "1789", "1791", "1801"],
            "correct_answer": 0,
            "points": 5,
            "difficulty": "medium"
        },
        {
            "question": "Кто был первым халифом ислама?",
            "options": ["Абу Бакр", "Умар", "Усман", "Али"],
            "correct_answer": 0,
            "points": 6,
            "difficulty": "medium"
        },
        {
            "question": "Когда произошла битва на реке Калка?",
            "options": ["1223", "1237", "1240", "1242"],
            "correct_answer": 0,
            "points": 7,
            "difficulty": "hard"
        },
        {
            "question": "Кто был первым королем Португалии?",
            "options": ["Афонсу I", "Саншу I", "Афонсу II", "Педру I"],
            "correct_answer": 0,
            "points": 7,
            "difficulty": "hard"
        },
        {
            "question": "Когда началась Война Алой и Белой розы?",
            "options": ["1455", "1485", "1435", "1460"],
            "correct_answer": 0,
            "points": 7,
            "difficulty": "hard"
        },
        {
            "question": "Кто был первым императором Священной Римской империи?",
            "options": ["Оттон I", "Карл Великий", "Фридрих I", "Генрих IV"],
            "correct_answer": 0,
            "points": 7,
            "difficulty": "hard"
        },
        {
            "question": "Когда произошла битва при Азенкуре?",
            "options": ["1415", "1429", "1453", "1475"],
            "correct_answer": 0,
            "points": 7,
            "difficulty": "hard"
        }
    ],
    "география": [
        {
            "question": "Какая самая длинная река в мире?",
            "options": ["Амазонка", "Нил", "Янцзы", "Миссисипи"],
            "correct_answer": 0,
            "points": 6,
            "difficulty": "medium"
        },
        {
            "question": "Столица Австралии?",
            "options": ["Сидней", "Мельбурн", "Канберра", "Перт"],
            "correct_answer": 2,
            "points": 3,
            "difficulty": "easy"
        },
        {
            "question": "Какая страна самая большая по площади?",
            "options": ["Канада", "США", "Россия", "Китай"],
            "correct_answer": 2,
            "points": 4,
            "difficulty": "easy"
        },
        {
            "question": "Какая пустыня самая большая в мире?",
            "options": ["Сахара", "Гоби", "Аравийская", "Антарктическая"],
            "correct_answer": 3,
            "points": 7,
            "difficulty": "hard"
        },
        {
            "question": "Столица Бразилии?",
            "options": ["Рио-де-Жанейро", "Сан-Паулу", "Бразилиа", "Сальвадор"],
            "correct_answer": 2,
            "points": 4,
            "difficulty": "medium"
        },
        {
            "question": "Какая гора самая высокая в мире?",
            "options": ["Килиманджаро", "Эверест", "Мак-Кинли", "Аконкагуа"],
            "correct_answer": 1,
            "points": 3,
            "difficulty": "easy"
        },
        {
            "question": "Какое озеро самое глубокое в мире?",
            "options": ["Байкал", "Танганьика", "Верхнее", "Виктория"],
            "correct_answer": 0,
            "points": 5,
            "difficulty": "medium"
        },
        {
            "question": "Сколько океанов на Земле?",
            "options": ["4", "5", "6", "7"],
            "correct_answer": 1,
            "points": 3,
            "difficulty": "easy"
        },
        {
            "question": "Какая страна имеет самую длинную береговую линию?",
            "options": ["Россия", "Канада", "Индонезия", "Филиппины"],
            "correct_answer": 1,
            "points": 6,
            "difficulty": "hard"
        },
        {
            "question": "Столица Исландии?",
            "options": ["Осло", "Копенгаген", "Рейкьявик", "Хельсинки"],
            "correct_answer": 2,
            "points": 4,
            "difficulty": "medium"
        },
        {
            "question": "Какое государство самое маленькое в мире?",
            "options": ["Монако", "Ватикан", "Сан-Марино", "Лихтенштейн"],
            "correct_answer": 1,
            "points": 5,
            "difficulty": "medium"
        },
        {
            "question": "Сколько штатов в США?",
            "options": ["48", "50", "52", "54"],
            "correct_answer": 1,
            "points": 4,
            "difficulty": "easy"
        },
        {
            "question": "Какая страна имеет форму сапога?",
            "options": ["Италия", "Греция", "Испания", "Португалия"],
            "correct_answer": 0,
            "points": 3,
            "difficulty": "easy"
        },
        {
            "question": "Столица Канады?",
            "options": ["Торонто", "Ванкувер", "Оттава", "Монреаль"],
            "correct_answer": 2,
            "points": 4,
            "difficulty": "medium"
        },
        {
            "question": "Какая река протекает через Париж?",
            "options": ["Сена", "Темза", "Рейн", "Дунай"],
            "correct_answer": 0,
            "points": 4,
            "difficulty": "easy"
        },
        {
            "question": "Самое большое озеро в мире?",
            "options": ["Каспийское море", "Байкал", "Верхнее", "Виктория"],
            "correct_answer": 0,
            "points": 5,
            "difficulty": "medium"
        },
        {
            "question": "Столица Египта?",
            "options": ["Александрия", "Каир", "Гиза", "Луксор"],
            "correct_answer": 1,
            "points": 3,
            "difficulty": "easy"
        },
        {
            "question": "Какая страна находится на двух континентах?",
            "options": ["Турция", "Египет", "Россия", "Все вышеперечисленные"],
            "correct_answer": 3,
            "points": 6,
            "difficulty": "medium"
        },
        {
            "question": "Самый высокий водопад в мире?",
            "options": ["Анхель", "Ниагара", "Виктория", "Игуасу"],
            "correct_answer": 0,
            "points": 5,
            "difficulty": "medium"
        },
        {
            "question": "Столица Японии?",
            "options": ["Осака", "Киото", "Токио", "Иокогама"],
            "correct_answer": 2,
            "points": 3,
            "difficulty": "easy"
        },
        {
            "question": "Какое море самое соленое?",
            "options": ["Мертвое море", "Красное море", "Средиземное море", "Черное море"],
            "correct_answer": 0,
            "points": 5,
            "difficulty": "medium"
        },
        {
            "question": "Столица Аргентины?",
            "options": ["Буэнос-Айрес", "Сантьяго", "Лима", "Бразилиа"],
            "correct_answer": 0,
            "points": 4,
            "difficulty": "medium"
        },
        {
            "question": "Какая пустыня находится в Южной Америке?",
            "options": ["Атакама", "Сахара", "Гоби", "Каракумы"],
            "correct_answer": 0,
            "points": 5,
            "difficulty": "medium"
        },
        {
            "question": "Самый большой остров в мире?",
            "options": ["Гренландия", "Новая Гвинея", "Борнео", "Мадагаскар"],
            "correct_answer": 0,
            "points": 4,
            "difficulty": "easy"
        },
        {
            "question": "Столица Южной Кореи?",
            "options": ["Пусан", "Сеул", "Инчхон", "Тэгу"],
            "correct_answer": 1,
            "points": 4,
            "difficulty": "easy"
        },
        {
            "question": "Какая страна имеет наибольшее количество островов?",
            "options": ["Швеция", "Индонезия", "Филиппины", "Япония"],
            "correct_answer": 0,
            "points": 7,
            "difficulty": "hard"
        },
        {
            "question": "Столица Норвегии?",
            "options": ["Осло", "Стокгольм", "Копенгаген", "Хельсинки"],
            "correct_answer": 0,
            "points": 4,
            "difficulty": "easy"
        },
        {
            "question": "Какая страна не имеет выхода к морю?",
            "options": ["Швейцария", "Австрия", "Венгрия", "Все вышеперечисленные"],
            "correct_answer": 3,
            "points": 5,
            "difficulty": "medium"
        },
        {
            "question": "Самый большой полуостров в мире?",
            "options": ["Аравийский", "Индостан", "Скандинавский", "Лабрадор"],
            "correct_answer": 0,
            "points": 6,
            "difficulty": "hard"
        },
        {
            "question": "Столица Марокко?",
            "options": ["Касабланка", "Рабат", "Марракеш", "Фес"],
            "correct_answer": 1,
            "points": 5,
            "difficulty": "medium"
        },
        {
            "question": "Какая страна имеет наибольшее количество часовых поясов?",
            "options": ["Россия", "США", "Канада", "Китай"],
            "correct_answer": 0,
            "points": 5,
            "difficulty": "medium"
        },
        {
            "question": "Столица Перу?",
            "options": ["Лима", "Кито", "Богота", "Ла-Пас"],
            "correct_answer": 0,
            "points": 4,
            "difficulty": "medium"
        },
        {
            "question": "Какое озеро находится между США и Канадой?",
            "options": ["Верхнее", "Мичиган", "Гурон", "Все вышеперечисленные"],
            "correct_answer": 3,
            "points": 6,
            "difficulty": "medium"
        },
        {
            "question": "Столица Вьетнама?",
            "options": ["Ханой", "Хошимин", "Дананг", "Хюэ"],
            "correct_answer": 0,
            "points": 4,
            "difficulty": "medium"
        },
        {
            "question": "Какая страна имеет самую длинную сухопутную границу?",
            "options": ["Россия", "Китай", "США", "Канада"],
            "correct_answer": 0,
            "points": 6,
            "difficulty": "hard"
        },
        {
            "question": "Столица Финляндии?",
            "options": ["Хельсинки", "Стокгольм", "Осло", "Таллин"],
            "correct_answer": 0,
            "points": 4,
            "difficulty": "easy"
        },
        {
            "question": "Какая страна полностью окружена территорией другой страны?",
            "options": ["Сан-Марино", "Ватикан", "Лесото", "Все вышеперечисленные"],
            "correct_answer": 3,
            "points": 7,
            "difficulty": "hard"
        },
        {
            "question": "Столица Чили?",
            "options": ["Сантьяго", "Буэнос-Айрес", "Лима", "Богота"],
            "correct_answer": 0,
            "points": 4,
            "difficulty": "medium"
        },
        {
            "question": "Какая страна имеет наибольшее количество официальных языков?",
            "options": ["Индия", "ЮАР", "Боливия", "Швейцария"],
            "correct_answer": 0,
            "points": 6,
            "difficulty": "hard"
        },
        {
            "question": "Столица Пакистана?",
            "options": ["Исламабад", "Карачи", "Лахор", "Пешавар"],
            "correct_answer": 0,
            "points": 5,
            "difficulty": "medium"
        },
        {
            "question": "Какая страна имеет самую молодую популяцию?",
            "options": ["Нигер", "Уганда", "Мали", "Чад"],
            "correct_answer": 0,
            "points": 7,
            "difficulty": "hard"
        },
        {
            "question": "Столица Саудовской Аравии?",
            "options": ["Эр-Рияд", "Мекка", "Медина", "Джидда"],
            "correct_answer": 0,
            "points": 5,
            "difficulty": "medium"
        },
        {
            "question": "Какая страна имеет наибольшее количество вулканов?",
            "options": ["Индонезия", "США", "Россия", "Япония"],
            "correct_answer": 0,
            "points": 6,
            "difficulty": "hard"
        },
        {
            "question": "Столица Украины?",
            "options": ["Киев", "Харьков", "Одесса", "Львов"],
            "correct_answer": 0,
            "points": 3,
            "difficulty": "easy"
        },
        {
            "question": "Какая страна имеет самую длинную систему метро?",
            "options": ["Китай", "США", "Россия", "Южная Корея"],
            "correct_answer": 0,
            "points": 6,
            "difficulty": "hard"
        },
        {
            "question": "Столица Малайзии?",
            "options": ["Куала-Лумпур", "Сингапур", "Бангкок", "Джакарта"],
            "correct_answer": 0,
            "points": 4,
            "difficulty": "medium"
        },
        {
            "question": "Какая страна имеет наибольшее количество природных озер?",
            "options": ["Канада", "Россия", "США", "Финляндия"],
            "correct_answer": 0,
            "points": 6,
            "difficulty": "hard"
        },
        {
            "question": "Столица Алжира?",
            "options": ["Алжир", "Касабланка", "Тунис", "Рабат"],
            "correct_answer": 0,
            "points": 5,
            "difficulty": "medium"
        },
        {
            "question": "Какая страна имеет самую длинную железнодорожную сеть?",
            "options": ["США", "Россия", "Китай", "Индия"],
            "correct_answer": 0,
            "points": 6,
            "difficulty": "hard"
        }
    ],
    "наука": [
        {
            "question": "Сколько элементов в периодической таблице?",
            "options": ["118", "92", "150", "206"],
            "correct_answer": 0,
            "points": 7,
            "difficulty": "hard"
        },
        {
            "question": "Какая планета самая большая в Солнечной системе?",
            "options": ["Земля", "Сатурн", "Юпитер", "Нептун"],
            "correct_answer": 2,
            "points": 3,
            "difficulty": "easy"
        },
        {
            "question": "Сколько костей в теле взрослого человека?",
            "options": ["206", "300", "150", "250"],
            "correct_answer": 0,
            "points": 5,
            "difficulty": "medium"
        },
        {
            "question": "Какой газ преобладает в атмосфере Земли?",
            "options": ["Кислород", "Азот", "Углекислый газ", "Аргон"],
            "correct_answer": 1,
            "points": 4,
            "difficulty": "easy"
        },
        {
            "question": "Сколько хромосом у человека?",
            "options": ["23", "46", "48", "52"],
            "correct_answer": 1,
            "points": 6,
            "difficulty": "medium"
        },
        {
            "question": "Какая самая твердая субстанция в человеческом теле?",
            "options": ["Кость", "Ноготь", "Зубная эмаль", "Волосы"],
            "correct_answer": 2,
            "points": 5,
            "difficulty": "medium"
        },
        {
            "question": "Сколько планет в Солнечной системе?",
            "options": ["7", "8", "9", "10"],
            "correct_answer": 1,
            "points": 3,
            "difficulty": "easy"
        },
        {
            "question": "Какой элемент имеет химический символ 'Au'?",
            "options": ["Серебро", "Золото", "Алюминий", "Аргон"],
            "correct_answer": 1,
            "points": 4,
            "difficulty": "easy"
        },
        {
            "question": "Сколько спутников у Марса?",
            "options": ["0", "1", "2", "3"],
            "correct_answer": 2,
            "points": 6,
            "difficulty": "hard"
        },
        {
            "question": "Какая скорость света в вакууме?",
            "options": ["300 000 км/с", "150 000 км/с", "500 000 км/с", "1 000 000 км/с"],
            "correct_answer": 0,
            "points": 7,
            "difficulty": "hard"
        },
        {
            "question": "Какой орган человека самый большой?",
            "options": ["Печень", "Сердце", "Кожа", "Мозг"],
            "correct_answer": 2,
            "points": 5,
            "difficulty": "medium"
        },
        {
            "question": "Сколько камер в сердце человека?",
            "options": ["2", "3", "4", "5"],
            "correct_answer": 2,
            "points": 4,
            "difficulty": "medium"
        },
        {
            "question": "Какой газ растения поглощают из атмосферы?",
            "options": ["Кислород", "Азот", "Углекислый газ", "Водород"],
            "correct_answer": 2,
            "points": 4,
            "difficulty": "easy"
        },
        {
            "question": "Сколько лет Земле примерно?",
            "options": ["4.5 млрд лет", "10 млн лет", "1 млрд лет", "100 млн лет"],
            "correct_answer": 0,
            "points": 6,
            "difficulty": "hard"
        },
        {
            "question": "Какой элемент самый распространенный во Вселенной?",
            "options": ["Водород", "Кислород", "Углерод", "Азот"],
            "correct_answer": 0,
            "points": 5,
            "difficulty": "medium"
        },
        {
            "question": "Сколько групп крови у человека?",
            "options": ["4", "6", "8", "10"],
            "correct_answer": 0,
            "points": 4,
            "difficulty": "easy"
        },
        {
            "question": "Какая планета ближе всего к Солнцу?",
            "options": ["Меркурий", "Венера", "Земля", "Марс"],
            "correct_answer": 0,
            "points": 3,
            "difficulty": "easy"
        },
        {
            "question": "Какой химический элемент имеет символ 'O'?",
            "options": ["Золото", "Кислород", "Осмий", "Олово"],
            "correct_answer": 1,
            "points": 3,
            "difficulty": "easy"
        },
        {
            "question": "Сколько спутников у Юпитера?",
            "options": ["4", "16", "79", "более 90"],
            "correct_answer": 3,
            "points": 7,
            "difficulty": "hard"
        },
        {
            "question": "Какая самая маленькая кость в человеческом теле?",
            "options": ["Стремечко", "Наковальня", "Молоточек", "Все вышеперечисленные"],
            "correct_answer": 0,
            "points": 6,
            "difficulty": "hard"
        },
        {
            "question": "Какой газ выделяют растения в процессе фотосинтеза?",
            "options": ["Кислород", "Углекислый газ", "Азот", "Водород"],
            "correct_answer": 0,
            "points": 4,
            "difficulty": "easy"
        },
        {
            "question": "Сколько мышц в человеческом теле?",
            "options": ["около 600", "около 300", "около 1000", "около 200"],
            "correct_answer": 0,
            "points": 6,
            "difficulty": "hard"
        },
        {
            "question": "Какая планета известна своими кольцами?",
            "options": ["Сатурн", "Юпитер", "Уран", "Нептун"],
            "correct_answer": 0,
            "points": 3,
            "difficulty": "easy"
        },
        {
            "question": "Какой элемент необходим для образования хлорофилла?",
            "options": ["Магний", "Железо", "Кальций", "Калий"],
            "correct_answer": 0,
            "points": 6,
            "difficulty": "hard"
        },
        {
            "question": "Сколько хромосом у шимпанзе?",
            "options": ["48", "46", "42", "44"],
            "correct_answer": 0,
            "points": 7,
            "difficulty": "hard"
        },
        {
            "question": "Какая звезда ближе всего к Земле?",
            "options": ["Солнце", "Проксима Центавра", "Сириус", "Альфа Центавра"],
            "correct_answer": 0,
            "points": 3,
            "difficulty": "easy"
        },
        {
            "question": "Какой газ вызывает парниковый эффект?",
            "options": ["Углекислый газ", "Кислород", "Азот", "Аргон"],
            "correct_answer": 0,
            "points": 4,
            "difficulty": "easy"
        },
        {
            "question": "Сколько отделов в головном мозге человека?",
            "options": ["5", "3", "7", "4"],
            "correct_answer": 0,
            "points": 6,
            "difficulty": "hard"
        },
        {
            "question": "Какая планета имеет самый большой перепад температур?",
            "options": ["Меркурий", "Венера", "Марс", "Земля"],
            "correct_answer": 0,
            "points": 6,
            "difficulty": "hard"
        },
        {
            "question": "Какой элемент составляет около 21% атмосферы Земли?",
            "options": ["Кислород", "Азот", "Углекислый газ", "Водород"],
            "correct_answer": 0,
            "points": 4,
            "difficulty": "easy"
        },
        {
            "question": "Сколько костей в черепе взрослого человека?",
            "options": ["22", "28", "32", "18"],
            "correct_answer": 0,
            "points": 6,
            "difficulty": "hard"
        },
        {
            "question": "Какая планета вращается 'лежа на боку'?",
            "options": ["Уран", "Нептун", "Сатурн", "Юпитер"],
            "correct_answer": 0,
            "points": 6,
            "difficulty": "hard"
        },
        {
            "question": "Какой витамин вырабатывается под воздействием солнечного света?",
            "options": ["Витамин D", "Витамин C", "Витамин A", "Витамин B12"],
            "correct_answer": 0,
            "points": 4,
            "difficulty": "easy"
        },
        {
            "question": "Сколько планет в Солнечной системе имеют кольца?",
            "options": ["4", "2", "3", "5"],
            "correct_answer": 0,
            "points": 7,
            "difficulty": "hard"
        },
        {
            "question": "Какая кислота находится в желудке?",
            "options": ["Соляная кислота", "Серная кислота", "Азотная кислота", "Уксусная кислота"],
            "correct_answer": 0,
            "points": 4,
            "difficulty": "easy"
        },
        {
            "question": "Сколько спутников у Венеры?",
            "options": ["0", "1", "2", "3"],
            "correct_answer": 0,
            "points": 5,
            "difficulty": "medium"
        },
        {
            "question": "Какой элемент имеет самую высокую температуру плавления?",
            "options": ["Вольфрам", "Железо", "Золото", "Серебро"],
            "correct_answer": 0,
            "points": 6,
            "difficulty": "hard"
        },
        {
            "question": "Сколько отделов в позвоночнике человека?",
            "options": ["5", "7", "3", "4"],
            "correct_answer": 0,
            "points": 5,
            "difficulty": "medium"
        },
        {
            "question": "Какая планета имеет самые длинные сутки?",
            "options": ["Венера", "Меркурий", "Марс", "Юпитер"],
            "correct_answer": 0,
            "points": 6,
            "difficulty": "hard"
        },
        {
            "question": "Какой газ используется в воздушных шарах?",
            "options": ["Гелий", "Водород", "Азот", "Кислород"],
            "correct_answer": 0,
            "points": 4,
            "difficulty": "easy"
        },
        {
            "question": "Сколько молочных зубов у человека?",
            "options": ["20", "28", "32", "24"],
            "correct_answer": 0,
            "points": 4,
            "difficulty": "easy"
        },
        {
            "question": "Какая планета имеет наибольшую плотность?",
            "options": ["Земля", "Меркурий", "Венера", "Марс"],
            "correct_answer": 0,
            "points": 6,
            "difficulty": "hard"
        },
        {
            "question": "Какой элемент является основой органической химии?",
            "options": ["Углерод", "Кислород", "Водород", "Азот"],
            "correct_answer": 0,
            "points": 4,
            "difficulty": "easy"
        },
        {
            "question": "Сколько пар ребер у человека?",
            "options": ["12", "10", "14", "8"],
            "correct_answer": 0,
            "points": 5,
            "difficulty": "medium"
        },
        {
            "question": "Какая звезда самая яркая на ночном небе?",
            "options": ["Сириус", "Полярная звезда", "Вега", "Арктур"],
            "correct_answer": 0,
            "points": 5,
            "difficulty": "medium"
        },
        {
            "question": "Какой газ составляет 78% атмосферы Земли?",
            "options": ["Азот", "Кислород", "Аргон", "Углекислый газ"],
            "correct_answer": 0,
            "points": 4,
            "difficulty": "easy"
        },
        {
            "question": "Сколько планет в Солнечной системе можно увидеть невооруженным глазом?",
            "options": ["5", "3", "6", "4"],
            "correct_answer": 0,
            "points": 6,
            "difficulty": "hard"
        },
        {
            "question": "Какая железа в организме человека самая большая?",
            "options": ["Печень", "Поджелудочная", "Щитовидная", "Вилочковая"],
            "correct_answer": 0,
            "points": 4,
            "difficulty": "easy"
        },
        {
            "question": "Какой элемент имеет атомный номер 1?",
            "options": ["Водород", "Гелий", "Литий", "Бор"],
            "correct_answer": 0,
            "points": 3,
            "difficulty": "easy"
        },
        {
            "question": "Сколько костей в стопе человека?",
            "options": ["26", "28", "24", "22"],
            "correct_answer": 0,
            "points": 6,
            "difficulty": "hard"
        },
        {
            "question": "Какая планета имеет наибольшее количество лун?",
            "options": ["Сатурн", "Юпитер", "Уран", "Нептун"],
            "correct_answer": 0,
            "points": 6,
            "difficulty": "hard"
        }
    ],
    "программирование": [
        {
            "question": "Какой язык программирования считается предком многих современных языков?",
            "options": ["C", "Python", "Java", "Fortran"],
            "correct_answer": 0,
            "points": 5,
            "difficulty": "medium"
        },
        {
            "question": "Что означает аббревиатура HTML?",
            "options": ["HyperText Markup Language", "HighTech Modern Language", "HyperTransfer Markup Language", "HighText Machine Language"],
            "correct_answer": 0,
            "points": 3,
            "difficulty": "easy"
        },
        {
            "question": "Какой оператор используется для сравнения на равенство в Python?",
            "options": ["=", "==", "===", "!="],
            "correct_answer": 1,
            "points": 4,
            "difficulty": "easy"
        },
        {
            "question": "Что такое ООП?",
            "options": ["Объектно-Ориентированное Программирование", "Основные Операции Процессора", "Общая Организация Программ", "Оптимальное Объемное Проектирование"],
            "correct_answer": 0,
            "points": 4,
            "difficulty": "easy"
        },
        {
            "question": "Какой язык используется для стилизации веб-страниц?",
            "options": ["HTML", "JavaScript", "CSS", "PHP"],
            "correct_answer": 2,
            "points": 3,
            "difficulty": "easy"
        },
        {
            "question": "Что такое Git?",
            "options": ["Язык программирования", "Система контроля версий", "Текстовый редактор", "Операционная система"],
            "correct_answer": 1,
            "points": 4,
            "difficulty": "medium"
        },
        {
            "question": "Какой тип данных в Python является изменяемым?",
            "options": ["int", "str", "tuple", "list"],
            "correct_answer": 3,
            "points": 5,
            "difficulty": "medium"
        },
        {
            "question": "Что такое API?",
            "options": ["Application Programming Interface", "Advanced Program Integration", "Automated Process Instruction", "Application Process Interface"],
            "correct_answer": 0,
            "points": 5,
            "difficulty": "medium"
        },
        {
            "question": "Какой метод используется для добавления элемента в список в Python?",
            "options": ["add()", "append()", "insert()", "push()"],
            "correct_answer": 1,
            "points": 4,
            "difficulty": "easy"
        },
        {
            "question": "Что такое SQL?",
            "options": ["Simple Query Language", "Structured Query Language", "System Query Logic", "Standard Question Language"],
            "correct_answer": 1,
            "points": 4,
            "difficulty": "medium"
        },
        {
            "question": "Какой символ используется для комментариев в Python?",
            "options": ["//", "#", "--", "/*"],
            "correct_answer": 1,
            "points": 3,
            "difficulty": "easy"
        },
        {
            "question": "Что такое рекурсия?",
            "options": ["Циклическое выполнение кода", "Вызов функции самой себя", "Быстрое выполнение программы", "Параллельное программирование"],
            "correct_answer": 1,
            "points": 6,
            "difficulty": "hard"
        },
        {
            "question": "Какой фреймворк для веб-разработки на Python самый популярный?",
            "options": ["Flask", "Django", "FastAPI", "Pyramid"],
            "correct_answer": 1,
            "points": 5,
            "difficulty": "medium"
        },
        {
            "question": "Что такое Big O notation?",
            "options": ["Система обозначений для больших чисел", "Обозначение сложности алгоритмов", "Стандарт для оформления кода", "Метод оптимизации программ"],
            "correct_answer": 1,
            "points": 7,
            "difficulty": "hard"
        },
        {
            "question": "Какой оператор используется для целочисленного деления в Python?",
            "options": ["/", "//", "%", "div"],
            "correct_answer": 1,
            "points": 4,
            "difficulty": "medium"
        },
        {
            "question": "Что такое Docker?",
            "options": ["Язык программирования", "Система контейнеризации", "База данных", "Фреймворк для тестирования"],
            "correct_answer": 1,
            "points": 6,
            "difficulty": "hard"
        },
        {
            "question": "Какой метод HTTP используется для получения данных?",
            "options": ["POST", "GET", "PUT", "DELETE"],
            "correct_answer": 1,
            "points": 4,
            "difficulty": "medium"
        },
        {
            "question": "Что такое JSON?",
            "options": ["JavaScript Object Notation", "Java Standard Object Network", "JavaScript Online Notation", "Java System Object Notation"],
            "correct_answer": 0,
            "points": 4,
            "difficulty": "easy"
        },
        {
            "question": "Какой алгоритм сортировки считается самым быстрым в среднем случае?",
            "options": ["Пузырьковая сортировка", "Быстрая сортировка", "Сортировка выбором", "Сортировка вставками"],
            "correct_answer": 1,
            "points": 6,
            "difficulty": "hard"
        },
        {
            "question": "Что такое MVC?",
            "options": ["Model-View-Controller", "Main-View-Component", "Module-View-Code", "Model-Value-Controller"],
            "correct_answer": 0,
            "points": 5,
            "difficulty": "medium"
        },
        {
            "question": "Какой тип базы данных использует SQL?",
            "options": ["Реляционная", "Документная", "Ключ-значение", "Графовая"],
            "correct_answer": 0,
            "points": 4,
            "difficulty": "medium"
        },
        {
            "question": "Что такое AJAX?",
            "options": ["Asynchronous JavaScript and XML", "Advanced JavaScript and XML", "Automated JavaScript Application", "Asynchronous Java and XML"],
            "correct_answer": 0,
            "points": 5,
            "difficulty": "medium"
        },
        {
            "question": "Какой оператор используется для наследования в Python?",
            "options": ["inherits", "extends", "super", "в скобках класса"],
            "correct_answer": 3,
            "points": 6,
            "difficulty": "hard"
        },
        {
            "question": "Что такое REST API?",
            "options": ["Representational State Transfer", "Remote System Transfer", "Resource State Transfer", "Rapid System Technology"],
            "correct_answer": 0,
            "points": 6,
            "difficulty": "hard"
        },
        {
            "question": "Какой метод используется для удаления элемента из словаря в Python?",
            "options": ["remove()", "delete()", "pop()", "discard()"],
            "correct_answer": 2,
            "points": 5,
            "difficulty": "medium"
        },
        {
            "question": "Что такое переменная в программировании?",
            "options": ["Константное значение", "Именованная область памяти", "Функция", "Цикл"],
            "correct_answer": 1,
            "points": 3,
            "difficulty": "easy"
        },
        {
            "question": "Какой язык программирования создан Microsoft?",
            "options": ["Java", "C#", "Python", "Ruby"],
            "correct_answer": 1,
            "points": 4,
            "difficulty": "medium"
        },
        {
            "question": "Что такое компилятор?",
            "options": ["Текстовый редактор", "Программа, переводящая код в машинный язык", "База данных", "Операционная система"],
            "correct_answer": 1,
            "points": 5,
            "difficulty": "medium"
        },
        {
            "question": "Какой язык используется для создания Android приложений?",
            "options": ["Java", "Swift", "C#", "Python"],
            "correct_answer": 0,
            "points": 4,
            "difficulty": "medium"
        },
        {
            "question": "Что такое алгоритм?",
            "options": ["Последовательность шагов для решения задачи", "Язык программирования", "База данных", "Графический интерфейс"],
            "correct_answer": 0,
            "points": 3,
            "difficulty": "easy"
        },
        {
            "question": "Какой язык программирования считается самым популярным в веб-разработке?",
            "options": ["JavaScript", "Python", "Java", "C++"],
            "correct_answer": 0,
            "points": 4,
            "difficulty": "easy"
        },
        {
            "question": "Что такое баг?",
            "options": ["Ошибка в программе", "Функция программы", "Тип данных", "Алгоритм"],
            "correct_answer": 0,
            "points": 3,
            "difficulty": "easy"
        },
        {
            "question": "Какой язык используется для разработки iOS приложений?",
            "options": ["Swift", "Java", "Kotlin", "C#"],
            "correct_answer": 0,
            "points": 4,
            "difficulty": "medium"
        },
        {
            "question": "Что такое фреймворк?",
            "options": ["Набор инструментов для разработки", "Язык программирования", "База данных", "Операционная система"],
            "correct_answer": 0,
            "points": 4,
            "difficulty": "medium"
        },
        {
            "question": "Какой язык имеет mascot в виде змеи?",
            "options": ["Python", "Java", "Ruby", "PHP"],
            "correct_answer": 0,
            "points": 3,
            "difficulty": "easy"
        },
        {
            "question": "Что такое IDE?",
            "options": ["Integrated Development Environment", "Internet Data Exchange", "Interactive Design Element", "International Development Engine"],
            "correct_answer": 0,
            "points": 4,
            "difficulty": "medium"
        },
        {
            "question": "Какой язык считается языком для Data Science?",
            "options": ["Python", "C++", "Java", "Go"],
            "correct_answer": 0,
            "points": 4,
            "difficulty": "medium"
        },
        {
            "question": "Что такое SQL инъекция?",
            "options": ["Вид кибератаки", "Метод оптимизации запросов", "Тип базы данных", "Язык программирования"],
            "correct_answer": 0,
            "points": 6,
            "difficulty": "hard"
        },
        {
            "question": "Какой язык создал Брендан Эйх?",
            "options": ["JavaScript", "Python", "Java", "C++"],
            "correct_answer": 0,
            "points": 5,
            "difficulty": "medium"
        },
        {
            "question": "Что такое паттерн проектирования?",
            "options": ["Типовое решение常见问题", "Язык программирования", "База данных", "Фреймворк"],
            "correct_answer": 0,
            "points": 5,
            "difficulty": "medium"
        },
        {
            "question": "Какой язык имеет сборщик мусора?",
            "options": ["Java", "C", "C++", "Assembly"],
            "correct_answer": 0,
            "points": 5,
            "difficulty": "medium"
        },
        {
            "question": "Что такое куки (cookies)?",
            "options": ["Небольшие файлы данных", "Язык программирования", "База данных", "Алгоритм"],
            "correct_answer": 0,
            "points": 4,
            "difficulty": "easy"
        },
        {
            "question": "Какой язык считается самым быстрым?",
            "options": ["C++", "Python", "Java", "JavaScript"],
            "correct_answer": 0,
            "points": 5,
            "difficulty": "medium"
        },
        {
            "question": "Что такое блокчейн?",
            "options": ["Распределенная база данных", "Язык программирования", "Фреймворк", "Алгоритм сортировки"],
            "correct_answer": 0,
            "points": 6,
            "difficulty": "hard"
        },
        {
            "question": "Какой язык используется для машинного обучения?",
            "options": ["Python", "C#", "Java", "Ruby"],
            "correct_answer": 0,
            "points": 4,
            "difficulty": "medium"
        },
        {
            "question": "Что такое веб-сокеты?",
            "options": ["Протокол для двусторонней связи", "Язык программирования", "База данных", "Фреймворк"],
            "correct_answer": 0,
            "points": 6,
            "difficulty": "hard"
        },
        {
            "question": "Какой язык имеет mascot в виде чашки кофе?",
            "options": ["Java", "Python", "JavaScript", "C++"],
            "correct_answer": 0,
            "points": 3,
            "difficulty": "easy"
        },
        {
            "question": "Что такое ORM?",
            "options": ["Object-Relational Mapping", "Object-Random Memory", "Online Resource Management", "Object-Runtime Module"],
            "correct_answer": 0,
            "points": 6,
            "difficulty": "hard"
        },
        {
            "question": "Какой язык считается функциональным?",
            "options": ["Haskell", "Java", "C++", "Python"],
            "correct_answer": 0,
            "points": 6,
            "difficulty": "hard"
        },
        {
            "question": "Что такое CI/CD?",
            "options": ["Continuous Integration/Continuous Deployment", "Computer Interface/Computer Design", "Code Integration/Code Development", "Continuous Input/Continuous Data"],
            "correct_answer": 0,
            "points": 6,
            "difficulty": "hard"
        },
        {
            "question": "Какой язык создал Гвидо ван Россум?",
            "options": ["Python", "Java", "C++", "JavaScript"],
            "correct_answer": 0,
            "points": 4,
            "difficulty": "medium"
        },
        {
            "question": "Что такое полиморфизм в ООП?",
            "options": ["Способность объектов иметь разные формы", "Наследование классов", "Инкапсуляция данных", "Абстракция"],
            "correct_answer": 0,
            "points": 6,
            "difficulty": "hard"
        },
        {
            "question": "Какой язык используется для системного программирования?",
            "options": ["C", "Python", "Java", "JavaScript"],
            "correct_answer": 0,
            "points": 5,
            "difficulty": "medium"
        },
        {
            "question": "Что такое DNS?",
            "options": ["Domain Name System", "Data Network Service", "Digital Naming Standard", "Domain Network Security"],
            "correct_answer": 0,
            "points": 5,
            "difficulty": "medium"
        },
        {
            "question": "Какой язык имеет статическую типизацию?",
            "options": ["Java", "Python", "JavaScript", "PHP"],
            "correct_answer": 0,
            "points": 5,
            "difficulty": "medium"
        },
        {
            "question": "Что такое XML?",
            "options": ["eXtensible Markup Language", "Extra Memory Language", "Xross Platform Markup Language", "Extended Module Library"],
            "correct_answer": 0,
            "points": 4,
            "difficulty": "medium"
        }
    ],
    "искусство": [
        {
            "question": "Кто написал картину 'Черный квадрат'?",
            "options": ["Василий Кандинский", "Казимир Малевич", "Пабло Пикассо", "Марк Шагал"],
            "correct_answer": 1,
            "points": 4,
            "difficulty": "easy"
        },
        {
            "question": "Какой композитор написал 'Лунную сонату'?",
            "options": ["Вольфганг Амадей Моцарт", "Людвиг ван Бетховен", "Иоганн Себастьян Бах", "Фредерик Шопен"],
            "correct_answer": 1,
            "points": 4,
            "difficulty": "easy"
        },
        {
            "question": "В каком веке жил Леонардо да Винчи?",
            "options": ["XIV век", "XV век", "XVI век", "XVII век"],
            "correct_answer": 1,
            "points": 5,
            "difficulty": "medium"
        },
        {
            "question": "Кто автор романа 'Война и мир'?",
            "options": ["Федор Достоевский", "Лев Толстой", "Антон Чехов", "Иван Тургенев"],
            "correct_answer": 1,
            "points": 4,
            "difficulty": "easy"
        },
        {
            "question": "Какой художественный стиль характеризуется изогнутыми линиями и орнаментальностью?",
            "options": ["Барокко", "Рококо", "Модерн", "Классицизм"],
            "correct_answer": 2,
            "points": 6,
            "difficulty": "hard"
        },
        {
            "question": "Кто скульптор 'Давида'?",
            "options": ["Донателло", "Микеланджело", "Бернини", "Роден"],
            "correct_answer": 1,
            "points": 5,
            "difficulty": "medium"
        },
        {
            "question": "В какой стране зародился стиль 'барокко' в архитектуре?",
            "options": ["Франция", "Италия", "Испания", "Германия"],
            "correct_answer": 1,
            "points": 6,
            "difficulty": "hard"
        },
        {
            "question": "Кто написал пьесу 'Ромео и Джульетта'?",
            "options": ["Уильям Шекспир", "Артур Миллер", "Бернард Шоу", "Оскар Уайльд"],
            "correct_answer": 0,
            "points": 3,
            "difficulty": "easy"
        },
        {
            "question": "Какой русский художник известен своими 'морскими' картинами?",
            "options": ["Иван Айвазовский", "Илья Репин", "Василий Суриков", "Виктор Васнецов"],
            "correct_answer": 0,
            "points": 5,
            "difficulty": "medium"
        },
        {
            "question": "Кто композитор балета 'Лебединое озеро'?",
            "options": ["Петр Чайковский", "Игорь Стравинский", "Сергей Прокофьев", "Модест Мусоргский"],
            "correct_answer": 0,
            "points": 4,
            "difficulty": "easy"
        },
        {
            "question": "Какая картина принадлежит кисти Сальвадора Дали?",
            "options": ["Крик", "Постоянство памяти", "Звездная ночь", "Девушка с жемчужной сережкой"],
            "correct_answer": 1,
            "points": 5,
            "difficulty": "medium"
        },
        {
            "question": "Кто написал 'Собор Парижской Богоматери'?",
            "options": ["Виктор Гюго", "Александр Дюма", "Оноре де Бальзак", "Гюстав Флобер"],
            "correct_answer": 0,
            "points": 5,
            "difficulty": "medium"
        },
        {
            "question": "Какой архитектор спроектировал собор Святого Петра в Риме?",
            "options": ["Донато Браманте", "Микеланджело", "Бернини", "Все вышеперечисленные"],
            "correct_answer": 3,
            "points": 7,
            "difficulty": "hard"
        },
        {
            "question": "Кто является автором скульптуры 'Мыслитель'?",
            "options": ["Огюст Роден", "Микеланджело", "Донателло", "Антонио Канова"],
            "correct_answer": 0,
            "points": 5,
            "difficulty": "medium"
        },
        {
            "question": "В каком городе находится музей Прадо?",
            "options": ["Мадрид", "Барселона", "Париж", "Рим"],
            "correct_answer": 0,
            "points": 4,
            "difficulty": "easy"
        },
        {
            "question": "Кто написал оперу 'Кармен'?",
            "options": ["Джордж Бизе", "Джузеппе Верди", "Вольфганг Моцарт", "Рихард Вагнер"],
            "correct_answer": 0,
            "points": 5,
            "difficulty": "medium"
        },
        {
            "question": "Какой художник основал направление кубизм?",
            "options": ["Пабло Пикассо", "Анри Матисс", "Василий Кандинский", "Сальвадор Дали"],
            "correct_answer": 0,
            "points": 6,
            "difficulty": "hard"
        },
        {
            "question": "Кто автор фрески 'Тайная вечеря'?",
            "options": ["Леонардо да Винчи", "Микеланджело", "Рафаэль", "Сандро Боттичелли"],
            "correct_answer": 0,
            "points": 5,
            "difficulty": "medium"
        },
        {
            "question": "В каком стиле писал Винсент Ван Гог?",
            "options": ["Импрессионизм", "Постимпрессионизм", "Экспрессионизм", "Сюрреализм"],
            "correct_answer": 1,
            "points": 6,
            "difficulty": "hard"
        },
        {
            "question": "Кто написал 'Анну Каренину'?",
            "options": ["Лев Толстой", "Федор Достоевский", "Антон Чехов", "Иван Тургенев"],
            "correct_answer": 0,
            "points": 4,
            "difficulty": "easy"
        },
        {
            "question": "Какой композитор написал 'Времена года'?",
            "options": ["Антонио Вивальди", "Иоганн Себастьян Бах", "Вольфганг Моцарт", "Людвиг ван Бетховен"],
            "correct_answer": 0,
            "points": 5,
            "difficulty": "medium"
        },
        {
            "question": "Кто является режиссером фильма 'Крестный отец'?",
            "options": ["Фрэнсис Форд Коппола", "Мартин Скорсезе", "Стивен Спилберг", "Альфред Хичкок"],
            "correct_answer": 0,
            "points": 5,
            "difficulty": "medium"
        },
        {
            "question": "В каком жанре писал Федор Достоевский?",
            "options": ["Реализм", "Романтизм", "Сентиментализм", "Классицизм"],
            "correct_answer": 0,
            "points": 6,
            "difficulty": "hard"
        },
        {
            "question": "Кто написал картину 'Утро в сосновом лесу'?",
            "options": ["Иван Шишкин", "Илья Репин", "Василий Перов", "Виктор Васнецов"],
            "correct_answer": 0,
            "points": 5,
            "difficulty": "medium"
        },
        {
            "question": "Какой русский композитор написал 'Щелкунчика'?",
            "options": ["Петр Чайковский", "Николай Римский-Корсаков", "Модест Мусоргский", "Сергей Прокофьев"],
            "correct_answer": 0,
            "points": 4,
            "difficulty": "easy"
        },
        {
            "question": "Кто является автором романа '1984'?",
            "options": ["Джордж Оруэлл", "Олдос Хаксли", "Рэй Брэдбери", "Артур Кларк"],
            "correct_answer": 0,
            "points": 5,
            "difficulty": "medium"
        },
        {
            "question": "В каком стиле построен Зимний дворец в Санкт-Петербурге?",
            "options": ["Барокко", "Классицизм", "Рококо", "Ампир"],
            "correct_answer": 0,
            "points": 6,
            "difficulty": "hard"
        },
        {
            "question": "Кто написал 'Гернику'?",
            "options": ["Пабло Пикассо", "Сальвадор Дали", "Жоан Миро", "Фрида Кало"],
            "correct_answer": 0,
            "points": 5,
            "difficulty": "medium"
        },
        {
            "question": "Какой художник является представителем поп-арта?",
            "options": ["Энди Уорхол", "Рой Лихтенштейн", "Кит Харинг", "Все вышеперечисленные"],
            "correct_answer": 3,
            "points": 6,
            "difficulty": "hard"
        },
        {
            "question": "Кто автор скульптуры 'Дискобол'?",
            "options": ["Мирон", "Поликлет", "Фидий", "Пракситель"],
            "correct_answer": 0,
            "points": 7,
            "difficulty": "hard"
        },
        {
            "question": "В каком городе находится Сикстинская капелла?",
            "options": ["Рим", "Флоренция", "Венеция", "Милан"],
            "correct_answer": 0,
            "points": 5,
            "difficulty": "medium"
        },
        {
            "question": "Кто написал 'Божественную комедию'?",
            "options": ["Данте Алигьери", "Джованни Боккаччо", "Франческо Петрарка", "Никколо Макиавелли"],
            "correct_answer": 0,
            "points": 5,
            "difficulty": "medium"
        },
        {
            "question": "Какой русский художник известен картинами на сказочные сюжеты?",
            "options": ["Виктор Васнецов", "Михаил Врубель", "Иван Билибин", "Все вышеперечисленные"],
            "correct_answer": 3,
            "points": 6,
            "difficulty": "hard"
        },
        {
            "question": "Кто композитор оперы 'Евгений Онегин'?",
            "options": ["Петр Чайковский", "Михаил Глинка", "Николай Римский-Корсаков", "Модест Мусоргский"],
            "correct_answer": 0,
            "points": 5,
            "difficulty": "medium"
        },
        {
            "question": "В каком стиле построен собор Василия Блаженного?",
            "options": ["Шатровый стиль", "Барокко", "Классицизм", "Готика"],
            "correct_answer": 0,
            "points": 6,
            "difficulty": "hard"
        },
        {
            "question": "Кто написал 'Три мушкетера'?",
            "options": ["Александр Дюма", "Виктор Гюго", "Оноре де Бальзак", "Гюстав Флобер"],
            "correct_answer": 0,
            "points": 4,
            "difficulty": "easy"
        },
        {
            "question": "Какой художник является основателем импрессионизма?",
            "options": ["Клод Моне", "Эдуард Мане", "Огюст Ренуар", "Эдгар Дега"],
            "correct_answer": 0,
            "points": 6,
            "difficulty": "hard"
        },
        {
            "question": "Кто автор романа 'Преступление и наказание'?",
            "options": ["Федор Достоевский", "Лев Толстой", "Антон Чехов", "Иван Тургенев"],
            "correct_answer": 0,
            "points": 5,
            "difficulty": "medium"
        },
        {
            "question": "В каком жанре работал композитор Иоганн Штраус?",
            "options": ["Вальс", "Симфония", "Опера", "Балет"],
            "correct_answer": 0,
            "points": 5,
            "difficulty": "medium"
        },
        {
            "question": "Кто написал картину 'Девочка с персиками'?",
            "options": ["Валентин Серов", "Илья Репин", "Василий Суриков", "Михаил Врубель"],
            "correct_answer": 0,
            "points": 5,
            "difficulty": "medium"
        },
        {
            "question": "Какой русский композитор написал 'Половецкие пляски'?",
            "options": ["Александр Бородин", "Николай Римский-Корсаков", "Модест Мусоргский", "Петр Чайковский"],
            "correct_answer": 0,
            "points": 6,
            "difficulty": "hard"
        },
        {
            "question": "Кто является архитектором Исаакиевского собора?",
            "options": ["Огюст Монферран", "Доменико Трезини", "Карл Росси", "Бартоломео Растрелли"],
            "correct_answer": 0,
            "points": 6,
            "difficulty": "hard"
        },
        {
            "question": "В каком стиле написана картина 'Крик'?",
            "options": ["Экспрессионизм", "Импрессионизм", "Сюрреализм", "Кубизм"],
            "correct_answer": 0,
            "points": 6,
            "difficulty": "hard"
        },
        {
            "question": "Кто автор повести 'Шинель'?",
            "options": ["Николай Гоголь", "Александр Пушкин", "Михаил Лермонтов", "Иван Тургенев"],
            "correct_answer": 0,
            "points": 5,
            "difficulty": "medium"
        },
        {
            "question": "Какой художник написал 'Последний день Помпеи'?",
            "options": ["Карл Брюллов", "Александр Иванов", "Павел Федотов", "Орест Кипренский"],
            "correct_answer": 0,
            "points": 6,
            "difficulty": "hard"
        },
        {
            "question": "Кто композитор 'Весны священной'?",
            "options": ["Игорь Стравинский", "Сергей Прокофьев", "Дмитрий Шостакович", "Арам Хачатурян"],
            "correct_answer": 0,
            "points": 6,
            "difficulty": "hard"
        },
        {
            "question": "В каком городе находится галерея Уффици?",
            "options": ["Флоренция", "Рим", "Венеция", "Милан"],
            "correct_answer": 0,
            "points": 5,
            "difficulty": "medium"
        },
        {
            "question": "Кто написал 'Горе от ума'?",
            "options": ["Александр Грибоедов", "Александр Пушкин", "Николай Гоголь", "Михаил Лермонтов"],
            "correct_answer": 0,
            "points": 5,
            "difficulty": "medium"
        },
        {
            "question": "Какой русский художник известен как 'мастер морского пейзажа'?",
            "options": ["Иван Айвазовский", "Архип Куинджи", "Исаак Левитан", "Алексей Саврасов"],
            "correct_answer": 0,
            "points": 4,
            "difficulty": "easy"
        },
        {
            "question": "Кто автор оперы 'Князь Игорь'?",
            "options": ["Александр Бородин", "Николай Римский-Корсаков", "Модест Мусоргский", "Петр Чайковский"],
            "correct_answer": 0,
            "points": 6,
            "difficulty": "hard"
        },
        {
            "question": "В каком стиле построен Храм Христа Спасителя?",
            "options": ["Русско-византийский", "Барокко", "Классицизм", "Готика"],
            "correct_answer": 0,
            "points": 6,
            "difficulty": "hard"
        }
    ],
    "спорт": [
        {
            "question": "Какая страна выиграла наибольшее количество золотых медалей на летних Олимпийских играх в истории?",
            "options": ["Китай", "Россия", "США", "Великобритания"],
            "correct_answer": 2,
            "points": 6,
            "difficulty": "hard"
        },
        {
            "question": "В каком виде спорта прославился Майкл Джордан?",
            "options": ["Бейсбол", "Баскетбол", "Американский футбол", "Гольф"],
            "correct_answer": 1,
            "points": 3,
            "difficulty": "easy"
        },
        {
            "question": "Сколько игроков входит в состав одной регбийной команды на поле?",
            "options": ["11", "15", "13", "9"],
            "correct_answer": 1,
            "points": 7,
            "difficulty": "hard"
        },
        {
            "question": "Кто holds рекорд по количеству голов в футболе за всю историю?",
            "options": ["Пеле", "Криштиану Роналду", "Лионель Месси", "Герд Мюллер"],
            "correct_answer": 1,
            "points": 5,
            "difficulty": "medium"
        },
        {
            "question": "В каком году проходили Олимпийские игры в Москве?",
            "options": ["1976", "1980", "1984", "1972"],
            "correct_answer": 1,
            "points": 5,
            "difficulty": "medium"
        },
        {
            "question": "Какой теннисист выиграл наибольшее количество турниров Большого шлема?",
            "options": ["Новак Джокович", "Рафаэль Надаль", "Роджер Федерер", "Пит Сампрас"],
            "correct_answer": 0,
            "points": 6,
            "difficulty": "hard"
        },
        {
            "question": "Сколько периодов в матче хоккея с шайбой?",
            "options": ["2", "3", "4", "5"],
            "correct_answer": 1,
            "points": 4,
            "difficulty": "easy"
        },
        {
            "question": "Какая страна является родиной дзюдо?",
            "options": ["Китай", "Корея", "Япония", "Вьетнам"],
            "correct_answer": 2,
            "points": 5,
            "difficulty": "medium"
        },
        {
            "question": "Кто был самым молодым чемпионом Формулы-1?",
            "options": ["Льюис Хэмилтон", "Себастьян Феттель", "Макс Ферстаппен", "Фернандо Алонсо"],
            "correct_answer": 2,
            "points": 7,
            "difficulty": "hard"
        },
        {
            "question": "В каком виде спорта разыгрывается Кубок Стэнли?",
            "options": ["Баскетбол", "Хоккей с шайбой", "Регби", "Американский футбол"],
            "correct_answer": 1,
            "points": 4,
            "difficulty": "easy"
        },
        {
            "question": "Сколько игроков в баскетбольной команде на площадке?",
            "options": ["5", "6", "7", "8"],
            "correct_answer": 0,
            "points": 3,
            "difficulty": "easy"
        },
        {
            "question": "Какая страна выиграла первый чемпионат мира по футболу?",
            "options": ["Уругвай", "Бразилия", "Аргентина", "Италия"],
            "correct_answer": 0,
            "points": 6,
            "difficulty": "hard"
        },
        {
            "question": "В каком году состоялся первый современный Олимпийские игры?",
            "options": ["1896", "1900", "1888", "1912"],
            "correct_answer": 0,
            "points": 5,
            "difficulty": "medium"
        },
        {
            "question": "Кто является рекордсменом по количеству титулов в теннисном Уимблдоне?",
            "options": ["Роджер Федерер", "Новак Джокович", "Пит Сампрас", "Рафаэль Надаль"],
            "correct_answer": 0,
            "points": 6,
            "difficulty": "hard"
        },
        {
            "question": "Сколько километров составляет марафонская дистанция?",
            "options": ["42.195 км", "40.2 км", "45 км", "38.5 км"],
            "correct_answer": 0,
            "points": 5,
            "difficulty": "medium"
        },
        {
            "question": "Какая страна является родиной футбола?",
            "options": ["Англия", "Бразилия", "Италия", "Германия"],
            "correct_answer": 0,
            "points": 4,
            "difficulty": "easy"
        },
        {
            "question": "Кто выиграл наибольшее количество чемпионатов мира по шахматам?",
            "options": ["Гарри Каспаров", "Магнус Карлсен", "Эмануил Ласкер", "Все вышеперечисленные"],
            "correct_answer": 0,
            "points": 7,
            "difficulty": "hard"
        },
        {
            "question": "Сколько очков дает трехочковый бросок в баскетболе?",
            "options": ["3", "2", "1", "4"],
            "correct_answer": 0,
            "points": 3,
            "difficulty": "easy"
        },
        {
            "question": "Какая страна принимала Олимпийские игры 2014 года?",
            "options": ["Россия", "Бразилия", "Китай", "Великобритания"],
            "correct_answer": 0,
            "points": 4,
            "difficulty": "easy"
        },
        {
            "question": "Кто является самым титулованным олимпийским чемпионом?",
            "options": ["Майкл Фелпс", "Лариса Латынина", "Пааво Нурми", "Марк Спитц"],
            "correct_answer": 0,
            "points": 5,
            "difficulty": "medium"
        },
        {
            "question": "Сколько игроков в волейбольной команде на площадке?",
            "options": ["6", "5", "7", "8"],
            "correct_answer": 0,
            "points": 4,
            "difficulty": "easy"
        },
        {
            "question": "Какая страна выиграла наибольшее количество чемпионатов мира по футболу?",
            "options": ["Бразилия", "Германия", "Италия", "Аргентина"],
            "correct_answer": 0,
            "points": 5,
            "difficulty": "medium"
        },
        {
            "question": "В каком виде спорта используется термин 'гол-пасс'?",
            "options": ["Хоккей", "Футбол", "Баскетбол", "Водное поло"],
            "correct_answer": 0,
            "points": 5,
            "difficulty": "medium"
        },
        {
            "question": "Кто является самым молодым чемпионом мира по футболу?",
            "options": ["Пеле", "Килиан Мбаппе", "Марадона", "Зидан"],
            "correct_answer": 0,
            "points": 6,
            "difficulty": "hard"
        },
        {
            "question": "Сколько сетов в матче большого тенниса у мужчин?",
            "options": ["3 или 5", "2 или 3", "только 3", "только 5"],
            "correct_answer": 0,
            "points": 5,
            "difficulty": "medium"
        },
        {
            "question": "Какая страна является родиной кёрлинга?",
            "options": ["Шотландия", "Канада", "Швеция", "Норвегия"],
            "correct_answer": 0,
            "points": 6,
            "difficulty": "hard"
        },
        {
            "question": "Кто выиграл наибольшее количество Суперкубков UEFA?",
            "options": ["Реал Мадрид", "Барселона", "Милан", "Ливерпуль"],
            "correct_answer": 0,
            "points": 7,
            "difficulty": "hard"
        },
        {
            "question": "Сколько кругов в гонке Формулы-1 'Гран-при Монако'?",
            "options": ["78", "70", "65", "80"],
            "correct_answer": 0,
            "points": 7,
            "difficulty": "hard"
        },
        {
            "question": "Какая страна является родиной бадминтона?",
            "options": ["Англия", "Индия", "Китай", "Япония"],
            "correct_answer": 0,
            "points": 6,
            "difficulty": "hard"
        },
        {
            "question": "Кто является рекордсменом по количеству голов в одном сезоне НХЛ?",
            "options": ["Уэйн Гретцки", "Александр Овечкин", "Марио Лемьё", "Горди Хоу"],
            "correct_answer": 0,
            "points": 7,
            "difficulty": "hard"
        },
        {
            "question": "Сколько минут длится тайм в футболе?",
            "options": ["45", "40", "50", "35"],
            "correct_answer": 0,
            "points": 3,
            "difficulty": "easy"
        },
        {
            "question": "Какая страна выиграла первый Кубок Азии по футболу?",
            "options": ["Южная Корея", "Япония", "Иран", "Саудовская Аравия"],
            "correct_answer": 0,
            "points": 7,
            "difficulty": "hard"
        },
        {
            "question": "Кто является самым титулованным игроком НБА?",
            "options": ["Билл Рассел", "Майкл Джордан", "Карим Абдул-Джаббар", "Леброн Джеймс"],
            "correct_answer": 0,
            "points": 6,
            "difficulty": "hard"
        },
        {
            "question": "Сколько весит ядро для толкания у мужчин?",
            "options": ["7.26 кг", "6 кг", "8 кг", "5 кг"],
            "correct_answer": 0,
            "points": 6,
            "difficulty": "hard"
        },
        {
            "question": "Какая страна является родиной настольного тенниса?",
            "options": ["Англия", "Китай", "Япония", "США"],
            "correct_answer": 0,
            "points": 6,
            "difficulty": "hard"
        },
        {
            "question": "Кто выиграл наибольшее количество 'Золотых мячей'?",
            "options": ["Лионель Месси", "Криштиану Роналду", "Йохан Кройф", "Мишель Платини"],
            "correct_answer": 0,
            "points": 5,
            "difficulty": "medium"
        },
        {
            "question": "Сколько игроков в бейсбольной команде на поле?",
            "options": ["9", "10", "8", "11"],
            "correct_answer": 0,
            "points": 5,
            "difficulty": "medium"
        },
        {
            "question": "Какая страна является родиной гребли?",
            "options": ["Англия", "США", "Германия", "Франция"],
            "correct_answer": 0,
            "points": 6,
            "difficulty": "hard"
        },
        {
            "question": "Кто является рекордсменом по количеству побед в Тур де Франс?",
            "options": ["Лэнс Армстронг", "Эдди Меркс", "Мигель Индурайн", "Бернар Ино"],
            "correct_answer": 1,
            "points": 7,
            "difficulty": "hard"
        },
        {
            "question": "Сколько очков дает touchdown в американском футболе?",
            "options": ["6", "7", "5", "3"],
            "correct_answer": 0,
            "points": 6,
            "difficulty": "hard"
        },
        {
            "question": "Какая страна является родиной биатлона?",
            "options": ["Норвегия", "Швеция", "Финляндия", "Россия"],
            "correct_answer": 0,
            "points": 6,
            "difficulty": "hard"
        },
        {
            "question": "Кто выиграл наибольшее количество чемпионатов мира по ралли?",
            "options": ["Себастьен Лёб", "Микка Хямюляйнен", "Юха Канккунен", "Томми Мякинен"],
            "correct_answer": 0,
            "points": 7,
            "difficulty": "hard"
        },
        {
            "question": "Сколько игроков в команде по водному поло?",
            "options": ["7", "6", "8", "5"],
            "correct_answer": 0,
            "points": 5,
            "difficulty": "medium"
        },
        {
            "question": "Какая страна является родиной синхронного плавания?",
            "options": ["Канада", "США", "Россия", "Австралия"],
            "correct_answer": 0,
            "points": 6,
            "difficulty": "hard"
        },
        {
            "question": "Кто является рекордсменом по количеству побед в Гран-при Формулы-1?",
            "options": ["Льюис Хэмилтон", "Михаэль Шумахер", "Себастьян Феттель", "Айртон Сенна"],
            "correct_answer": 0,
            "points": 5,
            "difficulty": "medium"
        },
        {
            "question": "Сколько весит молот для метания у мужчин?",
            "options": ["7.26 кг", "6 кг", "8 кг", "5 кг"],
            "correct_answer": 0,
            "points": 6,
            "difficulty": "hard"
        },
        {
            "question": "Какая страна является родиной спортивной гимнастики?",
            "options": ["Германия", "Франция", "Швеция", "Греция"],
            "correct_answer": 0,
            "points": 6,
            "difficulty": "hard"
        },
        {
            "question": "Кто выиграл наибольшее количество чемпионатов мира по MotoGP?",
            "options": ["Джакомо Агостини", "Валентино Росси", "Марк Маркес", "Мик Дуэн"],
            "correct_answer": 0,
            "points": 7,
            "difficulty": "hard"
        },
        {
            "question": "Сколько игроков в команде по регби-7?",
            "options": ["7", "6", "8", "9"],
            "correct_answer": 0,
            "points": 5,
            "difficulty": "medium"
        },
        {
            "question": "Какая страна является родиной скейтбординга?",
            "options": ["США", "Австралия", "Бразилия", "Канада"],
            "correct_answer": 0,
            "points": 5,
            "difficulty": "medium"
        },
        {
            "question": "Кто является рекордсменом по количеству побед в Уимблдоне среди женщин?",
            "options": ["Мартина Навратилова", "Серена Уильямс", "Штеффи Граф", "Маргарет Корт"],
            "correct_answer": 0,
            "points": 6,
            "difficulty": "hard"
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
    logger.info("База данных вопросов заполнена")

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
        logger.info(f"Профиль пользователя {user_id} сохранен")
    except Exception as e:
        logger.error(f"Ошибка при сохранении профиля: {e}")

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
        logger.error(f"Ошибка при загрузке профиля: {e}")
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
        logger.error(f"Ошибка при сохранении чат-сессии: {e}")

def clear_chat_session(user_id):
    cursor = db_connection.cursor()
    try:
        cursor.execute('DELETE FROM chat_sessions WHERE user_id = ?', (user_id,))
        db_connection.commit()
        if user_id in user_chat_sessions:
            del user_chat_sessions[user_id]
    except Exception as e:
        logger.error(f"Ошибка при очистке чат-сессии: {e}")

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
        logger.info(f"Ответ ИИ сохранен для пользователя {user_id}")
    except Exception as e:
        logger.error(f"Ошибка при сохранении ответа ИИ: {e}")

def increment_ai_response_usage(response_id):
    cursor = db_connection.cursor()
    try:
        cursor.execute('''
            UPDATE ai_responses SET used_count = used_count + 1 WHERE id = ?
        ''', (response_id,))
        db_connection.commit()
    except Exception as e:
        logger.error(f"Ошибка при обновлении счетчика использования: {e}")

def query_gemini(user_id, question):
    try:
        saved_response = get_saved_ai_response(user_id, question)
        if saved_response:
            logger.info(f"Использован сохраненный ответ для пользователя {user_id}")
            return f"💾 *Ответ из сохраненных:*\n\n{saved_response}"

        if model is None:
            return "❌ AI сервис временно недоступен.\n\nПожалуйста, проверьте настройки API ключа Gemini."

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
            reply = future.result(timeout=30)  # 30 секунд таймаут

        if reply:
            messages.append({"role": "user", "content": question})
            messages.append({"role": "assistant", "content": reply})

            if len(messages) > 20:
                messages = messages[-20:]

            save_chat_session(user_id, messages)
            return reply
        else:
            return "❌ Не удалось получить ответ от AI. Ответ пустой или некорректный."

    except Exception as e:
        logger.error(f"Ошибка Gemini API: {str(e)}")

        error_msg = str(e).lower()

        if "quota" in error_msg or "billing" in error_msg:
            return "❌ Превышена квота API или проблема с биллингом. Проверьте настройки Google AI Studio."
        elif "safety" in error_msg or "blocked" in error_msg:
            return "❌ Запрос был заблокирован системой безопасности. Попробуйте переформулировать вопрос."
        elif "api key" in error_msg:
            return "❌ Проблема с API ключом. Проверьте корректность ключа Gemini."
        elif "network" in error_msg or "connection" in error_msg:
            return "❌ Проблема с сетью. Проверьте интернет-соединение."
        elif "timeout" in error_msg:
            return "❌ Время ожидания ответа истекло. Попробуйте еще раз."
        else:
            return f"❌ Произошла ошибка при обращении к AI: {str(e)}\n\nПопробуйте переформулировать вопрос или повторить позже."

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
        buttons = ["🎯 Начать викторину", "🤖 Задать вопрос AI", "📊 Моя статистика",
                  "🏆 Топ игроков", "👤 Мой профиль", "📈 Сравнить", "🧹 Очистить историю", "❓ Помощь"]
        markup.add(*buttons)
    elif options:
        buttons = [f"{chr(65+i)}) {option}" for i, option in enumerate(options)]
        for i in range(0, len(buttons), 2):
            if i + 1 < len(buttons):
                markup.add(buttons[i], buttons[i + 1])
            else:
                markup.add(buttons[i])
        markup.add("⏹️ Стоп")

    return markup

def create_topic_keyboard():
    cursor = db_connection.cursor()
    cursor.execute("SELECT DISTINCT topic FROM questions")
    topics = [row[0] for row in cursor.fetchall()]

    markup = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(*topics)
    markup.add("🎲 Случайная тема", "🔙 Назад")
    return markup

def format_question(question_data, question_number):
    question = f"❓ Вопрос {question_number}:\n{question_data['question']}\n\n"
    options = question_data['options']
    for i, option in enumerate(options):
        question += f"{chr(65+i)}) {option}\n"
    question += f"\n🏅 Баллов за правильный ответ: {question_data['points']}"
    return question

def create_feedback_keyboard():
    markup = telebot.types.InlineKeyboardMarkup()
    markup.row(
        telebot.types.InlineKeyboardButton("👍 Понравился", callback_data="feedback_like"),
        telebot.types.InlineKeyboardButton("👎 Не понравился", callback_data="feedback_dislike")
    )
    return markup

def create_compare_keyboard():
    markup = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    buttons = ["📊 Сравнить с топ-игроками", "👥 Сравнить со средним", "📈 Сравнить по точности", "🔙 Назад"]
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
        bot.send_message(message.chat.id, "📊 Пока недостаточно данных для сравнения. Сыграйте несколько викторин!")
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
    
    compare_text = f"📊 *Сравнение статистики*\n"
    compare_text += f"👤 *Твоя статистика:*\n"
    compare_text += f"🏅 Баллы: {user_stats['total_points']}\n"
    compare_text += f"✅ Правильные ответы: {user_stats['correct_answers']}/{user_stats['total_questions']}\n"
    compare_text += f"🎯 Точность: {user_accuracy:.1f}%\n"
    compare_text += f"🎮 Игр сыграно: {user_stats['games_played']}\n\n"
    
    compare_text += f"📈 *Общая статистика {'в этой группе' if chat_type == 'group' else 'глобальная'}:*\n"
    compare_text += f"👥 Всего игроков: {total_players}\n"
    compare_text += f"📊 Средние баллы: {avg_points:.0f}\n"
    compare_text += f"🎯 Средняя точность: {avg_accuracy:.1f}%\n"
    compare_text += f"⭐ Максимум баллов: {max_points}\n"
    compare_text += f"💎 Максимум точности: {max_accuracy:.1f}%\n\n"

    points_diff = user_stats['total_points'] - avg_points
    accuracy_diff = user_accuracy - avg_accuracy
    
    compare_text += f"🆚 *Сравнение со средним:*\n"
    if points_diff > 0:
        compare_text += f"🏅 Ты выше среднего на {points_diff:.0f} баллов! 🎉\n"
    elif points_diff < 0:
        compare_text += f"🏅 Ты ниже среднего на {abs(points_diff):.0f} баллов 💪\n"
    else:
        compare_text += f"🏅 Ты на среднем уровне баллов\n"
    
    if accuracy_diff > 0:
        compare_text += f"🎯 Точность выше среднего на {accuracy_diff:.1f}%! 🎉\n"
    elif accuracy_diff < 0:
        compare_text += f"🎯 Точность ниже среднего на {abs(accuracy_diff):.1f}% 💪\n"
    else:
        compare_text += f"🎯 Точность на среднем уровне\n"
    
    if top_players:
        compare_text += f"\n🏆 *Топ-3 игрока:*\n"
        for i, (first_name, username, points, accuracy) in enumerate(top_players, 1):
            name = f"@{username}" if username else first_name
            medal = ["🥇", "🥈", "🥉"][i-1]
            
            if user_stats['total_points'] == points:
                compare_text += f"{medal} {name} - {points} баллов ({accuracy:.1f}%) ← ЭТО ТЫ! 🎉\n"
            else:
                compare_text += f"{medal} {name} - {points} баллов ({accuracy:.1f}%)\n"
            
            if i == 1 and user_stats['total_points'] < points:
                diff = points - user_stats['total_points']
                compare_text += f"   📍 До лидера: {diff} баллов\n"
    
    if user_stats['total_questions'] == 0:
        compare_text += f"\n💡 *Совет:* Сыграй свою первую викторину командой /quiz!"
    elif user_stats['total_points'] < avg_points:
        compare_text += f"\n💪 *Мотивация:* Продолжай играть! Ты сможешь обогнать средний результат!"
    else:
        compare_text += f"\n🎉 *Отлично!* Ты впереди большинства игроков! Продолжай в том же духе!"
    
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
            f"С возвращением, {user_profile.name}! 👋\n\n"
            f"Я помню о тебе:\n"
            f"👤 Имя: {user_profile.name}\n"
            f"🎂 Возраст: {user_profile.age}\n"
            f"🏙 Город: {user_profile.city}\n\n"
            "Теперь я могу отвечать на ЛЮБЫЕ твои вопросы! 🤖\n"
            "Просто напиши мне что-нибудь, и я постараюсь помочь!\n\n"
            "Выбери режим из меню ниже:"
        )
        bot.send_message(message.chat.id, welcome_text, reply_markup=create_keyboard(main_menu=True), parse_mode='Markdown')
    else:
        user_profile.waiting_for = 'name'
        bot.send_message(
            message.chat.id,
            f"Привет! 👋 Давай познакомимся!\n\n"
            f"Как тебя зовут?",
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
        "📖 *Помощь и команды бота*\n\n"
        
        "🎯 *Викторина*:\n"
        "• /quiz или кнопка '🎯 Начать викторину' - начать викторину\n"
        "• Выбирай тему: история, география, наука, программирование, искусство, спорт\n"
        "• Отвечай на вопросы и набирай баллы\n"
        "• Нажми '⏹️ Стоп' чтобы остановить викторину\n\n"
        
        "🤖 *AI помощник*:\n"
        "• /ai или кнопка '🤖 Задать вопрос AI' - задать любой вопрос\n"
        "• Просто напиши любой вопрос в чат\n"
        "• Используется Google Gemini AI\n"
        "• Бот помнит контекст разговора\n"
        "• 👍/👎 - оцени ответы ИИ для улучшения\n\n"
        
        "📊 *Статистика и рейтинг*:\n"
        "• /stats или кнопка '📊 Моя статистика' - твоя статистика\n"
        "• /top или кнопка '🏆 Топ игроков' - таблица лидеров\n"
        "• /compare или кнопка '📈 Сравнить' - сравнить с другими игроками\n\n"
        
        "👤 *Профиль*:\n"
        "• /profile или кнопка '👤 Мой профиль' - просмотр профиля\n"
        "• /start - заполнить/изменить профиль\n\n"
        
        "⚙️ *Другие команды*:\n"
        "• /clear или кнопка '🧹 Очистить историю' - очистить историю чата\n"
        "• /help или кнопка '❓ Помощь' - это сообщение\n"
        "• /start - перезапустить бота\n\n"
        
        "🎮 *Как играть*:\n"
        "1. Нажми '🎯 Начать викторину'\n"
        "2. Выбери тему или '🎲 Случайная тема'\n"
        "3. Отвечай на вопросы выбирая A, B, C или D\n"
        "4. Набирай баллы и улучшай свою статистику!\n\n"
        
        "💡 *Совет*: Просто напиши любой вопрос в чат - я отвечу на него! 🤖\n\n"
        
        "*Удачи в викторине!* 🚀"
    )
    bot.send_message(message.chat.id, help_text, parse_mode='Markdown')

def start_quiz_command(message, chat_type):
    user_id = message.from_user.id
    chat_id = message.chat.id

    user_quiz = get_user_quiz(user_id, chat_id, chat_type)
    user_quiz.waiting_for_topic = True

    bot.send_message(
        message.chat.id,
        f"🎯 {message.from_user.first_name}, выбери тему для викторины:",
        reply_markup=create_topic_keyboard()
    )

def stats_command(message, chat_type):
    user_id = message.from_user.id
    chat_id = message.chat.id
    stats = get_user_stats(user_id, chat_id, chat_type)

    accuracy = (stats['correct_answers'] / stats['total_questions'] * 100) if stats['total_questions'] > 0 else 0

    stats_text = (
        f"📊 Статистика {message.from_user.first_name}:\n\n"
        f"🏅 Всего баллов: {stats['total_points']}\n"
        f"✅ Правильных ответов: {stats['correct_answers']}\n"
        f"📝 Всего вопросов: {stats['total_questions']}\n"
        f"🎯 Точность: {accuracy:.1f}%\n"
        f"🎮 Сыграно игр: {stats['games_played']}\n"
        f"⏰ Последняя игра: {stats['last_played'] or 'Никогда'}"
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
        bot.send_message(message.chat.id, "🏆 Пока нет игроков в таблице лидеров! Стань первым! 🎯")
        return

    top_text = f"🏆 Топ игроков {'в этой группе' if chat_type == 'group' else 'глобальный'}:\n\n"

    for i, (first_name, username, points, correct, total) in enumerate(leaderboard, 1):
        accuracy = (correct / total * 100) if total > 0 else 0
        name = f"@{username}" if username else first_name
        medal = ["🥇", "🥈", "🥉"][i-1] if i <= 3 else f"{i}."

        top_text += f"{medal} {name} - {points} баллов ({accuracy:.1f}%)\n"

    bot.send_message(message.chat.id, top_text)

def ai_command(message):
    bot.send_message(
        message.chat.id,
        "🤖 *Режим AI Помощника*\n\n"
        "Задайте ЛЮБОЙ вопрос, и я постараюсь на него ответить! 🚀\n"
        "Я помню контекст нашего разговора.\n\n"
        "Примеры вопросов:\n"
        "• Объясни квантовую физику простыми словами\n"
        "• Расскажи о истории Древнего Рима\n"
        "Жду ваш вопрос...",
        parse_mode='Markdown'
    )

def profile_command(message):
    user_id = message.from_user.id
    user_profile = get_user_profile(user_id)

    if user_profile.name and user_profile.age and user_profile.city:
        profile_text = (
            f"👤 Твой профиль:\n\n"
            f"Имя: {user_profile.name}\n"
            f"Возраст: {user_profile.age}\n"
            f"Город: {user_profile.city}\n\n"
            f"Хочешь изменить информацию? Напиши /start заново!"
        )
    else:
        profile_text = (
            "❌ Информация о тебе не заполнена.\n\n"
            "Напиши /start чтобы представиться!"
        )

    bot.send_message(message.chat.id, profile_text)

def clear_history_command(message):
    user_id = message.from_user.id
    clear_chat_session(user_id)
    bot.send_message(
        message.chat.id,
        "🧹 История разговора очищена! Начинаем новый диалог!",
        reply_markup=create_keyboard(main_menu=True)
    )

@bot.message_handler(func=lambda message: message.text in [
    "🎯 Начать викторину", "🤖 Задать вопрос AI", "📊 Моя статистика",
    "🏆 Топ игроков", "👤 Мой профиль", "📈 Сравнить", "🧹 Очистить историю", "❓ Помощь"
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

    if message.text == "🎯 Начать викторину":
        start_quiz_command(message, chat_type)
    elif message.text == "🤖 Задать вопрос AI":
        ai_command(message)
    elif message.text == "📊 Моя статистика":
        stats_command(message, chat_type)
    elif message.text == "🏆 Топ игроков":
        top_command(message, chat_type)
    elif message.text == "👤 Мой профиль":
        profile_command(message)
    elif message.text == "📈 Сравнить":
        compare_stats_command(message, chat_type)
    elif message.text == "🧹 Очистить историю":
        clear_history_command(message)
    elif message.text == "❓ Помощь":
        help_command(message)

@bot.message_handler(func=lambda message: get_user_profile(message.from_user.id).waiting_for is not None)
def handle_profile_info(message):
    user_id = message.from_user.id
    user_profile = get_user_profile(user_id)

    if user_profile.waiting_for == 'name':
        user_profile.name = message.text
        user_profile.waiting_for = 'age'
        bot.send_message(message.chat.id, f"Приятно познакомиться, {user_profile.name}! 🎉\n\nСколько тебе лет?")

    elif user_profile.waiting_for == 'age':
        try:
            age = int(message.text)
            if age < 1 or age > 120:
                bot.send_message(message.chat.id, "Пожалуйста, введите реальный возраст (1-120 лет):")
                return
            user_profile.age = age
            user_profile.waiting_for = 'city'
            bot.send_message(message.chat.id, f"Отлично! А из какого ты города?")
        except ValueError:
            bot.send_message(message.chat.id, "Пожалуйста, введите возраст цифрами:")

    elif user_profile.waiting_for == 'city':
        user_profile.city = message.text
        user_profile.waiting_for = None

        save_user_profile_to_db(user_id, user_profile)

        welcome_text = (
            f"Супер! 🎉 Вот что я узнал о тебе:\n\n"
            f"👤 Имя: {user_profile.name}\n"
            f"🎂 Возраст: {user_profile.age}\n"
            f"🏙 Город: {user_profile.city}\n\n"
            f"Теперь я могу отвечать на ЛЮБЫЕ твои вопросы! 🤖\n"
            f"Просто напиши мне что-нибудь, и я постараюсь помочь!\n\n"
            f"Выбери режим из меню ниже:"
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
            
            bot.answer_callback_query(call.id, "✅ Ответ сохранен! Буду использовать его в будущем.")
            bot.edit_message_text(
                f"🤖 *AI Ответ:*\n\n{response}\n\n✅ *Ответ сохранен в базу данных*",
                call.message.chat.id,
                call.message.message_id,
                parse_mode='Markdown'
            )
        else:
            bot.answer_callback_query(call.id, "⚠️ Информация об ответе не найдена")
    
    elif call.data == 'feedback_dislike':
        if user_id in pending_ai_responses and message_id in pending_ai_responses[user_id]:
            question, old_response = pending_ai_responses[user_id][message_id]
            
            del pending_ai_responses[user_id][message_id]
            
            bot.answer_callback_query(call.id, "🔄 Генерирую новый ответ...")
            
            new_response = query_gemini(user_id, question)
            
            sent_message = bot.send_message(
                call.message.chat.id,
                f"🤖 *AI Ответ (обновленный):*\n\n{new_response}",
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

    if message.text == "⏹️ Стоп":
        if user_quiz.quiz_started:
            end_quiz(message, user_quiz)
        else:
            bot.send_message(message.chat.id, "❌ Викторина не активна.",
                           reply_markup=create_keyboard(main_menu=True))
        return

    if message.text == "🔙 Назад":
        user_quiz.waiting_for_topic = False
        user_quiz.quiz_started = False
        bot.send_message(message.chat.id, "Возвращаемся в главное меню:",
                        reply_markup=create_keyboard(main_menu=True))
        return

    if user_quiz.waiting_for_topic and (message.text in all_topics or message.text in ["🎲 Случайная тема", "🔙 Назад"]):
        handle_topic_selection(message, user_quiz, chat_type)
        return

    if user_quiz.quiz_started and user_quiz.current_question:
        user_answer = message.text.strip()
        if user_answer and len(user_answer) > 0 and user_answer[0].upper() in ['A', 'B', 'C', 'D']:
            handle_quiz_answer(message, user_quiz)
            return
        else:
            bot.send_message(message.chat.id, "Пожалуйста, выберите вариант ответа A, B, C или D.")
            return

    user_profile = get_user_profile(user_id)
    if user_profile.waiting_for is None:
        bot.send_chat_action(chat_id, 'typing')
        ai_response = query_gemini(user_id, message.text)
        
        sent_message = bot.send_message(
            chat_id, 
            f"🤖 *AI Ответ:*\n\n{ai_response}", 
            parse_mode='Markdown',
            reply_markup=create_feedback_keyboard()
        )
        
        if user_id not in pending_ai_responses:
            pending_ai_responses[user_id] = {}
        pending_ai_responses[user_id][sent_message.message_id] = (message.text, ai_response)

def handle_topic_selection(message, user_quiz, chat_type):
    if message.text == "🔙 Назад":
        user_quiz.waiting_for_topic = False
        bot.send_message(message.chat.id, "Возвращаемся в главное меню:",
                        reply_markup=create_keyboard(main_menu=True))
        return

    if message.text == "🎲 Случайная тема":
        user_quiz.current_topic = None
        topic_name = "случайные вопросы"
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
        f"🎯 {message.from_user.first_name}, тема: {topic_name.capitalize()}\n\n"
        "Викторина начинается! Отвечай на вопросы и набирай баллы! 💫\n"
        "Чтобы остановить викторину, нажми '⏹️ Стоп'",
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
            f"✅ Правильно! 🎉\n\n"
            f"Ты получаешь {points} баллов!\n"
            f"Текущий счет: {user_quiz.score} баллов"
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
            f"❌ Неправильно 😔\n\n"
            f"Правильный ответ: {correct_letter}) {correct_answer}\n"
            f"Твой счет: {user_quiz.score} баллов"
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
        bot.send_message(chat_id, "❌ Вопросы закончились!", reply_markup=create_keyboard(main_menu=True))
        user_quiz.quiz_started = False

def end_quiz(message, user_quiz):
    if user_quiz.questions_answered > 0:
        accuracy = (user_quiz.correct_answers / user_quiz.questions_answered * 100) if user_quiz.questions_answered > 0 else 0

        final_text = (
            f"🏁 Викторина завершена, {message.from_user.first_name}!\n\n"
            f"📊 Результаты:\n"
            f"✅ Правильных ответов: {user_quiz.correct_answers}/{user_quiz.questions_answered}\n"
            f"🎯 Точность: {accuracy:.1f}%\n"
            f"🏅 Набрано баллов: {user_quiz.score}\n\n"
            f"Сыграем еще? 🎯"
        )

        update_user_stats(
            user_id=user_quiz.user_id,
            chat_id=user_quiz.chat_id,
            chat_type=user_quiz.chat_type,
            game_played=True
        )
    else:
        final_text = "❌ Викторина остановлена."

    user_quiz.quiz_started = False
    user_quiz.waiting_for_topic = False
    bot.send_message(message.chat.id, final_text, reply_markup=create_keyboard(main_menu=True))

def check_gemini_availability():
    try:
        if model:
            response = model.generate_content("Привет! Ответь 'OK' если ты работаешь.")
            return response.text is not None
        return False
    except:
        return False

if __name__ == "__main__":
    print("=" * 50)
    print("🤖 Бот запускается...")

    gemini_available = check_gemini_availability()

    if gemini_available:
        print("✅ Gemini AI активен и готов к работе!")
    else:
        print("❌ Gemini AI недоступен. Проверьте API ключ и настройки.")

    print("🎯 Бот готов к работе! Используйте /start")
    print("=" * 50)

    try:
        bot.polling(none_stop=True, interval=0, timeout=60)
    except Exception as e:
        logger.error(f"Ошибка при запуске бота: {e}")
        print(f"❌ Произошла ошибка: {e}")

