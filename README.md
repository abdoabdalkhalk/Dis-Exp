# Discord File Uploader - رافع ملفات Discord (Vercel)

## 🚀 النشر على Vercel

### الخطوات البسيطة:

1. **إنشاء حساب على Vercel**
   - اذهب إلى https://vercel.com
   - سجل دخول بحساب GitHub الخاص بك

2. **رفع الملفات على GitHub**
   - أنشئ مستودع GitHub جديد
   - ارفع هذه الملفات:
     - `discord_uploader.py`
     - `requirements.txt`
     - `vercel.json`
     - مجلد `templates/` مع ملف `index.html` بداخله

3. **ربط المستودع بـ Vercel**
   - اضغط "New Project" في Vercel
   - اختر المستودع من GitHub
   - Vercel سيكتشف الإعدادات تلقائياً من `vercel.json`
   - اضغط "Deploy"

4. **الانتهاء!**
   - ستحصل على رابط مثل: `https://your-project.vercel.app`
   - التطبيق جاهز للاستخدام فوراً

## ⚡ مميزات Vercel

### ✅ جلسات منفصلة لكل مستخدم
- كل زائر له session خاص به
- لا تداخل بين المستخدمين
- خصوصية أفضل

### ✅ أداء سريع
- Serverless Functions
- Edge Network عالمي
- استجابة فورية

### ✅ مجاني بالكامل
- Hobby Plan مجاني للأبد
- 100GB Bandwidth شهرياً
- Serverless Function Execution

## ⚠️ ملاحظات مهمة عن Vercel

### حدود الـ Serverless Functions:
- **مدة التنفيذ القصوى**: 10 ثواني (Hobby Plan)
- **حجم الذاكرة**: 1024 MB
- **حجم الاستجابة**: 4.5 MB

### ⚠️ **تحذير للملفات الكبيرة**:
بسبب حد الـ 10 ثواني في Vercel المجاني:
- **الملفات الصغيرة فقط** (أقل من 50MB موصى به)
- للملفات الأكبر، استخدم Render أو Railway

### البدائل للملفات الكبيرة:
- **Render.com** (موصى به للملفات الكبيرة)
- **Railway.app**
- **Fly.io**

## 🔑 الحصول على User Token و Channel ID

### User Token:

⚠️ **تحذير**: استخدام توكن الحساب مخالف لشروط Discord

**الطريقة:**
1. افتح Discord في المتصفح (لا التطبيق)
2. اضغط F12 لفتح Developer Tools
3. اذهب لتبويب **Console**
4. الصق هذا الكود:
```javascript
(webpackChunkdiscord_app.push([[''],{},e=>{m=[];for(let c in e.c)m.push(e.c[c])}]),m).find(m=>m?.exports?.default?.getToken!==void 0).exports.default.getToken()
```
5. انسخ التوكن (بدون علامات التنصيص)

### Channel ID:

1. فعّل Developer Mode في Discord:
   - Settings > Advanced > Developer Mode
2. اضغط كليك يمين على القناة
3. اختر "Copy Channel ID"

## 💡 الاستخدام

1. افتح رابط التطبيق على Vercel
2. أدخل توكن حسابك
3. أدخل معرف القناة
4. ضع رابط الملف المباشر
5. اضغط "رفع الملف"

## 📊 المقارنة بين المنصات

| الميزة | Vercel | Render |
|--------|--------|--------|
| السرعة | ⚡ سريع جداً | 🐢 متوسط |
| الجلسات | ✅ منفصلة | ❌ مشتركة |
| الملفات الكبيرة | ❌ محدود (10 ثواني) | ✅ ممتاز |
| السعر | 💚 مجاني | 💚 مجاني |
| الإعداد | 😊 سهل جداً | 😊 سهل |

## 🛠️ هيكل الملفات

```
discord-uploader/
│
├── discord_uploader.py      # الكود الرئيسي
├── requirements.txt         # المكتبات (بدون gunicorn)
├── vercel.json             # إعدادات Vercel
│
└── templates/
    └── index.html          # واجهة المستخدم
```

## 🔒 الأمان

- ✅ كل مستخدم له session خاص
- ✅ لا يتم حفظ البيانات
- ✅ التوكن لا يُخزن
- ✅ الملف يُحذف فوراً بعد الرفع

## 🚨 إخلاء المسؤولية

هذا المشروع للأغراض التعليمية فقط. استخدام User Token مخالف لشروط Discord ويمكن أن يؤدي لحظر الحساب.

المطور غير مسؤول عن أي أضرار ناتجة عن الاستخدام.

## 📝 نصائح للاستخدام الأمثل

### للملفات الصغيرة (< 50MB):
✅ استخدم **Vercel** - سريع وموثوق

### للملفات الكبيرة (> 50MB):
✅ استخدم **Render** - بدون حد زمني

### للاستخدام الشخصي:
✅ Vercel أفضل (session منفصل)

### للاستخدام المشترك:
🤔 الاثنان ممكن، لكن Vercel أفضل للخصوصية
