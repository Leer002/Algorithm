import requests
import pyodbc
import json
import time
import uuid
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
        IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='trades' AND xtype='U')
        CREATE TABLE trades (
            id INT IDENTITY(1,1) PRIMARY KEY,
            trade_id NVARCHAR(128) NOT NULL,
            label NVARCHAR NOT(17) NULL,
            symbol NVARCHAR(10) NOT NULL,
            trade_type NVARCHAR(4) NOT NULL,
            quantity INT NOT NULL,
            amount FLOAT NOT NULL,
            start DATETIME DEFAULT GETDATE(),
            end DATETIME DEFAULT GETDATE()
        )
        ''')
        self.connect.commit()
    
    def get_price(self, action, symbol):
        for _ in range(2):
            response = requests.get(f"{self.base_url}/{action}/{symbol}/price", headers={"Authorization": f"Bearer {self.api_key}"})
            if response.status_code == 200:
                return response.json().get("price")
            time.sleep(2)
        print(f"خطا در دریافت قیمت {symbol}")
        return None

    def execute_trade(self, action, start, end, symbol, quantity, min_price, max_price, amount, min_stock, max_stock):
        price = self.get_price(action, symbol)
        if price is None or not (min_price <= price <= max_price):
            print(f"قیمت خارج از بازه است")
            return False

        trade_data = {
            "symbol": symbol,
            "quantity": quantity,
            "min_price": min_price,
            "max_price": max_price,
            "amount": amount,
            "min_stock": min_stock,
            "max_stock": max_stock,
            "start": start.strftime("%Y-%m-%d %H:%M:%S"),
            "end": end.strftime("%Y-%m-%d %H:%M:%S"),
        }
        
        response = requests.post(f"{self.base_url}/{action}", data=trade_data, headers={"Authorization": f"Bearer {self.api_key}"})
        if response.status_code == 200:
            print("سفارش انجام شد")
            trade_id = str(uuid.uuid4())
            now = datetime.now().time()
            if time(9, 0, 0) <= now or now <= time(8, 45, 0):
                label = "non-algorithmic"
            else:
                label = "algorithmic"
            self.save_trade(trade_id, label, symbol, action, quantity, amount)
        else:
            print(f"خطا در {action}: {response.text}")
            return False
        return True


    def buy(self, *args):
        return self.execute_trade("buy", *args)

    def sell(self, *args):
        return self.execute_trade("sell", *args)

    def update(self, id):
        response = requests.get(f"{self.base_url}/update/{id}", headers={"Authorization": f"Bearer {self.api_key}"})
        if response.status_code == 200:
            price = response.json()['price']
            trade_id = response.json()["trade_id"]

            symbol = input("نماد سهام: ")
            quantity = int(input("تعداد سهام: "))
            min_stock, max_stock = list(map(int, input("به این فرم حداقل و حداکثر سهم را وارد کنید(1000 2000)").split()))
            amount = float(input("مبلغ"))
            min_price, max_price = list(map(int, input("به این فرم حداقل و حداکثر قیمت را وارد کنید(100000 200000)").split()))

            if min_price <= price <= max_price:
                data = {
                    "symbol":symbol,
                    "quantity":quantity,
                    "min_price":min_price,
                    "max_price":max_price,
                    "amount":amount,
                    "min_stock":min_stock,
                    "max_stock":max_stock
                }
                update = requests.put(f"{self.base_url}/update/{id}/{trade_id}", data=data, headers={'Authorization': f'Bearer {self.api_key}'})

                if update.status_code == 200:
                    print(f'خرید {symbol} انجام شد')
                    trade_id = str(uuid.uuid4())
                    now = datetime.now().time()
                    if time(9, 0, 0) <= now or now <= time(8, 45, 0):
                        label = "non-algorithmic"
                    else:
                        label = "algorithmic"
                    self.save_trade(trade_id, label, symbol, 'update', quantity, amount)
                else:
                    print('خطا:', update.text)
                    time.sleep(3)
                    return False
            else:
                print(f' قیمت  خارج از بازه است  ')
                return False
        else:
            print('خطا در دریافت قیمت:', response.text)
            return False
        return True

    def delete(self, id):
        response = requests.delete(f"{self.base_url}/delete/{id}", headers={"Authorization": f"Bearer {self.api_key}"})
        if response.status_code == 200:
            print("حذف با موفقیت انجام شد.")
        else:
            print(f"خطا در حذف سفارش: {response.text}")
            return False
        return True
            
    
    def save_trade(self, trade_id, label, symbol, action, quantity, amount):
        self.cursor.execute('''
        INSERT INTO trades (trade_id, label, symbol, action, quantity, amount)
        VALUES (?, ?, ?, ?, ?, ?)
        ''', (trade_id, label, symbol, action, quantity, amount))
        self.connect.commit()

    def close(self):
        self.connect.close()

obj = Trade()


if datetime.now().strftime("%A") not in ("Thursday", "Friday"):
    if datetime.now().strftime(f"%X") >= "08:45:00":
        while True:
            inp = input("خرید: b / فروش: s / به روزرسانی: u / حذف: d / لغو: c: ").lower()

            if inp in ['b', 's']:
                symbol = input("نماد سهام: ")
                quantity = int(input("تعداد سهام: "))
                min_stock, max_stock = map(int, input("حداقل و حداکثر سهم (مثال: 1000 2000): ").split())
                amount = float(input("مبلغ: "))
                min_price, max_price = map(float, input("حداقل و حداکثر قیمت (مثال: 100000 200000): ").split())
                start = datetime.strptime(input("شروع (YYYY-MM-DD HH:MM:SS): "), "%Y-%m-%d %H:%M:%S")
                end = datetime.strptime(input("پایان (YYYY-MM-DD HH:MM:SS): "), "%Y-%m-%d %H:%M:%S")

                while True:
                    start = datetime.strptime(input("تاریخ شروع (YYYY-MM-DD HH:MM:SS): "), "%Y-%m-%d %H:%M:%S")
                    end = datetime.strptime(input("تاریخ پایان (YYYY-MM-DD HH:MM:SS): "), "%Y-%m-%d %H:%M:%S")

                    if start > end:
                        print("تاریخ شروع نمی‌تواند بعد از تاریخ پایان باشد")
                    else:
                        break

                success = obj.buy(start, end, symbol, quantity, min_price, max_price, amount, min_stock, max_stock) if inp == 'b' else obj.sell(start, end, symbol, quantity, min_price, max_price, amount, min_stock, max_stock)

            elif inp == 'u':
                success = obj.update(int(input("آیدی سفارش را وارد کنید: ")))

            elif inp == 'd':
                success = obj.delete(int(input("آیدی سفارش را وارد کنید: ")))

            elif inp == 'c':
                print("لغو شد")
                break
    else:
        obj.close()
else:
    print("بازار تعطیل است")

