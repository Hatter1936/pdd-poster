import json
import os
import re
import cloudscraper
from bs4 import BeautifulSoup

class PDDParser:
    def __init__(self, progress_file='progress.json'):
        self.progress_file = progress_file
        self.base_url = 'https://www.drom.ru/pdd/bilet_{}/training/'
        self.current_ticket = 1
        self.current_question = 1
        self.cached_questions = {}
        
        self.session = cloudscraper.create_scraper(
            browser={
                'browser': 'chrome',
                'platform': 'windows',
                'desktop': True
            }
        )
        
        self.load_progress()

    def load_progress(self):
        if os.path.exists(self.progress_file):
            try:
                with open(self.progress_file, 'r', encoding='utf-8') as f:
                    content = f.read().strip()
                    if content:
                        data = json.loads(content)
                        self.current_ticket = data.get('current_ticket', 1)
                        self.current_question = data.get('current_question', 1)
                        print(f"Загружен прогресс: билет {self.current_ticket}, вопрос {self.current_question}")
            except Exception as e:
                print(f"Ошибка загрузки прогресса: {e}")
                self.save_progress()
        else:
            print("Файл прогресса не найден, начинаем с начала")
            self.save_progress()

    def save_progress(self):
        try:
            with open(self.progress_file, 'w', encoding='utf-8') as f:
                json.dump({
                    'current_ticket': self.current_ticket,
                    'current_question': self.current_question
                }, f, indent=4, ensure_ascii=False)
            print(f"Сохранён прогресс: билет {self.current_ticket}, вопрос {self.current_question}")
        except Exception as e:
            print(f"Ошибка сохранения прогресса: {e}")

    def parse_ticket(self, ticket_number):
        if ticket_number in self.cached_questions:
            return self.cached_questions[ticket_number]

        url = self.base_url.format(ticket_number)
        print(f"Парсинг билета {ticket_number}")

        try:
            response = self.session.get(url, timeout=20)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'lxml')

            script_tag = soup.find('script', {'data-drom-module': 'pdd-exam'})
            if not script_tag:
                script_tag = soup.find('script', text=re.compile(r'initialState'))
                
            if not script_tag:
                print(f"⚠️ ОШИБКА: Скрипт не найден в билете {ticket_number}")
                print(f"DEBUG: Статус ответа: {response.status_code}")
                if "cloudflare" in response.text.lower() or "captcha" in response.text.lower() or "access denied" in response.text.lower():
                    print("DEBUG: Обнаружена блокировка Cloudflare или капча!")
                else:
                    print(f"DEBUG: Фрагмент ответа (первые 300 символов): {response.text[:300]}")
                return []

            script_content = script_tag.string
            if not script_content:
                return []

            data = json.loads(script_content)
            if 'initialState' in data:
                data = data['initialState']

            questions_data = data.get('questions', [])
            if not questions_data:
                print(f"Нет вопросов в билете {ticket_number}")
                return []

            questions = []
            for q in questions_data:
                raw_answers = q.get('answers', [])
                if len(raw_answers) < 2:
                    continue

                answers = []
                correct_index = 0

                for i, ans in enumerate(raw_answers):
                    text = ans.get('text', '')
                    if text:
                        text = re.sub(r'<[^>]+>', ' ', text)
                        text = re.sub(r'\s+', ' ', text).strip()
                        if text:
                            answers.append(text)
                            if ans.get('isCorrect') == True:
                                correct_index = i

                if len(answers) < 2:
                    continue

                question_text = q.get('text', '')
                question_text = re.sub(r'<[^>]+>', ' ', question_text)
                question_text = re.sub(r'\s+', ' ', question_text).strip()

                if not question_text:
                    continue

                explanation = q.get('commentTagged', '')
                if explanation:
                    explanation = re.sub(r'<[^>]+>', ' ', explanation)
                    explanation = re.sub(r'\s+', ' ', explanation).strip()
                else:
                    explanation = "Объяснение не найдено"

                image_url = None
                if q.get('image'):
                    if isinstance(q['image'], dict):
                        image_url = q['image'].get('url')
                    elif isinstance(q['image'], str):
                        image_url = q['image']
                    
                    if image_url:
                        if image_url.startswith('//'):
                            image_url = 'https:' + image_url
                        elif image_url.startswith('/'):
                            image_url = 'https://drom.ru' + image_url
                        elif not image_url.startswith('http'):
                            image_url = 'https://drom.ru' + image_url
                        print(f"Найдена картинка: {image_url}")

                questions.append({
                    'number': q.get('num', 0),
                    'ticket': ticket_number,
                    'question': question_text,
                    'answers': answers,
                    'correct_index': correct_index,
                    'explanation': explanation,
                    'image_url': image_url
                })

            if questions:
                self.cached_questions[ticket_number] = questions
                print(f"Найдено {len(questions)} вопросов в билете {ticket_number}")
                return questions
            return []

        except Exception as e:
            print(f"Ошибка парсинга билета {ticket_number}: {e}")
            return []

    def get_next_question(self):
        max_tickets = 40
        attempts = 0
        
        while attempts < max_tickets * 3:
            attempts += 1
            
            if self.current_ticket > max_tickets:
                self.current_ticket = 1
                self.current_question = 1
                self.save_progress()

            questions = self.parse_ticket(self.current_ticket)
            if not questions:
                print(f"Нет вопросов в билете {self.current_ticket}, переход к следующему")
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
                    print(f"Вопрос {self.current_question} не прошёл проверку, пропускаем")
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

        print("Подходящих вопросов не найдено")
        return None

    def check_limits(self, question_data):
        if len(question_data['question']) > 300:
            return False
        if len(question_data['question'].encode('utf-8')) > 255:
            return False

        for answer in question_data['answers']:
            if len(answer) > 150:
                return False
            if len(answer.encode('utf-8')) > 100:
                return False

        return True
