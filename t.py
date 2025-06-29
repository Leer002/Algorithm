import requests # برای ارسال درخواست‌ های HTTP
import pyodbc # اتصال به SQL Server
import json # کار با داده‌ های JSON
import time # برای توقف موقت در اجرای برنامه
import uuid # تولید شناسه‌ های یونیک
import jdatetime # تبدیل تاریخ
import logging # مدیریت و ثبت گزارش‌ خطاها
from datetime import datetime, time as dtime, date as ddate # ابزارهای تاریخ و زمان 

# پیکربندی لاگینگ
logging.basicConfig(
    level = logging.ERROR, # فقط خطاها (ERROR) ثبت شوند
    filemode="a", # حالت اضافه کردن (append)
    filename="errors.log", # اسم فایل خروجی
    format = "%(asctime)s : [%(levelname)s] - %(message)s" # (زمان، سطح، پیام)
)

def retry(url, headers, method="get", data=None):
    """ تعریف تابعی برای انجام درخواست با امکان تکرار تا ۳ بار """

    for i in range(3):
        try:
            response = getattr(requests, method)(url, headers=headers, data=data)  # اجرای متد موردنظر به صورت داینامیک
            if response.status_code == 200:
                print(f" تلاش {i+1} موفقیت‌آمیز بود: {url}")
                return response
            else:
                logging.error(f" تلاش {i+1} ناموفق: وضعیت {response.status_code} - {response.text}")

        except Exception as e:
            logging.error(f" تلاش {i+1} ناموفق به دلیل خطا: {url} - {e}")
            time.sleep(2)

    print("همه تلاش‌ ها ناموفق بودند")
    return None

