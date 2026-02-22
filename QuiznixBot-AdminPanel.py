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
        self.setWindowTitle("Admin Authorization")
        self.setFixedSize(400, 200)
        self.setModal(True)
        
        layout = QVBoxLayout()
        
        form_layout = QFormLayout()
        
        self.username_input = QLineEdit()
        self.username_input.setPlaceholderText("Enter username")
        form_layout.addRow("Username:", self.username_input)
        
        self.password_input = QLineEdit()
        self.password_input.setPlaceholderText("Enter password")
        self.password_input.setEchoMode(QLineEdit.Password)
        form_layout.addRow("Password:", self.password_input)
        
        layout.addLayout(form_layout)
        
        button_layout = QHBoxLayout()
        
        self.login_btn = QPushButton("Login")
        self.login_btn.clicked.connect(self.attempt_login)
        
        self.cancel_btn = QPushButton("Cancel")
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
            QMessageBox.warning(self, "Error", "Fill in all fields")
            return
        
        self.login_btn.setEnabled(False)
        self.login_btn.setText("Checking...")
        
        if self.check_credentials(username, password):
            self.accept()
        else:
            QMessageBox.warning(self, "Error", "Invalid username or password")
            self.password_input.clear()
            self.password_input.setFocus()
        
        self.login_btn.setEnabled(True)
        self.login_btn.setText("Login")
    
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
            logger.error(f"Error checking credentials: {e}")
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
        title = "Add Question" if question_id is None else "Edit Question"
        self.setWindowTitle(title)
        self.setFixedSize(500, 400)
        
        layout = QVBoxLayout()
        
        form_layout = QFormLayout()
        
        self.topic_input = QLineEdit()
        self.topic_input.setPlaceholderText("For example: history, geography")
        form_layout.addRow("Topic:", self.topic_input)
        
        self.question_input = QTextEdit()
        self.question_input.setMaximumHeight(80)
        self.question_input.setPlaceholderText("Enter question text")
        form_layout.addRow("Question:", self.question_input)
        
        self.options_input = QTextEdit()
        self.options_input.setMaximumHeight(100)
        self.options_input.setPlaceholderText("Enter answer options separated by commas")
        form_layout.addRow("Answer options:", self.options_input)
        
        self.correct_answer_input = QSpinBox()
        self.correct_answer_input.setMinimum(0)
        self.correct_answer_input.setMaximum(3)
        self.correct_answer_input.setValue(0)
        form_layout.addRow("Correct answer number (0-3):", self.correct_answer_input)
        
        self.points_input = QSpinBox()
        self.points_input.setMinimum(1)
        self.points_input.setMaximum(10)
        self.points_input.setValue(5)
        form_layout.addRow("Points:", self.points_input)
        
        self.difficulty_input = QComboBox()
        self.difficulty_input.addItems(["easy", "medium", "hard"])
        form_layout.addRow("Difficulty:", self.difficulty_input)
        
        layout.addLayout(form_layout)
        
        button_layout = QHBoxLayout()
        
        self.save_btn = QPushButton("Save")
        self.save_btn.clicked.connect(self.save_question)
        
        self.cancel_btn = QPushButton("Cancel")
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
            logger.error(f"Error loading question data: {e}")
    
    def save_question(self):
        try:
            topic = self.topic_input.text().strip()
            question = self.question_input.toPlainText().strip()
            options_text = self.options_input.toPlainText().strip()
            correct_answer = self.correct_answer_input.value()
            points = self.points_input.value()
            difficulty = self.difficulty_input.currentText()
            
            if not all([topic, question, options_text]):
                QMessageBox.warning(self, "Error", "Fill in all required fields")
                return
            
            options_list = [opt.strip() for opt in options_text.split(",") if opt.strip()]
            if len(options_list) != 4:
                QMessageBox.warning(self, "Error", "Must have exactly 4 answer options")
                return
            
            if correct_answer >= len(options_list):
                QMessageBox.warning(self, "Error", "Correct answer number must be from 0 to 3")
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
                QMessageBox.information(self, "Success", "Question saved")
                self.accept()
            else:
                QMessageBox.critical(self, "Error", "Could not save question")
                
        except Exception as e:
            logger.error(f"Error saving question: {e}")
            QMessageBox.critical(self, "Error", f"Error saving: {e}")

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
                user_id, username or "", first_name or "", last_name or "", admin_id, reason or "Not specified"
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
        message = f"🚫 <b>You have been banned from the bot!</b>\n\n"
        if reason:
            message += f"<b>Reason:</b> {reason}\n\n"
        message += "❌ You can no longer use the bot's functions.\n"
        message += "📞 For unban, contact the administrator."
        
        return self.send_message(user_id, message)
    
    def send_unban_notification(self, user_id):
        message = f"✅ <b>You have been unbanned!</b>\n\n"
        message += "🎉 You can now use all bot functions again.\n"
        message += "Thank you for your understanding!"
        
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
                    results.append(f"🚫 {user_id}: Banned (skipped)")
                    continue
                
                result = self.telegram.send_message(user_id, self.message_text)
                
                if result and result.get('ok'):
                    success += 1
                    results.append(f"✅ {user_id}: Success")
                else:
                    failed += 1
                    error = result.get('description', 'Unknown error') if result else 'Timeout'
                    results.append(f"❌ {user_id}: Error - {error}")
                
                progress = int((i + 1) / total * 100)
                status = f"Sent: {i+1}/{total} | Success: {success} | Errors: {failed}"
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
        
        title = QLabel("📈 Detailed Statistics")
        title.setFont(QFont('Arial', 16, QFont.Bold))
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)
        
        refresh_layout = QHBoxLayout()
        
        self.refresh_btn = QPushButton("🔄 Refresh All Statistics")
        self.refresh_btn.clicked.connect(self.load_statistics)
        
        refresh_layout.addWidget(self.refresh_btn)
        refresh_layout.addStretch()
        
        layout.addLayout(refresh_layout)
        
        splitter = QSplitter(Qt.Vertical)
        
        top_widget = QWidget()
        top_layout = QVBoxLayout(top_widget)
        
        general_stats_group = QGroupBox("📊 General Bot Statistics")
        general_stats_layout = QGridLayout(general_stats_group)
        
        self.total_users_label = QLabel("Total users: 0")
        self.active_users_label = QLabel("Active users: 0")
        self.banned_users_label = QLabel("Banned: 0")
        self.total_points_label = QLabel("Total points: 0")
        self.total_games_label = QLabel("Total games: 0")
        self.total_questions_label = QLabel("Total questions: 0")
        self.correct_answers_label = QLabel("Correct answers: 0")
        
        general_stats_layout.addWidget(self.total_users_label, 0, 0)
        general_stats_layout.addWidget(self.active_users_label, 0, 1)
        general_stats_layout.addWidget(self.banned_users_label, 0, 2)
        general_stats_layout.addWidget(self.total_points_label, 1, 0)
        general_stats_layout.addWidget(self.total_games_label, 1, 1)
        general_stats_layout.addWidget(self.total_questions_label, 1, 2)
        general_stats_layout.addWidget(self.correct_answers_label, 2, 0)
        
        top_layout.addWidget(general_stats_group)
        
        top_users_group = QGroupBox("🏆 Top Users")
        top_users_layout = QVBoxLayout(top_users_group)
        
        metric_layout = QHBoxLayout()
        metric_layout.addWidget(QLabel("Sort by:"))
        
        self.metric_combo = QComboBox()
        self.metric_combo.addItems(["Points", "Games", "Accuracy", "Activity"])
        self.metric_combo.currentTextChanged.connect(self.load_top_users)
        
        metric_layout.addWidget(self.metric_combo)
        metric_layout.addStretch()
        
        top_users_layout.addLayout(metric_layout)
        
        self.top_users_table = QTableWidget()
        self.top_users_table.setColumnCount(7)
        self.top_users_table.setHorizontalHeaderLabels([
            "#", "User ID", "Username", "Points", "Games", "Accuracy", "Last Activity"
        ])
        self.top_users_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        
        top_users_layout.addWidget(self.top_users_table)
        
        top_layout.addWidget(top_users_group)
        
        bottom_widget = QWidget()
        bottom_layout = QVBoxLayout(bottom_widget)
        
        detailed_stats_group = QGroupBox("👥 Detailed User Statistics")
        detailed_layout = QVBoxLayout(detailed_stats_group)
        
        search_layout = QHBoxLayout()
        search_layout.addWidget(QLabel("Search user:"))
        
        self.user_search_input = QLineEdit()
        self.user_search_input.setPlaceholderText("Enter User ID to search...")
        
        self.search_btn = QPushButton("🔍 Search")
        self.search_btn.clicked.connect(self.search_user_stats)
        
        self.show_all_btn = QPushButton("👁️ Show All")
        self.show_all_btn.clicked.connect(self.show_all_users_stats)
        
        search_layout.addWidget(self.user_search_input)
        search_layout.addWidget(self.search_btn)
        search_layout.addWidget(self.show_all_btn)
        search_layout.addStretch()
        
        detailed_layout.addLayout(search_layout)
        
        self.detailed_stats_table = QTableWidget()
        self.detailed_stats_table.setColumnCount(10)
        self.detailed_stats_table.setHorizontalHeaderLabels([
            "User ID", "Username", "First Name", "Last Name", "Points", "Games", 
            "Questions", "Correct", "Accuracy%", "Status"
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
            
            self.total_users_label.setText(f"Total users: {stats['total_users']}")
            self.active_users_label.setText(f"Active users: {stats['active_users']}")
            self.banned_users_label.setText(f"Banned: {stats['banned_users']}")
            self.total_points_label.setText(f"Total points: {stats['total_points']}")
            self.total_games_label.setText(f"Total games: {stats['total_games']}")
            self.total_questions_label.setText(f"Total questions: {stats['total_questions']}")
            self.correct_answers_label.setText(f"Correct answers: {stats['total_correct']}")
            
        except Exception as e:
            print(f"❌ Error loading general stats: {e}")
    
    def load_top_users(self):
        try:
            metric_map = {
                "Points": "points",
                "Games": "games", 
                "Accuracy": "accuracy",
                "Activity": "activity"
            }
            
            selected_metric = metric_map.get(self.metric_combo.currentText(), "points")
            top_users = self.stats.get_top_users(10, selected_metric)
            
            self.top_users_table.setRowCount(len(top_users))
            
            for row, user in enumerate(top_users):
                user_id, username, first_name, last_name, points, games, questions, correct, avg_score, last_activity = user
                
                accuracy = (correct / questions * 100) if questions > 0 else 0
                
                self.top_users_table.setItem(row, 0, QTableWidgetItem(str(row + 1)))
                self.top_users_table.setItem(row, 1, QTableWidgetItem(str(user_id)))
                self.top_users_table.setItem(row, 2, QTableWidgetItem(username or f"{first_name or ''} {last_name or ''}".strip() or "Unknown"))
                self.top_users_table.setItem(row, 3, QTableWidgetItem(str(points)))
                self.top_users_table.setItem(row, 4, QTableWidgetItem(str(games)))
                self.top_users_table.setItem(row, 5, QTableWidgetItem(f"{accuracy:.1f}%"))
                self.top_users_table.setItem(row, 6, QTableWidgetItem(last_activity.split()[0] if last_activity else "Unknown"))
                
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
                QMessageBox.warning(self, "Error", "Enter User ID to search")
                return
            
            detailed_stats = self.stats.get_detailed_user_stats(user_id)
            if not detailed_stats:
                QMessageBox.information(self, "Info", f"User with ID {user_id} not found")
                return
            
            self.display_detailed_stats(detailed_stats)
            
        except Exception as e:
            print(f"❌ Error searching user stats: {e}")
            QMessageBox.critical(self, "Error", f"Search error: {e}")
    
    def display_detailed_stats(self, stats_data):
        try:
            self.detailed_stats_table.setRowCount(len(stats_data))
            
            for row, user in enumerate(stats_data):
                user_id, username, first_name, last_name, points, games, questions, correct, incorrect, avg_score, last_activity, created_at, is_banned = user
                
                accuracy = (correct / questions * 100) if questions > 0 else 0
                status = "🚫 Banned" if is_banned else "✅ Active"
                
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
        
        self.setWindowTitle(f"User Management - {user_id}" if user_id else "User Management")
        self.setFixedSize(500, 400)
        
        self.init_ui()
        self.load_user_data()
    
    def init_ui(self):
        layout = QVBoxLayout()
        
        info_group = QGroupBox("User Information")
        info_layout = QFormLayout(info_group)
        
        self.user_id_label = QLabel(str(self.user_id) if self.user_id else "Unknown")
        self.username_label = QLabel("Loading...")
        self.name_label = QLabel("Loading...")
        self.points_label = QLabel("Loading...")
        self.status_label = QLabel("Loading...")
        
        info_layout.addRow("User ID:", self.user_id_label)
        info_layout.addRow("Username:", self.username_label)
        info_layout.addRow("Name:", self.name_label)
        info_layout.addRow("Points:", self.points_label)
        info_layout.addRow("Status:", self.status_label)
        
        layout.addWidget(info_group)
        
        actions_group = QGroupBox("Actions")
        actions_layout = QVBoxLayout(actions_group)
        
        self.ban_btn = QPushButton("🚫 Ban User")
        self.ban_btn.clicked.connect(self.ban_user)
        
        self.unban_btn = QPushButton("✅ Unban User")
        self.unban_btn.clicked.connect(self.unban_user)
        
        self.send_message_btn = QPushButton("📨 Send Message")
        self.send_message_btn.clicked.connect(self.send_message)
        
        actions_layout.addWidget(self.ban_btn)
        actions_layout.addWidget(self.unban_btn)
        actions_layout.addWidget(self.send_message_btn)
        
        layout.addWidget(actions_group)
        
        self.reason_input = QLineEdit()
        self.reason_input.setPlaceholderText("Ban reason (optional)")
        layout.addWidget(QLabel("Ban reason:"))
        layout.addWidget(self.reason_input)
        
        self.message_input = QTextEdit()
        self.message_input.setMaximumHeight(80)
        self.message_input.setPlaceholderText("Message to user...")
        layout.addWidget(QLabel("Message:"))
        layout.addWidget(self.message_input)
        
        button_layout = QHBoxLayout()
        
        self.close_btn = QPushButton("Close")
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
                
                self.username_label.setText(username or "Not specified")
                self.name_label.setText(f"{first_name or ''} {last_name or ''}".strip() or "Not specified")
                self.points_label.setText(str(points))
                self.status_label.setText("🚫 Banned" if is_banned else "✅ Active")
                
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
                QMessageBox.information(self, "Success", "User banned")
                self.telegram.send_ban_notification(self.user_id, reason)
                self.load_user_data()
            else:
                QMessageBox.critical(self, "Error", "Could not ban user")
                
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Ban error: {e}")
    
    def unban_user(self):
        if not self.user_id:
            return
            
        try:
            if self.stats.unban_user(self.user_id):
                QMessageBox.information(self, "Success", "User unbanned")
                self.telegram.send_unban_notification(self.user_id)
                self.load_user_data()
            else:
                QMessageBox.critical(self, "Error", "Could not unban user")
                
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Unban error: {e}")
    
    def send_message(self):
        if not self.user_id:
            return
            
        message = self.message_input.toPlainText().strip()
        if not message:
            QMessageBox.warning(self, "Error", "Enter message")
            return
            
        try:
            result = self.telegram.send_message(self.user_id, message)
            if result and result.get('ok'):
                QMessageBox.information(self, "Success", "Message sent")
                self.message_input.clear()
            else:
                QMessageBox.critical(self, "Error", "Could not send message")
                
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Send error: {e}")

class AIDialogsTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.db_manager = DatabaseManager(DATABASE_PATH)
        self.init_ui()
        self.load_ai_dialogs()
    
    def init_ui(self):
        layout = QVBoxLayout(self)
        
        title = QLabel("💬 AI Dialogs (AI Responses)")
        title.setFont(QFont('Arial', 16, QFont.Bold))
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)
        
        control_layout = QHBoxLayout()
        
        self.refresh_btn = QPushButton("🔄 Refresh")
        self.refresh_btn.clicked.connect(self.load_ai_dialogs)
        
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search by question...")
        self.search_input.textChanged.connect(self.search_dialogs)
        
        self.add_test_group = QGroupBox("Add Test Entry")
        add_test_layout = QFormLayout(self.add_test_group)
        
        self.test_user_id = QLineEdit()
        self.test_user_id.setPlaceholderText("User ID")
        add_test_layout.addRow("User ID:", self.test_user_id)
        
        self.test_question = QTextEdit()
        self.test_question.setMaximumHeight(60)
        self.test_question.setPlaceholderText("Question")
        add_test_layout.addRow("Question:", self.test_question)
        
        self.test_answer = QTextEdit()
        self.test_answer.setMaximumHeight(60)
        self.test_answer.setPlaceholderText("Answer")
        add_test_layout.addRow("Answer:", self.test_answer)
        
        self.add_test_btn = QPushButton("💾 Save Test Entry")
        self.add_test_btn.clicked.connect(self.add_test_dialog)
        add_test_layout.addRow(self.add_test_btn)
        
        control_layout.addWidget(self.refresh_btn)
        control_layout.addWidget(QLabel("Search:"))
        control_layout.addWidget(self.search_input)
        control_layout.addStretch()
        
        layout.addLayout(control_layout)
        layout.addWidget(self.add_test_group)
        
        self.dialogs_table = QTableWidget()
        self.dialogs_table.setColumnCount(7)
        self.dialogs_table.setHorizontalHeaderLabels([
            "ID", "User ID", "Question", "Answer", "Like", "Used", "Date/Time"
        ])
        self.dialogs_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.dialogs_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.dialogs_table.selectionModel().selectionChanged.connect(self.show_dialog_details)
        
        layout.addWidget(self.dialogs_table)
        
        details_group = QGroupBox("Detailed View")
        details_layout = QVBoxLayout(details_group)
        
        details_layout.addWidget(QLabel("Full Question:"))
        self.question_details = QTextEdit()
        self.question_details.setMaximumHeight(80)
        self.question_details.setReadOnly(True)
        details_layout.addWidget(self.question_details)
        
        details_layout.addWidget(QLabel("Full Answer:"))
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
                QMessageBox.information(self, "Info", "Table ai_responses not found")
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
            QMessageBox.critical(self, "Error", f"Error loading dialogs: {e}")
    
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
                QMessageBox.warning(self, "Error", "Fill in all fields")
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
                QMessageBox.information(self, "Success", "Test entry added")
                self.test_user_id.clear()
                self.test_question.clear()
                self.test_answer.clear()
                self.load_ai_dialogs()
            else:
                QMessageBox.critical(self, "Error", "Could not add entry")
                
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error adding entry: {e}")

class AIFeedbackTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.db_manager = DatabaseManager(DATABASE_PATH)
        self.init_ui()
        self.load_feedback()
    
    def init_ui(self):
        layout = QVBoxLayout(self)
        
        title = QLabel("⭐ AI Response Ratings")
        title.setFont(QFont('Arial', 16, QFont.Bold))
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)
        
        control_layout = QHBoxLayout()
        
        self.refresh_btn = QPushButton("🔄 Refresh")
        self.refresh_btn.clicked.connect(self.load_feedback)
        
        self.filter_combo = QComboBox()
        self.filter_combo.addItems(["All ratings", "Only liked", "Only disliked"])
        self.filter_combo.currentTextChanged.connect(self.filter_feedback)
        
        control_layout.addWidget(self.refresh_btn)
        control_layout.addWidget(QLabel("Filter:"))
        control_layout.addWidget(self.filter_combo)
        control_layout.addStretch()
        
        layout.addLayout(control_layout)
        
        self.feedback_table = QTableWidget()
        self.feedback_table.setColumnCount(6)
        self.feedback_table.setHorizontalHeaderLabels([
            "ID", "User ID", "Question", "Answer", "Rating", "Date/Time"
        ])
        self.feedback_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.feedback_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.feedback_table.selectionModel().selectionChanged.connect(self.show_feedback_details)
        
        layout.addWidget(self.feedback_table)
        
        details_group = QGroupBox("Detailed View and Management")
        details_layout = QVBoxLayout(details_group)
        
        details_layout.addWidget(QLabel("Full Question:"))
        self.full_question = QTextEdit()
        self.full_question.setMaximumHeight(60)
        self.full_question.setReadOnly(True)
        details_layout.addWidget(self.full_question)
        
        details_layout.addWidget(QLabel("Full Answer:"))
        self.full_answer = QTextEdit()
        self.full_answer.setMaximumHeight(60)
        self.full_answer.setReadOnly(True)
        details_layout.addWidget(self.full_answer)
        
        self.change_rating_btn = QPushButton("🔄 Change Rating")
        self.change_rating_btn.clicked.connect(self.change_rating)
        self.change_rating_btn.setEnabled(False)
        details_layout.addWidget(self.change_rating_btn)
        
        layout.addWidget(details_group)
    
    def load_feedback(self, rating_filter=None):
        try:
            tables = self.db_manager.execute_select("SELECT name FROM sqlite_master WHERE type='table' AND name='ai_responses'")
            if not tables:
                self.feedback_table.setRowCount(0)
                QMessageBox.information(self, "Info", "Table ai_responses not found")
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
            QMessageBox.critical(self, "Error", f"Error loading ratings: {e}")
    
    def filter_feedback(self):
        filter_text = self.filter_combo.currentText()
        
        if filter_text == "All ratings":
            self.load_feedback()
        elif filter_text == "Only liked":
            self.load_feedback(1)
        elif filter_text == "Only disliked":
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
                if current_filter != "All ratings":
                    self.filter_feedback()
                
                QMessageBox.information(self, "Success", "Rating changed")
                
        except Exception as e:
            print(f"❌ Error changing rating: {e}")
            QMessageBox.critical(self, "Error", f"Could not change rating: {e}")

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
        
        title = QLabel('Telegram Bot Admin Panel')
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
        self.status_bar.showMessage('Ready')
    
    def create_dashboard_tab(self):
        dashboard_widget = QWidget()
        layout = QVBoxLayout(dashboard_widget)
        
        stats_group = QGroupBox("📊 General Statistics")
        stats_layout = QGridLayout(stats_group)
        
        stats_cards = [
            ("👥 Total Users", "total_users_card"),
            ("🔥 Active", "active_users_card"), 
            ("🚫 Banned", "banned_users_card"),
            ("⭐ Total Points", "total_points_card"),
            ("🎮 Total Games", "total_games_card"),
            ("❓ Total Questions", "total_questions_card"),
            ("✅ Correct Answers", "correct_answers_card"),
            ("📈 Average Accuracy", "avg_accuracy_card")
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
        
        actions_group = QGroupBox("⚡ Quick Actions")
        actions_layout = QHBoxLayout(actions_group)
        
        self.refresh_stats_btn = QPushButton("🔄 Refresh Statistics")
        self.refresh_stats_btn.clicked.connect(self.update_stats)
        
        self.add_question_btn = QPushButton("➕ Add Question")
        self.add_question_btn.clicked.connect(self.add_question)
        
        self.broadcast_btn = QPushButton("📢 Create Broadcast")
        self.broadcast_btn.clicked.connect(lambda: self.tabs.setCurrentIndex(3))
        
        self.stats_btn = QPushButton("📈 Detailed Statistics")
        self.stats_btn.clicked.connect(lambda: self.tabs.setCurrentIndex(4))
        
        actions_layout.addWidget(self.refresh_stats_btn)
        actions_layout.addWidget(self.add_question_btn)
        actions_layout.addWidget(self.broadcast_btn)
        actions_layout.addWidget(self.stats_btn)
        actions_layout.addStretch()
        
        layout.addWidget(actions_group)
        
        activity_group = QGroupBox("📅 Recent Activity")
        activity_layout = QVBoxLayout(activity_group)
        
        self.activity_label = QLabel("Loading activity data...")
        self.activity_label.setWordWrap(True)
        activity_layout.addWidget(self.activity_label)
        
        layout.addWidget(activity_group)
        
        layout.addStretch()
        
        self.tabs.addTab(dashboard_widget, "🏠 Dashboard")
    
    def create_questions_tab(self):
        questions_widget = QWidget()
        layout = QVBoxLayout(questions_widget)
        
        control_group = QGroupBox("Question Management")
        control_layout = QHBoxLayout(control_group)
        
        self.add_question_btn = QPushButton("➕ Add Question")
        self.add_question_btn.clicked.connect(self.add_question)
        
        self.edit_question_btn = QPushButton("✏️ Edit")
        self.edit_question_btn.clicked.connect(self.edit_question)
        
        self.delete_question_btn = QPushButton("🗑️ Delete")
        self.delete_question_btn.clicked.connect(self.delete_question)
        
        self.refresh_questions_btn = QPushButton("🔄 Refresh")
        self.refresh_questions_btn.clicked.connect(self.load_questions)
        
        control_layout.addWidget(self.add_question_btn)
        control_layout.addWidget(self.edit_question_btn)
        control_layout.addWidget(self.delete_question_btn)
        control_layout.addWidget(self.refresh_questions_btn)
        control_layout.addStretch()
        
        layout.addWidget(control_group)
        
        search_group = QGroupBox("Search and Filter")
        search_layout = QHBoxLayout(search_group)
        
        self.question_search_input = QLineEdit()
        self.question_search_input.setPlaceholderText("Search by question text...")
        self.question_search_input.textChanged.connect(self.search_questions)
        
        search_layout.addWidget(QLabel("Search:"))
        search_layout.addWidget(self.question_search_input)
        
        layout.addWidget(search_group)
        
        self.questions_table = QTableWidget()
        self.questions_table.setColumnCount(7)
        self.questions_table.setHorizontalHeaderLabels([
            "ID", "Topic", "Question", "Answer Options", "Correct Answer", "Points", "Difficulty"
        ])
        self.questions_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.questions_table.setSelectionBehavior(QTableWidget.SelectRows)
        
        layout.addWidget(self.questions_table)
        
        self.tabs.addTab(questions_widget, "❓ Questions")
    
    def create_users_tab(self):
        users_widget = QWidget()
        layout = QVBoxLayout(users_widget)
        
        search_group = QGroupBox("User Search")
        search_layout = QHBoxLayout(search_group)
        
        self.user_search_input = QLineEdit()
        self.user_search_input.setPlaceholderText("Search by ID, name or username...")
        
        self.user_search_btn = QPushButton("🔍 Search")
        self.user_search_btn.clicked.connect(self.search_users)
        
        self.show_all_users_btn = QPushButton("👥 All Users")
        self.show_all_users_btn.clicked.connect(self.load_all_users)
        
        search_layout.addWidget(QLabel("Search:"))
        search_layout.addWidget(self.user_search_input)
        search_layout.addWidget(self.user_search_btn)
        search_layout.addWidget(self.show_all_users_btn)
        search_layout.addStretch()
        
        layout.addWidget(search_group)
        
        self.users_table = QTableWidget()
        self.users_table.setColumnCount(6)
        self.users_table.setHorizontalHeaderLabels([
            "ID", "Username", "First Name", "Last Name", "Points", "Status"
        ])
        self.users_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.users_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.users_table.doubleClicked.connect(self.manage_user)
        
        layout.addWidget(self.users_table)
        
        user_actions_layout = QHBoxLayout()
        
        self.manage_user_btn = QPushButton("👤 Manage User")
        self.manage_user_btn.clicked.connect(self.manage_user)
        
        self.ban_user_btn = QPushButton("🚫 Ban")
        self.ban_user_btn.clicked.connect(self.ban_selected_user)
        
        self.unban_user_btn = QPushButton("✅ Unban")
        self.unban_user_btn.clicked.connect(self.unban_selected_user)
        
        user_actions_layout.addWidget(self.manage_user_btn)
        user_actions_layout.addWidget(self.ban_user_btn)
        user_actions_layout.addWidget(self.unban_user_btn)
        user_actions_layout.addStretch()
        
        layout.addLayout(user_actions_layout)
        
        self.tabs.addTab(users_widget, "👥 Users")
    
    def create_broadcast_tab(self):
        broadcast_widget = QWidget()
        layout = QVBoxLayout(broadcast_widget)
        
        message_group = QGroupBox("Broadcast Message")
        message_layout = QVBoxLayout(message_group)
        
        self.broadcast_message_input = QTextEdit()
        self.broadcast_message_input.setMaximumHeight(150)
        self.broadcast_message_input.setPlaceholderText("Enter message for broadcast...")
        message_layout.addWidget(self.broadcast_message_input)
        
        layout.addWidget(message_group)
        
        control_group = QGroupBox("Broadcast Control")
        control_layout = QHBoxLayout(control_group)
        
        self.start_broadcast_btn = QPushButton("📢 Start Broadcast")
        self.start_broadcast_btn.clicked.connect(self.start_broadcast)
        
        self.stop_broadcast_btn = QPushButton("⏹️ Stop")
        self.stop_broadcast_btn.clicked.connect(self.stop_broadcast)
        self.stop_broadcast_btn.setEnabled(False)
        
        control_layout.addWidget(self.start_broadcast_btn)
        control_layout.addWidget(self.stop_broadcast_btn)
        control_layout.addStretch()
        
        layout.addWidget(control_group)
        
        progress_group = QGroupBox("Broadcast Progress")
        progress_layout = QVBoxLayout(progress_group)
        
        self.broadcast_progress = QProgressBar()
        self.broadcast_progress.setVisible(False)
        progress_layout.addWidget(self.broadcast_progress)
        
        self.broadcast_status = QLabel("Ready for broadcast")
        progress_layout.addWidget(self.broadcast_status)
        
        layout.addWidget(progress_group)
        
        results_group = QGroupBox("Broadcast Results")
        results_layout = QVBoxLayout(results_group)
        
        self.broadcast_results = QTextEdit()
        self.broadcast_results.setMaximumHeight(200)
        results_layout.addWidget(self.broadcast_results)
        
        layout.addWidget(results_group)
        
        self.tabs.addTab(broadcast_widget, "📢 Broadcast")
    
    def create_statistics_tab(self):
        statistics_tab = StatisticsTab()
        self.tabs.addTab(statistics_tab, "📈 Statistics")
    
    def create_ai_dialogs_tab(self):
        ai_dialogs_tab = AIDialogsTab()
        self.tabs.addTab(ai_dialogs_tab, "💬 AI Dialogs")
    
    def create_ai_feedback_tab(self):
        ai_feedback_tab = AIFeedbackTab()
        self.tabs.addTab(ai_feedback_tab, "⭐ AI Ratings")
    
    def create_settings_tab(self):
        settings_widget = QWidget()
        layout = QVBoxLayout(settings_widget)
        
        bot_settings_group = QGroupBox("Bot Settings")
        bot_settings_layout = QFormLayout(bot_settings_group)
        
        self.bot_token_input = QLineEdit()
        self.bot_token_input.setText(BOT_TOKEN)
        bot_settings_layout.addRow("Bot Token:", self.bot_token_input)
        
        self.admin_ids_input = QLineEdit()
        self.admin_ids_input.setText(",".join(map(str, ADMIN_IDS)))
        bot_settings_layout.addRow("Admin IDs:", self.admin_ids_input)
        
        layout.addWidget(bot_settings_group)
        
        db_group = QGroupBox("Database Management")
        db_layout = QVBoxLayout(db_group)
        
        self.backup_db_btn = QPushButton("💾 Create Backup")
        self.backup_db_btn.clicked.connect(self.backup_database)
        
        self.create_admin_btn = QPushButton("👨‍💼 Create Admin")
        self.create_admin_btn.clicked.connect(self.create_admin)
        
        db_layout.addWidget(self.backup_db_btn)
        db_layout.addWidget(self.create_admin_btn)
        
        layout.addWidget(db_group)
        
        layout.addStretch()
        
        self.tabs.addTab(settings_widget, "⚙️ Settings")
    
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
                self.status_bar.showMessage('Questions table not found')
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
            
            self.status_bar.showMessage(f'Loaded {len(questions)} questions')
            
        except Exception as e:
            self.status_bar.showMessage(f'Error loading questions: {e}')
    
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
            
            self.status_bar.showMessage(f'Found {len(questions)} questions')
            
        except Exception as e:
            self.status_bar.showMessage(f'Search error: {e}')
    
    def add_question(self):
        dialog = QuestionDialog(self)
        if dialog.exec_() == QDialog.Accepted:
            self.load_questions()
    
    def edit_question(self):
        selected_rows = self.questions_table.selectionModel().selectedRows()
        if not selected_rows:
            QMessageBox.warning(self, "Error", "Select a question to edit")
            return
        
        question_id = int(self.questions_table.item(selected_rows[0].row(), 0).text())
        dialog = QuestionDialog(self, question_id)
        if dialog.exec_() == QDialog.Accepted:
            self.load_questions()
    
    def delete_question(self):
        selected_rows = self.questions_table.selectionModel().selectedRows()
        if not selected_rows:
            QMessageBox.warning(self, "Error", "Select a question to delete")
            return
        
        question_id = int(self.questions_table.item(selected_rows[0].row(), 0).text())
        question_text = self.questions_table.item(selected_rows[0].row(), 2).text()
        
        reply = QMessageBox.question(
            self, 
            "Confirm Delete", 
            f"Are you sure you want to delete this question?\n\n{question_text[:100]}...",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            try:
                result = self.db_manager.execute_query("DELETE FROM questions WHERE id = ?", (question_id,))
                if result:
                    QMessageBox.information(self, "Success", "Question deleted")
                    self.load_questions()
                else:
                    QMessageBox.critical(self, "Error", "Could not delete question")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Delete error: {e}")
    
    def load_users(self):
        try:
            users = self.stats.get_all_users()
            self.users_table.setRowCount(len(users))
            
            for row, user in enumerate(users):
                user_id, username, first_name, last_name, points, _, created_at, is_banned = user
                
                status = "✅ Active" if not is_banned else "🚫 Banned"
                
                self.users_table.setItem(row, 0, QTableWidgetItem(str(user_id)))
                self.users_table.setItem(row, 1, QTableWidgetItem(username or ""))
                self.users_table.setItem(row, 2, QTableWidgetItem(first_name or ""))
                self.users_table.setItem(row, 3, QTableWidgetItem(last_name or ""))
                self.users_table.setItem(row, 4, QTableWidgetItem(str(points)))
                self.users_table.setItem(row, 5, QTableWidgetItem(status))
            
            self.status_bar.showMessage(f'Loaded {len(users)} users')
            
        except Exception as e:
            self.status_bar.showMessage(f'Error loading users: {e}')
    
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
                
                status = "✅ Active" if not is_banned else "🚫 Banned"
                
                self.users_table.setItem(row, 0, QTableWidgetItem(str(user_id)))
                self.users_table.setItem(row, 1, QTableWidgetItem(username or ""))
                self.users_table.setItem(row, 2, QTableWidgetItem(first_name or ""))
                self.users_table.setItem(row, 3, QTableWidgetItem(last_name or ""))
                self.users_table.setItem(row, 4, QTableWidgetItem(str(points)))
                self.users_table.setItem(row, 5, QTableWidgetItem(status))
            
            self.status_bar.showMessage(f'Found {len(users)} users')
            
        except Exception as e:
            self.status_bar.showMessage(f'User search error: {e}')
    
    def load_all_users(self):
        self.load_users()
    
    def manage_user(self):
        selected_rows = self.users_table.selectionModel().selectedRows()
        if not selected_rows:
            QMessageBox.warning(self, "Error", "Select a user to manage")
            return
        
        user_id = int(self.users_table.item(selected_rows[0].row(), 0).text())
        dialog = UserManagementDialog(self, user_id)
        dialog.exec_()
        self.load_users()
    
    def ban_selected_user(self):
        selected_rows = self.users_table.selectionModel().selectedRows()
        if not selected_rows:
            QMessageBox.warning(self, "Error", "Select a user to ban")
            return
        
        user_id = int(self.users_table.item(selected_rows[0].row(), 0).text())
        username = self.users_table.item(selected_rows[0].row(), 1).text()
        
        reply = QMessageBox.question(
            self, 
            "Confirm Ban", 
            f"Are you sure you want to ban user {username} (ID: {user_id})?",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            try:
                if self.stats.ban_user(user_id, ADMIN_IDS[0] if ADMIN_IDS else 0, "Banned by admin"):
                    QMessageBox.information(self, "Success", "User banned")
                    self.load_users()
                else:
                    QMessageBox.critical(self, "Error", "Could not ban user")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Ban error: {e}")
    
    def unban_selected_user(self):
        selected_rows = self.users_table.selectionModel().selectedRows()
        if not selected_rows:
            QMessageBox.warning(self, "Error", "Select a user to unban")
            return
        
        user_id = int(self.users_table.item(selected_rows[0].row(), 0).text())
        username = self.users_table.item(selected_rows[0].row(), 1).text()
        
        reply = QMessageBox.question(
            self, 
            "Confirm Unban", 
            f"Are you sure you want to unban user {username} (ID: {user_id})?",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            try:
                if self.stats.unban_user(user_id):
                    QMessageBox.information(self, "Success", "User unbanned")
                    self.load_users()
                else:
                    QMessageBox.critical(self, "Error", "Could not unban user")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Unban error: {e}")
    
    def start_broadcast(self):
        message = self.broadcast_message_input.toPlainText().strip()
        
        if not message:
            QMessageBox.warning(self, "Error", "Enter message for broadcast")
            return
        
        self.broadcast_worker = BroadcastWorker(self.db_manager, self.telegram, message)
        self.broadcast_worker.progress.connect(self.update_broadcast_progress)
        self.broadcast_worker.finished.connect(self.broadcast_finished)
        
        self.start_broadcast_btn.setEnabled(False)
        self.stop_broadcast_btn.setEnabled(True)
        self.broadcast_progress.setVisible(True)
        self.broadcast_status.setText("Broadcast started...")
        
        self.broadcast_worker.start()
    
    def stop_broadcast(self):
        if self.broadcast_worker and self.broadcast_worker.isRunning():
            self.broadcast_worker.is_running = False
            self.broadcast_status.setText("Stopping broadcast...")
    
    def update_broadcast_progress(self, progress, current, status):
        self.broadcast_progress.setValue(progress)
        self.broadcast_status.setText(status)
    
    def broadcast_finished(self, result):
        self.start_broadcast_btn.setEnabled(True)
        self.stop_broadcast_btn.setEnabled(False)
        self.broadcast_progress.setVisible(False)
        
        if 'error' in result:
            self.broadcast_status.setText(f"Error: {result['error']}")
            QMessageBox.critical(self, "Error", f"Broadcast error: {result['error']}")
        else:
            success = result['success']
            failed = result['failed']
            banned = result['banned']
            total = result['total']
            
            self.broadcast_status.setText(f"Completed: Success {success}, Errors {failed}, Banned {banned}")
            
            results_text = f"Broadcast Results:\n"
            results_text += f"✅ Success: {success}\n"
            results_text += f"❌ Errors: {failed}\n"
            results_text += f"🚫 Banned: {banned}\n"
            results_text += f"📊 Total: {total}\n\n"
            
            for i, res in enumerate(result['results'][-20:]):
                results_text += f"{res}\n"
            
            self.broadcast_results.setPlainText(results_text)
            
            QMessageBox.information(self, "Success", 
                f"Broadcast completed!\n\n"
                f"Success: {success}\n"
                f"Errors: {failed}\n"
                f"Banned: {banned}"
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
            
            self.status_bar.showMessage('Statistics updated')
            
        except Exception as e:
            self.status_bar.showMessage(f'Error updating statistics: {e}')
    
    def update_activity(self):
        try:
            daily_activity = self.stats.get_daily_activity(3)
            activity_text = "<b>Activity for last 3 days:</b><br>"
            
            if daily_activity:
                for date, new_users, active_users in daily_activity:
                    activity_text += f"• {date}: +{new_users} new, {active_users} active<br>"
            else:
                activity_text += "No activity data"
            
            self.activity_label.setText(activity_text)
            
        except Exception as e:
            self.activity_label.setText(f"Error loading activity: {e}")
    
    def backup_database(self):
        try:
            import shutil
            import datetime
            
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = f"quiz_bot_backup_{timestamp}.db"
            
            shutil.copy2(DATABASE_PATH, backup_path)
            
            QMessageBox.information(self, "Success", f"Backup created: {backup_path}")
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Could not create backup: {e}")
    
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
            
            QMessageBox.information(self, "Success", 
                "Admin created!\n\n"
                "Username: admin\n"
                "Password: admin123\n\n"
                "You can now enable authorization in the code."
            )
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Could not create admin: {e}")

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
