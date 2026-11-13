/* Shared UI primitives. All server/user text is escaped before HTML rendering. */
window.Arena = (() => {
  const paths = {
    grid:'M3 3h7v7H3zM14 3h7v7h-7zM3 14h7v7H3zM14 14h7v7h-7z',
    code:'m8 5-7 7 7 7m8-14 7 7-7 7m-3-17-2 20',
    sword:'m3 3 13 13m-2 3 5-5m-2 8 5-5M3 3l1 6 5-5-6-1m11 11 6-11 1 6-4 4',
    play:'m8 4 13 8-13 8z', pause:'M8 4v16M16 4v16',
    trophy:'M7 3h10v7a5 5 0 0 1-10 0V3Zm0 2H3v3a4 4 0 0 0 4 4m10-7h4v3a4 4 0 0 1-4 4m-5 3v6m-5 0h10',
    book:'M12 5C8 2 4 3 2 4v16c4-2 7-1 10 1 3-2 6-3 10-1V4c-4-2-7-1-10 1Zm0 0v16',
    eye:'M2 12s3-7 10-7 10 7 10 7-3 7-10 7S2 12 2 12Zm13 0a3 3 0 1 1-6 0 3 3 0 0 1 6 0',
    arrow:'M20 12H4m6-6-6 6 6 6', upload:'M12 16V3m-5 5 5-5 5 5M4 15v6h16v-6',
    download:'M12 3v13m-5-5 5 5 5-5M4 16v5h16v-5',
    clock:'M12 8v5l3 2m7-3a10 10 0 1 1-20 0 10 10 0 0 1 20 0',
    users:'M16 21v-3a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v3m17 0v-3a4 4 0 0 0-3-4M13 3a4 4 0 0 1 0 8m0-4a4 4 0 1 1-8 0 4 4 0 0 1 8 0',
    logout:'M9 3H3v18h6m5-14 5 5-5 5m-6-5h13',
    settings:'M4 5h16M4 12h16M4 19h16M8 2v6m8 1v6M8 16v6',
    spark:'m12 2 3 7 7 3-7 3-3 7-3-7-7-3 7-3 3-7',
    shield:'m12 2 9 4v6c0 6-9 10-9 10S3 18 3 12V6l9-4m-4 10 3 3 5-6',
    chevron:'m14 6-6 6 6 6', plus:'M12 4v16M4 12h16', menu:'M3 6h18M3 12h18M3 18h18',
    check:'m4 12 5 5L20 6', mail:'M3 4h18v16H3V4Zm0 0 9 9 9-9',
    next:'m5 4 12 8-12 8V4Zm14 0v16', back:'m19 4-12 8 12 8V4ZM5 4v16',
  };
  const icon = (name) => `<svg class="icon" viewBox="0 0 24 24" aria-hidden="true"><path d="${paths[name]||paths.spark}"/></svg>`;
  const esc = s => String(s ?? '').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const fa = n => new Intl.NumberFormat('fa-IR').format(n ?? 0);
  const date = n => n ? new Date(n*1000).toLocaleString('fa-IR',{month:'short',day:'numeric',hour:'2-digit',minute:'2-digit'}) : '—';
  const labels = {completed:'پایان‌یافته',running:'در حال اجرا',queued:'در صف',failed:'خطای زیرساخت',scheduled:'برنامه‌ریزی‌شده',cancelled:'لغوشده',accepted:'پذیرفته‌شده',rejected:'ردشده',expired:'منقضی',pending:'در انتظار پاسخ',win:'برد',loss:'باخت',draw:'مساوی'};
  const reasons = {completed:'پایان ۳۰ انتخاب',turn_timeout:'پایان زمان نوبت',total_timeout:'پایان زمان مجموع',total_cpu_timeout:'پایان زمان پردازش',invalid_output:'خروجی نامعتبر',extra_output:'خروجی اضافه',inactive_output:'خروجی در نوبت حریف',stdout_limit:'خروجی بیش از حد',stderr_limit:'گزارش خطای بیش از حد',premature_exit:'بسته شدن زودهنگام کد',runtime_error:'خطای اجرای کد',exit_timeout:'کد پس از پایان بسته نشد'};
  const badge = (s,label) => `<span class="badge ${esc(s)}">${esc(label||labels[s]||s)}</span>`;
  const brand = () => `<a class="brand" href="/"><img src="/assets/logo.svg" alt="" width="43" height="43"><div><strong>نبرد هیولاها</strong><small>میدان رقابت کدها</small></div></a>`;
  const art = () => `<div class="hero-art" aria-hidden="true"><div class="art-card"><b>C <span>۴ ★</span></b><img src="/assets/monster-c.svg" alt=""><small>هیولای آتشین</small></div><div class="art-card"><b>B <span>۵ ★</span></b><img src="/assets/monster-b.svg" alt=""><small>هیولای سایه</small></div><div class="art-card"><b>A <span>۵ ★</span></b><img src="/assets/monster-a.svg" alt=""><small>هیولای جنگل</small></div><span class="art-star">✧</span><span class="art-star">✦</span></div>`;
  let csrf = '', toastTimer;
  async function api(path, body) {
    const response = await fetch('/api'+path,{method:body?'POST':'GET',credentials:'same-origin',headers:body?{'Content-Type':'application/json','X-CSRF-Token':csrf}:{},body:body?JSON.stringify(body):undefined});
    const data = await response.json();
    if(!response.ok) throw new Error(data.error||'ارتباط با سرور برقرار نشد.');
    return data;
  }
  function toast(message,error=false){const el=document.getElementById('toast');if(!el)return;el.textContent=message;el.className='show'+(error?' error':'');clearTimeout(toastTimer);toastTimer=setTimeout(()=>el.className='',6000)}
  function modal(title,content){const el=document.getElementById('modal');el.innerHTML=`<div class="modal-head"><h2 id="modal-title">${esc(title)}</h2><button type="button" data-close aria-label="بستن">×</button></div><div class="modal-body">${content}</div>`;el.querySelector('[data-close]').onclick=()=>el.close();if(!el.open)el.showModal();return el}
  const empty=(text,link='')=>`<div class="empty">${icon('spark')}<p>${esc(text)}</p>${link}</div>`;
  return {icon,esc,fa,date,badge,brand,art,api,toast,modal,empty,labels,reasons,setCSRF:v=>csrf=v};
})();
