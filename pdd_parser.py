import json
import os
import re
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
import time

class PDDParser:
    def __init__(self, progress_file='progress.json'):
        self.progress_file = progress_file
        self.base_url = 'https://www.drom.ru/pdd/bilet_{}/training/'
        self.current_ticket = 1
        self.current_question = 1
        self.driver = None
        self.cached_questions = {}  # Кеш для уже загруженных билетов
        self.load_progress()
        self._init_driver()

    def _init_driver(self):
        options = Options()
        options.add_argument('--disable-blink-features=AutomationControlled')
        options.add_argument('--disable-gpu')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--headless')
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option('useAutomationExtension', False)
        options.add_argument(
            'user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')

        try:
            service = Service('/usr/lib/chromium-browser/chromedriver')
            self.driver = webdriver.Chrome(service=service, options=options)
            print("Драйвер Chrome был инициализирован")
        except:
            from webdriver_manager.chrome import ChromeDriverManager
            service = Service(ChromeDriverManager().install())
            self.driver = webdriver.Chrome(service=service, options=options)
            print("Драйвер Chrome инициализирован (локально)")

        self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

    def load_progress(self):
        if os.path.exists(self.progress_file):
            try:
                with open(self.progress_file, 'r', encoding='utf-8') as f:
                    content = f.read().strip()
                    if content:
                        data = json.loads(content)
                        self.current_ticket = data.get('current_ticket', 1)
                        self.current_question = data.get('current_question', 1)
                        print(f"Загрузила прогресс: билет {self.current_ticket}, вопрос {self.current_question}")
                    else:
                        self.save_progress()
            except:
                self.save_progress()
        else:
            self.save_progress()

    def save_progress(self):
        try:
            with open(self.progress_file, 'w', encoding='utf-8') as f:
                json.dump({
                    'current_ticket': self.current_ticket,
                    'current_question': self.current_question
                }, f, indent=4, ensure_ascii=False)
        except Exception as e:
            print(f"Ошибка при сохранении прогресса: {e}")

    def parse_ticket(self, ticket_number):
        # Проверяем кеш
        if ticket_number in self.cached_questions:
            print(f"Билет №{ticket_number} взят из кеша")
            return self.cached_questions[ticket_number]

        url = self.base_url.format(ticket_number)
        print(f"Паршу билет №{ticket_number}...")
        try:
            self.driver.get(url)
            time.sleep(1)  # Уменьшила с 2 до 1 секунды
            scripts = self.driver.find_elements(By.TAG_NAME, 'script')
            for script in scripts:
                outer_html = script.get_attribute('outerHTML')
                if 'data-drom-module="pdd-exam"' in outer_html:
                    print("Найден скрипт pdd-exam")
                    content = script.get_attribute('innerHTML')

                    if not content:
                        print("Содержимое скрипта пусто")
                        continue

                    try:
                        data = json.loads(content)
                        if 'initialState' in data:
                            data = data['initialState']
                        questions_data = data.get('questions', [])
                        if not questions_data:
                            continue
                        questions = []
                        for q in questions_data:
                            answers = []
                            for answer in q.get('answers', []):
                                ans_text = answer.get('text', '')
                                if ans_text:
                                    answers.append(ans_text)
                            if len(answers) < 2:
                                continue
                            correct_index = 0
                            for i, answer in enumerate(q.get('answers', [])):
                                if answer.get('isCorrect', False):
                                    correct_index = i
                                    break
                            explanation = q.get('commentTagged', '')
                            if explanation:
                                explanation = re.sub(r'<[^>]+>', ' ', explanation)
                                explanation = re.sub(r'\s+', ' ', explanation).strip()
                            else:
                                explanation = "Не нашла объяснение"
                            questions.append({
                                'number': q.get('num', 0),
                                'ticket': ticket_number,
                                'question': q.get('text', ''),
                                'answers': answers,
                                'correct_index': correct_index,
                                'explanation': explanation,
                                'image_url': q.get('image', None)
                            })

                        if questions:
                            print(f"Найдено {len(questions)} вопросов в билете {ticket_number}")
                            self.cached_questions[ticket_number] = questions  # Сохраняем в кеш
                            return questions

                    except Exception as e:
                        print(f"Ошибка обработки: {e}")
                        continue

            print(f"Не нашла вопросы на странице билета {ticket_number}")
            return []

        except Exception as e:
            print(f"Ошибка при загрузке билета {ticket_number}: {e}")
            return []

    def get_next_question(self):
        max_tickets = 40

        for attempt in range(max_tickets * 2):
            if self.current_ticket > max_tickets:
                print("Я всё сделала, господин! Начинаем с первого.")
                self.current_ticket = 1
                self.current_question = 1
                self.save_progress()

            questions = self.parse_ticket(self.current_ticket)

            if not questions:
                print(f"Не смогла получить вопросы из билета {self.current_ticket}, переходим к следующему")
                self.current_ticket += 1
                self.current_question = 1
                self.save_progress()
                continue

            if self.current_question <= len(questions):
                question_data = questions[self.current_question - 1]

                if self.check_limits(question_data):
                    result = question_data.copy()
                    self.current_question += 1

                    if self.current_question > len(questions):
                        self.current_ticket += 1
                        self.current_question = 1

                    self.save_progress()
                    return result
                else:
                    print(f"Вопрос {self.current_question} билета {self.current_ticket} оказался слишком длинный, пропускаем")
                    self.current_question += 1
                    if self.current_question > len(questions):
                        self.current_ticket += 1
                        self.current_question = 1
                    self.save_progress()
                    continue
            else:
                self.current_ticket += 1
                self.current_question = 1
                self.save_progress()
                continue

        print("Не нашла подходящих вопросов")
        return None

    def check_limits(self, question_data):
        if len(question_data['question']) > 255:
            print(f"Вопрос оказался слишком длинным: {len(question_data['question'])}")
            return False
        for i, answer in enumerate(question_data['answers']):
            if len(answer) > 100:
                print(f"Ответ {i + 1} оказался слишком длинным: {len(answer)} символов")
                return False
        return True

    def reset_progress(self):
        self.current_ticket = 1
        self.current_question = 1
        self.save_progress()
        print("Сбросила прогресс на начало")

    def close(self):
        if self.driver:
            self.driver.quit()
            print("Драйвер закрыла")