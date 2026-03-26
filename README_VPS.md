# تشغيل البوت على VPS

هذا المشروع مناسب للتشغيل على Linux VPS باستخدام `systemd`.

## المتطلبات

- Ubuntu أو Debian
- Python 3.10 أو أحدث
- صلاحية sudo

## 1) تثبيت المتطلبات الأساسية

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip
```

إذا كان إصدار `python3` أقل من 3.10، ثبّت Python 3.10 أو 3.11 أولاً.

## 2) رفع المشروع إلى السيرفر

ضع الملفات داخل مجلد مثل:

```bash
/opt/telegram-bot
```

## 3) إنشاء البيئة وتثبيت المكتبات

```bash
cd /opt/telegram-bot
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

## 4) إنشاء ملف البيئة

أنشئ ملف `.env` داخل مجلد المشروع:

```env
BOT_TOKEN=YOUR_BOT_TOKEN
ADMIN_ID=123456789
ADMIN_IDS=123456789,2078667491
REQUIRED_CHANNELS=@your_channel_username
CHANNEL_ID=-1001234567890
KEEP_ALIVE_PORT=8080
```

ملاحظات:

- `ADMIN_IDS` اختياري ويدعم أكثر من أدمن مفصولين بفواصل.
- `REQUIRED_CHANNELS` يدعم أكثر من قناة مفصولة بفواصل.
- `KEEP_ALIVE_PORT` اختياري. إذا لم تضعه فالقيمة الافتراضية `8080`.

## 5) اختبار التشغيل يدويًا

```bash
cd /opt/telegram-bot
source .venv/bin/activate
python run_bot.py
```

إذا اشتغل البوت بنجاح، أوقفه ثم فعّل الخدمة الدائمة.

## 6) تفعيل systemd

انسخ الملف `bot.service.example` إلى `/etc/systemd/system/telegram-bot.service` ثم عدّل المسارات واسم المستخدم.

```bash
sudo cp bot.service.example /etc/systemd/system/telegram-bot.service
sudo nano /etc/systemd/system/telegram-bot.service
```

بعد التعديل:

```bash
sudo systemctl daemon-reload
sudo systemctl enable telegram-bot
sudo systemctl start telegram-bot
sudo systemctl status telegram-bot
```

## 7) السجلات

```bash
sudo journalctl -u telegram-bot -f
```

وسيُكتب أيضًا ملف محلي باسم `bot.log` داخل مجلد المشروع.

## 8) فحص الصحة

البوت يفتح مسار صحة HTTP:

- `/`
- `/health`

مثال محلي:

```bash
curl http://127.0.0.1:8080/health
```

إذا أردت ربطه مع UptimeRobot أو Nginx فهذا جاهز من دون تعديل إضافي.

## ملاحظات تشغيل

- لا تشغّل أكثر من نسخة من البوت بنفس `BOT_TOKEN`.
- الأفضل تشغيله من خلال `systemd` وليس `screen` أو جلسة SSH مباشرة.
- عند تحديث الكود نفّذ:

```bash
cd /opt/telegram-bot
source .venv/bin/activate
pip install -r requirements.txt
sudo systemctl restart telegram-bot
```