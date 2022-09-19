import os
import time
import logging

import telegram
import requests
from dotenv import load_dotenv
from requests.exceptions import RequestException
from http import HTTPStatus

from exception import ResponsePracticumException

load_dotenv()

secret_token = os.getenv('TOKEN')

PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_TIME = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'

HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}


logging.basicConfig(
    level=logging.DEBUG,
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(__file__ + '.log', encoding='UTF-8')],
    format=(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    ))


def send_message(bot, message):
    """Отправляет сообщение в Телеграм."""
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
    except Exception as error:
        error_message = f'Сообщение не отправлено {error}'
        raise telegram.error.TelegramError(error_message)


def get_api_answer(current_timestamp):
    """Возвращаем ответ API, преобразовав его к типам данных Python."""
    timestamp = current_timestamp or int(time.time())
    url = ENDPOINT
    headers = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}
    params = {'from_date': timestamp}

    try:
        response = requests.get(url=url, params=params, headers=headers)
    except RequestException as error:
        error_message = (
            'Ошибка подключения к API: {error}\n {url}\n {headers}\n {params}'
            .format(error=error, url=url, params=params, headers=headers))
        raise ResponsePracticumException(error_message)

    if response.status_code != HTTPStatus.OK:
        error_message = f'Ошибка, Код ответа: {response.status_code}'
        raise ResponsePracticumException(error_message)

    return response.json()


def check_response(response):
    """
    Проверяет ответ API на корректность.
    В случае успеха, выводит список домашних работ.
    """
    if not isinstance(response, dict):
        error_message = 'Не верный тип ответа API, ожидаем словарь'
        raise TypeError(error_message)
    if 'homeworks' not in response:
        error_message = 'Ключ homeworks отсутствует'
        raise KeyError(error_message)
    if 'current_date' not in response:
        error_message = 'Ключ current_date отсутствует'
        raise KeyError(error_message)
    homeworks = response.get('homeworks')
    if not isinstance(homeworks, list):
        error_message = 'homeworks не является списком'
        raise ResponsePracticumException(error_message)
    if len(homeworks) == 0:
        error_message = 'Пустой список домашних работ'
        raise ValueError(error_message)
    homework = homeworks[0]
    return homework


def parse_status(homework):
    """Возвращает статус домашней работы."""
    if 'homework_name' not in homework:
        error_message = 'Ключ homework_name отсутствует'
        raise KeyError(error_message)
    if 'status' not in homework:
        error_message = 'Ключ status отсутствует'
        raise KeyError(error_message)
    homework_name = homework.get('homework_name')
    homework_status = homework.get('status')
    if homework_status not in HOMEWORK_VERDICTS:
        error_message = f'Статус домашней работы неизветен "{homework_status}"'
        raise ValueError(error_message)
    verdict = HOMEWORK_VERDICTS.get(homework_status)
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def check_tokens():
    """Проверяет доступность переменных окружения."""
    tokens = all([PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID])
    return tokens or logging.critical('Токен {} не найден!'.format(tokens))


def main():
    """Основная логика работы бота."""
    if not check_tokens():
        error_message = 'Токены недоступны'
        logging.error(error_message)
        raise Exception(error_message)
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    current_timestamp = int(time.time())
    last_message = ''

    while True:
        try:
            response = get_api_answer(current_timestamp)
            if response:
                homework = check_response(response)
                logging.info('Есть новости')
                message = parse_status(homework)
                if message != last_message:
                    send_message(bot, message)
                    logging.info('Сообщение отправлено')
                    last_message = message
            current_timestamp = response.get('current_date')
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            if message != last_message:
                send_message(bot, message)
                last_message = message
            logging.error(message)
        finally:
            logging.info(f'Sleeping for {RETRY_TIME} seconds...')
            time.sleep(RETRY_TIME)


if __name__ == '__main__':
    logging.info('START START START')
    main()