class Trade:
    def __init__(self):
        with open("info.json") as info_file:
            info = json.load(info_file)
        
        # استخراج اطلاعات از فایل JSON
        self.api_key = info["api_key"]
        self.api_secret = info["api_secret"]
        self.base_url = info["base_url"]
        
        # اتصال به پایگاه‌ داده SQL Server
        self.connect = pyodbc.connect(f'DRIVER={{ODBC Driver 17 for SQL Server}};SERVER={info["server"]};DATABASE={info["database"]};UID={info["username"]};PWD={info["password"]}')

        self.cursor = self.connect.cursor()

        self.create_table()

    def create_table(self):
        """ایجاد جدول"""
        self.cursor.execute('''
        IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='trades' AND xtype='U')
        BEGIN
        CREATE TABLE trades (
            id INT IDENTITY(1,1) PRIMARY KEY,
            action NVARCHAR(10) NOT NULL, -- نوع عملیات (خرید یا فروش)
            market NVARCHAR(70) NOT NULL, -- بازار
            securities_type NVARCHAR(50) NOT NULL, -- نوع اوراق بهادار
            start DATETIME DEFAULT GETDATE(), -- زمان شروع معامله (پیش‌ فرض: الان)
            end DATETIME DEFAULT GETDATE(), -- زمان پایان معامله
            symbol NVARCHAR(10) NOT NULL, -- نماد
            quantity INT NOT NULL, -- تعداد سهام معامله‌ شده
            amount FLOAT NOT NULL, -- مبلغ معامله
            trade_id NVARCHAR(128) NOT NULL, -- شناسه ای یونیک برای معامله
            label NVARCHAR(17) NOT NULL -- تعیین الگوریتمی بودن یا نبودن معامله
        )
        END
        ''')
        self.connect.commit()
    
    def get_price(self, action, symbol):
        """برای دریافت قیمت نماد از API"""

        for attempt in range(2):
            response = requests.get(f"{self.base_url}/{action}/{symbol}/price", headers={"Authorization": f"Bearer {self.api_key}"})
            
            if response.status_code == 200:
                print(f" قیمت {symbol} با موفقیت دریافت شد")
                return response.json().get("price")
            logging.error(f" تلاش {attempt + 1} ناموفق برای دریافت قیمت {symbol}. وضعیت: {response.status_code}")
            time.sleep(2)

        logging.error(f" دریافت قیمت {symbol} پس از دو تلاش ناموفق بود.")
        return None

    def execute_trade(self, action, market, securities_type, start, end, symbol, quantity, min_price, max_price, amount, min_stock, max_stock):
        """تابع اجرای یک معامله (خرید یا فروش)"""

        price = self.get_price(action, symbol)

        # بررسی اینکه آیا قیمت در محدوده مجاز قرار دارد یا خیر
        if price is None or not (min_price <= price <= max_price):
            logging.error(f" قیمت {symbol} خارج از محدوده تعیین‌شده ({min_price} - {max_price}) است")
            return False
        
        # داده‌ های معامله برای ارسال به سرور
        data = {
            "market": market,
            "securities_type":securities_type,
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
        
        # ارسال درخواست پست برای اجرای معامله
        url = f"{self.base_url}/{action}"
        response = retry(url, headers={"Authorization": f"Bearer {self.api_key}"}, method="post", data=data)

        if response is not None:
            print(f" سفارش {action} برای {symbol} با موفقیت انجام شد")

            trade_id = str(uuid.uuid4())
            now = datetime.now().time()
            # اگه زمان معامله بین 8و45 تا 9 بود الگوریتمی و در غیر این صورت معامله غیرالگوریتمی است
            label = "non-algorithmic" if dtime(8, 45) <= now <= dtime(9, 0) else "algorithmic"
            
            # ثبت معامله در پایگاه‌ داده
            self.save_trade(action, market, securities_type, start, end, symbol, quantity, amount, trade_id, label)
            return True
        
        else:
            logging.error(f" خطا در ارسال سفارش {action} برای {symbol}")
            return False

    def buy(self, *args):
        return self.execute_trade("buy", *args)

    def sell(self, *args):
        return self.execute_trade("sell", *args)

    def update(self, id):
        """بروزرسانی اطلاعات معامله"""

        # دریافت اطلاعات فعلی معامله از سرور
        response = requests.get(f"{self.base_url}/update/{id}", headers={"Authorization": f"Bearer {self.api_key}"})

        if response.status_code == 200:
            price = response.json()['price']
            trade_id = response.json()["trade_id"]
            
            # دریافت اطلاعات جدید از کاربر
            symbol = input("نماد سهام: ")
            quantity = int(input("تعداد سهام: "))
            min_stock, max_stock = map(int, input("به این فرم حداقل و حداکثر سهم را وارد کنید(1000 2000): ").split())
            amount = float(input("مبلغ"))
            min_price, max_price = map(int, input("به این فرم حداقل و حداکثر قیمت را وارد کنید(100000 200000): ").split())
            securities_type = input("نوع اوراق بهادار:")
            market = input("بازار:")
            start_date = input("تاریخ شروع (YYYY-MM-DD HH:MM:SS): ")
            end_date = input("تاریخ پایان (YYYY-MM-DD HH:MM:SS): ")
            start = datetime.strptime(start_date, "%Y-%m-%d %H:%M:%S")
            end = datetime.strptime(end_date, "%Y-%m-%d %H:%M:%S")

            if min_price <= price <= max_price:
                data = {
                    "symbol":symbol,
                    "quantity":quantity,
                    "min_price":min_price,
                    "max_price":max_price,
                    "amount":amount,
                    "min_stock":min_stock,
                    "max_stock":max_stock,
                    "securities_type": securities_type,
                    "market":market
                }

                # ارسال درخواست PUT برای بروزرسانی
                url = f"{self.base_url}/update/{id}"
                update = retry(url, headers={'Authorization': f'Bearer {self.api_key}'}, method="put", data=data)

                if update is not None and update.status_code == 200:
                    print(f'خرید {symbol} انجام شد')

                    # ثبت اطلاعات بروزرسانی‌ شده در دیتابیس
                    trade_id = str(uuid.uuid4())
                    now = datetime.now().time()

                    if dtime(8, 45, 0) <= now <= dtime(9, 0, 0):
                        label = "non-algorithmic"

                    else:
                        label = "algorithmic"

                    self.save_trade("update", market, securities_type, start, end, symbol, quantity, amount, trade_id, label)
                    return True
                
                logging.error("خطا در درخواست")
                return False
            else:
                logging.error(f' قیمت  خارج از بازه است  ')
                return False
        else:
            logging.error('خطا در دریافت قیمت:'+ response.text)
            return False

    def delete(self, id):
        """ ارسال درخواست DELETE
            برای حذف سفارش
        """
        response = requests.delete(f"{self.base_url}/delete/{id}", headers={"Authorization": f"Bearer {self.api_key}"})
        if response.status_code == 200:
            print("حذف با موفقیت انجام شد")
        else:
            logging.error(f"خطا در حذف سفارش {id}: {response.text}")
            return False
        return True
            
    def save_trade(self, action, market, securities_type, start, end, symbol, quantity, amount, trade_id, label):
        """ذخیره اطلاعات یک معامله در جدول پایگاه داده"""

        self.cursor.execute('''
        INSERT INTO trades (action, market, securities_type, start, end, symbol, quantity, amount, trade_id, label)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (action, market, securities_type, start, end, symbol, quantity, amount, trade_id, label))

        self.connect.commit()

    def close(self):
        """بستن اتصال دیتابیس"""
        self.connect.close()

obj = Trade()

def is_market_open():
    """بررسی باز بودن بازار"""

    now = datetime.now() # تاریخ فعلی
    day = now.strftime("%A") # استخراج نام روز هفته

    #تعیین زمان باز و بسته شدن بازار
    market_open_time = now.replace(hour=8, minute=45, second=0)
    market_close_time = now.replace(hour=12, minute=30, second=0)
    
    # ایجاد لیستی برای تعطیلات رسمی
    holidays = [
    ]
    
    # تعطیلات رسمی به جز جمعه ها از تیر به بعد -> ماه, روز
    date_list = [(4,14), (4,15), (5,23), (6,10), (6,10), (6,19), (9,3), (10,13), (10,27), (11,15), (11,22), (12,20)]
    
    # تبدیل تاریخ ‌های شمسی به میلادی و ذخیره در لیست
    for d in date_list:
        date = jdatetime.date(1404, d[0], d[1])
        gregorian_date  = date.togregorian()
        gregorian_datetime = ddate(gregorian_date.year, gregorian_date.month, gregorian_date.day)
        holidays.append(gregorian_datetime) 

    # بررسی شرایط باز بودن بازار:
    # - نباشد پنج‌ شنبه یا جمعه
    # - ساعت فعلی بین ساعات مجاز بازار باشد
    # - تاریخ فعلی یکی از تعطیلات رسمی نباشد
    if day not in ("Thursday", "Friday") and market_open_time <= now <= market_close_time and now.date() not in holidays:
        return True
    else:
        return False

if is_market_open():
        while True:
            #دریافت نوع عملیات از کاربر 
            inp = input("خرید: b / فروش: s / بروزرسانی: u / حذف: d / لغو: c: ").lower()

            if inp in ['b', 's']:
                # دریافت اطلاعات معامله از کاربر
                while True:
                    try:
                        symbol = input("نماد سهام: ").strip()
                        quantity = int(input("تعداد سهام: "))
                        min_stock, max_stock = map(int, input("حداقل و حداکثر سهم (مثال: 1000 2000): ").split())
                        amount = float(input("مبلغ: "))
                        min_price, max_price = map(float, input("حداقل و حداکثر قیمت (مثال: 100000 200000): ").split())
                        securities_type = input("نوع اوراق بهادار:").strip()
                        market = input("بازار:").strip()

                        # اعتبارسنجی ورودی‌ ها
                        if quantity <= 0 or amount <= 0:
                            logging.error("عدد وارد شده باید مثبت باشد")
                            continue
                        elif min_stock > max_stock or min_price > max_price:
                            logging.error("حداقل نمی‌ تواند بیشتر از حداکثر باشد")
                            continue
                        elif securities_type.strip() == "" or symbol.strip() == "" or market.strip() == "":
                            logging.error("مقدار وارد شده معتبر نیست")
                            continue
                        break
                    except ValueError:
                        logging.error("لطفاً دوباره تلاش کنید")

                # دریافت و بررسی تاریخ شروع و پایان معامله
                while True:
                    try:
                        start = datetime.strptime(input("تاریخ شروع (YYYY-MM-DD HH:MM:SS): "), "%Y-%m-%d %H:%M:%S")
                        end = datetime.strptime(input("تاریخ پایان (YYYY-MM-DD HH:MM:SS): "), "%Y-%m-%d %H:%M:%S")

                        if start > end:
                            logging.error("تاریخ شروع نمی‌ تواند بعد از تاریخ پایان باشد")
                            continue
                        else:
                            break
                    except ValueError:
                        logging.error("فرمت تاریخ صحیح نیست")
                        

                success = obj.buy(market, securities_type, start, end, symbol, quantity, min_price, max_price, amount, min_stock, max_stock) if inp == 'b' else obj.sell(market, securities_type, start, end, symbol, quantity, min_price, max_price, amount, min_stock, max_stock)

                if success:
                    print("عملیات با موفقیت انجام شد")
                else:
                    logging.error(f"خطا در انجام عملیات برای {symbol}")

            elif inp == 'u':
                try:
                    success = obj.delete(int(input("آیدی سفارش را وارد کنید: ")))
                except ValueError:
                    logging.error("لطفاً یک عدد صحیح وارد کنید")
        
                else:
                    if success:
                        print("عملیات با موفقیت انجام شد.")
                    else:
                        logging.error(f"خطا در انجام عملیات برای {symbol}")
                        
            elif inp == 'd':
                try:
                    success = obj.delete(int(input("آیدی سفارش را وارد کنید: ")))
                except ValueError:
                    logging.error("لطفاً یک عدد صحیح وارد کنید")
                else:
                    if success:
                        print("عملیات با موفقیت انجام شد")
                    else:
                        logging.error(f"خطا در انجام عملیات برای {symbol}")
            elif inp == 'c':
                print("لغو شد")
                break
            else:
                logging.error("گزینه‌ی انتخاب شده معتبر نیست {inp}")
else:
    print("بازار تعطیل است")
    obj.close()
