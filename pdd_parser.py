import json
import os
import re
import requests
from bs4 import BeautifulSoup

class PDDParser:
    def __init__(self, progress_file='progress.json'):
        self.progress_file = progress_file
        self.base_url = 'https://www.drom.ru/pdd/bilet_{}/training/'
        self.current_ticket = 1
        self.current_question = 1
        self.cached_questions = {}
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }
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
            print(f"Прогресс сохранён: билет {self.current_ticket}, вопрос {self.current_question}")

            github_env = os.environ.get('GITHUB_ENV')
            if github_env and os.path.exists(github_env):
                with open(github_env, 'a', encoding='utf-8') as f:
                    f.write(f"LAST_TICKET={self.current_ticket}\n")
                    f.write(f"LAST_QUESTION={self.current_question}\n")
        except Exception as e:
            print(f"Ошибка сохранения прогресса: {e}")

    def parse_ticket(self, ticket_number):
        if ticket_number in self.cached_questions:
            print(f"Билет {ticket_number} взят из кэша")
            return self.cached_questions[ticket_number]

        url = self.base_url.format(ticket_number)
        print(f"Парсинг билета {ticket_number}...")
        print(f"URL: {url}")

        try:
            response = requests.get(url, headers=self.headers, timeout=15)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')

            script_tag = soup.find('script', {'data-drom-module': 'pdd-exam'})
            if not script_tag:
                print(f"Скрипт с данными не найден в билете {ticket_number}")
                return []

            try:
                data = json.loads(script_tag.string)
                if 'initialState' in data:
                    data = data['initialState']

                questions_data = data.get('questions', [])
                if not questions_data:
                    print(f"В билете {ticket_number} нет вопросов")
                    return []

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
                        explanation = "Объяснение не найдено"

                    image_url = None
                    if q.get('image'):
                        if isinstance(q['image'], dict):
                            image_url = q['image'].get('url')
                        else:
                            image_url = q['image']

                    questions.append({
                        'number': q.get('num', 0),
                        'ticket': ticket_number,
                        'question': q.get('text', ''),
                        'answers': answers,
                        'correct_index': correct_index,
                        'explanation': explanation,
                        'image_url': image_url
                    })

                if questions:
                    print(f"Найдено {len(questions)} вопросов в билете {ticket_number}")
                    self.cached_questions[ticket_number] = questions
                    return questions
                else:
                    return []
            except Exception as e:
                print(f"Ошибка обработки данных билета {ticket_number}: {e}")
                return []
        except Exception as e:
            print(f"Ошибка загрузки билета {ticket_number}: {e}")
            return []

    def get_next_question(self):
        max_tickets = 40
        for attempt in range(max_tickets * 2):
            if self.current_ticket > max_tickets:
                print("Достигнут последний билет. Начинаем с первого.")
                self.current_ticket = 1
                self.current_question = 1
                self.save_progress()

            questions = self.parse_ticket(self.current_ticket)
            if not questions:
                print(f"Не удалось получить вопросы из билета {self.current_ticket}, переход к следующему")
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
                    print(f"Вопрос {self.current_question} из билета {self.current_ticket} превышает лимиты, пропуск")
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
        if len(question_data['question']) > 500:
            print(f"Вопрос слишком длинный: {len(question_data['question'])} символов (максимум 500)")
            return False
        for i, answer in enumerate(question_data['answers']):
            if len(answer) > 100:
                print(f"Ответ {i + 1} слишком длинный: {len(answer)} символов (максимум 100)")
                return False
        return True

    def reset_progress(self):
        self.current_ticket = 1
        self.current_question = 1
        self.save_progress()
        print("Прогресс сброшен на начало")

    def close(self):
        pass