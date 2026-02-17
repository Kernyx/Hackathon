"""
LLM-клиент: подключение к OpenAI-совместимому API (LM Studio) с retry.
"""

import time
from typing import Optional

import httpx
from openai import OpenAI, APITimeoutError, APIConnectionError, APIStatusError
from colorama import Fore, Style

from config import LLM_BASE_URL, LLM_API_KEY, LLM_MODEL, LLM_TIMEOUT, LLM_MAX_RETRIES, LLM_RETRY_DELAY

http_client = httpx.Client(
    timeout=httpx.Timeout(LLM_TIMEOUT, connect=10.0),
    proxy=None,
)

client = OpenAI(
    base_url=LLM_BASE_URL,
    api_key=LLM_API_KEY,
    timeout=LLM_TIMEOUT,
    max_retries=0,
    http_client=http_client,
)


def llm_chat(messages: list[dict], temperature: float = 0.8) -> Optional[str]:
    """Отправить запрос к LLM с retry и таймаутом. Возвращает None при неудаче."""
    if messages and messages[0]["role"] == "system":
        if "/no_think" not in messages[0]["content"]:
            messages = messages.copy()
            messages[0] = messages[0].copy()
            messages[0]["content"] = "/no_think\n" + messages[0]["content"]

    for attempt in range(1, LLM_MAX_RETRIES + 1):
        try:
            resp = client.chat.completions.create(
                model=LLM_MODEL,
                messages=messages,
                temperature=temperature,
                max_tokens=150,
            )
            return resp.choices[0].message.content.strip()

        except APITimeoutError:
            wait = LLM_RETRY_DELAY * attempt
            print(f"{Fore.RED}  LLM таймаут (попытка {attempt}/{LLM_MAX_RETRIES}), жду {wait:.0f}с...{Style.RESET_ALL}")
            time.sleep(wait)

        except APIConnectionError as e:
            wait = LLM_RETRY_DELAY * attempt
            print(f"{Fore.RED}  LLM недоступен (попытка {attempt}/{LLM_MAX_RETRIES}): {e}{Style.RESET_ALL}")
            time.sleep(wait)

        except APIStatusError as e:
            if e.status_code == 400:
                # Переполнение контекста — не ретраим, бесполезно
                msg_str = str(e.message) if hasattr(e, 'message') else str(e)
                if 'context' in msg_str.lower() or 'token' in msg_str.lower() or 'overflow' in msg_str.lower():
                    total_tokens = sum(len(m.get('content', '')) // 3 for m in messages)
                    print(f"{Fore.RED}  Контекст переполнен (~{total_tokens} токенов)! Обрезаю...{Style.RESET_ALL}")
                else:
                    print(f"{Fore.RED}  LLM ошибка 400: {msg_str[:120]}{Style.RESET_ALL}")
                return None
            elif e.status_code == 429:
                wait = LLM_RETRY_DELAY * attempt * 2
                print(f"{Fore.RED}  LLM перегружен (429), жду {wait:.0f}с...{Style.RESET_ALL}")
                time.sleep(wait)
            elif e.status_code >= 500:
                wait = LLM_RETRY_DELAY * attempt
                print(f"{Fore.RED}  LLM ошибка сервера ({e.status_code}), жду {wait:.0f}с...{Style.RESET_ALL}")
                time.sleep(wait)
            else:
                print(f"{Fore.RED}  LLM ошибка {e.status_code}: {e.message}{Style.RESET_ALL}")
                return None

        except Exception as e:
            print(f"{Fore.RED}  Неожиданная ошибка: {e}{Style.RESET_ALL}")
            return None

    print(f"{Fore.RED}  LLM не ответил после {LLM_MAX_RETRIES} попыток, пропускаю ход.{Style.RESET_ALL}")
    return None
