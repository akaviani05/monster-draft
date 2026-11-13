/* Private test runs of the current editor contents, through the isolated queue. */
const DebugUI=(()=>{
  const {api,esc,fa,icon,badge}=Arena;
  let bots=[],owner=null,selected='greedy',job=null,report=null,error='',busy=false,loadingFile=false,cursor=0,timer=null,generation=0;
  const pending=()=>job&&['queued','running'].includes(job.status);
  const last=()=>report?Math.max(0,...report.events.map(e=>e.turn+1)):0;
  const hints={invalid_output:'فقط یک شمارهٔ ۰ تا ۵ و خط جدید چاپ کنید؛ توضیح‌ها را به stderr بفرستید.',
    inactive_output:'در OPPTURN چیزی چاپ نکنید؛ فقط شش کارت و سپس شمارهٔ حریف را بخوانید.',
    premature_exit:'برنامه پیش از پایان بسته شد. گزارش stderr را برای خطای اجرا یا ورودیِ اشتباه بخوانید.',
    turn_timeout:'پاسخ در ۰٫۳ ثانیه نرسید. حلقهٔ بی‌پایان، input اضافه در YOURTURN و فراموش کردن flush را بررسی کنید.',
    total_timeout:'مجموع زمان پاسخ‌ها از ۲ ثانیه گذشت؛ محاسبات هر نوبت را کمتر کنید.',
    total_cpu_timeout:'مجموع زمان پردازش از ۲ ثانیه گذشت؛ در نوبت حریف هم پردازش سنگین انجام ندهید.',
    runtime_error:'برنامه با خطای اجرا پایان یافت؛ stderr و کد خروج را بررسی کنید.',
    extra_output:'پاسخ اضافی چاپ شده است؛ در هر YOURTURN فقط یک خط چاپ کنید.',
    stdout_limit:'خروجی پاسخ بیش از حد است؛ پیام‌های توضیحی را در stdout چاپ نکنید.',
    stderr_limit:'گزارش stderr بیش از ۶۴ کیلوبایت شد؛ تعداد پیام‌های بررسی را کمتر کنید.',
    exit_timeout:'پس از ۳۰ پیام نوبت از برنامه خارج شوید؛ منتظر پیام END نباشید.'};
  function body(){
    let result='';
    const chosen=document.getElementById('source-file')?.files?.[0];
    if(report){
      const reason=report.result.reason,events=report.events.filter(e=>e.turn===cursor-1);
      const stream=kind=>events.filter(e=>e.stream===kind).map(e=>e.text).join('');
      const stderr=report.events.filter(e=>e.stream==='stderr').map(e=>e.text).join('');
      const outcome=report.result.winner===null?'مساوی':report.result.winner===report.seat?'پیروزی کد شما':'پیروزی ربات حریف';
      const signalHint=({'-11':'دسترسی نامعتبر به حافظه (SIGSEGV)؛ شمارهٔ خانه‌های آرایه و اشاره‌گرها را بررسی کنید.', '-8':'خطای محاسباتی (SIGFPE)؛ تقسیم بر صفر را بررسی کنید.', '-6':'برنامه با SIGABRT متوقف شد؛ assert یا خطای کتابخانه را بررسی کنید.', '-9':'فرایند به‌اجبار متوقف شد؛ علت پایان آزمایش را در بالا بخوانید.'})[String(report.exit_code)];
      result=`<div class="notice ${reason==='completed'?'':'warning'}" role="status">${esc(Arena.reasons[reason]||reason)}${reason==='completed'?'؛ اجرای ۳۰ انتخاب کامل شد. '+outcome:'؛ خطا برای '+(report.result.loser===report.seat?'کد شما':'ربات حریف')+'؛ '+esc(hints[reason]||'گزارش ورودی و خروجی را بررسی کنید.')}<br>امتیاز کد شما: ${fa(report.result.scores[report.seat].total)} · امتیاز حریف: ${fa(report.result.scores[1-report.seat].total)}<br><small>زمان پاسخ‌ها: ${fa(report.timing.wall_ms)} میلی‌ثانیه · زمان پردازش: ${fa(report.timing.cpu_ms)} میلی‌ثانیه · کد خروج: <bdi>${esc(report.exit_code)}</bdi></small></div>
      <div class="toolbar"><button type="button" class="btn small" data-debug-action="previous" ${cursor===0?'disabled':''}>گام قبل</button><label for="debug-step">گام آزمایش</label><input id="debug-step" type="range" min="0" max="${last()}" value="${cursor}"><button type="button" class="btn small" data-debug-action="next" ${cursor===last()?'disabled':''}>گام بعد</button><strong>${cursor===0?'شروع برنامه و پرچم قدرت':'نوبت '+fa(cursor)}</strong></div>
      <div class="form-grid"><div><h3><span dir="ltr">stdin</span> · ورودی برنامه</h3><pre class="debug-stream" data-debug-stream="stdin" dir="ltr">${esc(stream('stdin')||'در این گام ورودی دیگری ارسال نشده است.')}</pre></div><div><h3><span dir="ltr">stdout</span> · پاسخ برنامه</h3><pre class="debug-stream" data-debug-stream="stdout" dir="ltr">${esc(stream('stdout')||'در این گام خروجی‌ای ثبت نشده است.')}</pre></div></div>
      <details><summary>ترتیب تبادل پیام‌های این گام</summary><ol>${events.map(e=>`<li><bdi>${esc(e.stream)}</bdi><pre class="debug-stream" dir="ltr">${esc(e.text)}</pre></li>`).join('')}</ol></details>
      <h3><span dir="ltr">stderr</span> · گزارش‌ها و خطاهای کل اجرا</h3><pre class="debug-stream" data-debug-stream="stderr" dir="ltr">${esc(stderr||'گزارشی در stderr ثبت نشده است.')}</pre>
      ${signalHint?`<p class="notice warning">${signalHint}</p>`:''}
      ${report.truncated?'<p class="notice warning">گزارش طولانی بود؛ فقط بخش نخستِ جریان‌ها ذخیره شده است.</p>':''}
      <a class="btn" href="/visualizer?match=${job.id}" target="_blank" rel="noopener">${icon('play')}دیدن بازپخش همین آزمایش</a>`;
    }
    return `<h2>آزمایش تعاملی کد</h2><p class="hint">کد فعلیِ ویرایشگر بالا را با یک ربات اجرا کنید. این آزمایش نسخهٔ نهایی تیم را تغییر نمی‌دهد و از سهمیهٔ بازی و ارسال کد استفاده می‌کند. گزارش ورودی، خروجی و خطا فقط برای تیم شماست.</p>
    <form id="debug-form" class="section-gap"><div class="field"><label for="debug-source-file">فایل کد آزمایش</label><input id="debug-source-file" type="file" accept=".py,.cpp" ${loadingFile?'disabled':''}><p class="hint">Python یا C++، حداکثر ۶۴ کیلوبایت. انتخاب فایل، کد و زبان ویرایشگر بالا را هم به‌روز می‌کند.${chosen?` فایل ویرایشگر: <bdi>${esc(chosen.name)}</bdi>`:''}</p></div><div class="field"><label for="debug-opponent">ربات حریف آزمایش</label><select id="debug-opponent" name="bot">${bots.map(b=>`<option value="${esc(b.id)}" ${b.id===selected?'selected':''}>${esc(b.name)}</option>`).join('')}</select></div><button class="btn primary" type="submit" ${busy||loadingFile||pending()&&!error?'disabled':''}>${icon('play')}${loadingFile?'در حال خواندن فایل…':busy?'در حال بررسی کد…':'آزمایش کد فعلی'}</button></form>
    ${error?`<pre class="debug-stream inline-error" id="debug-error" role="alert" dir="auto">${esc(error)}</pre>${job?'<button type="button" class="btn small" data-debug-action="retry">بررسی دوبارهٔ آزمایش</button>':''}`:''}
    ${job?`<p class="section-gap">آزمایش #${fa(job.id)} · <bdi>${esc(job.filename)}</bdi> ${badge(job.status)}</p><p class="hint">گزارش مربوط به کد هنگام شروع همین آزمایش است؛ پس از تغییر کد، دوباره آزمایش کنید. بازپخش در برگهٔ جدا باز می‌شود تا کد ویرایشگر حفظ شود.</p>`:''}
    ${pending()&&!error?'<p role="status">پس از پایان اجرا، ورودی و خروجی هر نوبت را با «گام بعد» بررسی کنید. اگر اجراکننده خاموش باشد، درخواست در صف محفوظ می‌ماند.</p>':''}
    ${result}<p class="hint section-gap">گزارش، پیام‌های واقعی ردوبدل‌شده با داور را نشان می‌دهد. ورودی یا خروجی خالی در OPPTURN می‌تواند طبیعی باشد. پیام‌های بررسی را با print(..., file=sys.stderr) در پایتون یا cerr در C++ بنویسید. <a href="/guide#protocol">راهنمای ورودی و خروجی</a></p>`;
  }
  function update(){
    const panel=document.getElementById('debug-panel');
    if(panel){panel.innerHTML=body();const files=document.getElementById('source-file')?.files;if(files?.length)document.getElementById('debug-source-file').files=files}
  }
  async function watch(version){
    try{
      const status=await api('/matches/'+job.id);if(version!==generation)return;
      job={...job,...status};error='';
      if(status.status==='completed'){
        const result=await api('/debug/'+job.id);if(version!==generation)return;
        report=result;cursor=result.result.reason==='completed'?Math.min(1,last()):last();
      }else if(status.status==='failed')error=status.error||'اجراکننده دچار خطا شد؛ با مسئول مسابقه تماس بگیرید.';
      update();if(pending())timer=setTimeout(()=>watch(version),1000);
    }catch(e){if(version===generation){error=e.message;update()}}
  }
  function reset(){generation++;clearTimeout(timer);owner=null;job=null;report=null;error='';busy=false;loadingFile=false;cursor=0;selected='greedy'}
  document.addEventListener('submit',async e=>{
    if(e.target.id!=='debug-form')return;e.preventDefault();
    if(busy||loadingFile||pending()&&!error)return;
    const form=document.getElementById('submission-form'),values=new FormData(form);
    const file=document.getElementById('source-file').files[0];
    const payload={source:values.get('source'),language:values.get('language'),filename:file?.name||(values.get('language')==='cpp'?'bot.cpp':'bot.py'),bot:selected};
    const version=++generation;clearTimeout(timer);busy=true;job=null;report=null;error='';update();
    try{const response=await api('/debug',payload);if(version!==generation)return;job={...response,status:'queued'};busy=false;update();watch(version)}
    catch(err){if(version===generation){busy=false;error=err.message;update()}}
  });
  document.addEventListener('change',async e=>{
    if(e.target.id==='debug-opponent')selected=e.target.value;
    if(e.target.id==='debug-step'){cursor=Number(e.target.value);update();document.getElementById('debug-step')?.focus()}
    if(e.target.id==='debug-source-file'){
      const files=e.target.files,file=files[0];if(!file)return;
      if(file.size>65536||!/\.(py|cpp)$/i.test(file.name)){error='فقط فایل .py یا .cpp، حداکثر ۶۴ کیلوبایت، انتخاب کنید.';update();return}
      const version=generation;loadingFile=true;error='';update();
      try{
        const source=await file.text();if(version!==generation)return;
        document.getElementById('source-file').files=files;
        document.getElementById('source').value=source;
        document.getElementById('language').value=/\.cpp$/i.test(file.name)?'cpp':'python';
      }catch(err){if(version===generation)error=err.message}
      finally{if(version===generation){loadingFile=false;update()}}
    }
  });
  document.addEventListener('click',e=>{
    const action=e.target.closest('[data-debug-action]')?.dataset.debugAction;if(!action)return;
    if(action==='retry'){clearTimeout(timer);watch(generation);return}
    if(report){cursor=Math.max(0,Math.min(last(),cursor+(action==='next'?1:-1)));update()}
  });
  return {reset,render:(items,uid)=>{if(owner!==uid){reset();owner=uid}bots=items;return `<section class="panel pad section-gap" id="debug-panel">${body()}</section>`}};
})();
