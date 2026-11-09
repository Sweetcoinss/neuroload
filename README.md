# NeuroLoad for Windows

تطبيق شبيه ديال NeuroLoad للـ Android، ولكن للويندوز، بواجهة CustomTkinter عصرية (Cyber dark + تدرجات cyan→violet).

## كيفاش تشغّلو بسرعة (بلا بناء)
```powershell
pip install customtkinter pillow yt-dlp imageio-ffmpeg
python neuroload_win.py
```

## EXE جاهز (واحد الملف)
`dist/NeuroLoad.exe` — موجود فالريبو، يمشي دايركت بلا Python.

إذا بغيتي تبنيو بيدك:
```powershell
pip install pyinstaller
pyinstaller --noconfirm --clean --onefile --windowed --name NeuroLoad --icon neuroload.ico `
  --collect-all customtkinter --collect-all yt_dlp --collect-all imageio_ffmpeg --collect-all PIL `
  neuroload_win.py
```

## المميزات
- لصق الرابط + Analyze: يجيب العنوان، القناة، المدة، الثامبنايل، والرخصة.
- اختيار الجودة: 1080p / 720p / 480p / 360p / MP3 (صوت فقط).
- تحميل سريع: `concurrent_fragment_downloads=16` (+ aria2c إلا كان منصب: `-x16 -s16 -k1M`).
- Progress حي + ETA + زر Cancel.
- التحميلات كتتحفظ فـ `Downloads\NeuroLoad` (قابل للتغيير من التطبيق).
- Open / Folder للفتح بعد اكتمال التحميل.
- شارة الرخصة: خضراء = Creative Commons، كهرمانية = تحقق من الحقوق.

## ملاحظة قانونية
للاستخدام الشخصي ومحتوى Creative Commons فقط. احترام شروط استخدام YouTube ضروري.
