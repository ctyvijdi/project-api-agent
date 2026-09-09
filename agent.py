import os
import json
from dotenv import load_dotenv
from gigachat import GigaChat
from gigachat.models import Chat, Function, FunctionParameters
import subprocess

load_dotenv()

def verify_with_model(chad, user_request, code, code_output):
    verification_messages = [
        {
            "role": "system",
            "content": (
                "Ты проверяешь, соответствует ли КОД запросу пользователя "
                "(а не только его вывод — вывод может выглядеть правильно "
                "даже если реализован другой алгоритм). "
                "Если пользователь просил конкретный алгоритм (например, "
                "пузырьковую сортировку), убедись, что в коде реализован "
                "именно он, а не встроенная функция вроде sorted()/sort(). "
                "Если запрос не требует конкретного алгоритма (просто "
                "'отсортируй список' и т.п.) — оценивай только правильность результата. "
                "Отвечай СТРОГО одним словом: 'True' или 'False'."
            )
        },
        {
            "role": "user",
            "content": (
                f"Запрос пользователя: {user_request}\n\n"
                f"Код:\n{code}\n\n"
                f"Вывод программы: {code_output}\n\n"
                "Код и вывод соответствуют запросу?"
            )
        }
    ]

    verification_response = chad.get_response(verification_messages)

    if verification_response and verification_response.choices:
        answer = verification_response.choices[0].message.content.lower().strip()
        print(f' Проверка: {answer}')
        return answer.startswith('true') or answer.startswith('да')
    return False

def check(code):
    with open("project_info.py", 'w', encoding='utf-8') as f:
        f.write(str(code))  # Преобразуем в строку на всякий случай
    
    result = subprocess.run(
        ['python', 'project_info.py'],
        capture_output=True,
        text=True,
        timeout=30
    )
    
    return {
        "success": result.returncode == 0,
        "output": result.stdout.strip(),
        "error": result.stderr.strip() or None
    }

few_shot_examples = [
    {
        'role': 'user',
        'content': 'Напиши мне код который выводит hello world',
    },
    {
        'role': 'assistant',
        'content': "print('hello world')"
    },
]

class gigachat:
    def __init__(self, api_key: str = os.getenv("API_KEY"), model: str = "GigaChat-2-Max"):
        self.api_key = api_key
        self.model = model
        self.client = self.get_client()
        self.dialog_history = []
        self.promt = ''
        
    def get_client(self):
        return GigaChat(
            base_url="https://api.giga.chat/v1",
            credentials=self.api_key,
            scope="GIGACHAT_API_PERS",
            verify_ssl_certs=False,
        )
    
    def get_response(self, MESSAGE):
        chat = Chat(
            model=self.model,
            messages=MESSAGE,
            functions=[
                Function(
                    name='vibe_code',
                    description='Вызывай когда нужно написать код. Передавай код в параметре code',
                    parameters=FunctionParameters(
                        type='object',
                        properties={
                            'code': {
                                'type': 'string',
                                'description': 'Python код для выполнения'
                            }
                        },
                        required=['code']
                    )
                ),
            ],
            function_call="auto"
        )
        return self.client.chat(chat)
    
    def create_system_prompt(self) -> str:
        prompt = f"""Ты - интеллектуальный автоответчик для проекта '{self.promt}'

Правила работы:
1. Когда пользователь просит написать код, ВЫЗЫВАЙ функцию vibe_code
2. Передавай код в параметре 'code' функции vibe_code
3. Код должен быть чистым Python кодом без пояснений
4. Если результат не тот который ожидался, переписываешь код"""
        return prompt

def extract_code_from_response(resp):
    if not resp or not resp.choices:
        return None
    
    message = resp.choices[0].message

    if hasattr(message, 'function_call') and message.function_call:
        args = message.function_call.arguments
        
        if isinstance(args, dict):
            return args.get('code', '')

        if isinstance(args, str):
            try:
                args_dict = json.loads(args)
                if isinstance(args_dict, dict):
                    return args_dict.get('code', '')
                else:
                    return args
            except:
                return args
    return message.content or ''

def main():
    chad = gigachat()

    MESSAGES = [
        {"role": "system", "content": chad.create_system_prompt()}
    ]
    
    for example in few_shot_examples:
        MESSAGES.append(example)

    while True:
        user_request = input("\nВведи запрос: ")

        if user_request.lower() == "exit":
            break
        
        USER_PROMPT = {"role": "user", "content": user_request}
        MESSAGES.append(USER_PROMPT)
        
        final_response = None
        code_success = False

        for attempt in range(3):
            print(f'\n Попытка {attempt + 1} из 3...')
            
            resp = chad.get_response(MESSAGES)
            
            if not resp or not resp.choices:
                print(" Ошибка получения ответа")
                break

            if hasattr(resp.choices[0].message, 'function_call') and resp.choices[0].message.function_call:
                print(' Произошел вызов функции!')

                code = extract_code_from_response(resp)
                print(f' Код: {str(code)[:100]}...')
                
                if not code:
                    print(' Код пустой!')
                    MESSAGES.append({
                        "role": "user",
                        "content": "Ты вызвал функцию vibe_code, но не передал код. Передай Python код в параметре 'code'."
                    })
                    continue

                check_result = check(code)
                
                if check_result["success"]:
                    print(f' Код выполнен без ошибок')
                    print(f' Вывод: {check_result["output"]}')
                    if verify_with_model(chad, user_request, code, check_result["output"]):
                        print(' Код делает то, что нужно!')
                        code_success = True
                        assistant_message = {
                            "role": "assistant",
                            "content": resp.choices[0].message.content or "",
                            "function_call": {
                                "name": resp.choices[0].message.function_call.name,
                                "arguments": resp.choices[0].message.function_call.arguments
                            }
                        }
                        MESSAGES.append(assistant_message)
                        MESSAGES.append({
                            "role": "function", 
                            "name": "vibe_code", 
                            "content": json.dumps(check_result, ensure_ascii=False)
                        })

                        final_response = chad.get_response(MESSAGES)
                        break
                    else:
                        print(' Код работает, но делает не то')
                        MESSAGES.append({
                            "role": "user",
                            "content": f"Код вывел: {check_result['output']}, но я просил: {user_request}. Исправь код."
                        })
                else:
                    print(f' Ошибка: {check_result["error"]}')
                    MESSAGES.append({
                        "role": "user",
                        "content": f"Код вызвал ошибку: {check_result['error']}. Исправь код и вызови функцию vibe_code снова."
                    })
            else:
                final_response = resp
                break
        if final_response and final_response.choices:
            ANSWER = {
                "role": final_response.choices[0].message.role,
                "content": final_response.choices[0].message.content
            }
            MESSAGES.append(ANSWER)
            print(f'\n\nВам ответил: {final_response.choices[0].message.content}')
            print(f'Потрачено: {final_response.usage.total_tokens}')
        else:
            print(' Не удалось получить ответ')
if __name__ == '__main__':
    main()
