# Discord File Uploader - رافع ملفات Discord

## 📋 الوصف
تطبيق ويب يسمح لك برفع الملفات الكبيرة إلى Discord من خلال رابط مباشر باستخدام حسابك الشخصي، مثالي للملفات الكبيرة عندما يكون لديك إنترنت ضعيف.

## 🚀 النشر على Render

### طريقة 1: استخدام Docker (موصى به)

1. **إنشاء حساب على Render**
   - اذهب إلى https://render.com
   - سجل حساب جديد (مجاني)

2. **رفع الملفات على GitHub**
   - أنشئ مستودع GitHub جديد
   - ارفع جميع الملفات:
     - `discord_uploader.py`
     - `requirements.txt`
     - `Dockerfile`
     - `.dockerignore`
     - مجلد `templates/` مع ملف `index.html` بداخله

3. **إنشاء Web Service على Render**
   - اضغط "New +" ثم اختر "Web Service"
   - اربط حسابك بـ GitHub
   - اختر المستودع الخاص بك
   - املأ البيانات:
     - **Name**: discord-uploader (أو أي اسم تريده)
     - **Environment**: Docker
     - **Branch**: main (أو master)
   - اضغط "Create Web Service"

4. **الانتظار**
   - Render سيقوم ببناء ونشر التطبيق (5-10 دقائق)
   - ستحصل على رابط مثل: `https://discord-uploader.onrender.com`

### طريقة 2: بدون Docker (Python مباشرة)

- اتبع نفس الخطوات لكن:
  - **Environment**: Python 3
  - **Build Command**: `pip install -r requirements.txt`
  - **Start Command**: `gunicorn discord_uploader:app`

## 🔑 الحصول على User Token و Channel ID

### User Token (توكن الحساب):

⚠️ **تحذير مهم**: استخدام توكن الحساب مخالف لشروط خدمة Discord وقد يؤدي لحظر حسابك. استخدمه بحذر وعلى مسؤوليتك الخاصة.

**الطريقة (للمتصفح):**
1. افتح Discord في المتصفح (لا تستخدم التطبيق)
2. افتح Developer Tools بالضغط على F12
3. اذهب إلى تبويب **Console**
4. الصق هذا الكود واضغط Enter:
```javascript
(webpackChunkdiscord_app.push([[''],{},e=>{m=[];for(let c in e.c)m.push(e.c[c])}]),m).find(m=>m?.exports?.default?.getToken!==void 0).exports.default.getToken()
```
5. انسخ التوكن الذي سيظهر (بدون علامات التنصيص)

**ملاحظة**: هذا التوكن شديد الحساسية - لا تشاركه مع أحد!

### Channel ID (معرف القناة):

1. فعّل Developer Mode في Discord:
   - Settings > Advanced > Developer Mode
2. اضغط كليك يمين على القناة التي تريد الرفع إليها
3. اختر "Copy Channel ID"
4. الصق المعرف في الحقل المخصص

## 💡 الاستخدام

1. افتح رابط التطبيق على Render
2. أدخل توكن حسابك (User Token)
3. أدخل معرف القناة (Channel ID)
4. ضع رابط الملف المباشر
5. اضغط "رفع الملف"

## ⚠️ ملاحظات مهمة

### حدود الرفع:
- **بدون Nitro**: 25MB
- **مع Nitro Classic**: 50MB
- **مع Nitro**: 500MB

### متطلبات الرابط:
- يجب أن يكون الرابط مباشراً
- يفضل أن ينتهي باسم الملف (مثل: .zip, .mp4, .pdf)
- مثال صحيح: `https://example.com/file.zip`
- مثال خاطئ: `https://drive.google.com/file/d/xxx` (ليس مباشر)

### الأمان:
- ⚠️ **لا تشارك توكنك مع أحد أبداً**
- استخدام User Token قد يؤدي لحظر حسابك
- Discord قد يكتشف النشاط الآلي
- استخدم على مسؤوليتك الخاصة

### الأداء:
- العملية تستغرق وقتاً حسب حجم الملف
- Render المجاني قد يكون بطيئاً قليلاً
- الملف يُحذف تلقائياً بعد الرفع

## 🐳 تشغيل محلياً باستخدام Docker

```bash
# بناء الصورة
docker build -t discord-uploader .

# تشغيل الحاوية
docker run -p 5000:10000 discord-uploader

# افتح المتصفح على
http://localhost:5000
```

## 🔒 الأمان والخصوصية

- ❌ لا يتم حفظ أي بيانات على الخادم
- ❌ لا يتم تخزين التوكن
- ✅ التوكن يُستخدم فقط للطلب الحالي
- ✅ الملف يُحذف فوراً بعد الرفع
- ✅ كل الطلبات تتم عبر HTTPS

## 🛠️ هيكل الملفات

```
discord-uploader/
│
├── discord_uploader.py      # الكود الرئيسي
├── requirements.txt         # المكتبات المطلوبة
├── Dockerfile              # إعدادات Docker
├── .dockerignore           # ملفات يتم تجاهلها
├── README.md               # هذا الملف
│
└── templates/
    └── index.html          # واجهة المستخدم
```

## 🚨 إخلاء المسؤولية

هذا المشروع للأغراض التعليمية فقط. استخدام User Token مخالف لشروط خدمة Discord ويمكن أن يؤدي إلى:
- حظر الحساب
- تعليق الوصول
- فقدان البيانات

المطور غير مسؤول عن أي أضرار أو عواقب ناتجة عن استخدام هذا التطبيق.

## 📝 الترخيص

هذا المشروع مجاني للاستخدام الشخصي فقط.
