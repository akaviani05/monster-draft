"""Build the student-only download from an explicit, reviewed file allowlist."""
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED, ZipInfo

ROOT=Path(__file__).resolve().parent.parent
OUT=ROOT/'web/downloads/runner.zip'
README="""بستهٔ تمرین نبرد هیولاها

۱. تمام فایل‌های ZIP را در یک پوشه استخراج کنید.
۲. فایل play.py را در IDLE باز کنید (Edit with IDLE).
۳. سه مقدار ابتدای فایل را تنظیم کنید:
   BOT1 = "A.cpp"
   BOT2 = "B.py"
   OUT = "replay.json"
۴. با F5 برنامه را اجرا کنید. نتیجه نمایش داده می‌شود و replay.json ذخیره می‌شود.
۵. viewer/index.html را با مرورگر باز کنید و فایل نتیجه را انتخاب کنید.

برای دو برنامهٔ پایتون، هر دو نام را B.py قرار دهید. این حالت فقط Python لازم دارد.
برای اجرای C++، کامپایلر g++ نیز باید نصب باشد. در صورت نیاز از دبیر کمک بگیرید.
این ابزار برای برنامه‌های خودتان است؛ فایل‌های ناشناس را با آن اجرا نکنید.
نمایشگر بدون اینترنت کار می‌کند. راهنمای دانش‌آموز در سایت مسابقه در دسترس است.
دو فایل A.cpp و B.py صرفاً نمونه‌های ابتدایی شما هستند؛ ربات حریف در بسته نیست.
مجوز قلم: viewer/assets/OFL.txt
"""


def offline_viewer_source():
    source=(ROOT/'web/assets/viewer.js').read_text()
    source=source.replace('icon,esc,fa,api,toast,modal','icon,esc,fa,toast')
    start=source.index('  async function watch(id){')
    end=source.index("  document.getElementById('load-log')",start)
    source=source[:start]+source[end:]
    source='\n'.join(line for line in source.split('\n') if "document.getElementById('sample-replay').onclick" not in line)
    start=source.index("  document.getElementById('local-codes').onclick")
    end=source.index("  document.addEventListener('keydown'",start)
    source=source[:start]+source[end:]
    source='\n'.join(line for line in source.split('\n') if 'const match=new URLSearchParams' not in line)
    source=source.replace("||document.getElementById('modal').open",'')
    for forbidden in ('fetch(', '/api/', 'local-codes', 'sample-replay', 'async function watch'):
        if forbidden in source:raise RuntimeError('Offline viewer unexpectedly contains '+forbidden)
    return source.encode()


def build():
    # No directory globs: adding files to the repository cannot expand this ZIP.
    files={name:(ROOT/name).read_bytes() for name in (
        'play.py','A.cpp','B.py','runner/__init__.py','runner/game.py','runner/local.py')}
    for name in ('logo.svg','Vazirmatn.ttf','OFL.txt','monster-a.svg','monster-b.svg','monster-c.svg','monster-d.svg','monster-e.svg'):
        files['viewer/assets/'+name]=(ROOT/'web/assets'/name).read_bytes()
    files['viewer/index.html']=(ROOT/'scripts/student-viewer.html').read_bytes()
    files['viewer/assets/style.css']=(ROOT/'web/assets/offline.css').read_bytes()
    files['viewer/assets/common.js']=(ROOT/'web/assets/offline-common.js').read_bytes()
    files['viewer/assets/viewer.js']=offline_viewer_source()
    files['README.txt']=README.encode()
    OUT.parent.mkdir(exist_ok=True)
    with ZipFile(OUT,'w',ZIP_DEFLATED) as archive:
        for name,data in sorted(files.items()):
            info=ZipInfo(name,date_time=(2026,1,1,0,0,0));info.compress_type=ZIP_DEFLATED;info.external_attr=0o644<<16
            archive.writestr(info,data)
    print(f'{OUT}: {len(files)} allowlisted files, {OUT.stat().st_size:,} bytes')
    return OUT


if __name__=='__main__':build()
