#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
🚀 ملف البدء - بوت تليغرام
شغّل هذا الملف لبدء البوت
متوافق مع REPLIT + Windows + Linux
"""

import os
import sys
import subprocess

def check_python_version():
    """التحقق من إصدار Python"""
    if sys.version_info < (3, 10):
        print("❌ خطأ: يتطلب Python 3.10 أو أحدث")
        sys.exit(1)
    print(f"✅ Python {sys.version.split()[0]} جاهز")

def check_env_file():
    """التحقق من وجود BOT_TOKEN في البيئة أو .env"""
    if os.path.exists('.env'):
        with open('.env', 'r', encoding='utf-8') as f:
            content = f.read()
            if 'BOT_TOKEN' not in content:
                print("❌ لم يتم العثور على BOT_TOKEN في .env!")
                sys.exit(1)
            if 'YOUR_BOT_TOKEN' in content or 'YOUR_BOT_TOKEN_HERE' in content:
                print("❌ استبدل YOUR_BOT_TOKEN بالتوكن الفعلي!")
                sys.exit(1)

        print("✅ ملف .env موجود وصحيح")
        return

    env_token = os.getenv('BOT_TOKEN', '').strip()
    if env_token:
        if env_token in {'YOUR_BOT_TOKEN', 'YOUR_BOT_TOKEN_HERE'}:
            print("❌ قيمة BOT_TOKEN غير صحيحة في متغيرات البيئة")
            sys.exit(1)
        print("✅ تم العثور على BOT_TOKEN في متغيرات البيئة")
        return

    if not os.path.exists('.env'):
        print("❌ لم يتم العثور على BOT_TOKEN")
        print("📝 على Replit أضف BOT_TOKEN داخل Secrets")
        print("📝 أو أنشئ ملف .env محلياً")
        sys.exit(1)

def check_requirements():
    """التحقق من المكتبات المطلوبة"""
    try:
        import telebot
        print("✅ pyTelegramBotAPI مثبت")
    except ImportError:
        print("⚠️ تثبيت pyTelegramBotAPI...")
        subprocess.check_call([sys.executable, '-m', 'pip', 'install', '-q', 'pyTelegramBotAPI'])
        print("✅ تم تثبيت pyTelegramBotAPI")
    
    try:
        import dotenv
        print("✅ python-dotenv مثبت")
    except ImportError:
        print("⚠️ تثبيت python-dotenv...")
        subprocess.check_call([sys.executable, '-m', 'pip', 'install', '-q', 'python-dotenv'])
        print("✅ تم تثبيت python-dotenv")

def check_files_directory():
    """التحقق من وجود مجلد الملفات المحلية الاختيارية"""
    if not os.path.exists('files'):
        print("⚠️ مجلد files غير موجود، جاري الإنشاء...")
        os.makedirs('files')
        print("✅ تم إنشاء مجلد files للاستخدام الاختياري")
    else:
        file_count = len([f for f in os.listdir('files') if f.endswith('.pdf')])
        if file_count == 0:
            print("ℹ️ مجلد files فارغ، وهذا طبيعي إذا كنت سترفع الملفات من داخل البوت")
        else:
            print(f"✅ توجد {file_count} ملفات PDF محلية في مجلد files/")

def show_startup_info():
    """عرض معلومات البدء"""
    print("\n" + "="*70)
    print("🤖 بوت تليغرام - ملازم تعليمية")
    print("="*70)
    print("")
    print("📌 معلومات الإعداد:")
    print("   ✅ لغة البرمجة: Python")
    print("   ✅ المكتبة: pyTelegramBotAPI")
    print("   👨‍💻 مطور البوت: @jih_313")
    print("   ✅ الواجهة: Inline Buttons (نوافذ)")
    print("   ✅ فحص الاشتراك الإجباري: مفعّل ✓")
    print("   ✅ لوحة أدمن ديناميكية: مفعّلة ✓")
    print("   ✅ رفع الملفات من تيليغرام: مدعوم ✓")
    print("   ✅ متوافق مع REPLIT: نعم ✓")
    print("   ✅ يدعم Replit Secrets: نعم ✓")
    print("")
    print("⏳ جاري بدء البوت...")
    print("="*70 + "\n")

def main():
    """البدء الرئيسي"""
    print("🚀 جاري التحضير...\n")
    
    # فحوصات البداية
    check_python_version()
    check_env_file()
    check_requirements()
    check_files_directory()
    
    show_startup_info()
    
    # بدء البوت
    try:
        import bot
        bot.main()
    except KeyboardInterrupt:
        print("\n✅ تم الإيقاف بنجاح")
    except Exception as e:
        print(f"\n❌ خطأ: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    main()
