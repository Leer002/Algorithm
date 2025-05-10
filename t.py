import requests
import pyodbc
import json
from datetime import datetime

class Trade:
    def __init__(self):
        with open("info.json") as info_file:
            info = json.load(info_file)
        self.api_key = info["api_key"]
        self.api_secret = info["api_secret"]
        self.base_url = info["base_url"]
        self.connect = pyodbc.connect(f'DRIVER={{ODBC Driver 17 for SQL Server}};SERVER={info["server"]};DATABASE={info["database"]};UID={info["username"]};PWD={info["password"]}')
        self.cursor = self.connect.cursor()
        self.create_table()

    def create_table(self):
        self.cursor.execute('''
        IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='trades')
        CREATE TABLE trades (
            id INT IDENTITY(1,1) PRIMARY KEY,
            stock_symbol NVARCHAR(10) NOT NULL,
            user NVARCHAR(10) NOT NULL,
            trade_type NVARCHAR(4) NOT NULL,
            quantity INT NOT NULL,
            price FLOAT NOT NULL,
            timestamp DATETIME DEFAULT GETDATE()
        )
        ''')
        self.connect.commit()

    def buy(self, user, symbol, quantity, price_range):
        response = requests.get(f"{self.base_url}/buy/{symbol}/price", headers={"Authorization": f"Bearer{self.api_key}"})
        if response.status_code == 200:
            price = response.json()["price"]
            if price_range[0] <= price <= price_range[1]:
                buy = requests.post(f"{self.api_key}/...", data={"sybmol":symbol, "quantity":quantity}, headers={'Authorization': f'Bearer {self.api_key}'})
                if buy.status_code == 200:
                    print(f'خرید {symbol} انجام شد')
                    self.save(user, symbol, 'buy', quantity, price)
                else:
                    print('خطا:', buy.text)
            else:
                print(f'قیمت  خارج از بازه‌ی تعیین‌شده ')
        else:
            print('خطا در دریافت قیمت:', response.text)
    
    def sell(self, user, symbol, quantity, price_range):
        response = requests.get(f"{self.base_url}/sell/{symbol}/price", headers={'Authorization': f'Bearer {self.api_key}'})
        
        if response.status_code == 200:
            price = response.json()['price']
            if price_range[0] <= price <= price_range[1]:
                sell = requests.post(f"{self.api_url}/sell", data={
                    'symbol': symbol,
                    'quantity': quantity,
                    'price': price
                }, headers={'Authorization': f'Bearer {self.api_key}'})

                if sell.status_code == 200:
                    print(f'خرید {symbol} انجام شد')
                    self.save(user, symbol, 'sell', quantity, price)
                else:
                    print('خطا:', sell.text)
            else:
                print(f'قیمت  خارج از بازه  ')
        else:
            print('خطا در دریافت قیمت:', response.text)
    
    def save_trade(self, user, symbol, type, quantity, price):
        self.cursor.execute('''
        INSERT INTO trades (user, symbol, type, quantity, price)
        VALUES (?, ?, ?, ?)
        ''', (user, symbol, type, quantity, price))
        self.connect.commit()

    def close(self):
        self.connect.close()

obj = Trade()

while True:
    inp = input("خرید: b / فروش: s / لغو: c): ").lower()

    if inp in ['b', 's']:
        symbol = input("نماد سهام: ")
        quantity = int(input("تعداد سهام: "))
        
        
        min_price = float(input("حداقل قیمت : "))
        max_price = float(input("حداکثر قیمت: "))
        price_range = (min_price, max_price)

        
        start = input(" شروع (YYYY-MM-DD): ")
        end = input(" پایان (YYYY-MM-DD): ")

        
        try:
            start = datetime.strptime(start, '%Y-%m-%d')
            end = datetime.strptime(end, '%Y-%m-%d')
            
            if start > end:
                print("تاریخ شروع نمی‌ تواند بعد از پایان باشد")
                continue
            
            if inp == 'b':
                obj.buy(symbol, quantity, price_range)
            
            elif inp == 's':
                obj.sell(symbol, quantity, price_range)

        except ValueError:
            print("فرمت تاریخ نامعتبر است")

    elif inp == 'c':
        print("لغو شد")
        break

    else:
        print("انتخاب نامعتبر است")

obj.close()