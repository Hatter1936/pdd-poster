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
                    else:
                        self.save_progress()
            except Exception:
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
        except Exception:
            pass

    def parse_ticket(self, ticket_number):
        if ticket_number in self.cached_questions:
            return self.cached_questions[ticket_number]

        url = self.base_url.format(ticket_number)

        try:
            response = requests.get(url, headers=self.headers, timeout=15)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')

            script_tag = soup.find('script', {'data-drom-module': 'pdd-exam'})
            if not script_tag:
                return []

            try:
                data = json.loads(script_tag.string)
                if 'initialState' in data:
                    data = data['initialState']

                questions_data = data.get('questions', [])
                if not questions_data:
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
                            answers.append(text)
                            if ans.get('isCorrect') == True:
                                correct_index = i

                    if len(answers) < 2:
                        continue

                    question_text = q.get('text', '')
                    question_text = re.sub(r'<[^>]+>', ' ', question_text)
                    question_text = re.sub(r'\s+', ' ', question_text).strip()

                    explanation = q.get('commentTagged', '')
                    if explanation:
                        explanation = re.sub(r'<[^>]+>', ' ', explanation)
                        explanation = re.sub(r'\s+', ' ', explanation).strip()
                    else:
                        explanation = "No explanation available"

                    image_url = None
                    if q.get('image'):
                        if isinstance(q['image'], dict):
                            image_url = q['image'].get('url')
                        else:
                            image_url = q['image']

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
                    return questions
                else:
                    return []

            except Exception:
                return []

        except Exception:
            return []

    def get_next_question(self):
        max_tickets = 40
        for attempt in range(max_tickets * 3):
            if self.current_ticket > max_tickets:
                self.current_ticket = 1
                self.current_question = 1
                self.save_progress()

            questions = self.parse_ticket(self.current_ticket)
            if not questions:
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

        return None

    def check_limits(self, question_data):
        if len(question_data['question']) > 255:
            return False
        
        if len(question_data['question'].encode('utf-8')) > 255:
            return False

        for answer in question_data['answers']:
            if len(answer) > 100:
                return False
            if len(answer.encode('utf-8')) > 100:
                return False

        return True

    def reset_progress(self):
        self.current_ticket = 1
        self.current_question = 1
        self.save_progress()

    def close(self):
        pass
