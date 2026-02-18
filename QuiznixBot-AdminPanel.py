import sys
import sqlite3
import requests
import logging
import os
import hashlib
import json
from datetime import datetime, timedelta
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, 
    QHBoxLayout, QPushButton, QTextEdit, QLineEdit, 
    QLabel, QTabWidget, QTableWidget, QTableWidgetItem, 
    QHeaderView, QProgressBar, QGroupBox, QFormLayout,
    QMessageBox, QComboBox, QSplitter, QDialog,
    QDialogButtonBox, QCheckBox, QSpinBox, QDateEdit,
    QListWidget, QListWidgetItem, QGridLayout
)
from PyQt5.QtCore import QTimer, QThread, pyqtSignal, Qt, QDate
from PyQt5.QtGui import QFont, QColor, QBrush, QIcon, QPalette

BOT_TOKEN = "YOUR_TELEGRAM_BOT_TOKEN"
ADMIN_IDS = [YOUR_TELEGRAM_ID]
DATABASE_PATH = "quiz_bot.db"

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class LoginDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Авторизация администратора")
        self.setFixedSize(400, 200)
        self.setModal(True)
        
        layout = QVBoxLayout()
        
        form_layout = QFormLayout()
        
        self.username_input = QLineEdit()
        self.username_input.setPlaceholderText("Введите логин")
        form_layout.addRow("Логин:", self.username_input)
        
        self.password_input = QLineEdit()
        self.password_input.setPlaceholderText("Введите пароль")
        self.password_input.setEchoMode(QLineEdit.Password)
        form_layout.addRow("Пароль:", self.password_input)
        
        layout.addLayout(form_layout)
        
        button_layout = QHBoxLayout()
        
        self.login_btn = QPushButton("Войти")
        self.login_btn.clicked.connect(self.attempt_login)
        
        self.cancel_btn = QPushButton("Отмена")
        self.cancel_btn.clicked.connect(self.reject)
        
        button_layout.addWidget(self.login_btn)
        button_layout.addWidget(self.cancel_btn)
        
        layout.addLayout(button_layout)
        
        self.setLayout(layout)
        self.username_input.setFocus()
    
    def attempt_login(self):
        username = self.username_input.text().strip()
        password = self.password_input.text().strip()
        
        if not username or not password:
            QMessageBox.warning(self, "Ошибка", "Заполните все поля")
            return
        
        self.login_btn.setEnabled(False)
        self.login_btn.setText("Проверка...")
        
        if self.check_credentials(username, password):
            self.accept()
        else:
            QMessageBox.warning(self, "Ошибка", "Неверный логин или пароль")
            self.password_input.clear()
            self.password_input.setFocus()
        
        self.login_btn.setEnabled(True)
        self.login_btn.setText("Войти")
    
    def check_credentials(self, username, password):
        try:
            if not os.path.exists(DATABASE_PATH):
                try:
                    open(DATABASE_PATH, 'a').close()
                except Exception as e:
                    return False
            
            password_hash = hashlib.md5(password.encode()).hexdigest()
            
            conn = sqlite3.connect(DATABASE_PATH)
            cursor = conn.cursor()
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS admins (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            cursor.execute("SELECT COUNT(*) FROM admins")
            admin_count = cursor.fetchone()[0]
            
            if admin_count == 0:
                test_password_hash = hashlib.md5("admin123".encode()).hexdigest()
                try:
                    cursor.execute(
                        "INSERT INTO admins (username, password_hash) VALUES (?, ?)",
                        ("admin", test_password_hash)
                    )
                    conn.commit()
                except Exception as e:
                    pass
            
            cursor.execute(
                "SELECT username, password_hash FROM admins WHERE username = ?",
                (username,)
            )
            
            user_data = cursor.fetchone()
            if not user_data:
                conn.close()
                return False
            
            cursor.execute(
                "SELECT 1 FROM admins WHERE username = ? AND password_hash = ?",
                (username, password_hash)
            )
            
            result = cursor.fetchone() is not None
            conn.close()
            return result
            
        except Exception as e:
            logger.error(f"Ошибка проверки учетных данных: {e}")
            return False

class DatabaseManager:
    def __init__(self, db_path):
        self.db_path = db_path
        self.check_database()
    
    def check_database(self):
        if not os.path.exists(self.db_path):
            logger.error(f"Database file {self.db_path} not found!")
            return False
        
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = cursor.fetchall()
            table_names = [table[0] for table in tables]
            
            if 'ai_responses' in table_names:
                cursor.execute("PRAGMA table_info(ai_responses)")
                columns = cursor.fetchall()
            
            if 'chat_sessions' in table_names:
                cursor.execute("PRAGMA table_info(chat_sessions)")
                columns = cursor.fetchall()
            
            conn.close()
            return True
            
        except Exception as e:
            logger.error(f"Error checking database: {e}")
            return False
    
    def get_connection(self):
        try:
            conn = sqlite3.connect(self.db_path, check_same_thread=False)
            return conn
        except sqlite3.Error as e:
            logger.error(f"Database connection error: {e}")
            return None
    
    def execute_query(self, query, params=()):
        conn = self.get_connection()
        if not conn:
            return None
            
        cursor = conn.cursor()
        try:
            cursor.execute(query, params)
            conn.commit()
            return cursor
        except sqlite3.Error as e:
            logger.error(f"Database error: {e}")
            conn.rollback()
            return None
        finally:
            conn.close()
    
    def execute_select(self, query, params=()):
        conn = self.get_connection()
        if not conn:
            return []
            
        try:
            cursor = conn.cursor()
            cursor.execute(query, params)
            results = cursor.fetchall()
            return results
        except sqlite3.Error as e:
            logger.error(f"Database select error: {e}")
            return []
        finally:
            conn.close()

class QuestionDialog(QDialog):
    def __init__(self, parent=None, question_id=None):
        super().__init__(parent)
        self.question_id = question_id
        title = "Добавить вопрос" if question_id is None else "Редактировать вопрос"
        self.setWindowTitle(title)
        self.setFixedSize(500, 400)
        
        layout = QVBoxLayout()
        
        form_layout = QFormLayout()
        
        self.topic_input = QLineEdit()
        self.topic_input.setPlaceholderText("Например: история, география")
        form_layout.addRow("Тема:", self.topic_input)
        
        self.question_input = QTextEdit()
        self.question_input.setMaximumHeight(80)
        self.question_input.setPlaceholderText("Введите текст вопроса")
        form_layout.addRow("Вопрос:", self.question_input)
        
        self.options_input = QTextEdit()
        self.options_input.setMaximumHeight(100)
        self.options_input.setPlaceholderText("Введите варианты ответов через запятую")
        form_layout.addRow("Варианты ответов:", self.options_input)
        
        self.correct_answer_input = QSpinBox()
        self.correct_answer_input.setMinimum(0)
        self.correct_answer_input.setMaximum(3)
        self.correct_answer_input.setValue(0)
        form_layout.addRow("Номер правильного ответа (0-3):", self.correct_answer_input)
        
        self.points_input = QSpinBox()
        self.points_input.setMinimum(1)
        self.points_input.setMaximum(10)
        self.points_input.setValue(5)
        form_layout.addRow("Баллы:", self.points_input)
        
        self.difficulty_input = QComboBox()
        self.difficulty_input.addItems(["easy", "medium", "hard"])
        form_layout.addRow("Сложность:", self.difficulty_input)
        
        layout.addLayout(form_layout)
        
        button_layout = QHBoxLayout()
        
        self.save_btn = QPushButton("Сохранить")
        self.save_btn.clicked.connect(self.save_question)
        
        self.cancel_btn = QPushButton("Отмена")
        self.cancel_btn.clicked.connect(self.reject)
        
        button_layout.addWidget(self.save_btn)
        button_layout.addWidget(self.cancel_btn)
        
        layout.addLayout(button_layout)
        
        self.setLayout(layout)
        
        if question_id is not None:
            self.load_question_data()
    
    def load_question_data(self):
        try:
            db = DatabaseManager(DATABASE_PATH)
            query = "SELECT topic, question, options, correct_answer, points, difficulty FROM questions WHERE id = ?"
            result = db.execute_select(query, (self.question_id,))
            
            if result:
                topic, question, options, correct_answer, points, difficulty = result[0]
                
                self.topic_input.setText(topic)
                self.question_input.setPlainText(question)
                
                try:
                    options_list = json.loads(options)
                    self.options_input.setPlainText(", ".join(options_list))
                except:
                    self.options_input.setPlainText(options)
                
                self.correct_answer_input.setValue(correct_answer)
                self.points_input.setValue(points)
                
                index = self.difficulty_input.findText(difficulty)
                if index >= 0:
                    self.difficulty_input.setCurrentIndex(index)
                    
        except Exception as e:
            logger.error(f"Ошибка загрузки данных вопроса: {e}")
    
    def save_question(self):
        try:
            topic = self.topic_input.text().strip()
            question = self.question_input.toPlainText().strip()
            options_text = self.options_input.toPlainText().strip()
            correct_answer = self.correct_answer_input.value()
            points = self.points_input.value()
            difficulty = self.difficulty_input.currentText()
            
            if not all([topic, question, options_text]):
                QMessageBox.warning(self, "Ошибка", "Заполните все обязательные поля")
                return
            
            options_list = [opt.strip() for opt in options_text.split(",") if opt.strip()]
            if len(options_list) != 4:
                QMessageBox.warning(self, "Ошибка", "Должно быть ровно 4 варианта ответа")
                return
            
            if correct_answer >= len(options_list):
                QMessageBox.warning(self, "Ошибка", "Номер правильного ответа должен быть от 0 до 3")
                return
            
            options_json = json.dumps(options_list)
            
            db = DatabaseManager(DATABASE_PATH)
            
            if self.question_id is None:
                query = """
                INSERT INTO questions (topic, question, options, correct_answer, points, difficulty)
                VALUES (?, ?, ?, ?, ?, ?)
                """
                result = db.execute_query(query, (topic, question, options_json, correct_answer, points, difficulty))
            else:
                query = """
                UPDATE questions 
                SET topic = ?, question = ?, options = ?, correct_answer = ?, points = ?, difficulty = ?
                WHERE id = ?
                """
                result = db.execute_query(query, (topic, question, options_json, correct_answer, points, difficulty, self.question_id))
            
            if result:
                QMessageBox.information(self, "Успех", "Вопрос сохранен")
                self.accept()
            else:
                QMessageBox.critical(self, "Ошибка", "Не удалось сохранить вопрос")
                
        except Exception as e:
            logger.error(f"Ошибка сохранения вопроса: {e}")
            QMessageBox.critical(self, "Ошибка", f"Ошибка сохранения: {e}")

class BotStatistics:
    def __init__(self, db_manager):
        self.db = db_manager
    
    def get_bot_stats(self):
        try:
            stats = {
                'total_users': 0,
                'active_users': 0,
                'banned_users': 0,
                'total_points': 0,
                'total_questions': 0,
                'total_correct': 0,
                'total_games': 0
            }
            
            users_result = self.db.execute_select("SELECT COUNT(*) FROM users")
            if users_result:
                stats['total_users'] = users_result[0][0]
            
            try:
                active_result = self.db.execute_select(
                    "SELECT COUNT(DISTINCT user_id) FROM user_stats WHERE last_played > datetime('now', '-30 days')"
                )
                if active_result and active_result[0][0] is not None:
                    stats['active_users'] = active_result[0][0]
            except Exception:
                stats['active_users'] = 0
            
            try:
                points_result = self.db.execute_select("SELECT SUM(total_points) FROM user_stats")
                if points_result and points_result[0][0] is not None:
                    stats['total_points'] = points_result[0][0]
            except Exception:
                stats['total_points'] = 0
                
            try:
                questions_result = self.db.execute_select("SELECT SUM(total_questions) FROM user_stats")
                if questions_result and questions_result[0][0] is not None:
                    stats['total_questions'] = questions_result[0][0]
            except Exception:
                stats['total_questions'] = 0
                
            try:
                correct_result = self.db.execute_select("SELECT SUM(correct_answers) FROM user_stats")
                if correct_result and correct_result[0][0] is not None:
                    stats['total_correct'] = correct_result[0][0]
            except Exception:
                stats['total_correct'] = 0
                
            try:
                games_result = self.db.execute_select("SELECT SUM(games_played) FROM user_stats")
                if games_result and games_result[0][0] is not None:
                    stats['total_games'] = games_result[0][0]
            except Exception:
                stats['total_games'] = 0
            
            banned_result = self.db.execute_select("SELECT COUNT(*) FROM banned_users")
            if banned_result:
                stats['banned_users'] = banned_result[0][0]
            
            return stats
            
        except Exception as e:
            logger.error(f"Error getting bot stats: {e}")
            return {
                'total_users': 0, 'active_users': 0, 'banned_users': 0,
                'total_points': 0, 'total_questions': 0, 'total_correct': 0, 'total_games': 0
            }
    
    def get_detailed_user_stats(self, user_id=None):
        try:
            if user_id:
                user_exists = self.db.execute_select("SELECT 1 FROM users WHERE user_id = ?", (user_id,))
                if not user_exists:
                    return []
            
            if user_id:
                query = """
                SELECT 
                    u.user_id, 
                    u.username, 
                    u.first_name, 
                    u.last_name, 
                    COALESCE(us.total_points, 0) as points,
                    COALESCE(us.games_played, 0) as games,
                    COALESCE(us.total_questions, 0) as questions,
                    COALESCE(us.correct_answers, 0) as correct,
                    COALESCE(us.incorrect_answers, 0) as incorrect,
                    COALESCE(us.average_score, 0) as avg_score,
                    COALESCE(us.last_played, u.created_at) as last_activity,
                    u.created_at,
                    CASE WHEN bu.user_id IS NOT NULL THEN 1 ELSE 0 END as is_banned
                FROM users u
                LEFT JOIN user_stats us ON u.user_id = us.user_id
                LEFT JOIN banned_users bu ON u.user_id = bu.user_id
                WHERE u.user_id = ?
                """
                results = self.db.execute_select(query, (user_id,))
            else:
                query = """
                SELECT 
                    u.user_id, 
                    u.username, 
                    u.first_name, 
                    u.last_name, 
                    COALESCE(us.total_points, 0) as points,
                    COALESCE(us.games_played, 0) as games,
                    COALESCE(us.total_questions, 0) as questions,
                    COALESCE(us.correct_answers, 0) as correct,
                    COALESCE(us.incorrect_answers, 0) as incorrect,
                    COALESCE(us.average_score, 0) as avg_score,
                    COALESCE(us.last_played, u.created_at) as last_activity,
                    u.created_at,
                    CASE WHEN bu.user_id IS NOT NULL THEN 1 ELSE 0 END as is_banned
                FROM users u
                LEFT JOIN user_stats us ON u.user_id = us.user_id
                LEFT JOIN banned_users bu ON u.user_id = bu.user_id
                ORDER BY points DESC, games DESC
                """
                results = self.db.execute_select(query)
            
            return results
        except Exception as e:
            logger.error(f"Error getting detailed user stats: {e}")
            return []
    
    def get_user_activity_stats(self, days=30):
        try:
            query = """
            SELECT 
                DATE(created_at) as date,
                COUNT(*) as new_users,
                (SELECT COUNT(DISTINCT user_id) 
                 FROM user_stats 
                 WHERE DATE(last_played) = DATE(users.created_at)) as active_users
            FROM users 
            WHERE created_at >= date('now', ?)
            GROUP BY DATE(created_at)
            ORDER BY date
            """
            return self.db.execute_select(query, (f'-{days} days',))
        except Exception as e:
            logger.error(f"Error getting activity stats: {e}")
            return []
    
    def get_top_users(self, limit=10, metric='points'):
        try:
            order_by = {
                'points': 'points DESC',
                'games': 'games DESC', 
                'accuracy': 'CASE WHEN questions > 0 THEN CAST(correct as REAL) / questions ELSE 0 END DESC',
                'activity': 'last_activity DESC'
            }.get(metric, 'points DESC')
            
            query = f"""
            SELECT u.user_id, u.username, u.first_name, u.last_name, 
                   COALESCE(us.total_points, 0) as points,
                   COALESCE(us.games_played, 0) as games,
                   COALESCE(us.total_questions, 0) as questions,
                   COALESCE(us.correct_answers, 0) as correct,
                   COALESCE(us.average_score, 0) as avg_score,
                   COALESCE(us.last_played, u.created_at) as last_activity
            FROM users u
            LEFT JOIN user_stats us ON u.user_id = us.user_id
            WHERE u.user_id NOT IN (SELECT user_id FROM banned_users)
            ORDER BY {order_by}
            LIMIT ?
            """
            return self.db.execute_select(query, (limit,))
        except Exception as e:
            logger.error(f"Error getting top users: {e}")
            return []
    
    def get_all_users(self):
        try:
            query = "SELECT user_id, username, first_name, last_name, created_at FROM users ORDER BY created_at DESC"
            users = self.db.execute_select(query)
            
            enriched_users = []
            for user in users:
                user_id, username, first_name, last_name, created_at = user
                
                points = 0
                stats_query = "SELECT total_points FROM user_stats WHERE user_id = ? LIMIT 1"
                stats = self.db.execute_select(stats_query, (user_id,))
                if stats and stats[0] and stats[0][0] is not None:
                    points = stats[0][0]
                
                is_banned = False
                banned_query = "SELECT 1 FROM banned_users WHERE user_id = ?"
                is_banned = len(self.db.execute_select(banned_query, (user_id,))) > 0
                
                enriched_users.append((
                    user_id, username, first_name, last_name, points, 0, created_at, is_banned
                ))
            
            return enriched_users
            
        except Exception as e:
            logger.error(f"Error getting users: {e}")
            return []
    
    def get_user_by_id(self, user_id):
        try:
            query = "SELECT user_id, username, first_name, last_name FROM users WHERE user_id = ?"
            result = self.db.execute_select(query, (user_id,))
            if result:
                return result[0]
            else:
                return None
        except Exception as e:
            logger.error(f"Error getting user by ID: {e}")
            return None
    
    def ban_user(self, user_id, admin_id, reason=""):
        try:
            user = self.get_user_by_id(user_id)
            if not user:
                return False
            
            user_id, username, first_name, last_name = user
            
            tables = self.db.execute_select("SELECT name FROM sqlite_master WHERE type='table' AND name='banned_users'")
            if not tables:
                create_table_query = """
                CREATE TABLE IF NOT EXISTS banned_users (
                    user_id INTEGER PRIMARY KEY,
                    username TEXT,
                    first_name TEXT,
                    last_name TEXT,
                    banned_by INTEGER,
                    reason TEXT,
                    banned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
                self.db.execute_query(create_table_query)
            
            existing_ban = self.db.execute_select("SELECT 1 FROM banned_users WHERE user_id = ?", (user_id,))
            if existing_ban:
                return True
            
            query = """
            INSERT INTO banned_users 
            (user_id, username, first_name, last_name, banned_by, reason) 
            VALUES (?, ?, ?, ?, ?, ?)
            """
            result = self.db.execute_query(query, (
                user_id, username or "", first_name or "", last_name or "", admin_id, reason or "Не указана"
            ))
            
            return result is not None
            
        except Exception as e:
            logger.error(f"Error banning user: {e}")
            return False
    
    def unban_user(self, user_id):
        try:
            tables = self.db.execute_select("SELECT name FROM sqlite_master WHERE type='table' AND name='banned_users'")
            if not tables:
                return False
            
            existing_ban = self.db.execute_select("SELECT 1 FROM banned_users WHERE user_id = ?", (user_id,))
            if not existing_ban:
                return True
            
            query = "DELETE FROM banned_users WHERE user_id = ?"
            result = self.db.execute_query(query, (user_id,))
            
            return result is not None
            
        except Exception as e:
            logger.error(f"Error unbanning user: {e}")
            return False
    
    def get_banned_users(self):
        try:
            tables = self.db.execute_select("SELECT name FROM sqlite_master WHERE type='table' AND name='banned_users'")
            if not tables:
                return []
            
            query = "SELECT user_id, username, first_name, last_name, reason, banned_at FROM banned_users ORDER BY banned_at DESC"
            result = self.db.execute_select(query)
            return result
        except Exception as e:
            logger.error(f"Error getting banned users: {e}")
            return []
    
    def search_users(self, search_term):
        try:
            query = """
            SELECT user_id, username, first_name, last_name, created_at 
            FROM users 
            WHERE user_id LIKE ? OR username LIKE ? OR first_name LIKE ? OR last_name LIKE ?
            ORDER BY created_at DESC
            """
            search_pattern = f'%{search_term}%'
            return self.db.execute_select(query, (search_pattern, search_pattern, search_pattern, search_pattern))
        except Exception as e:
            logger.error(f"Error searching users: {e}")
            return []

    def get_daily_activity(self, days=7):
        try:
            query = """
            SELECT 
                DATE(created_at) as date,
                COUNT(*) as new_users,
                (SELECT COUNT(*) FROM user_stats WHERE DATE(last_played) = DATE(users.created_at)) as active_users
            FROM users 
            WHERE created_at >= date('now', ?)
            GROUP BY DATE(created_at)
            ORDER BY date DESC
            """
            return self.db.execute_select(query, (f'-{days} days',))
        except Exception as e:
            logger.error(f"Error getting daily activity: {e}")
            return []

    def get_questions_statistics(self):
        try:
            query = """
            SELECT 
                difficulty,
                COUNT(*) as total_questions,
                AVG(points) as avg_points
            FROM questions 
            GROUP BY difficulty
            """
            return self.db.execute_select(query)
        except Exception as e:
            logger.error(f"Error getting questions statistics: {e}")
            return []

    def get_user_growth(self, days=30):
        try:
            query = """
            SELECT 
                DATE(created_at) as date,
                COUNT(*) as daily_new_users,
                (SELECT COUNT(*) FROM users WHERE DATE(created_at) <= date) as total_users
            FROM users 
            WHERE created_at >= date('now', ?)
            GROUP BY DATE(created_at)
            ORDER BY date
            """
            return self.db.execute_select(query, (f'-{days} days',))
        except Exception as e:
            logger.error(f"Error getting user growth: {e}")
            return []

class TelegramAPI:
    def __init__(self, bot_token):
        self.bot_token = bot_token
        self.base_url = f"https://api.telegram.org/bot{bot_token}"
    
    def send_message(self, chat_id, text, parse_mode='HTML'):
        url = f"{self.base_url}/sendMessage"
        data = {
            'chat_id': chat_id,
            'text': text,
            'parse_mode': parse_mode
        }
        try:
            response = requests.post(url, data=data, timeout=10)
            return response.json()
        except Exception as e:
            logger.error(f"Error sending message: {e}")
            return None
    
    def send_ban_notification(self, user_id, reason=""):
        message = f"🚫 <b>Вы были заблокированы в боте!</b>\n\n"
        if reason:
            message += f"<b>Причина:</b> {reason}\n\n"
        message += "❌ Вы больше не можете использовать функции бота.\n"
        message += "📞 Для разблокировки обратитесь к администратору."
        
        return self.send_message(user_id, message)
    
    def send_unban_notification(self, user_id):
        message = f"✅ <b>Вы были разблокированы!</b>\n\n"
        message += "🎉 Теперь вы снова можете использовать все функции бота.\n"
        message += "Спасибо за понимание!"
        
        return self.send_message(user_id, message)

class BroadcastWorker(QThread):
    progress = pyqtSignal(int, int, str)
    finished = pyqtSignal(dict)
    
    def __init__(self, db_manager, telegram_api, message_text):
        super().__init__()
        self.db = db_manager
        self.telegram = telegram_api
        self.message_text = message_text
        self.is_running = True
    
    def run(self):
        try:
            users = self.db.execute_select("SELECT user_id FROM users")
            if not users:
                self.finished.emit({'error': 'No users found'})
                return
                
            user_ids = [row[0] for row in users]
            
            total = len(user_ids)
            success = 0
            failed = 0
            banned = 0
            results = []
            
            for i, user_id in enumerate(user_ids):
                if not self.is_running:
                    break
                
                check_result = self.db.execute_select("SELECT 1 FROM banned_users WHERE user_id = ?", (user_id,))
                if check_result:
                    banned += 1
                    results.append(f"🚫 {user_id}: Заблокирован (пропущен)")
                    continue
                
                result = self.telegram.send_message(user_id, self.message_text)
                
                if result and result.get('ok'):
                    success += 1
                    results.append(f"✅ {user_id}: Успешно")
                else:
                    failed += 1
                    error = result.get('description', 'Unknown error') if result else 'Timeout'
                    results.append(f"❌ {user_id}: Ошибка - {error}")
                
                progress = int((i + 1) / total * 100)
                status = f"Отправлено: {i+1}/{total} | Успешно: {success} | Ошибок: {failed}"
                self.progress.emit(progress, i + 1, status)
                
                self.msleep(100)
            
            report = {
                'success': success,
                'failed': failed,
                'banned': banned,
                'total': total,
                'results': results
            }
            self.finished.emit(report)
            
        except Exception as e:
            logger.error(f"Broadcast error: {e}")
            self.finished.emit({'error': str(e)})

class StatisticsTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.db_manager = DatabaseManager(DATABASE_PATH)
        self.stats = BotStatistics(self.db_manager)
        self.init_ui()
        self.load_statistics()
    
    def init_ui(self):
        layout = QVBoxLayout(self)
        
        title = QLabel("📈 Детальная статистика")
        title.setFont(QFont('Arial', 16, QFont.Bold))
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)
        
        refresh_layout = QHBoxLayout()
        
        self.refresh_btn = QPushButton("🔄 Обновить всю статистику")
        self.refresh_btn.clicked.connect(self.load_statistics)
        
        refresh_layout.addWidget(self.refresh_btn)
        refresh_layout.addStretch()
        
        layout.addLayout(refresh_layout)
        
        splitter = QSplitter(Qt.Vertical)
        
        top_widget = QWidget()
        top_layout = QVBoxLayout(top_widget)
        
        general_stats_group = QGroupBox("📊 Общая статистика бота")
        general_stats_layout = QGridLayout(general_stats_group)
        
        self.total_users_label = QLabel("Всего пользователей: 0")
        self.active_users_label = QLabel("Активных пользователей: 0")
        self.banned_users_label = QLabel("Заблокированных: 0")
        self.total_points_label = QLabel("Всего баллов: 0")
        self.total_games_label = QLabel("Всего игр: 0")
        self.total_questions_label = QLabel("Всего вопросов: 0")
        self.correct_answers_label = QLabel("Правильных ответов: 0")
        
        general_stats_layout.addWidget(self.total_users_label, 0, 0)
        general_stats_layout.addWidget(self.active_users_label, 0, 1)
        general_stats_layout.addWidget(self.banned_users_label, 0, 2)
        general_stats_layout.addWidget(self.total_points_label, 1, 0)
        general_stats_layout.addWidget(self.total_games_label, 1, 1)
        general_stats_layout.addWidget(self.total_questions_label, 1, 2)
        general_stats_layout.addWidget(self.correct_answers_label, 2, 0)
        
        top_layout.addWidget(general_stats_group)
        
        top_users_group = QGroupBox("🏆 Топ пользователей")
        top_users_layout = QVBoxLayout(top_users_group)
        
        metric_layout = QHBoxLayout()
        metric_layout.addWidget(QLabel("Сортировка по:"))
        
        self.metric_combo = QComboBox()
        self.metric_combo.addItems(["Баллы", "Игры", "Точность", "Активность"])
        self.metric_combo.currentTextChanged.connect(self.load_top_users)
        
        metric_layout.addWidget(self.metric_combo)
        metric_layout.addStretch()
        
        top_users_layout.addLayout(metric_layout)
        
        self.top_users_table = QTableWidget()
        self.top_users_table.setColumnCount(7)
        self.top_users_table.setHorizontalHeaderLabels([
            "№", "User ID", "Username", "Баллы", "Игры", "Точность", "Последняя активность"
        ])
        self.top_users_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        
        top_users_layout.addWidget(self.top_users_table)
        
        top_layout.addWidget(top_users_group)
        
        bottom_widget = QWidget()
        bottom_layout = QVBoxLayout(bottom_widget)
        
        detailed_stats_group = QGroupBox("👥 Детальная статистика пользователей")
        detailed_layout = QVBoxLayout(detailed_stats_group)
        
        search_layout = QHBoxLayout()
        search_layout.addWidget(QLabel("Поиск пользователя:"))
        
        self.user_search_input = QLineEdit()
        self.user_search_input.setPlaceholderText("Введите User ID для поиска...")
        
        self.search_btn = QPushButton("🔍 Поиск")
        self.search_btn.clicked.connect(self.search_user_stats)
        
        self.show_all_btn = QPushButton("👁️ Показать всех")
        self.show_all_btn.clicked.connect(self.show_all_users_stats)
        
        search_layout.addWidget(self.user_search_input)
        search_layout.addWidget(self.search_btn)
        search_layout.addWidget(self.show_all_btn)
        search_layout.addStretch()
        
        detailed_layout.addLayout(search_layout)
        
        self.detailed_stats_table = QTableWidget()
        self.detailed_stats_table.setColumnCount(10)
        self.detailed_stats_table.setHorizontalHeaderLabels([
            "User ID", "Username", "Имя", "Фамилия", "Баллы", "Игры", 
            "Вопросы", "Правильно", "Точность%", "Статус"
        ])
        self.detailed_stats_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        
        detailed_layout.addWidget(self.detailed_stats_table)
        
        bottom_layout.addWidget(detailed_stats_group)
        
        splitter.addWidget(top_widget)
        splitter.addWidget(bottom_widget)
        splitter.setSizes([400, 500])
        
        layout.addWidget(splitter)
    
    def load_statistics(self):
        self.load_general_stats()
        self.load_top_users()
        self.show_all_users_stats()
    
    def load_general_stats(self):
        try:
            stats = self.stats.get_bot_stats()
            
            self.total_users_label.setText(f"Всего пользователей: {stats['total_users']}")
            self.active_users_label.setText(f"Активных пользователей: {stats['active_users']}")
            self.banned_users_label.setText(f"Заблокированных: {stats['banned_users']}")
            self.total_points_label.setText(f"Всего баллов: {stats['total_points']}")
            self.total_games_label.setText(f"Всего игр: {stats['total_games']}")
            self.total_questions_label.setText(f"Всего вопросов: {stats['total_questions']}")
            self.correct_answers_label.setText(f"Правильных ответов: {stats['total_correct']}")
            
        except Exception as e:
            print(f"❌ Error loading general stats: {e}")
    
    def load_top_users(self):
        try:
            metric_map = {
                "Баллы": "points",
                "Игры": "games", 
                "Точность": "accuracy",
                "Активность": "activity"
            }
            
            selected_metric = metric_map.get(self.metric_combo.currentText(), "points")
            top_users = self.stats.get_top_users(10, selected_metric)
            
            self.top_users_table.setRowCount(len(top_users))
            
            for row, user in enumerate(top_users):
                user_id, username, first_name, last_name, points, games, questions, correct, avg_score, last_activity = user
                
                accuracy = (correct / questions * 100) if questions > 0 else 0
                
                self.top_users_table.setItem(row, 0, QTableWidgetItem(str(row + 1)))
                self.top_users_table.setItem(row, 1, QTableWidgetItem(str(user_id)))
                self.top_users_table.setItem(row, 2, QTableWidgetItem(username or f"{first_name or ''} {last_name or ''}".strip() or "Неизвестно"))
                self.top_users_table.setItem(row, 3, QTableWidgetItem(str(points)))
                self.top_users_table.setItem(row, 4, QTableWidgetItem(str(games)))
                self.top_users_table.setItem(row, 5, QTableWidgetItem(f"{accuracy:.1f}%"))
                self.top_users_table.setItem(row, 6, QTableWidgetItem(last_activity.split()[0] if last_activity else "Неизвестно"))
                
                if row < 3:
                    for col in range(self.top_users_table.columnCount()):
                        item = self.top_users_table.item(row, col)
                        if row == 0:
                            item.setBackground(QBrush(QColor(255, 215, 0)))
                        elif row == 1:
                            item.setBackground(QBrush(QColor(192, 192, 192)))
                        elif row == 2:
                            item.setBackground(QBrush(QColor(205, 127, 50)))
            
        except Exception as e:
            print(f"❌ Error loading top users: {e}")
    
    def show_all_users_stats(self):
        try:
            detailed_stats = self.stats.get_detailed_user_stats()
            self.display_detailed_stats(detailed_stats)
            
        except Exception as e:
            print(f"❌ Error loading all users stats: {e}")
    
    def search_user_stats(self):
        try:
            user_id = self.user_search_input.text().strip()
            if not user_id:
                QMessageBox.warning(self, "Ошибка", "Введите User ID для поиска")
                return
            
            detailed_stats = self.stats.get_detailed_user_stats(user_id)
            if not detailed_stats:
                QMessageBox.information(self, "Информация", f"Пользователь с ID {user_id} не найден")
                return
            
            self.display_detailed_stats(detailed_stats)
            
        except Exception as e:
            print(f"❌ Error searching user stats: {e}")
            QMessageBox.critical(self, "Ошибка", f"Ошибка поиска: {e}")
    
    def display_detailed_stats(self, stats_data):
        try:
            self.detailed_stats_table.setRowCount(len(stats_data))
            
            for row, user in enumerate(stats_data):
                user_id, username, first_name, last_name, points, games, questions, correct, incorrect, avg_score, last_activity, created_at, is_banned = user
                
                accuracy = (correct / questions * 100) if questions > 0 else 0
                status = "🚫 Заблокирован" if is_banned else "✅ Активен"
                
                self.detailed_stats_table.setItem(row, 0, QTableWidgetItem(str(user_id)))
                self.detailed_stats_table.setItem(row, 1, QTableWidgetItem(username or ""))
                self.detailed_stats_table.setItem(row, 2, QTableWidgetItem(first_name or ""))
                self.detailed_stats_table.setItem(row, 3, QTableWidgetItem(last_name or ""))
                self.detailed_stats_table.setItem(row, 4, QTableWidgetItem(str(points)))
                self.detailed_stats_table.setItem(row, 5, QTableWidgetItem(str(games)))
                self.detailed_stats_table.setItem(row, 6, QTableWidgetItem(str(questions)))
                self.detailed_stats_table.setItem(row, 7, QTableWidgetItem(str(correct)))
                self.detailed_stats_table.setItem(row, 8, QTableWidgetItem(f"{accuracy:.1f}%"))
                self.detailed_stats_table.setItem(row, 9, QTableWidgetItem(status))
                
                if is_banned:
                    for col in range(self.detailed_stats_table.columnCount()):
                        item = self.detailed_stats_table.item(row, col)
                        item.setBackground(QBrush(QColor(255, 200, 200)))
            
        except Exception as e:
            print(f"❌ Error displaying detailed stats: {e}")

class UserManagementDialog(QDialog):
    def __init__(self, parent=None, user_id=None):
        super().__init__(parent)
        self.user_id = user_id
        self.db_manager = DatabaseManager(DATABASE_PATH)
        self.stats = BotStatistics(self.db_manager)
        self.telegram = TelegramAPI(BOT_TOKEN)
        
        self.setWindowTitle(f"Управление пользователем {user_id}" if user_id else "Управление пользователем")
        self.setFixedSize(500, 400)
        
        self.init_ui()
        self.load_user_data()
    
    def init_ui(self):
        layout = QVBoxLayout()
        
        info_group = QGroupBox("Информация о пользователе")
        info_layout = QFormLayout(info_group)
        
        self.user_id_label = QLabel(str(self.user_id) if self.user_id else "Неизвестно")
        self.username_label = QLabel("Загрузка...")
        self.name_label = QLabel("Загрузка...")
        self.points_label = QLabel("Загрузка...")
        self.status_label = QLabel("Загрузка...")
        
        info_layout.addRow("User ID:", self.user_id_label)
        info_layout.addRow("Username:", self.username_label)
        info_layout.addRow("Имя:", self.name_label)
        info_layout.addRow("Баллы:", self.points_label)
        info_layout.addRow("Статус:", self.status_label)
        
        layout.addWidget(info_group)
        
        actions_group = QGroupBox("Действия")
        actions_layout = QVBoxLayout(actions_group)
        
        self.ban_btn = QPushButton("🚫 Заблокировать пользователя")
        self.ban_btn.clicked.connect(self.ban_user)
        
        self.unban_btn = QPushButton("✅ Разблокировать пользователя")
        self.unban_btn.clicked.connect(self.unban_user)
        
        self.send_message_btn = QPushButton("📨 Отправить сообщение")
        self.send_message_btn.clicked.connect(self.send_message)
        
        actions_layout.addWidget(self.ban_btn)
        actions_layout.addWidget(self.unban_btn)
        actions_layout.addWidget(self.send_message_btn)
        
        layout.addWidget(actions_group)
        
        self.reason_input = QLineEdit()
        self.reason_input.setPlaceholderText("Причина блокировки (необязательно)")
        layout.addWidget(QLabel("Причина блокировки:"))
        layout.addWidget(self.reason_input)
        
        self.message_input = QTextEdit()
        self.message_input.setMaximumHeight(80)
        self.message_input.setPlaceholderText("Сообщение для пользователя...")
        layout.addWidget(QLabel("Сообщение:"))
        layout.addWidget(self.message_input)
        
        button_layout = QHBoxLayout()
        
        self.close_btn = QPushButton("Закрыть")
        self.close_btn.clicked.connect(self.reject)
        
        button_layout.addWidget(self.close_btn)
        layout.addLayout(button_layout)
        
        self.setLayout(layout)
    
    def load_user_data(self):
        if not self.user_id:
            return
            
        try:
            user_stats = self.stats.get_detailed_user_stats(self.user_id)
            if user_stats:
                user_data = user_stats[0]
                user_id, username, first_name, last_name, points, games, questions, correct, incorrect, avg_score, last_activity, created_at, is_banned = user_data
                
                self.username_label.setText(username or "Не указан")
                self.name_label.setText(f"{first_name or ''} {last_name or ''}".strip() or "Не указано")
                self.points_label.setText(str(points))
                self.status_label.setText("🚫 Заблокирован" if is_banned else "✅ Активен")
                
                self.ban_btn.setEnabled(not is_banned)
                self.unban_btn.setEnabled(is_banned)
                
        except Exception as e:
            print(f"❌ Error loading user data: {e}")
    
    def ban_user(self):
        if not self.user_id:
            return
            
        try:
            reason = self.reason_input.text().strip()
            if self.stats.ban_user(self.user_id, ADMIN_IDS[0] if ADMIN_IDS else 0, reason):
                QMessageBox.information(self, "Успех", "Пользователь заблокирован")
                self.telegram.send_ban_notification(self.user_id, reason)
                self.load_user_data()
            else:
                QMessageBox.critical(self, "Ошибка", "Не удалось заблокировать пользователя")
                
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Ошибка блокировки: {e}")
    
    def unban_user(self):
        if not self.user_id:
            return
            
        try:
            if self.stats.unban_user(self.user_id):
                QMessageBox.information(self, "Успех", "Пользователь разблокирован")
                self.telegram.send_unban_notification(self.user_id)
                self.load_user_data()
            else:
                QMessageBox.critical(self, "Ошибка", "Не удалось разблокировать пользователя")
                
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Ошибка разблокировки: {e}")
    
    def send_message(self):
        if not self.user_id:
            return
            
        message = self.message_input.toPlainText().strip()
        if not message:
            QMessageBox.warning(self, "Ошибка", "Введите сообщение")
            return
            
        try:
            result = self.telegram.send_message(self.user_id, message)
            if result and result.get('ok'):
                QMessageBox.information(self, "Успех", "Сообщение отправлено")
                self.message_input.clear()
            else:
                QMessageBox.critical(self, "Ошибка", "Не удалось отправить сообщение")
                
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Ошибка отправки: {e}")

class AIDialogsTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.db_manager = DatabaseManager(DATABASE_PATH)
        self.init_ui()
        self.load_ai_dialogs()
    
    def init_ui(self):
        layout = QVBoxLayout(self)
        
        title = QLabel("💬 Диалоги с ИИ (AI Responses)")
        title.setFont(QFont('Arial', 16, QFont.Bold))
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)
        
        control_layout = QHBoxLayout()
        
        self.refresh_btn = QPushButton("🔄 Обновить")
        self.refresh_btn.clicked.connect(self.load_ai_dialogs)
        
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Поиск по вопросу...")
        self.search_input.textChanged.connect(self.search_dialogs)
        
        self.add_test_group = QGroupBox("Добавить тестовую запись")
        add_test_layout = QFormLayout(self.add_test_group)
        
        self.test_user_id = QLineEdit()
        self.test_user_id.setPlaceholderText("User ID")
        add_test_layout.addRow("User ID:", self.test_user_id)
        
        self.test_question = QTextEdit()
        self.test_question.setMaximumHeight(60)
        self.test_question.setPlaceholderText("Вопрос")
        add_test_layout.addRow("Вопрос:", self.test_question)
        
        self.test_answer = QTextEdit()
        self.test_answer.setMaximumHeight(60)
        self.test_answer.setPlaceholderText("Ответ")
        add_test_layout.addRow("Ответ:", self.test_answer)
        
        self.add_test_btn = QPushButton("💾 Сохранить тестовую запись")
        self.add_test_btn.clicked.connect(self.add_test_dialog)
        add_test_layout.addRow(self.add_test_btn)
        
        control_layout.addWidget(self.refresh_btn)
        control_layout.addWidget(QLabel("Поиск:"))
        control_layout.addWidget(self.search_input)
        control_layout.addStretch()
        
        layout.addLayout(control_layout)
        layout.addWidget(self.add_test_group)
        
        self.dialogs_table = QTableWidget()
        self.dialogs_table.setColumnCount(7)
        self.dialogs_table.setHorizontalHeaderLabels([
            "ID", "User ID", "Вопрос", "Ответ", "Лайк", "Использовано", "Дата/Время"
        ])
        self.dialogs_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.dialogs_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.dialogs_table.selectionModel().selectionChanged.connect(self.show_dialog_details)
        
        layout.addWidget(self.dialogs_table)
        
        details_group = QGroupBox("Детальный просмотр")
        details_layout = QVBoxLayout(details_group)
        
        details_layout.addWidget(QLabel("Полный вопрос:"))
        self.question_details = QTextEdit()
        self.question_details.setMaximumHeight(80)
        self.question_details.setReadOnly(True)
        details_layout.addWidget(self.question_details)
        
        details_layout.addWidget(QLabel("Полный ответ:"))
        self.answer_details = QTextEdit()
        self.answer_details.setMaximumHeight(80)
        self.answer_details.setReadOnly(True)
        details_layout.addWidget(self.answer_details)
        
        layout.addWidget(details_group)
    
    def load_ai_dialogs(self):
        try:
            tables = self.db_manager.execute_select("SELECT name FROM sqlite_master WHERE type='table' AND name='ai_responses'")
            if not tables:
                self.dialogs_table.setRowCount(0)
                QMessageBox.information(self, "Информация", "Таблица ai_responses не найдена")
                return
            
            dialogs = self.db_manager.execute_select(
                "SELECT id, user_id, question, response, liked, used_count, created_at FROM ai_responses ORDER BY created_at DESC"
            )
            
            self.dialogs_table.setRowCount(len(dialogs))
            
            for row, dialog in enumerate(dialogs):
                id, user_id, question, response, liked, used_count, created_at = dialog
                
                short_question = question[:100] + "..." if len(question) > 100 else question
                short_response = response[:100] + "..." if len(response) > 100 else response
                like_display = "👍" if liked else "👎"
                
                self.dialogs_table.setItem(row, 0, QTableWidgetItem(str(id)))
                self.dialogs_table.setItem(row, 1, QTableWidgetItem(str(user_id)))
                self.dialogs_table.setItem(row, 2, QTableWidgetItem(short_question))
                self.dialogs_table.setItem(row, 3, QTableWidgetItem(short_response))
                self.dialogs_table.setItem(row, 4, QTableWidgetItem(like_display))
                self.dialogs_table.setItem(row, 5, QTableWidgetItem(str(used_count)))
                self.dialogs_table.setItem(row, 6, QTableWidgetItem(created_at))
            
        except Exception as e:
            print(f"❌ Error loading AI dialogs: {e}")
            QMessageBox.critical(self, "Ошибка", f"Ошибка загрузки диалогов: {e}")
    
    def search_dialogs(self):
        search_term = self.search_input.text().strip()
        if not search_term:
            self.load_ai_dialogs()
            return
        
        try:
            dialogs = self.db_manager.execute_select(
                "SELECT id, user_id, question, response, liked, used_count, created_at FROM ai_responses WHERE question LIKE ? ORDER BY created_at DESC",
                (f'%{search_term}%',)
            )
            
            self.dialogs_table.setRowCount(len(dialogs))
            
            for row, dialog in enumerate(dialogs):
                id, user_id, question, response, liked, used_count, created_at = dialog
                
                short_question = question[:100] + "..." if len(question) > 100 else question
                short_response = response[:100] + "..." if len(response) > 100 else response
                like_display = "👍" if liked else "👎"
                
                self.dialogs_table.setItem(row, 0, QTableWidgetItem(str(id)))
                self.dialogs_table.setItem(row, 1, QTableWidgetItem(str(user_id)))
                self.dialogs_table.setItem(row, 2, QTableWidgetItem(short_question))
                self.dialogs_table.setItem(row, 3, QTableWidgetItem(short_response))
                self.dialogs_table.setItem(row, 4, QTableWidgetItem(like_display))
                self.dialogs_table.setItem(row, 5, QTableWidgetItem(str(used_count)))
                self.dialogs_table.setItem(row, 6, QTableWidgetItem(created_at))
            
        except Exception as e:
            print(f"❌ Error searching AI dialogs: {e}")
    
    def show_dialog_details(self):
        selected_rows = self.dialogs_table.selectionModel().selectedRows()
        if not selected_rows:
            self.question_details.clear()
            self.answer_details.clear()
            return
        
        row = selected_rows[0].row()
        
        try:
            dialog_id = int(self.dialogs_table.item(row, 0).text())
            
            full_dialog = self.db_manager.execute_select(
                "SELECT question, response FROM ai_responses WHERE id = ?",
                (dialog_id,)
            )
            
            if full_dialog:
                full_question, full_response = full_dialog[0]
                self.question_details.setPlainText(full_question)
                self.answer_details.setPlainText(full_response)
        except Exception as e:
            print(f"❌ Error loading full dialog: {e}")
    
    def add_test_dialog(self):
        try:
            user_id = self.test_user_id.text().strip()
            question = self.test_question.toPlainText().strip()
            response = self.test_answer.toPlainText().strip()
            
            if not all([user_id, question, response]):
                QMessageBox.warning(self, "Ошибка", "Заполните все поля")
                return
            
            tables = self.db_manager.execute_select("SELECT name FROM sqlite_master WHERE type='table' AND name='ai_responses'")
            if not tables:
                create_table_query = """
                CREATE TABLE IF NOT EXISTS ai_responses (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    question TEXT NOT NULL,
                    response TEXT NOT NULL,
                    liked BOOLEAN DEFAULT 0,
                    used_count INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
                self.db_manager.execute_query(create_table_query)
            
            query = """
            INSERT INTO ai_responses (user_id, question, response, liked, used_count) 
            VALUES (?, ?, ?, ?, ?)
            """
            result = self.db_manager.execute_query(query, (user_id, question, response, 1, 1))
            
            if result:
                QMessageBox.information(self, "Успех", "Тестовая запись добавлена")
                self.test_user_id.clear()
                self.test_question.clear()
                self.test_answer.clear()
                self.load_ai_dialogs()
            else:
                QMessageBox.critical(self, "Ошибка", "Не удалось добавить запись")
                
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Ошибка добавления записи: {e}")

class AIFeedbackTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.db_manager = DatabaseManager(DATABASE_PATH)
        self.init_ui()
        self.load_feedback()
    
    def init_ui(self):
        layout = QVBoxLayout(self)
        
        title = QLabel("⭐ Оценки ответов ИИ")
        title.setFont(QFont('Arial', 16, QFont.Bold))
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)
        
        control_layout = QHBoxLayout()
        
        self.refresh_btn = QPushButton("🔄 Обновить")
        self.refresh_btn.clicked.connect(self.load_feedback)
        
        self.filter_combo = QComboBox()
        self.filter_combo.addItems(["Все оценки", "Только понравившиеся", "Только не понравившиеся"])
        self.filter_combo.currentTextChanged.connect(self.filter_feedback)
        
        control_layout.addWidget(self.refresh_btn)
        control_layout.addWidget(QLabel("Фильтр:"))
        control_layout.addWidget(self.filter_combo)
        control_layout.addStretch()
        
        layout.addLayout(control_layout)
        
        self.feedback_table = QTableWidget()
        self.feedback_table.setColumnCount(6)
        self.feedback_table.setHorizontalHeaderLabels([
            "ID", "User ID", "Вопрос", "Ответ", "Оценка", "Дата/Время"
        ])
        self.feedback_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.feedback_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.feedback_table.selectionModel().selectionChanged.connect(self.show_feedback_details)
        
        layout.addWidget(self.feedback_table)
        
        details_group = QGroupBox("Детальный просмотр и управление")
        details_layout = QVBoxLayout(details_group)
        
        details_layout.addWidget(QLabel("Вопрос целиком:"))
        self.full_question = QTextEdit()
        self.full_question.setMaximumHeight(60)
        self.full_question.setReadOnly(True)
        details_layout.addWidget(self.full_question)
        
        details_layout.addWidget(QLabel("Ответ целиком:"))
        self.full_answer = QTextEdit()
        self.full_answer.setMaximumHeight(60)
        self.full_answer.setReadOnly(True)
        details_layout.addWidget(self.full_answer)
        
        self.change_rating_btn = QPushButton("🔄 Изменить оценку")
        self.change_rating_btn.clicked.connect(self.change_rating)
        self.change_rating_btn.setEnabled(False)
        details_layout.addWidget(self.change_rating_btn)
        
        layout.addWidget(details_group)
    
    def load_feedback(self, rating_filter=None):
        try:
            tables = self.db_manager.execute_select("SELECT name FROM sqlite_master WHERE type='table' AND name='ai_responses'")
            if not tables:
                self.feedback_table.setRowCount(0)
                QMessageBox.information(self, "Информация", "Таблица ai_responses не найдена")
                return
            
            if rating_filter is None:
                feedbacks = self.db_manager.execute_select(
                    "SELECT id, user_id, question, response, liked, created_at FROM ai_responses ORDER BY created_at DESC"
                )
            else:
                feedbacks = self.db_manager.execute_select(
                    "SELECT id, user_id, question, response, liked, created_at FROM ai_responses WHERE liked = ? ORDER BY created_at DESC",
                    (rating_filter,)
                )
            
            self.feedback_table.setRowCount(len(feedbacks))
            
            for row, feedback in enumerate(feedbacks):
                id, user_id, question, response, liked, created_at = feedback
                
                short_question = question[:80] + "..." if len(question) > 80 else question
                short_response = response[:80] + "..." if len(response) > 80 else response
                
                if liked == 1:
                    rating_display = "👍"
                    rating_item = QTableWidgetItem(rating_display)
                    rating_item.setBackground(QBrush(QColor(144, 238, 144)))
                else:
                    rating_display = "👎" 
                    rating_item = QTableWidgetItem(rating_display)
                    rating_item.setBackground(QBrush(QColor(255, 182, 193)))
                
                self.feedback_table.setItem(row, 0, QTableWidgetItem(str(id)))
                self.feedback_table.setItem(row, 1, QTableWidgetItem(str(user_id)))
                self.feedback_table.setItem(row, 2, QTableWidgetItem(short_question))
                self.feedback_table.setItem(row, 3, QTableWidgetItem(short_response))
                self.feedback_table.setItem(row, 4, rating_item)
                self.feedback_table.setItem(row, 5, QTableWidgetItem(created_at))
            
        except Exception as e:
            print(f"❌ Error loading feedback: {e}")
            QMessageBox.critical(self, "Ошибка", f"Ошибка загрузки оценок: {e}")
    
    def filter_feedback(self):
        filter_text = self.filter_combo.currentText()
        
        if filter_text == "Все оценки":
            self.load_feedback()
        elif filter_text == "Только понравившиеся":
            self.load_feedback(1)
        elif filter_text == "Только не понравившиеся":
            self.load_feedback(0)
    
    def show_feedback_details(self):
        selected_rows = self.feedback_table.selectionModel().selectedRows()
        if not selected_rows:
            self.full_question.clear()
            self.full_answer.clear()
            self.change_rating_btn.setEnabled(False)
            return
        
        row = selected_rows[0].row()
        
        try:
            feedback_id = int(self.feedback_table.item(row, 0).text())
            
            full_feedback = self.db_manager.execute_select(
                "SELECT question, response, liked FROM ai_responses WHERE id = ?",
                (feedback_id,)
            )
            
            if full_feedback:
                full_question, full_response, liked = full_feedback[0]
                self.full_question.setPlainText(full_question)
                self.full_answer.setPlainText(full_response)
                self.change_rating_btn.setEnabled(True)
        except Exception as e:
            print(f"❌ Error loading full feedback: {e}")
    
    def change_rating(self):
        selected_rows = self.feedback_table.selectionModel().selectedRows()
        if not selected_rows:
            return
        
        row = selected_rows[0].row()
        feedback_id = int(self.feedback_table.item(row, 0).text())
        
        try:
            current_feedback = self.db_manager.execute_select(
                "SELECT liked FROM ai_responses WHERE id = ?",
                (feedback_id,)
            )
            
            if not current_feedback:
                return
            
            current_liked = current_feedback[0][0]
            new_liked = 0 if current_liked == 1 else 1
            
            result = self.db_manager.execute_query(
                "UPDATE ai_responses SET liked = ? WHERE id = ?",
                (new_liked, feedback_id)
            )
            
            if result:
                if new_liked == 1:
                    rating_display = "👍"
                    rating_item = QTableWidgetItem(rating_display)
                    rating_item.setBackground(QBrush(QColor(144, 238, 144)))
                else:
                    rating_display = "👎"
                    rating_item = QTableWidgetItem(rating_display)
                    rating_item.setBackground(QBrush(QColor(255, 182, 193)))
                
                self.feedback_table.setItem(row, 4, rating_item)
                
                current_filter = self.filter_combo.currentText()
                if current_filter != "Все оценки":
                    self.filter_feedback()
                
                QMessageBox.information(self, "Успех", "Оценка изменена")
                
        except Exception as e:
            print(f"❌ Error changing rating: {e}")
            QMessageBox.critical(self, "Ошибка", f"Не удалось изменить оценку: {e}")

class AdminPanel(QMainWindow):
    def __init__(self):
        super().__init__()
        
        self.db_manager = DatabaseManager(DATABASE_PATH)
        self.stats = BotStatistics(self.db_manager)
        self.telegram = TelegramAPI(BOT_TOKEN)
        
        self.check_and_create_tables()
        
        self.broadcast_worker = None
        
        self.init_ui()
        self.load_all_data()
    
    def check_and_create_tables(self):
        try:
            create_ai_responses = """
            CREATE TABLE IF NOT EXISTS ai_responses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                question TEXT NOT NULL,
                response TEXT NOT NULL,
                liked BOOLEAN DEFAULT 0,
                used_count INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
            
            create_chat_sessions = """
            CREATE TABLE IF NOT EXISTS chat_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                messages TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
            
            self.db_manager.execute_query(create_ai_responses)
            self.db_manager.execute_query(create_chat_sessions)
            
        except Exception as e:
            print(f"❌ Error creating tables: {e}")
    
    def init_ui(self):
        self.setWindowTitle('Telegram Bot Admin Panel')
        self.setGeometry(100, 100, 1400, 900)
        
        self.setStyleSheet("""
            QMainWindow {
                background-color: #f5f5f5;
            }
            QTabWidget::pane {
                border: 1px solid #C2C7CB;
                background-color: white;
            }
            QTabBar::tab {
                background-color: #E1E1E1;
                border: 1px solid #C4C4C3;
                padding: 8px 20px;
                margin-right: 2px;
            }
            QTabBar::tab:selected {
                background-color: #4CAF50;
                color: white;
            }
            QGroupBox {
                font-weight: bold;
                border: 2px solid #CCCCCC;
                border-radius: 5px;
                margin-top: 1ex;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
            }
            QPushButton {
                background-color: #4CAF50;
                border: none;
                color: white;
                padding: 8px 16px;
                text-align: center;
                text-decoration: none;
                font-size: 14px;
                margin: 4px 2px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
            QPushButton:pressed {
                background-color: #3d8b40;
            }
            QTableWidget {
                gridline-color: #d0d0d0;
                selection-background-color: #4CAF50;
            }
            QHeaderView::section {
                background-color: #f0f0f0;
                padding: 4px;
                border: 1px solid #d0d0d0;
                font-weight: bold;
            }
        """)
        
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        
        title_widget = QWidget()
        title_layout = QHBoxLayout(title_widget)
        title_layout.setContentsMargins(0, 0, 0, 20)
        
        title = QLabel('Панель управления Telegram ботом')
        title.setFont(QFont('Arial', 18, QFont.Bold))
        title.setStyleSheet("color: #2E7D32; padding: 10px;")
        title.setAlignment(Qt.AlignCenter)
        
        title_layout.addWidget(title)
        layout.addWidget(title_widget)
        
        self.tabs = QTabWidget()
        layout.addWidget(self.tabs)
        
        self.create_dashboard_tab()
        self.create_questions_tab()
        self.create_users_tab()
        self.create_broadcast_tab()
        self.create_statistics_tab()
        self.create_ai_dialogs_tab()
        self.create_ai_feedback_tab()
        self.create_settings_tab()
        
        self.status_bar = self.statusBar()
        self.status_bar.showMessage('Готов к работе')
    
    def create_dashboard_tab(self):
        dashboard_widget = QWidget()
        layout = QVBoxLayout(dashboard_widget)
        
        stats_group = QGroupBox("📊 Общая статистика")
        stats_layout = QGridLayout(stats_group)
        
        stats_cards = [
            ("👥 Всего пользователей", "total_users_card"),
            ("🔥 Активных", "active_users_card"), 
            ("🚫 Заблокированных", "banned_users_card"),
            ("⭐ Всего баллов", "total_points_card"),
            ("🎮 Всего игр", "total_games_card"),
            ("❓ Всего вопросов", "total_questions_card"),
            ("✅ Правильных ответов", "correct_answers_card"),
            ("📈 Средняя точность", "avg_accuracy_card")
        ]
        
        self.stats_cards = {}
        row, col = 0, 0
        for title, key in stats_cards:
            card = QGroupBox(title)
            card_layout = QVBoxLayout(card)
            
            value_label = QLabel("0")
            value_label.setFont(QFont('Arial', 20, QFont.Bold))
            value_label.setAlignment(Qt.AlignCenter)
            value_label.setStyleSheet("color: #2E7D32; padding: 10px;")
            
            card_layout.addWidget(value_label)
            stats_layout.addWidget(card, row, col)
            
            self.stats_cards[key] = value_label
            
            col += 1
            if col > 2:
                col = 0
                row += 1
        
        layout.addWidget(stats_group)
        
        actions_group = QGroupBox("⚡ Быстрые действия")
        actions_layout = QHBoxLayout(actions_group)
        
        self.refresh_stats_btn = QPushButton("🔄 Обновить статистику")
        self.refresh_stats_btn.clicked.connect(self.update_stats)
        
        self.add_question_btn = QPushButton("➕ Добавить вопрос")
        self.add_question_btn.clicked.connect(self.add_question)
        
        self.broadcast_btn = QPushButton("📢 Создать рассылку")
        self.broadcast_btn.clicked.connect(lambda: self.tabs.setCurrentIndex(3))
        
        self.stats_btn = QPushButton("📈 Подробная статистика")
        self.stats_btn.clicked.connect(lambda: self.tabs.setCurrentIndex(4))
        
        actions_layout.addWidget(self.refresh_stats_btn)
        actions_layout.addWidget(self.add_question_btn)
        actions_layout.addWidget(self.broadcast_btn)
        actions_layout.addWidget(self.stats_btn)
        actions_layout.addStretch()
        
        layout.addWidget(actions_group)
        
        activity_group = QGroupBox("📅 Последняя активность")
        activity_layout = QVBoxLayout(activity_group)
        
        self.activity_label = QLabel("Загрузка данных активности...")
        self.activity_label.setWordWrap(True)
        activity_layout.addWidget(self.activity_label)
        
        layout.addWidget(activity_group)
        
        layout.addStretch()
        
        self.tabs.addTab(dashboard_widget, "🏠 Дашборд")
    
    def create_questions_tab(self):
        questions_widget = QWidget()
        layout = QVBoxLayout(questions_widget)
        
        control_group = QGroupBox("Управление вопросами")
        control_layout = QHBoxLayout(control_group)
        
        self.add_question_btn = QPushButton("➕ Добавить вопрос")
        self.add_question_btn.clicked.connect(self.add_question)
        
        self.edit_question_btn = QPushButton("✏️ Редактировать")
        self.edit_question_btn.clicked.connect(self.edit_question)
        
        self.delete_question_btn = QPushButton("🗑️ Удалить")
        self.delete_question_btn.clicked.connect(self.delete_question)
        
        self.refresh_questions_btn = QPushButton("🔄 Обновить")
        self.refresh_questions_btn.clicked.connect(self.load_questions)
        
        control_layout.addWidget(self.add_question_btn)
        control_layout.addWidget(self.edit_question_btn)
        control_layout.addWidget(self.delete_question_btn)
        control_layout.addWidget(self.refresh_questions_btn)
        control_layout.addStretch()
        
        layout.addWidget(control_group)
        
        search_group = QGroupBox("Поиск и фильтрация")
        search_layout = QHBoxLayout(search_group)
        
        self.question_search_input = QLineEdit()
        self.question_search_input.setPlaceholderText("Поиск по тексту вопроса...")
        self.question_search_input.textChanged.connect(self.search_questions)
        
        search_layout.addWidget(QLabel("Поиск:"))
        search_layout.addWidget(self.question_search_input)
        
        layout.addWidget(search_group)
        
        self.questions_table = QTableWidget()
        self.questions_table.setColumnCount(7)
        self.questions_table.setHorizontalHeaderLabels([
            "ID", "Тема", "Вопрос", "Варианты ответов", "Правильный ответ", "Баллы", "Сложность"
        ])
        self.questions_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.questions_table.setSelectionBehavior(QTableWidget.SelectRows)
        
        layout.addWidget(self.questions_table)
        
        self.tabs.addTab(questions_widget, "❓ Вопросы")
    
    def create_users_tab(self):
        users_widget = QWidget()
        layout = QVBoxLayout(users_widget)
        
        search_group = QGroupBox("Поиск пользователей")
        search_layout = QHBoxLayout(search_group)
        
        self.user_search_input = QLineEdit()
        self.user_search_input.setPlaceholderText("Поиск по ID, имени или username...")
        
        self.user_search_btn = QPushButton("🔍 Поиск")
        self.user_search_btn.clicked.connect(self.search_users)
        
        self.show_all_users_btn = QPushButton("👥 Все пользователи")
        self.show_all_users_btn.clicked.connect(self.load_all_users)
        
        search_layout.addWidget(QLabel("Поиск:"))
        search_layout.addWidget(self.user_search_input)
        search_layout.addWidget(self.user_search_btn)
        search_layout.addWidget(self.show_all_users_btn)
        search_layout.addStretch()
        
        layout.addWidget(search_group)
        
        self.users_table = QTableWidget()
        self.users_table.setColumnCount(6)
        self.users_table.setHorizontalHeaderLabels([
            "ID", "Username", "Имя", "Фамилия", "Баллы", "Статус"
        ])
        self.users_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.users_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.users_table.doubleClicked.connect(self.manage_user)
        
        layout.addWidget(self.users_table)
        
        user_actions_layout = QHBoxLayout()
        
        self.manage_user_btn = QPushButton("👤 Управление пользователем")
        self.manage_user_btn.clicked.connect(self.manage_user)
        
        self.ban_user_btn = QPushButton("🚫 Заблокировать")
        self.ban_user_btn.clicked.connect(self.ban_selected_user)
        
        self.unban_user_btn = QPushButton("✅ Разблокировать")
        self.unban_user_btn.clicked.connect(self.unban_selected_user)
        
        user_actions_layout.addWidget(self.manage_user_btn)
        user_actions_layout.addWidget(self.ban_user_btn)
        user_actions_layout.addWidget(self.unban_user_btn)
        user_actions_layout.addStretch()
        
        layout.addLayout(user_actions_layout)
        
        self.tabs.addTab(users_widget, "👥 Пользователи")
    
    def create_broadcast_tab(self):
        broadcast_widget = QWidget()
        layout = QVBoxLayout(broadcast_widget)
        
        message_group = QGroupBox("Сообщение для рассылки")
        message_layout = QVBoxLayout(message_group)
        
        self.broadcast_message_input = QTextEdit()
        self.broadcast_message_input.setMaximumHeight(150)
        self.broadcast_message_input.setPlaceholderText("Введите сообщение для рассылки...")
        message_layout.addWidget(self.broadcast_message_input)
        
        layout.addWidget(message_group)
        
        control_group = QGroupBox("Управление рассылкой")
        control_layout = QHBoxLayout(control_group)
        
        self.start_broadcast_btn = QPushButton("📢 Начать рассылку")
        self.start_broadcast_btn.clicked.connect(self.start_broadcast)
        
        self.stop_broadcast_btn = QPushButton("⏹️ Остановить")
        self.stop_broadcast_btn.clicked.connect(self.stop_broadcast)
        self.stop_broadcast_btn.setEnabled(False)
        
        control_layout.addWidget(self.start_broadcast_btn)
        control_layout.addWidget(self.stop_broadcast_btn)
        control_layout.addStretch()
        
        layout.addWidget(control_group)
        
        progress_group = QGroupBox("Прогресс рассылки")
        progress_layout = QVBoxLayout(progress_group)
        
        self.broadcast_progress = QProgressBar()
        self.broadcast_progress.setVisible(False)
        progress_layout.addWidget(self.broadcast_progress)
        
        self.broadcast_status = QLabel("Готов к рассылке")
        progress_layout.addWidget(self.broadcast_status)
        
        layout.addWidget(progress_group)
        
        results_group = QGroupBox("Результаты рассылки")
        results_layout = QVBoxLayout(results_group)
        
        self.broadcast_results = QTextEdit()
        self.broadcast_results.setMaximumHeight(200)
        results_layout.addWidget(self.broadcast_results)
        
        layout.addWidget(results_group)
        
        self.tabs.addTab(broadcast_widget, "📢 Рассылка")
    
    def create_statistics_tab(self):
        statistics_tab = StatisticsTab()
        self.tabs.addTab(statistics_tab, "📈 Статистика")
    
    def create_ai_dialogs_tab(self):
        ai_dialogs_tab = AIDialogsTab()
        self.tabs.addTab(ai_dialogs_tab, "💬 Диалоги с ИИ")
    
    def create_ai_feedback_tab(self):
        ai_feedback_tab = AIFeedbackTab()
        self.tabs.addTab(ai_feedback_tab, "⭐ Оценки ИИ")
    
    def create_settings_tab(self):
        settings_widget = QWidget()
        layout = QVBoxLayout(settings_widget)
        
        bot_settings_group = QGroupBox("Настройки бота")
        bot_settings_layout = QFormLayout(bot_settings_group)
        
        self.bot_token_input = QLineEdit()
        self.bot_token_input.setText(BOT_TOKEN)
        bot_settings_layout.addRow("Токен бота:", self.bot_token_input)
        
        self.admin_ids_input = QLineEdit()
        self.admin_ids_input.setText(",".join(map(str, ADMIN_IDS)))
        bot_settings_layout.addRow("ID администраторов:", self.admin_ids_input)
        
        layout.addWidget(bot_settings_group)
        
        db_group = QGroupBox("Управление базой данных")
        db_layout = QVBoxLayout(db_group)
        
        self.backup_db_btn = QPushButton("💾 Создать резервную копию")
        self.backup_db_btn.clicked.connect(self.backup_database)
        
        self.create_admin_btn = QPushButton("👨‍💼 Создать администратора")
        self.create_admin_btn.clicked.connect(self.create_admin)
        
        db_layout.addWidget(self.backup_db_btn)
        db_layout.addWidget(self.create_admin_btn)
        
        layout.addWidget(db_group)
        
        layout.addStretch()
        
        self.tabs.addTab(settings_widget, "⚙️ Настройки")
    
    def load_all_data(self):
        self.load_questions()
        self.update_stats()
        self.load_users()
        self.update_activity()
    
    def load_questions(self):
        try:
            tables = self.db_manager.execute_select("SELECT name FROM sqlite_master WHERE type='table' AND name='questions'")
            if not tables:
                self.questions_table.setRowCount(0)
                self.status_bar.showMessage('Таблица вопросов не найдена')
                return
            
            questions = self.db_manager.execute_select("SELECT id, topic, question, options, correct_answer, points, difficulty FROM questions ORDER BY id")
            
            self.questions_table.setRowCount(len(questions))
            
            for row, question in enumerate(questions):
                id, topic, question_text, options, correct_answer, points, difficulty = question
                
                try:
                    options_list = json.loads(options)
                    options_text = ", ".join(options_list)
                except:
                    options_text = options
                
                self.questions_table.setItem(row, 0, QTableWidgetItem(str(id)))
                self.questions_table.setItem(row, 1, QTableWidgetItem(topic))
                self.questions_table.setItem(row, 2, QTableWidgetItem(question_text))
                self.questions_table.setItem(row, 3, QTableWidgetItem(options_text))
                self.questions_table.setItem(row, 4, QTableWidgetItem(str(correct_answer)))
                self.questions_table.setItem(row, 5, QTableWidgetItem(str(points)))
                self.questions_table.setItem(row, 6, QTableWidgetItem(difficulty))
            
            self.status_bar.showMessage(f'Загружено {len(questions)} вопросов')
            
        except Exception as e:
            self.status_bar.showMessage(f'Ошибка загрузки вопросов: {e}')
    
    def search_questions(self):
        search_term = self.question_search_input.text().strip()
        if not search_term:
            self.load_questions()
            return
        
        try:
            query = """
            SELECT id, topic, question, options, correct_answer, points, difficulty 
            FROM questions 
            WHERE question LIKE ? 
            ORDER BY id
            """
            questions = self.db_manager.execute_select(query, (f'%{search_term}%',))
            
            self.questions_table.setRowCount(len(questions))
            
            for row, question in enumerate(questions):
                id, topic, question_text, options, correct_answer, points, difficulty = question
                
                try:
                    options_list = json.loads(options)
                    options_text = ", ".join(options_list)
                except:
                    options_text = options
                
                self.questions_table.setItem(row, 0, QTableWidgetItem(str(id)))
                self.questions_table.setItem(row, 1, QTableWidgetItem(topic))
                self.questions_table.setItem(row, 2, QTableWidgetItem(question_text))
                self.questions_table.setItem(row, 3, QTableWidgetItem(options_text))
                self.questions_table.setItem(row, 4, QTableWidgetItem(str(correct_answer)))
                self.questions_table.setItem(row, 5, QTableWidgetItem(str(points)))
                self.questions_table.setItem(row, 6, QTableWidgetItem(difficulty))
            
            self.status_bar.showMessage(f'Найдено {len(questions)} вопросов')
            
        except Exception as e:
            self.status_bar.showMessage(f'Ошибка поиска: {e}')
    
    def add_question(self):
        dialog = QuestionDialog(self)
        if dialog.exec_() == QDialog.Accepted:
            self.load_questions()
    
    def edit_question(self):
        selected_rows = self.questions_table.selectionModel().selectedRows()
        if not selected_rows:
            QMessageBox.warning(self, "Ошибка", "Выберите вопрос для редактирования")
            return
        
        question_id = int(self.questions_table.item(selected_rows[0].row(), 0).text())
        dialog = QuestionDialog(self, question_id)
        if dialog.exec_() == QDialog.Accepted:
            self.load_questions()
    
    def delete_question(self):
        selected_rows = self.questions_table.selectionModel().selectedRows()
        if not selected_rows:
            QMessageBox.warning(self, "Ошибка", "Выберите вопрос для удаления")
            return
        
        question_id = int(self.questions_table.item(selected_rows[0].row(), 0).text())
        question_text = self.questions_table.item(selected_rows[0].row(), 2).text()
        
        reply = QMessageBox.question(
            self, 
            "Подтверждение удаления", 
            f"Вы уверены, что хотите удалить вопрос?\n\n{question_text[:100]}...",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            try:
                result = self.db_manager.execute_query("DELETE FROM questions WHERE id = ?", (question_id,))
                if result:
                    QMessageBox.information(self, "Успех", "Вопрос удален")
                    self.load_questions()
                else:
                    QMessageBox.critical(self, "Ошибка", "Не удалось удалить вопрос")
            except Exception as e:
                QMessageBox.critical(self, "Ошибка", f"Ошибка удаления: {e}")
    
    def load_users(self):
        try:
            users = self.stats.get_all_users()
            self.users_table.setRowCount(len(users))
            
            for row, user in enumerate(users):
                user_id, username, first_name, last_name, points, _, created_at, is_banned = user
                
                status = "✅ Активен" if not is_banned else "🚫 Заблокирован"
                
                self.users_table.setItem(row, 0, QTableWidgetItem(str(user_id)))
                self.users_table.setItem(row, 1, QTableWidgetItem(username or ""))
                self.users_table.setItem(row, 2, QTableWidgetItem(first_name or ""))
                self.users_table.setItem(row, 3, QTableWidgetItem(last_name or ""))
                self.users_table.setItem(row, 4, QTableWidgetItem(str(points)))
                self.users_table.setItem(row, 5, QTableWidgetItem(status))
            
            self.status_bar.showMessage(f'Загружено {len(users)} пользователей')
            
        except Exception as e:
            self.status_bar.showMessage(f'Ошибка загрузки пользователей: {e}')
    
    def search_users(self):
        search_term = self.user_search_input.text().strip()
        if not search_term:
            self.load_users()
            return
        
        try:
            users = self.stats.search_users(search_term)
            self.users_table.setRowCount(len(users))
            
            for row, user in enumerate(users):
                user_id, username, first_name, last_name, created_at = user
                
                points = 0
                is_banned = False
                
                status = "✅ Активен" if not is_banned else "🚫 Заблокирован"
                
                self.users_table.setItem(row, 0, QTableWidgetItem(str(user_id)))
                self.users_table.setItem(row, 1, QTableWidgetItem(username or ""))
                self.users_table.setItem(row, 2, QTableWidgetItem(first_name or ""))
                self.users_table.setItem(row, 3, QTableWidgetItem(last_name or ""))
                self.users_table.setItem(row, 4, QTableWidgetItem(str(points)))
                self.users_table.setItem(row, 5, QTableWidgetItem(status))
            
            self.status_bar.showMessage(f'Найдено {len(users)} пользователей')
            
        except Exception as e:
            self.status_bar.showMessage(f'Ошибка поиска пользователей: {e}')
    
    def load_all_users(self):
        self.load_users()
    
    def manage_user(self):
        selected_rows = self.users_table.selectionModel().selectedRows()
        if not selected_rows:
            QMessageBox.warning(self, "Ошибка", "Выберите пользователя для управления")
            return
        
        user_id = int(self.users_table.item(selected_rows[0].row(), 0).text())
        dialog = UserManagementDialog(self, user_id)
        dialog.exec_()
        self.load_users()
    
    def ban_selected_user(self):
        selected_rows = self.users_table.selectionModel().selectedRows()
        if not selected_rows:
            QMessageBox.warning(self, "Ошибка", "Выберите пользователя для блокировки")
            return
        
        user_id = int(self.users_table.item(selected_rows[0].row(), 0).text())
        username = self.users_table.item(selected_rows[0].row(), 1).text()
        
        reply = QMessageBox.question(
            self, 
            "Подтверждение блокировки", 
            f"Вы уверены, что хотите заблокировать пользователя {username} (ID: {user_id})?",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            try:
                if self.stats.ban_user(user_id, ADMIN_IDS[0] if ADMIN_IDS else 0, "Блокировка администратором"):
                    QMessageBox.information(self, "Успех", "Пользователь заблокирован")
                    self.load_users()
                else:
                    QMessageBox.critical(self, "Ошибка", "Не удалось заблокировать пользователя")
            except Exception as e:
                QMessageBox.critical(self, "Ошибка", f"Ошибка блокировки: {e}")
    
    def unban_selected_user(self):
        selected_rows = self.users_table.selectionModel().selectedRows()
        if not selected_rows:
            QMessageBox.warning(self, "Ошибка", "Выберите пользователя для разблокировки")
            return
        
        user_id = int(self.users_table.item(selected_rows[0].row(), 0).text())
        username = self.users_table.item(selected_rows[0].row(), 1).text()
        
        reply = QMessageBox.question(
            self, 
            "Подтверждение разблокировки", 
            f"Вы уверены, что хотите разблокировать пользователя {username} (ID: {user_id})?",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            try:
                if self.stats.unban_user(user_id):
                    QMessageBox.information(self, "Успех", "Пользователь разблокирован")
                    self.load_users()
                else:
                    QMessageBox.critical(self, "Ошибка", "Не удалось разблокировать пользователя")
            except Exception as e:
                QMessageBox.critical(self, "Ошибка", f"Ошибка разблокировки: {e}")
    
    def start_broadcast(self):
        message = self.broadcast_message_input.toPlainText().strip()
        
        if not message:
            QMessageBox.warning(self, "Ошибка", "Введите сообщение для рассылки")
            return
        
        self.broadcast_worker = BroadcastWorker(self.db_manager, self.telegram, message)
        self.broadcast_worker.progress.connect(self.update_broadcast_progress)
        self.broadcast_worker.finished.connect(self.broadcast_finished)
        
        self.start_broadcast_btn.setEnabled(False)
        self.stop_broadcast_btn.setEnabled(True)
        self.broadcast_progress.setVisible(True)
        self.broadcast_status.setText("Рассылка начата...")
        
        self.broadcast_worker.start()
    
    def stop_broadcast(self):
        if self.broadcast_worker and self.broadcast_worker.isRunning():
            self.broadcast_worker.is_running = False
            self.broadcast_status.setText("Рассылка останавливается...")
    
    def update_broadcast_progress(self, progress, current, status):
        self.broadcast_progress.setValue(progress)
        self.broadcast_status.setText(status)
    
    def broadcast_finished(self, result):
        self.start_broadcast_btn.setEnabled(True)
        self.stop_broadcast_btn.setEnabled(False)
        self.broadcast_progress.setVisible(False)
        
        if 'error' in result:
            self.broadcast_status.setText(f"Ошибка: {result['error']}")
            QMessageBox.critical(self, "Ошибка", f"Ошибка рассылки: {result['error']}")
        else:
            success = result['success']
            failed = result['failed']
            banned = result['banned']
            total = result['total']
            
            self.broadcast_status.setText(f"Завершено: Успешно {success}, Ошибок {failed}, Заблокировано {banned}")
            
            results_text = f"Результаты рассылки:\n"
            results_text += f"✅ Успешно: {success}\n"
            results_text += f"❌ Ошибок: {failed}\n"
            results_text += f"🚫 Заблокировано: {banned}\n"
            results_text += f"📊 Всего: {total}\n\n"
            
            for i, res in enumerate(result['results'][-20:]):
                results_text += f"{res}\n"
            
            self.broadcast_results.setPlainText(results_text)
            
            QMessageBox.information(self, "Успех", 
                f"Рассылка завершена!\n\n"
                f"Успешно: {success}\n"
                f"Ошибок: {failed}\n"
                f"Заблокировано: {banned}"
            )
    
    def update_stats(self):
        try:
            stats = self.stats.get_bot_stats()
            
            self.stats_cards['total_users_card'].setText(str(stats['total_users']))
            self.stats_cards['active_users_card'].setText(str(stats['active_users']))
            self.stats_cards['banned_users_card'].setText(str(stats['banned_users']))
            self.stats_cards['total_points_card'].setText(str(stats['total_points']))
            self.stats_cards['total_games_card'].setText(str(stats['total_games']))
            self.stats_cards['total_questions_card'].setText(str(stats['total_questions']))
            self.stats_cards['correct_answers_card'].setText(str(stats['total_correct']))
            
            avg_accuracy = (stats['total_correct'] / stats['total_questions'] * 100) if stats['total_questions'] > 0 else 0
            self.stats_cards['avg_accuracy_card'].setText(f"{avg_accuracy:.1f}%")
            
            self.status_bar.showMessage('Статистика обновлена')
            
        except Exception as e:
            self.status_bar.showMessage(f'Ошибка обновления статистики: {e}')
    
    def update_activity(self):
        try:
            daily_activity = self.stats.get_daily_activity(3)
            activity_text = "<b>Активность за последние 3 дня:</b><br>"
            
            if daily_activity:
                for date, new_users, active_users in daily_activity:
                    activity_text += f"• {date}: +{new_users} новых, {active_users} активных<br>"
            else:
                activity_text += "Нет данных об активности"
            
            self.activity_label.setText(activity_text)
            
        except Exception as e:
            self.activity_label.setText(f"Ошибка загрузки активности: {e}")
    
    def backup_database(self):
        try:
            import shutil
            import datetime
            
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = f"quiz_bot_backup_{timestamp}.db"
            
            shutil.copy2(DATABASE_PATH, backup_path)
            
            QMessageBox.information(self, "Успех", f"Резервная копия создана: {backup_path}")
            
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось создать резервную копию: {e}")
    
    def create_admin(self):
        try:
            conn = sqlite3.connect(DATABASE_PATH)
            cursor = conn.cursor()
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS admins (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            password_hash = hashlib.md5("admin123".encode()).hexdigest()
            
            cursor.execute(
                "INSERT OR REPLACE INTO admins (username, password_hash) VALUES (?, ?)",
                ("admin", password_hash)
            )
            
            conn.commit()
            conn.close()
            
            QMessageBox.information(self, "Успех", 
                "Администратор создан!\n\n"
                "Логин: admin\n"
                "Пароль: admin123\n\n"
                "Теперь вы можете включить авторизацию в коде."
            )
            
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось создать администратора: {e}")

def main():
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    
    login_dialog = LoginDialog()
    if login_dialog.exec_() == QDialog.Accepted:
        admin_panel = AdminPanel()
        admin_panel.show()
        sys.exit(app.exec_())
    else:
        sys.exit(0)

if __name__ == '__main__':

    main()


