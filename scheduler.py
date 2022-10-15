import datetime
import logging.config
import os
import re

import apiclient.discovery
import httplib2
import prettytable as pt
import telebot
from PIL import Image, ImageDraw, ImageFont
from oauth2client.service_account import ServiceAccountCredentials
from telebot import types
from telegram_bot_calendar import DetailedTelegramCalendar
import traceback

# Настройки бота
bot_token = os.environ.get('bot_token')
bot = telebot.TeleBot(bot_token)

# Настройки Google sheets
creds_json = 'creds.json'
scopes = ['https://www.googleapis.com/auth/spreadsheets']
sheet_id = os.environ.get('sheet_id')
creds_service = ServiceAccountCredentials.from_json_keyfile_name(creds_json, scopes).authorize(httplib2.Http())
service = apiclient.discovery.build('sheets', 'v4', http=creds_service)


def get_table():
    try:
        logging.info('Получаем таблицу из Google sheets..')
        resp = service.spreadsheets().values().get(spreadsheetId=sheet_id, range="Лист1!A1:AA1001").execute()
        h_values = resp['values'].pop(0)
        values = resp['values']
        max_len_row = max([len(r) for r in values])
        for r in values:
            current_len = len(r)
            if current_len < max_len_row:
                while current_len < max_len_row:
                    r.append('')
                    current_len += 1
        table = pt.PrettyTable(h_values)

        for line in values:
            table.add_row(line)

        logging.info(f'Полученная таблица:\n{table}')
        return table
    except Exception as e:
        logging.error(f'Error in get_table:', traceback.format_exc())
        return False


def add_row_to_table(day_1, day_2, name):
    logging.info('Добавление строки в таблицу..')
    cell_occupied = False
    msg = ''
    try:
        resp = service.spreadsheets().values().get(spreadsheetId=sheet_id, range="Лист1!A1:AA1001").execute()
        values = resp['values']

        for i in range(len(values)):
            if values[i] and (re.search(day_1, values[i][0]) or re.search(day_2, values[i][0])):
                cell_occupied = i

        if cell_occupied:
            values[i] = [f'{day_1} - {day_2}', values[i][1], name]
            resp_upd = service.spreadsheets().values().update(spreadsheetId=sheet_id,
                                                              range="Лист1!A1",
                                                              valueInputOption="RAW",
                                                              body={'values': values}).execute()
            msg = f'Обновлена существующая строка:\n{values[i]}'
        else:
            new_row = [[f'{day_1} - {day_2}', '', name]]
            resp_upd = service.spreadsheets().values().append(spreadsheetId=sheet_id,
                                                              range="Лист1!A1:C1",
                                                              valueInputOption="RAW",
                                                              body={'values': new_row}).execute()
            msg = f'Добавлена строка:\n{new_row}'
        logging.info(msg)
        return True, msg
    except Exception as e:
        msg = 'Ошибка обновления данных в таблице!'
        logging.error(f'{msg} {e}')
        return False, msg


def create_img_from_table(table, name_png='table.png'):
    logging.info('Создание картинки из таблицы..')
    font = ImageFont.truetype("FreeMonospaced.ttf", 18)
    width_row = font.getsize([line for line in table.get_string().split('\n')][1])
    number_rows = len([line for line in table.get_string().split('\n')])

    size = (width_row[0], int(number_rows * width_row[1]))
    logging.info(f'Вычисленные размеры картинки: {size}')

    im = Image.new("RGB", size, "white")
    draw = ImageDraw.Draw(im)
    draw.text((5, 5), str(table), font=font, fill="black")
    im.save(name_png)
    logging.info(f'Картинка {name_png} сохранена')


@bot.message_handler(commands=['start'])
def start(message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    btn = types.KeyboardButton('/get_table')
    markup.add(btn)
    bot.send_message(message.chat.id, text='bot is running..', reply_markup=markup)
    logging.info('bot is running..')


class MyStyleCalendar(DetailedTelegramCalendar):
    # previous and next buttons style. they are emoji now!
    prev_button = "⬅️"
    next_button = "➡️"
    # you do not want empty cells when month and year are being selected
    empty_month_button = ""
    empty_year_button = ""


@bot.message_handler(commands=['get_table'])
def send_table_photo(message):
    logging.info('Нажата кнопка `get_table`')
    markup = types.InlineKeyboardMarkup()
    button = types.InlineKeyboardButton('Добавить дежурство', callback_data='add')
    markup.add(button)

    table = get_table()
    if table:
        create_img_from_table(table, 'table.png')
        with open('table.png', 'rb') as image:
            bot.send_photo(message.chat.id, image, reply_markup=markup)
            logging.info('В telegram отправлена картинка с таблицей')
    else:
        logging.error('Не удалось получить таблицу')
        bot.send_message(message.chat.id, text='Ошибка получения таблицы', reply_markup=markup)


@bot.callback_query_handler(lambda c: c.data == "add")
def process_callback_1(c):
    logging.info('Нажата кнопка `Добавить дежурство`')
    calendar, step = MyStyleCalendar(min_date=datetime.date.today(),
                                     max_date=datetime.date.today()+datetime.timedelta(weeks=26),
                                     locale='ru').build()

    bot.send_message(c.message.chat.id, f"Выберите год:", reply_markup=calendar)


@bot.callback_query_handler(func=MyStyleCalendar.func())
def cal(c):
    result, key, step = MyStyleCalendar(
        min_date=datetime.date.today(),
        max_date=datetime.date.today()+datetime.timedelta(weeks=26),
        locale='ru').process(c.data)
    if not result and key:
        cur_str = 'год'
        if step == 'm':
            cur_str = 'месяц'
        elif step == 'd':
            cur_str = 'день'
        bot.edit_message_text(f"Выберите {cur_str}:", c.message.chat.id, c.message.message_id, reply_markup=key)
    elif result:
        day_1 = (result - datetime.timedelta(days=1)).strftime("%d.%m")
        day_2 = result.strftime("%d.%m")
        msg_str = f'{day_1} - {day_2}'
        name_user = c.from_user.first_name
        if c.from_user.last_name:
            name_user = f'{c.from_user.first_name} {c.from_user.last_name}'
        res, msg = add_row_to_table(day_1, day_2, name_user)
        if res:
            logging.info(f'Пользовтаель `{name_user}` выбрал дежурство: {msg_str}')
            bot.edit_message_text(f'{name_user}, вы выбрали дежурство *{msg_str}*',
                                  c.message.chat.id, c.message.message_id, parse_mode='Markdown')
        else:
            bot.edit_message_text(msg, c.message.chat.id, c.message.message_id, parse_mode='Markdown')


if __name__ == '__main__':
    logging.config.fileConfig('logging.ini')
    bot.polling(none_stop=True)
